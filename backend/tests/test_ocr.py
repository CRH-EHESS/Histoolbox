"""
Tests des endpoints OCR :
  POST /ocr/upload
  GET  /ocr/status/{task_id}
  GET  /ocr/result/{task_id}
"""

import io
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_upload_returns_task_id(client: AsyncClient):
    """POST /ocr/upload doit retourner un task_id UUID."""
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    files = {"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    with patch("app.routers.ocr._process_task", new_callable=AsyncMock):
        r = await client.post("/ocr/upload", files=files)

    assert r.status_code == 202
    body = r.json()
    assert "task_id" in body
    assert len(body["task_id"]) == 36  # format UUID


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf(client: AsyncClient):
    """POST /ocr/upload doit rejeter les fichiers non-PDF."""
    files = {"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")}
    r = await client.post("/ocr/upload", files=files)
    assert r.status_code == 415


@pytest.mark.asyncio
async def test_status_pending_after_upload(client: AsyncClient):
    """GET /ocr/status doit retourner pending juste après l'upload."""
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    files = {"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    with patch("app.routers.ocr._process_task", new_callable=AsyncMock):
        upload_r = await client.post("/ocr/upload", files=files)

    task_id = upload_r.json()["task_id"]
    status_r = await client.get(f"/ocr/status/{task_id}")
    assert status_r.status_code == 200
    assert status_r.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_status_unknown_task(client: AsyncClient):
    """GET /ocr/status avec un ID inconnu doit retourner 404."""
    r = await client.get("/ocr/status/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_result_not_completed_returns_409(client: AsyncClient):
    """GET /ocr/result sur tâche pending doit retourner 409."""
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    files = {"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    with patch("app.routers.ocr._process_task", new_callable=AsyncMock):
        upload_r = await client.post("/ocr/upload", files=files)

    task_id = upload_r.json()["task_id"]
    r = await client.get(f"/ocr/result/{task_id}")
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_result_unknown_task(client: AsyncClient):
    """GET /ocr/result avec un ID inconnu doit retourner 404."""
    r = await client.get("/ocr/result/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_result_completed(client: AsyncClient, tmp_path):
    """GET /ocr/result retourne les fichiers Chandra si status=completed."""
    from app.database import create_task, update_task_status

    # Simule une tâche terminée avec de vrais fichiers de sortie
    # Chandra crée output_dir/<stem>/ comme répertoire de sortie effectif
    task_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    output_dir = tmp_path / task_id
    output_dir.mkdir()
    chandra_subdir = output_dir / "doc"
    chandra_subdir.mkdir()
    (chandra_subdir / "doc.md").write_text("# Transcription")
    (chandra_subdir / "doc.html").write_text("<h1>Transcription</h1>")
    (chandra_subdir / "doc_metadata.json").write_text('{"pages": 5}')

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"fake")

    create_task(task_id, str(pdf_path), str(output_dir))
    update_task_status(task_id, "completed")

    r = await client.get(f"/ocr/result/{task_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["markdown"] == "# Transcription"
    assert body["html"] == "<h1>Transcription</h1>"
    assert body["metadata"] == {"pages": 5}
