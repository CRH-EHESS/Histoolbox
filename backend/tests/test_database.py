"""
Tests de app.database — CRUD SQLite raw.
"""

import pytest
import time
from app.database import create_task, update_task_status, get_task


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
