"""Tests du worker RQ (process_ocr_job + requeue_pending_tasks)."""

from pathlib import Path
from unittest.mock import patch

from app.database import create_task, get_task
from app.worker import process_ocr_job, requeue_pending_tasks


def test_process_ocr_job_success(tmp_path):
    task_id = "worker-success"
    upload_dir = tmp_path / "uploads" / task_id
    upload_dir.mkdir(parents=True)
    pdf_path = upload_dir / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    output_dir = tmp_path / "outputs" / task_id
    output_dir.mkdir(parents=True)

    create_task(task_id, str(pdf_path), str(output_dir), email="user@example.com")

    with (
        patch("app.worker.run_chandra_sync", return_value={}),
        patch("app.worker.send_notification_email") as mail_mock,
    ):
        process_ocr_job(task_id, str(pdf_path), str(output_dir), "user@example.com")

    row = get_task(task_id)
    assert row["status"] == "completed"
    mail_mock.assert_called_once()
    assert not upload_dir.exists()


def test_process_ocr_job_error(tmp_path):
    task_id = "worker-error"
    upload_dir = tmp_path / "uploads" / task_id
    upload_dir.mkdir(parents=True)
    pdf_path = upload_dir / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    output_dir = tmp_path / "outputs" / task_id
    output_dir.mkdir(parents=True)

    create_task(task_id, str(pdf_path), str(output_dir), email="user@example.com")

    with (
        patch("app.worker.run_chandra_sync", side_effect=RuntimeError("boom")),
        patch("app.worker.send_notification_email") as mail_mock,
    ):
        process_ocr_job(task_id, str(pdf_path), str(output_dir), "user@example.com")

    row = get_task(task_id)
    assert row["status"] == "error"
    assert "boom" in row["error_message"]
    mail_mock.assert_called_once()
    assert not upload_dir.exists()


def test_requeue_pending_tasks():
    create_task("rq-1", "/uploads/rq1/doc.pdf", "/outputs/rq1", email="a@example.com")
    create_task("rq-2", "/uploads/rq2/doc.pdf", "/outputs/rq2", email="b@example.com")

    class FakeQueue:
        def __init__(self):
            self.jobs = []
            self.job_ids = {"rq-2"}

        def enqueue(self, func, *args, **kwargs):
            self.jobs.append((func, args, kwargs))
            self.job_ids.add(kwargs.get("job_id"))

    queue = FakeQueue()
    count = requeue_pending_tasks(queue)

    assert count == 1
    assert len(queue.jobs) == 1
    _func, args, kwargs = queue.jobs[0]
    assert args[0] == "rq-1"
    assert kwargs["job_id"] == "rq-1"
