"""
Tests de ChandraService — subprocess mocké pour ne pas invoquer le vrai CLI.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.services.chandra_service import run_chandra, _read_outputs


@pytest.mark.asyncio
async def test_run_chandra_success(tmp_path):
    """run_chandra appelle le CLI et retourne le contenu des fichiers produits."""
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"fake")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    # Simule les fichiers que Chandra aurait produits (dans output_dir/<stem>/)
    chandra_subdir = output_dir / "doc"
    chandra_subdir.mkdir()
    (chandra_subdir / "doc.md").write_text("# Résultat OCR")
    (chandra_subdir / "doc.html").write_text("<h1>Résultat OCR</h1>")
    (chandra_subdir / "doc_metadata.json").write_text('{"pages": 3}')

    with patch("app.services.chandra_service.asyncio.to_thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        result = await run_chandra(str(pdf_path), str(output_dir))

    assert result["markdown"] == "# Résultat OCR"
    assert result["html"] == "<h1>Résultat OCR</h1>"
    assert result["metadata"] == {"pages": 3}


@pytest.mark.asyncio
async def test_run_chandra_propagates_error(tmp_path):
    """run_chandra propage l'exception si le CLI echoue."""
    import subprocess
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"fake")

    with patch("app.services.chandra_service.asyncio.to_thread",
               side_effect=subprocess.CalledProcessError(1, "chandra")):
        with pytest.raises(Exception):
            await run_chandra(str(pdf_path), str(tmp_path / "out"))


def test_read_outputs_missing_files(tmp_path):
    """_read_outputs retourne des chaînes vides si les fichiers n'existent pas."""
    result = _read_outputs("doc", tmp_path)
    assert result["markdown"] == ""
    assert result["html"] == ""
    assert result["metadata"] == {}


def test_read_outputs_partial_files(tmp_path):
    """_read_outputs retourne le contenu disponible si certains fichiers manquent."""
    # _read_outputs reçoit directement le répertoire effectif (output_dir/<stem>)
    (tmp_path / "rapport.md").write_text("Contenu MD")
    result = _read_outputs("rapport", tmp_path)
    assert result["markdown"] == "Contenu MD"
    assert result["html"] == ""
