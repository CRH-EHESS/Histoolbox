"""
Tests de ChandraService — InferenceManager et load_file mockés pour ne pas
appeler le vrai vLLM ni lire de vrais fichiers PDF.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from app.services.chandra_service import (
    ChandraVllmUnavailableError,
    _assemble_and_persist,
    _check_vllm_available,
    run_chandra,
)


def _make_page(markdown="# OCR", html="<h1>OCR</h1>", token_count=42, error=None, chunks=None):
    """Crée un faux BatchOutputItem pour les tests."""
    item = MagicMock()
    item.markdown = markdown
    item.html = html
    item.token_count = token_count
    item.page_box = [0, 0, 1000, 1000]
    item.chunks = chunks if chunks is not None else []
    item.error = error
    return item


# ---------------------------------------------------------------------------
# run_chandra
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_chandra_success(tmp_path):
    """run_chandra retourne le contenu assemblé quand l'inférence réussit."""
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"fake")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    fake_results = [
        _make_page("# Page 1", "<h1>Page 1</h1>", 10),
        _make_page("# Page 2", "<h1>Page 2</h1>", 20),
    ]

    with patch(
        "app.services.chandra_service.asyncio.to_thread",
        return_value=fake_results,
    ):
        result = await run_chandra(str(pdf_path), str(output_dir))

    assert result["markdown"] == "# Page 1\n\n# Page 2"
    assert result["num_pages"] == 2
    assert result["total_token_count"] == 30
    assert len(result["blocks"]) == 2  # 1 bloc synthétique par page (chunks=[])
    assert result["blocks"][0]["bbox_norm"] == [0.0, 0.0, 1.0, 1.0]


@pytest.mark.asyncio
async def test_run_chandra_propagates_error(tmp_path):
    """run_chandra propage l'exception si l'inférence échoue."""
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"fake")

    with patch(
        "app.services.chandra_service.asyncio.to_thread",
        side_effect=RuntimeError("vLLM connection refused"),
    ):
        with pytest.raises(RuntimeError, match="vLLM connection refused"):
            await run_chandra(str(pdf_path), str(tmp_path / "out"))


@pytest.mark.asyncio
async def test_run_chandra_raises_on_page_errors(tmp_path):
    """run_chandra lève RuntimeError si le vLLM retourne des erreurs sur certaines pages."""
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"fake")

    with patch(
        "app.services.chandra_service.asyncio.to_thread",
        side_effect=RuntimeError("Chandra vLLM a retourné des erreurs sur 1/2"),
    ):
        with pytest.raises(RuntimeError, match="Chandra vLLM"):
            await run_chandra(str(pdf_path), str(tmp_path / "out"))


# ---------------------------------------------------------------------------
# _check_vllm_available
# ---------------------------------------------------------------------------

def test_check_vllm_available_success():
    """_check_vllm_available réussit si /health retourne un statut < 500."""
    with patch("app.services.chandra_service.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200)
        _check_vllm_available()
    mock_get.assert_called_once()


def test_check_vllm_available_fallback_to_models():
    """_check_vllm_available essaie /v1/models si /health échoue."""
    def side_effect(url, timeout):
        if "/health" in url:
            raise httpx.ConnectError("refused")
        return MagicMock(status_code=200)

    with patch("app.services.chandra_service.httpx.get", side_effect=side_effect):
        _check_vllm_available()  # ne doit pas lever


def test_check_vllm_unavailable_raises():
    """_check_vllm_available lève ChandraVllmUnavailableError si aucun endpoint ne répond."""
    with patch(
        "app.services.chandra_service.httpx.get",
        side_effect=httpx.ConnectError("refused"),
    ):
        with pytest.raises(ChandraVllmUnavailableError):
            _check_vllm_available()


# ---------------------------------------------------------------------------
# _assemble_and_persist
# ---------------------------------------------------------------------------

def test_assemble_and_persist_writes_files(tmp_path):
    """_assemble_and_persist crée les fichiers .md, _blocks.json et _metadata.json."""
    results = [_make_page("# OCR", "<h1>OCR</h1>", 42)]
    output = _assemble_and_persist("rapport", results, tmp_path / "rapport")

    chandra_dir = tmp_path / "rapport"
    assert (chandra_dir / "rapport.md").read_text() == "# OCR"
    assert (chandra_dir / "rapport_blocks.json").exists()
    assert (chandra_dir / "rapport_metadata.json").exists()
    assert output["markdown"] == "# OCR"
    assert output["num_pages"] == 1
    assert output["total_token_count"] == 42
    assert len(output["blocks"]) == 1
    assert output["blocks"][0]["bbox_norm"] == [0.0, 0.0, 1.0, 1.0]


def test_assemble_and_persist_multipage(tmp_path):
    """_assemble_and_persist concatène correctement plusieurs pages."""
    results = [
        _make_page("Page A", "<p>A</p>", 10),
        _make_page("Page B", "<p>B</p>", 15),
    ]
    output = _assemble_and_persist("doc", results, tmp_path / "doc")

    assert output["markdown"] == "Page A\n\nPage B"
    assert output["total_token_count"] == 25
    assert len(output["pages"]) == 2
    assert output["num_pages"] == 2
    assert len(output["blocks"]) == 2


def test_assemble_and_persist_with_chunks(tmp_path):
    """_assemble_and_persist normalise correctement les bbox quand des chunks sont présents."""
    chunks = [{"bbox": [100, 50, 500, 200], "label": "Text", "content": "<p>Hello</p>"}]
    results = [_make_page("# Unused", "", 30, chunks=chunks)]
    output = _assemble_and_persist("doc", results, tmp_path / "doc")

    assert len(output["blocks"]) == 1
    block = output["blocks"][0]
    assert block["id"] == "0_0"
    assert block["page"] == 0
    assert block["block_index"] == 0
    assert block["label"] == "Text"
    # page_box = [0, 0, 1000, 1000] d'après _make_page
    assert block["bbox_norm"] == [0.1, 0.05, 0.5, 0.2]
    assert isinstance(block["markdown"], str)

