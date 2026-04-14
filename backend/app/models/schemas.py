from pydantic import BaseModel
from typing import Literal


TaskStatus = Literal["pending", "processing", "completed", "error"]


class UploadResponse(BaseModel):
    task_id: str


class StatusResponse(BaseModel):
    task_id: str
    status: TaskStatus


class ChandraMetadata(BaseModel):
    """Métadonnées produites par Chandra (_metadata.json)."""
    model_config = {"extra": "allow"}


class ResultResponse(BaseModel):
    task_id: str
    markdown: str
    html: str
    metadata: dict
