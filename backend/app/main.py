"""
Point d'entrée FastAPI — Histoolbox Backend
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.database import init_db
from app.routers.ocr import OUTPUT_ROOT, UPLOAD_ROOT, router as ocr_router

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialisation au démarrage
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    init_db()  # crée la table + corrige les tâches bloquées
    logger.info("Histoolbox backend démarré | LOG_LEVEL={}", LOG_LEVEL)
    yield
    # (pas de nettoyage requis à l'arrêt)


app = FastAPI(
    title="Histoolbox API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # dev frontend Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ocr_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
