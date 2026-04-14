"""
Point d'entrée FastAPI — Histoolbox Backend
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers.ocr import OUTPUT_ROOT, UPLOAD_ROOT, router as ocr_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialisation au démarrage
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    init_db()  # crée la table + corrige les tâches bloquées
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
