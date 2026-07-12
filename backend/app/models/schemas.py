from pydantic import BaseModel
from typing import List, Literal, Optional


TaskStatus = Literal["pending_upload", "assembling", "pending", "processing", "completed", "error"]


class UploadResponse(BaseModel):
    task_id: str


class StatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    error_message: Optional[str] = None
    created_at: int
    updated_at: int
    progress_step: Optional[int] = None
    progress_total: Optional[int] = None
    progress_label: Optional[str] = None
    queue_position: Optional[int] = None


class BlockItem(BaseModel):
    """Bloc de layout détecté par Chandra sur une page du PDF."""
    id: str                  # "{page}_{block_index}"
    page: int                # 0-indexed
    block_index: int
    label: str               # "Text", "Table", "Image", "Figure", "Page-Header", …
    bbox_norm: List[float]   # [x1, y1, x2, y2] normalisé dans [0, 1]
    markdown: str


class PageInfo(BaseModel):
    """Statistiques et dimensions d'une page traitée."""
    page_num: int
    page_box: List[int]      # [0, 0, width_px, height_px]
    token_count: int
    num_blocks: int


class ResultResponse(BaseModel):
    """Résultat complet d'un traitement OCR."""
    task_id: str
    filename: str
    created_at: int
    completed_at: int
    markdown: str
    blocks: List[BlockItem]
    num_pages: int
    total_token_count: int
    pages: List[PageInfo]


class ChunkUploadResponse(BaseModel):
    """Réponse de l'endpoint POST /ocr/upload/chunk."""
    task_id: str
    chunks_received: int
    total_chunks: int
    assembled: bool              # True si c'était le dernier chunk (job enqueued)


class ChunkListResponse(BaseModel):
    """Réponse de GET /ocr/upload/chunks/{task_id} — liste des chunks déjà reçus."""
    task_id: str
    received: List[int]          # index des chunks déjà enregistrés en base
    total_chunks: Optional[int]  # None si la tâche n'existe pas encore (chunk 0 pas envoyé)
