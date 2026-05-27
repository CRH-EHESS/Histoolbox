"""Tests du service email (SMTP)."""

from unittest.mock import patch


def test_send_notification_email_without_smtp_host():
    from app.services.email_service import send_notification_email

    # Le test vérifie surtout l'absence d'exception si SMTP_HOST est vide.
    send_notification_email("t-1", "user@example.com", "completed", "doc.pdf")


def test_send_notification_email_uses_smtp_client():
    from app.services import email_service

    with patch.object(email_service, "_SMTP_HOST", "smtp.example.com"), \
         patch.object(email_service, "_SMTP_PORT", 587), \
         patch.object(email_service, "_SMTP_USER", "user"), \
         patch.object(email_service, "_SMTP_PASSWORD", "pass"), \
         patch.object(email_service, "_SMTP_FROM", "noreply@example.com"), \
         patch("smtplib.SMTP") as smtp_mock:

        email_service.send_notification_email(
            task_id="t-2",
            email="dest@example.com",
            status="completed",
            filename="doc.pdf",
        )

    smtp_mock.assert_called_once()
    smtp_instance = smtp_mock.return_value.__enter__.return_value
    smtp_instance.sendmail.assert_called_once()
