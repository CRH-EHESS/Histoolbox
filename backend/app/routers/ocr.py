"""
Router OCR — endpoints :
  POST /ocr/upload
  GET  /ocr/status/{task_id}
  GET  /ocr/result/{task_id}
"""

import json
import unicodedata
import uuid
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile, File
from loguru import logger

from app.database import create_task, get_queue_position, get_task, touch_task
from app.limiter import limiter
from app.models.schemas import BlockItem, PageInfo, ResultResponse, StatusResponse, UploadResponse
from app.services.chandra_service import INFERENCE_TIMEOUT_SECONDS
from app.worker import process_ocr_job

# Timeout RQ = timeout Chandra + 5 min de marge pour la finalisation du job.
# Sans ça, RQ tue le work-horse après 180s (défaut), bien avant la fin d'une
# inférence longue.
_RQ_JOB_TIMEOUT = INFERENCE_TIMEOUT_SECONDS + 300

router = APIRouter(prefix="/ocr", tags=["OCR"])

# Répertoires de stockage (créés au démarrage par main.py)
UPLOAD_ROOT = Path(__file__).parent.parent.parent / "data" / "uploads"
OUTPUT_ROOT = Path(__file__).parent.parent.parent / "data" / "outputs"


def _sanitize_filename(filename: str | None) -> str:
    """Réduit le nom d'origine à son dernier composant, sans caractères de contrôle.

    Ce nom n'est conservé qu'en base (affichage, email) : le PDF est toujours
    écrit sous le nom fixe input.pdf, ce qui neutralise le path traversal (S1).
    """
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(c for c in name if unicodedata.category(c)[0] != "C").strip()
    if name in ("", ".", ".."):
        return "document.pdf"
    return name[:255]


@router.post("/upload", response_model=UploadResponse, status_code=202)
@limiter.limit("10/minute")
async def upload_pdf(
    request: Request,
    file: UploadFile = File(...),
    email: str = Form(default=""),
) -> UploadResponse:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Seuls les fichiers PDF sont acceptés.")

    # Validation basique de l'email si fourni
    normalized_email: str | None = email.strip() or None
    if normalized_email and "@" not in normalized_email:
        raise HTTPException(status_code=422, detail="Adresse email invalide.")

    task_id = str(uuid.uuid4())
    filename = _sanitize_filename(file.filename)
    logger.info("[{}] Upload reçu | filename={} | email={}", task_id, filename, bool(normalized_email))

    # Sauvegarde du PDF sous un nom fixe : le nom fourni par le client
    # n'entre jamais dans un chemin du serveur.
    task_upload_dir = UPLOAD_ROOT / task_id
    task_upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = task_upload_dir / "input.pdf"
    content = await file.read()
    pdf_path.write_bytes(content)
    logger.debug("[{}] PDF sauvegardé | taille={}o", task_id, len(content))

    # Répertoire de sortie Chandra
    output_dir = OUTPUT_ROOT / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Persistance SQLite
    create_task(task_id, str(pdf_path), str(output_dir), email=normalized_email, filename=filename)

    # Enqueue dans la queue RQ
    queue = request.app.state.rq_queue
    if queue is None:
        raise HTTPException(status_code=503, detail="File de traitement indisponible (Redis non connecté).")
    queue.enqueue(
        process_ocr_job,
        task_id,
        str(pdf_path),
        str(output_dir),
        normalized_email,
        job_id=task_id,
        job_timeout=_RQ_JOB_TIMEOUT,
    )
    logger.info("[{}] Job enqueueé dans la queue RQ 'ocr'", task_id)

    return UploadResponse(task_id=task_id)


@router.get("/status/{task_id}", response_model=StatusResponse)
async def get_status(task_id: str) -> StatusResponse:
    row = get_task(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tâche introuvable.")
    touch_task(task_id)
    logger.debug("[{}] Statut consulté : {}", task_id, row["status"])
    return StatusResponse(
        task_id=task_id,
        status=row["status"],
        error_message=row["error_message"],
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
        progress_step=row["progress_step"],
        progress_total=row["progress_total"],
        progress_label=row["progress_label"],
        queue_position=get_queue_position(task_id),
    )


@router.get("/result/{task_id}", response_model=ResultResponse)
async def get_result(task_id: str) -> ResultResponse:
    row = get_task(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tâche introuvable.")
    if row["status"] != "completed":
        raise HTTPException(status_code=409, detail=f"Tâche non terminée (statut : {row['status']}).")
    touch_task(task_id)

    # Chandra crée un sous-répertoire output_dir/<stem>/ pour chaque fichier traité
    pdf_stem = Path(row["pdf_path"]).stem
    # Repli sur le nom du fichier pour les tâches antérieures à la colonne filename
    filename = row["filename"] or Path(row["pdf_path"]).name
    chandra_dir = Path(row["output_dir"]) / pdf_stem

    md_file = chandra_dir / f"{pdf_stem}.md"
    blocks_file = chandra_dir / f"{pdf_stem}_blocks.json"
    meta_file = chandra_dir / f"{pdf_stem}_metadata.json"

    markdown = md_file.read_text(encoding="utf-8") if md_file.exists() else ""

    blocks_raw: list = []
    if blocks_file.exists():
        blocks_raw = json.loads(blocks_file.read_text(encoding="utf-8"))

    meta: dict = {}
    if meta_file.exists():
        meta = json.loads(meta_file.read_text(encoding="utf-8"))

    blocks = [BlockItem(**b) for b in blocks_raw]
    pages = [PageInfo(**p) for p in meta.get("pages", [])]

    return ResultResponse(
        task_id=task_id,
        filename=filename,
        created_at=int(row["created_at"]),
        completed_at=int(row["updated_at"]),
        markdown=markdown,
        blocks=blocks,
        num_pages=meta.get("num_pages", len(pages)),
        total_token_count=meta.get("total_token_count", 0),
        pages=pages,
    )
