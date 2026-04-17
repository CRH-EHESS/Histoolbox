from pydantic import BaseModel
from typing import Literal, Optional


TaskStatus = Literal["pending", "processing", "completed", "error"]


class UploadResponse(BaseModel):
    task_id: str


class StatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    error_message: Optional[str] = None


class ChandraMetadata(BaseModel):
    """Métadonnées produites par Chandra (_metadata.json)."""
    model_config = {"extra": "allow"}


class ResultResponse(BaseModel):
    task_id: str
    markdown: str
    html: str
    metadata: dict
