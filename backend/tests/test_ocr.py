"""
Tests des endpoints OCR :
  POST /ocr/upload
  GET  /ocr/status/{task_id}
  GET  /ocr/result/{task_id}
"""

import io
import pytest
from unittest.mock import patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_upload_returns_task_id(client: AsyncClient):
    """POST /ocr/upload doit retourner un task_id UUID."""
    from app.main import app

    pdf_bytes = b"%PDF-1.4 fake pdf content"
    files = {"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    r = await client.post("/ocr/upload", files=files)

    assert r.status_code == 202
    body = r.json()
    assert "task_id" in body
    assert len(body["task_id"]) == 36  # format UUID
    assert len(app.state.rq_queue.enqueued) == 1
    assert app.state.rq_queue.enqueued[0]["job_timeout"] > 180


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

    upload_r = await client.post("/ocr/upload", files=files)

    task_id = upload_r.json()["task_id"]
    status_r = await client.get(f"/ocr/status/{task_id}")
    assert status_r.status_code == 200
    body = status_r.json()
    assert body["status"] == "pending"
    assert body["queue_position"] == 1
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
async def test_upload_accepts_optional_email(client: AsyncClient):
    """POST /ocr/upload accepte un email optionnel et persiste la valeur."""
    from app.database import get_task

    files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    data = {"email": "user@example.com"}
    r = await client.post("/ocr/upload", files=files, data=data)

    assert r.status_code == 202
    task_id = r.json()["task_id"]
    row = get_task(task_id)
    assert row["email"] == "user@example.com"


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
async def test_upload_rejects_invalid_email(client: AsyncClient):
    """POST /ocr/upload retourne 422 si l'email fourni est invalide."""
    files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    data = {"email": "invalid-email"}
    r = await client.post("/ocr/upload", files=files, data=data)
    assert r.status_code == 422


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


# ---------------------------------------------------------------------------
# Tests upload par chunks
# ---------------------------------------------------------------------------

def _make_task_id() -> str:
    import uuid
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_chunk_upload_single_chunk(client: AsyncClient):
    """Un PDF < 5 Mo envoyé en 1 chunk : assemblage immédiat + job enqueued."""
    from app.main import app

    task_id = _make_task_id()
    pdf_bytes = b"%PDF-1.4 single chunk content"

    data = {
        "task_id": task_id,
        "chunk_index": "0",
        "total_chunks": "1",
        "filename": "doc.pdf",
    }
    files = {"chunk": ("doc.pdf", io.BytesIO(pdf_bytes), "application/octet-stream")}

    r = await client.post("/ocr/upload/chunk", data=data, files=files)
    assert r.status_code == 202
    body = r.json()
    assert body["task_id"] == task_id
    assert body["chunks_received"] == 1
    assert body["total_chunks"] == 1
    assert body["assembled"] is True
    assert len(app.state.rq_queue.enqueued) == 1


@pytest.mark.asyncio
async def test_chunk_upload_multi_chunk_sequence(client: AsyncClient):
    """Upload en 3 chunks : le job est enqueued uniquement au 3ème chunk."""
    from app.main import app
    from app.database import get_task

    task_id = _make_task_id()
    parts = [b"part0_data", b"part1_data", b"part2_data"]

    for i, part in enumerate(parts):
        data = {
            "task_id": task_id,
            "chunk_index": str(i),
            "total_chunks": "3",
            "filename": "big.pdf",
        }
        files = {"chunk": ("big.pdf", io.BytesIO(part), "application/octet-stream")}
        r = await client.post("/ocr/upload/chunk", data=data, files=files)
        assert r.status_code == 202
        body = r.json()
        assert body["chunks_received"] == i + 1
        is_last = i == 2
        assert body["assembled"] is is_last

    # Le job ne doit être enqueued qu'une seule fois (au dernier chunk)
    enqueued = [e for e in app.state.rq_queue.enqueued if e["args"][0] == task_id]
    assert len(enqueued) == 1

    # Le statut final est 'pending' (pas 'pending_upload')
    row = get_task(task_id)
    assert row["status"] == "pending"


@pytest.mark.asyncio
async def test_chunk_upload_chunk_index_out_of_range(client: AsyncClient):
    """chunk_index hors plage [0, total_chunks-1] → 422."""
    task_id = _make_task_id()
    data = {
        "task_id": task_id,
        "chunk_index": "5",   # > total_chunks - 1 = 2
        "total_chunks": "3",
        "filename": "doc.pdf",
    }
    files = {"chunk": ("doc.pdf", io.BytesIO(b"data"), "application/octet-stream")}
    r = await client.post("/ocr/upload/chunk", data=data, files=files)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_chunk_upload_missing_chunk_0_first(client: AsyncClient):
    """Envoyer chunk_index=1 sans avoir envoyé chunk_index=0 → 404."""
    task_id = _make_task_id()
    data = {
        "task_id": task_id,
        "chunk_index": "1",
        "total_chunks": "2",
        "filename": "doc.pdf",
    }
    files = {"chunk": ("doc.pdf", io.BytesIO(b"data"), "application/octet-stream")}
    r = await client.post("/ocr/upload/chunk", data=data, files=files)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_chunk_upload_idempotent_resend(client: AsyncClient):
    """Re-envoyer un chunk déjà reçu est idempotent (pas d'erreur, pas de doublon en DB)."""
    from app.database import get_received_chunks_count

    task_id = _make_task_id()
    data = {
        "task_id": task_id,
        "chunk_index": "0",
        "total_chunks": "2",
        "filename": "doc.pdf",
    }
    files = {"chunk": ("doc.pdf", io.BytesIO(b"data0"), "application/octet-stream")}

    r1 = await client.post("/ocr/upload/chunk", data=data, files=files)
    assert r1.status_code == 202

    # Re-envoyer le même chunk
    files = {"chunk": ("doc.pdf", io.BytesIO(b"data0"), "application/octet-stream")}
    r2 = await client.post("/ocr/upload/chunk", data=data, files=files)
    assert r2.status_code == 202

    # Toujours 1 chunk enregistré (INSERT OR IGNORE)
    assert get_received_chunks_count(task_id) == 1


@pytest.mark.asyncio
async def test_chunk_upload_with_email(client: AsyncClient):
    """L'email est persisté si fourni au chunk 0."""
    from app.database import get_task

    task_id = _make_task_id()
    data = {
        "task_id": task_id,
        "chunk_index": "0",
        "total_chunks": "1",
        "filename": "doc.pdf",
        "email": "historien@exemple.fr",
    }
    files = {"chunk": ("doc.pdf", io.BytesIO(b"%PDF-1.4 data"), "application/octet-stream")}
    r = await client.post("/ocr/upload/chunk", data=data, files=files)
    assert r.status_code == 202
    row = get_task(task_id)
    assert row["email"] == "historien@exemple.fr"


@pytest.mark.asyncio
async def test_chunk_upload_invalid_email(client: AsyncClient):
    """Un email invalide au chunk 0 doit retourner 422."""
    task_id = _make_task_id()
    data = {
        "task_id": task_id,
        "chunk_index": "0",
        "total_chunks": "1",
        "filename": "doc.pdf",
        "email": "not-an-email",
    }
    files = {"chunk": ("doc.pdf", io.BytesIO(b"data"), "application/octet-stream")}
    r = await client.post("/ocr/upload/chunk", data=data, files=files)
    assert r.status_code == 422
