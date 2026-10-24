"""Tests de app.main — boucle de nettoyage, vérification de la clé d'API au démarrage."""

import pytest

from app import main
from app.database import create_task, get_task, update_task_status


@pytest.mark.asyncio
async def test_cleanup_only_removes_finished_tasks(tmp_path, monkeypatch):
    """Le nettoyage ne supprime jamais une tâche en attente ou en cours (F2, N3)."""
    monkeypatch.setattr(main, "CLEANUP_TTL_SECONDS", -10)  # toutes les tâches sont « anciennes »
    dirs = {}
    for status in ("pending", "processing", "completed", "error"):
        upload_dir = tmp_path / "uploads" / status
        output_dir = tmp_path / "outputs" / status
        upload_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)
        (upload_dir / "input.pdf").write_bytes(b"%PDF-1.4")
        create_task(status, str(upload_dir / "input.pdf"), str(output_dir))
        update_task_status(status, status)
        dirs[status] = (upload_dir, output_dir)

    await main._cleanup_expired_tasks()

    for status in ("pending", "processing"):
        assert get_task(status) is not None
        assert all(d.exists() for d in dirs[status])
    for status in ("completed", "error"):
        assert get_task(status) is None
        assert not any(d.exists() for d in dirs[status])


# ---------------------------------------------------------------------------
# Clé d'API au démarrage (N6)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", ["", "changeme"])
def test_check_api_key_refuses_placeholder_in_production(monkeypatch, key):
    monkeypatch.setattr(main, "HISTOOLBOX_ENV", "production")
    monkeypatch.setattr(main, "API_KEY", key)
    with pytest.raises(RuntimeError, match="API_KEY"):
        main._check_api_key()


def test_check_api_key_accepts_real_key_in_production(monkeypatch):
    monkeypatch.setattr(main, "HISTOOLBOX_ENV", "production")
    monkeypatch.setattr(main, "API_KEY", "3f9c2a7e5b1d4c8a")
    main._check_api_key()


def test_check_api_key_allows_empty_key_in_development(monkeypatch):
    monkeypatch.setattr(main, "HISTOOLBOX_ENV", "development")
    monkeypatch.setattr(main, "API_KEY", "")
    main._check_api_key()
