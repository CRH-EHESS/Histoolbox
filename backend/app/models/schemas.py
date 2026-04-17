from pydantic import BaseModel
from typing import List, Literal, Optional


TaskStatus = Literal["pending", "processing", "completed", "error"]


class UploadResponse(BaseModel):
    task_id: str


class StatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    error_message: Optional[str] = None
    created_at: int
    updated_at: int


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
    markdown: str                # Concaténation des markdown par bloc
    blocks: List[BlockItem]      # Blocs de layout avec bbox normalisées
    num_pages: int
    total_token_count: int
    pages: List[PageInfo]
