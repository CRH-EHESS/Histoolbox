"""
Router OCR — endpoints :
  POST /ocr/upload               — upload monolithique (rétrocompatibilité CLI)
  POST /ocr/upload/chunk         — upload par chunks de 5 Mo (web)
  GET  /ocr/upload/chunks/{id}   — liste des chunks déjà reçus (resume upload)
  GET  /ocr/status/{task_id}
  GET  /ocr/result/{task_id}
"""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile, File
from loguru import logger

from app.database import (
    create_task,
    create_task_pending_upload,
    delete_upload_chunks,
    get_queue_position,
    get_received_chunk_indexes,
    get_task,
    touch_task,
    try_finalize_assembly,
    update_task_status,
)
from app.limiter import limiter
from app.models.schemas import BlockItem, ChunkListResponse, ChunkUploadResponse, PageInfo, ResultResponse, StatusResponse, UploadResponse
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
    logger.info("[{}] Upload reçu | filename={} | email={}", task_id, file.filename, bool(normalized_email))

    # Sauvegarde du PDF
    task_upload_dir = UPLOAD_ROOT / task_id
    task_upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = task_upload_dir / (file.filename or "input.pdf")
    content = await file.read()
    pdf_path.write_bytes(content)
    logger.debug("[{}] PDF sauvegardé | taille={}o", task_id, len(content))

    # Répertoire de sortie Chandra
    output_dir = OUTPUT_ROOT / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Persistance SQLite
    create_task(task_id, str(pdf_path), str(output_dir), email=normalized_email)

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


@router.post("/upload/chunk", response_model=ChunkUploadResponse, status_code=202)
@limiter.limit("60/minute")
async def upload_chunk(
    request: Request,
    task_id: str = Form(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    filename: str = Form(...),
    chunk: UploadFile = File(...),
    email: str = Form(default=""),
) -> ChunkUploadResponse:
    """Reçoit un chunk d'un PDF découpé côté client (5 Mo max par chunk).

    Protocole :
    - Le client génère un task_id (UUID) avant le premier envoi.
    - Chunk 0 crée la tâche en statut 'pending_upload' et les répertoires.
    - Chaque chunk est écrit dans data/uploads/<task_id>/chunk_<index>.bin.
    - Lorsque tous les chunks sont reçus, le PDF est assemblé et le job est
      enqueued dans RQ (statut passe à 'pending').
    """
    # Validation
    if total_chunks < 1:
        raise HTTPException(status_code=422, detail="total_chunks doit être ≥ 1.")
    if chunk_index < 0 or chunk_index >= total_chunks:
        raise HTTPException(status_code=422, detail=f"chunk_index {chunk_index} hors plage [0, {total_chunks - 1}].")

    normalized_email: str | None = email.strip() or None
    if normalized_email and "@" not in normalized_email:
        raise HTTPException(status_code=422, detail="Adresse email invalide.")

    # Vérifier l'état de la tâche (sauf pour le premier chunk qui la crée)
    task_upload_dir = UPLOAD_ROOT / task_id
    if chunk_index == 0:
        # Créer la tâche et les répertoires — idempotent si chunk 0 est renvoyé
        existing = get_task(task_id)
        if existing is None:
            task_upload_dir.mkdir(parents=True, exist_ok=True)
            output_dir = OUTPUT_ROOT / task_id
            output_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = task_upload_dir / filename
            create_task_pending_upload(task_id, str(pdf_path), str(output_dir), email=normalized_email)
            logger.info(
                "[{}] Début upload chunked | filename={} | total_chunks={} | email={}",
                task_id, filename, total_chunks, bool(normalized_email),
            )
        elif existing["status"] != "pending_upload":
            raise HTTPException(
                status_code=409,
                detail=f"Impossible d'ajouter un chunk : statut actuel '{existing['status']}'.",
            )
        else:
            # Chunk 0 renvoyé pour une tâche déjà initialisée — on continue sans recréer
            task_upload_dir.mkdir(parents=True, exist_ok=True)
    else:
        row = get_task(task_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Tâche introuvable (le chunk 0 doit être envoyé en premier).")
        if row["status"] != "pending_upload":
            raise HTTPException(
                status_code=409,
                detail=f"Impossible d'ajouter un chunk : statut actuel '{row['status']}'.",
            )

    # Écrire le chunk temporaire
    chunk_path = task_upload_dir / f"chunk_{chunk_index}.bin"
    content = await chunk.read()
    chunk_path.write_bytes(content)
    logger.debug("[{}] Chunk {}/{} reçu | taille={}o", task_id, chunk_index + 1, total_chunks, len(content))

    # Enregistrement atomique + vérification si l'assemblage doit être lancé.
    # try_finalize_assembly utilise BEGIN IMMEDIATE pour éviter les race conditions
    # quand plusieurs chunks arrivent simultanément.
    should_assemble = try_finalize_assembly(task_id, chunk_index, total_chunks)
    # Compte le nombre de chunks réellement reçus pour la réponse
    chunks_received = len(get_received_chunk_indexes(task_id))

    assembled = False
    if should_assemble:
        # Cet appelant est l'unique gagnant de la course — on assemble
        row = get_task(task_id)
        pdf_path = Path(row["pdf_path"])
        output_dir = Path(row["output_dir"])

        with pdf_path.open("wb") as out_f:
            for i in range(total_chunks):
                out_f.write((task_upload_dir / f"chunk_{i}.bin").read_bytes())

        # Supprimer les fichiers temporaires
        for i in range(total_chunks):
            (task_upload_dir / f"chunk_{i}.bin").unlink(missing_ok=True)

        delete_upload_chunks(task_id)
        update_task_status(task_id, "pending")

        queue = request.app.state.rq_queue
        if queue is None:
            raise HTTPException(status_code=503, detail="File de traitement indisponible (Redis non connecté).")
        queue.enqueue(
            process_ocr_job,
            task_id,
            str(pdf_path),
            str(output_dir),
            row["email"],
            job_id=task_id,
            job_timeout=_RQ_JOB_TIMEOUT,
        )
        assembled = True
        logger.info("[{}] PDF assemblé ({} chunks) et job enqueued", task_id, total_chunks)

    return ChunkUploadResponse(
        task_id=task_id,
        chunks_received=chunks_received,
        total_chunks=total_chunks,
        assembled=assembled,
    )


@router.get("/upload/chunks/{task_id}", response_model=ChunkListResponse)
async def get_received_chunks(task_id: str) -> ChunkListResponse:
    """Retourne la liste des index de chunks déjà reçus par le serveur.

    Utilisé par le mécanisme de recovery côté frontend : au retour sur la page
    d'upload après une interruption, le client interroge cet endpoint pour
    n'envoyer que les chunks manquants (reprise partielle).

    - 200 + liste vide → tâche inexistante ou aucun chunk reçu (envoyer depuis chunk 0)
    - 200 + liste partielle → reprendre depuis le premier index absent
    - 409 → tâche dans un état incompatible (assembling/pending/completed)
    """
    row = get_task(task_id)
    if row is not None and row["status"] not in ("pending_upload", "assembling"):
        if row["status"] in ("pending", "processing", "completed", "error"):
            raise HTTPException(
                status_code=409,
                detail=f"La tâche est dans un état non-resumable : '{row['status']}'.",
            )
    received = get_received_chunk_indexes(task_id)
    return ChunkListResponse(task_id=task_id, received=received, total_chunks=None)


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
    filename = Path(row["pdf_path"]).name
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
