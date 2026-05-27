"""
Tests de app.database — CRUD SQLite raw.
"""

import pytest
import time
from app.database import (
    create_task,
    delete_task,
    get_expired_tasks,
    get_pending_tasks,
    get_queue_position,
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


# ---------------------------------------------------------------------------
# init_db crash-recovery (Bug 1)
# ---------------------------------------------------------------------------

def test_init_db_converts_processing_to_error_on_restart():
    """init_db() doit convertir les tâches 'processing' en 'error' au redémarrage."""
    from app.database import init_db, update_task_error
    create_task("t-crash-proc", "/uploads/t-cp/doc.pdf", "/outputs/t-cp")
    update_task_status("t-crash-proc", "processing")
    assert get_task("t-crash-proc")["status"] == "processing"

    init_db()  # simule un redémarrage

    row = get_task("t-crash-proc")
    assert row["status"] == "error"
    assert row["error_message"] is not None
    assert "redémarrage" in row["error_message"]


def test_init_db_keeps_pending_on_restart():
    """init_db() conserve les tâches 'pending' pour permettre le requeue worker."""
    from app.database import init_db
    create_task("t-crash-pend", "/uploads/t-cpnd/doc.pdf", "/outputs/t-cpnd")
    assert get_task("t-crash-pend")["status"] == "pending"

    init_db()  # simule un redémarrage

    row = get_task("t-crash-pend")
    assert row["status"] == "pending"


def test_init_db_does_not_touch_completed_tasks():
    """init_db() ne doit pas modifier les tâches déjà 'completed' ou 'error'."""
    from app.database import init_db
    create_task("t-done", "/uploads/t-done/doc.pdf", "/outputs/t-done")
    update_task_status("t-done", "completed")

    create_task("t-err", "/uploads/t-err/doc.pdf", "/outputs/t-err")
    update_task_status("t-err", "error")

    init_db()

    assert get_task("t-done")["status"] == "completed"
    assert get_task("t-err")["status"] == "error"


def test_get_queue_position_pending_and_processing():
    create_task("q-1", "/uploads/q1/doc.pdf", "/outputs/q1")
    create_task("q-2", "/uploads/q2/doc.pdf", "/outputs/q2")
    create_task("q-3", "/uploads/q3/doc.pdf", "/outputs/q3")

    update_task_status("q-1", "processing")
    assert get_queue_position("q-1") == 1
    assert get_queue_position("q-2") == 2
    assert get_queue_position("q-3") == 3


def test_get_queue_position_none_for_done_or_unknown():
    create_task("q-done", "/uploads/qd/doc.pdf", "/outputs/qd")
    update_task_status("q-done", "completed")
    assert get_queue_position("q-done") is None
    assert get_queue_position("unknown") is None


def test_get_pending_tasks_lists_only_pending():
    create_task("p-1", "/uploads/p1/doc.pdf", "/outputs/p1")
    create_task("p-2", "/uploads/p2/doc.pdf", "/outputs/p2")
    update_task_status("p-2", "processing")

    pending_ids = [row["id"] for row in get_pending_tasks()]
    assert "p-1" in pending_ids
    assert "p-2" not in pending_ids
