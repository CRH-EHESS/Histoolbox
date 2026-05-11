"""
Tests de app.database — CRUD SQLite raw.
"""

import pytest
import time
from app.database import (
    create_task,
    delete_task,
    get_expired_tasks,
    get_task,
    touch_task,
    update_task_status,
)


def test_create_and_get_task():
    create_task("t-001", "/uploads/t-001/doc.pdf", "/outputs/t-001")
    row = get_task("t-001")
    assert row is not None
    assert row["id"] == "t-001"
    assert row["status"] == "pending"
    assert row["pdf_path"] == "/uploads/t-001/doc.pdf"
    assert row["created_at"] > 0


def test_update_task_status():
    create_task("t-002", "/uploads/t-002/doc.pdf", "/outputs/t-002")
    update_task_status("t-002", "processing")
    row = get_task("t-002")
    assert row["status"] == "processing"


def test_update_task_status_updated_at():
    create_task("t-003", "/uploads/t-003/doc.pdf", "/outputs/t-003")
    before = get_task("t-003")["updated_at"]
    time.sleep(0.01)
    update_task_status("t-003", "completed")
    after = get_task("t-003")["updated_at"]
    assert after >= before


def test_get_task_unknown():
    row = get_task("inexistant-id")
    assert row is None


def test_create_task_full_lifecycle():
    tid = "lifecycle-001"
    create_task(tid, "/p/doc.pdf", "/o/")
    assert get_task(tid)["status"] == "pending"
    update_task_status(tid, "processing")
    assert get_task(tid)["status"] == "processing"
    update_task_status(tid, "completed")
    assert get_task(tid)["status"] == "completed"


def test_touch_task_updates_timestamp():
    create_task("t-touch", "/uploads/t-touch/doc.pdf", "/outputs/t-touch")
    before = get_task("t-touch")["updated_at"]
    time.sleep(0.01)
    touch_task("t-touch")
    after = get_task("t-touch")["updated_at"]
    assert after >= before


def test_get_expired_tasks_returns_old_entries():
    """Les tâches dont updated_at < cutoff doivent apparaître dans la liste."""
    create_task("t-expired", "/uploads/t-expired/doc.pdf", "/outputs/t-expired")
    # cutoff dans le futur : la tâche est considérée comme expirée
    cutoff = int(time.time()) + 10
    expired = get_expired_tasks(cutoff)
    ids = [row["id"] for row in expired]
    assert "t-expired" in ids


def test_get_expired_tasks_excludes_recent():
    """Les tâches récentes ne doivent pas apparaître."""
    create_task("t-recent", "/uploads/t-recent/doc.pdf", "/outputs/t-recent")
    # cutoff dans le passé : la tâche est récente
    cutoff = int(time.time()) - 10
    expired = get_expired_tasks(cutoff)
    ids = [row["id"] for row in expired]
    assert "t-recent" not in ids


def test_delete_task_removes_entry():
    create_task("t-delete", "/uploads/t-delete/doc.pdf", "/outputs/t-delete")
    assert get_task("t-delete") is not None
    delete_task("t-delete")
    assert get_task("t-delete") is None
