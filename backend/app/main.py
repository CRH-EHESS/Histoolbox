"""
Point d'entrée FastAPI — Histoolbox Backend
"""

import asyncio
import os
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from redis import Redis
from rq import Queue
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.database import init_db, get_expired_tasks, delete_task
from app.limiter import limiter
from app.routers.ocr import OUTPUT_ROOT, UPLOAD_ROOT, router as ocr_router

# --------------------------------------------------------------------------- #
# Authentification par clé API (header X-API-Key)                             #
# Si API_KEY n'est pas défini (dev local), la vérification est ignorée.       #
# En production (HISTOOLBOX_ENV=production, fixé par docker-compose.yml),     #
# l'API refuse de démarrer sans clé ou avec la valeur d'exemple.              #
# --------------------------------------------------------------------------- #
API_KEY = os.getenv("API_KEY", "")
HISTOOLBOX_ENV = os.getenv("HISTOOLBOX_ENV", "development")
_PLACEHOLDER_API_KEYS = ("", "changeme")


def _check_api_key() -> None:
    """Refuse de démarrer en production sans vraie clé ; signale l'authentification désactivée."""
    if HISTOOLBOX_ENV == "production" and API_KEY in _PLACEHOLDER_API_KEYS:
        raise RuntimeError(
            "API_KEY vide ou égale à « changeme » : démarrage refusé en production "
            "(générer une clé : openssl rand -hex 32)."
        )
    if not API_KEY:
        logger.warning("API_KEY non définie : authentification désactivée (HISTOOLBOX_ENV={})", HISTOOLBOX_ENV)

# --------------------------------------------------------------------------- #
# Logging — contrôlé par la variable d'environnement LOG_LEVEL (défaut: INFO) #
# Lancer en mode verbose : LOG_LEVEL=DEBUG uv run uvicorn app.main:app ...    #
# --------------------------------------------------------------------------- #
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger.remove()  # supprime le handler par défaut de loguru
logger.add(
    sys.stderr,
    level=LOG_LEVEL,
    format=(
        "<green>{time:HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
        "<level>{message}</level>"
    ),
    colorize=True,
)


# Délai de conservation (en secondes) d'une tâche terminée (completed ou error) après
# sa dernière consultation ; les tâches en attente ou en cours ne sont jamais supprimées.
# Contrôlé par la variable CLEANUP_TTL_SECONDS (défaut : 86400 = 24 heures, en attendant
# la durée fixée par l'ADR 0002).
CLEANUP_TTL_SECONDS = int(os.getenv("CLEANUP_TTL_SECONDS", "86400"))
# Intervalle entre deux passes de nettoyage (10 minutes).
_CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "600"))


async def _cleanup_expired_tasks() -> None:
    """Supprime les fichiers et l'entrée SQLite des tâches terminées inactives depuis > CLEANUP_TTL_SECONDS."""
    import time

    cutoff = int(time.time()) - CLEANUP_TTL_SECONDS
    expired = get_expired_tasks(cutoff)
    if not expired:
        return
    logger.info("Nettoyage : {} tâche(s) expirée(s) à supprimer", len(expired))
    for row in expired:
        task_id = row["id"]
        # Suppression des répertoires (idempotent si déjà absents)
        upload_dir = Path(row["pdf_path"]).parent
        shutil.rmtree(upload_dir, ignore_errors=True)
        shutil.rmtree(row["output_dir"], ignore_errors=True)
        delete_task(task_id)
        logger.info("[{}] Supprimé (inactif depuis > {}s)", task_id, CLEANUP_TTL_SECONDS)


async def _cleanup_loop() -> None:
    """Boucle de nettoyage périodique — tourne en arrière-plan pendant toute la vie de l'app."""
    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)
        try:
            await _cleanup_expired_tasks()
        except Exception as exc:  # pragma: no cover
            logger.error("Erreur inattendue dans la boucle de nettoyage : {}", exc)



async def lifespan(app: FastAPI):
    # Initialisation au démarrage
    _check_api_key()
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    init_db()  # crée la table + corrige les tâches bloquées

    # Connexion Redis + queue RQ
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        conn = Redis.from_url(redis_url)
        conn.ping()
        app.state.rq_queue = Queue("ocr", connection=conn)
        logger.info("RQ queue 'ocr' initialisée | redis={}", redis_url)
    except Exception as exc:  # pragma: no cover
        logger.error("Connexion Redis échouée | redis={} | {}", redis_url, exc)
        app.state.rq_queue = None

    logger.info(
        "Histoolbox backend démarré | LOG_LEVEL={} | CLEANUP_TTL={}s",
        LOG_LEVEL,
        CLEANUP_TTL_SECONDS,
    )
    cleanup_task = asyncio.create_task(_cleanup_loop())
    yield
    cleanup_task.cancel()


def get_rq_queue(request: Request) -> Queue:
    """Retourne la queue RQ depuis l'état de l'app (injectée via Depends ou request.app.state)."""
    return request.app.state.rq_queue


# --------------------------------------------------------------------------- #
# Origines CORS autorisées                                                     #
# En prod : ALLOWED_ORIGINS="https://user.github.io,https://autredomaine.fr" #
# --------------------------------------------------------------------------- #
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]


app = FastAPI(
    title="Histoolbox API",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """Vérifie le header X-API-Key si API_KEY est défini en variable d'environnement."""
    if API_KEY and request.url.path != "/health":
        key = request.headers.get("X-API-Key", "")
        if key != API_KEY:
            logger.warning("Accès refusé | path={} | ip={}", request.url.path, request.client.host if request.client else "?")
            return JSONResponse(status_code=401, content={"detail": "Clé d'accès invalide ou manquante."})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ocr_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
