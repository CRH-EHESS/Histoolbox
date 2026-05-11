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
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.database import init_db, get_expired_tasks, delete_task
from app.limiter import limiter
from app.routers.ocr import OUTPUT_ROOT, UPLOAD_ROOT, router as ocr_router

# --------------------------------------------------------------------------- #
# Authentification par clé API (header X-API-Key)                             #
# Si API_KEY n'est pas défini (dev local), la vérification est ignorée.       #
# --------------------------------------------------------------------------- #
API_KEY = os.getenv("API_KEY", "")

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


# Durée d'inactivité (en secondes) avant suppression automatique des fichiers d'une tâche.
# Contrôlé par la variable CLEANUP_TTL_SECONDS (défaut : 3600 = 1 heure).
CLEANUP_TTL_SECONDS = int(os.getenv("CLEANUP_TTL_SECONDS", "3600"))
# Intervalle entre deux passes de nettoyage (10 minutes).
_CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "600"))


async def _cleanup_expired_tasks() -> None:
    """Supprime les fichiers et l'entrée SQLite des tâches inactives depuis > CLEANUP_TTL_SECONDS."""
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
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    init_db()  # crée la table + corrige les tâches bloquées
    logger.info(
        "Histoolbox backend démarré | LOG_LEVEL={} | CLEANUP_TTL={}s",
        LOG_LEVEL,
        CLEANUP_TTL_SECONDS,
    )
    cleanup_task = asyncio.create_task(_cleanup_loop())
    yield
    cleanup_task.cancel()


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
