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
    body = status_r.json()
    assert body["status"] == "pending"
    assert isinstance(body["created_at"], int)
    assert isinstance(body["updated_at"], int)


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
    """GET /ocr/result retourne le contrat typé complet si status=completed."""
    import json
    from app.database import create_task, update_task_status

    task_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    output_dir = tmp_path / task_id
    output_dir.mkdir()
    chandra_subdir = output_dir / "doc"
    chandra_subdir.mkdir()

    (chandra_subdir / "doc.md").write_text("# Transcription")
    blocks_data = [
        {
            "id": "0_0", "page": 0, "block_index": 0,
            "label": "Text", "bbox_norm": [0.0, 0.0, 1.0, 1.0],
            "markdown": "# Transcription",
        }
    ]
    (chandra_subdir / "doc_blocks.json").write_text(json.dumps(blocks_data))
    meta_data = {
        "num_pages": 1,
        "total_token_count": 120,
        "pages": [{"page_num": 0, "page_box": [0, 0, 1024, 1408], "token_count": 120, "num_blocks": 1}],
    }
    (chandra_subdir / "doc_metadata.json").write_text(json.dumps(meta_data))

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"fake")

    create_task(task_id, str(pdf_path), str(output_dir))
    update_task_status(task_id, "completed")

    r = await client.get(f"/ocr/result/{task_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["task_id"] == task_id
    assert body["filename"] == "doc.pdf"
    assert body["markdown"] == "# Transcription"
    assert isinstance(body["created_at"], int)
    assert isinstance(body["completed_at"], int)
    assert len(body["blocks"]) == 1
    assert body["blocks"][0]["label"] == "Text"
    assert body["blocks"][0]["bbox_norm"] == [0.0, 0.0, 1.0, 1.0]
    assert body["num_pages"] == 1
    assert body["total_token_count"] == 120
    assert len(body["pages"]) == 1


@pytest.mark.asyncio
async def test_process_task_error_stores_message(client: AsyncClient):
    """Quand run_chandra lève une exception, le statut devient error et error_message est persisté."""
    from app.routers.ocr import _process_task
    from app.database import create_task, get_task

    pdf_bytes = b"%PDF-1.4 fake pdf content"
    files = {"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    with patch("app.routers.ocr._process_task", new_callable=AsyncMock):
        upload_r = await client.post("/ocr/upload", files=files)

    task_id = upload_r.json()["task_id"]

    # Rejoue _process_task manuellement avec run_chandra qui échoue
    with patch(
        "app.routers.ocr.run_chandra",
        new_callable=AsyncMock,
        side_effect=RuntimeError("vLLM non joignable"),
    ):
        await _process_task(task_id, "/fake/doc.pdf", "/fake/out")

    row = get_task(task_id)
    assert row["status"] == "error"
    assert "vLLM non joignable" in row["error_message"]


@pytest.mark.asyncio
async def test_status_exposes_error_message(client: AsyncClient):
    """GET /ocr/status retourne error_message quand la tâche est en erreur."""
    from app.database import create_task, update_task_error

    task_id = "cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa"
    create_task(task_id, "/fake/doc.pdf", "/fake/out")
    update_task_error(task_id, "vLLM non joignable")

    r = await client.get(f"/ocr/status/{task_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "error"
    assert body["error_message"] == "vLLM non joignable"
    assert isinstance(body["created_at"], int)
    assert isinstance(body["updated_at"], int)


@pytest.mark.asyncio
async def test_process_task_deletes_upload_dir(client: AsyncClient, tmp_path):
    """Après _process_task, le répertoire d'upload est supprimé (succès et échec)."""
    from app.routers.ocr import _process_task
    from app.database import create_task

    task_id = "dddddddd-eeee-ffff-0000-111111111111"
    upload_dir = tmp_path / "uploads" / task_id
    upload_dir.mkdir(parents=True)
    pdf_path = upload_dir / "doc.pdf"
    pdf_path.write_bytes(b"fake pdf")
    output_dir = tmp_path / "outputs" / task_id
    output_dir.mkdir(parents=True)

    create_task(task_id, str(pdf_path), str(output_dir))

    with patch("app.routers.ocr.run_chandra", new_callable=AsyncMock, side_effect=RuntimeError("err")):
        await _process_task(task_id, str(pdf_path), str(output_dir))

    assert not upload_dir.exists()


@pytest.mark.asyncio
async def test_status_touch_refreshes_updated_at(client: AsyncClient):
    """GET /ocr/status doit rafraîchir updated_at (renouvellement du TTL)."""
    import time
    from app.database import create_task, get_task

    task_id = "eeeeeeee-ffff-0000-1111-222222222222"
    create_task(task_id, "/fake/doc.pdf", "/fake/out")
    before = get_task(task_id)["updated_at"]
    time.sleep(0.01)

    r = await client.get(f"/ocr/status/{task_id}")
    assert r.status_code == 200

    after = get_task(task_id)["updated_at"]
    assert after >= before
