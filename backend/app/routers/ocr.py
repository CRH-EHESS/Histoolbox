"""
Router OCR — endpoints :
  POST /ocr/upload
  GET  /ocr/status/{task_id}
  GET  /ocr/result/{task_id}
"""

import json
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from loguru import logger

from app.database import create_task, get_task, update_task_status, update_task_error
from app.models.schemas import ResultResponse, StatusResponse, UploadResponse
from app.services.chandra_service import run_chandra

router = APIRouter(prefix="/ocr", tags=["OCR"])

# Répertoires de stockage (créés au démarrage par main.py)
UPLOAD_ROOT = Path(__file__).parent.parent.parent / "data" / "uploads"
OUTPUT_ROOT = Path(__file__).parent.parent.parent / "data" / "outputs"


async def _process_task(task_id: str, pdf_path: str, output_dir: str) -> None:
    """Tâche d'arrière-plan : lance Chandra et met à jour le statut SQLite."""
    logger.info("[{}] Démarrage traitement | pdf={}", task_id, pdf_path)
    update_task_status(task_id, "processing")
    t0 = time.monotonic()
    try:
        await run_chandra(pdf_path, output_dir)
        elapsed = time.monotonic() - t0
        update_task_status(task_id, "completed")
        logger.success("[{}] Traitement terminé en {:.1f}s", task_id, elapsed)
    except Exception as e:
        elapsed = time.monotonic() - t0
        error_msg = str(e)
        logger.error("[{}] Erreur Chandra après {:.1f}s : {}", task_id, elapsed, error_msg)
        update_task_error(task_id, error_msg)


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> UploadResponse:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Seuls les fichiers PDF sont acceptés.")

    task_id = str(uuid.uuid4())
    logger.info("[{}] Upload reçu | filename={} | content_type={}", task_id, file.filename, file.content_type)

    # Sauvegarde du PDF
    task_upload_dir = UPLOAD_ROOT / task_id
    task_upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = task_upload_dir / (file.filename or "input.pdf")
    content = await file.read()
    pdf_path.write_bytes(content)
    logger.debug("[{}] PDF sauvegardé | taille={}o | chemin={}", task_id, len(content), pdf_path)

    # Répertoire de sortie Chandra
    output_dir = OUTPUT_ROOT / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Persistance SQLite
    create_task(task_id, str(pdf_path), str(output_dir))

    # Lance le traitement en arrière-plan
    background_tasks.add_task(_process_task, task_id, str(pdf_path), str(output_dir))
    logger.info("[{}] Tâche enregistrée, traitement en arrière-plan lancé", task_id)

    return UploadResponse(task_id=task_id)


@router.get("/status/{task_id}", response_model=StatusResponse)
async def get_status(task_id: str) -> StatusResponse:
    row = get_task(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tâche introuvable.")
    logger.debug("[{}] Statut consulté : {}", task_id, row["status"])
    return StatusResponse(
        task_id=task_id,
        status=row["status"],
        error_message=row["error_message"],
    )


@router.get("/result/{task_id}", response_model=ResultResponse)
async def get_result(task_id: str) -> ResultResponse:
    row = get_task(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tâche introuvable.")
    if row["status"] != "completed":
        raise HTTPException(status_code=409, detail=f"Tâche non terminée (statut : {row['status']}).")

    # Chandra crée un sous-répertoire output_dir/<stem>/ pour chaque fichier traité
    output_dir = Path(row["output_dir"]) / Path(row["pdf_path"]).stem
    pdf_stem = Path(row["pdf_path"]).stem

    md_file = output_dir / f"{pdf_stem}.md"
    html_file = output_dir / f"{pdf_stem}.html"
    meta_file = output_dir / f"{pdf_stem}_metadata.json"

    markdown = md_file.read_text(encoding="utf-8") if md_file.exists() else ""
    html = html_file.read_text(encoding="utf-8") if html_file.exists() else ""
    metadata: dict = {}
    if meta_file.exists():
        metadata = json.loads(meta_file.read_text(encoding="utf-8"))

    return ResultResponse(task_id=task_id, markdown=markdown, html=html, metadata=metadata)
