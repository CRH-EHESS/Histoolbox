"""
Service de notification email — Histoolbox.

Envoie un email à la fin d'un traitement OCR (succès ou erreur).
Utilise uniquement smtplib (stdlib) — zéro dépendance supplémentaire.

Configuration via variables d'environnement :
    SMTP_HOST       — Serveur SMTP (ex: smtp.brevo.com). Si absent, l'envoi est désactivé.
    SMTP_PORT       — Port (défaut : 587, TLS STARTTLS)
    SMTP_USER       — Identifiant SMTP
    SMTP_PASSWORD   — Mot de passe SMTP
    SMTP_FROM       — Adresse expéditeur (ex: noreply@histoolbox.fr)
    APP_BASE_URL    — URL de base de l'application (ex: https://histoolbox.example.com)
                      Utilisé pour construire le lien dans l'email.
                      Défaut : http://localhost:5173
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

_SMTP_HOST = os.getenv("SMTP_HOST", "")
_SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
_SMTP_USER = os.getenv("SMTP_USER", "")
_SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
_SMTP_FROM = os.getenv("SMTP_FROM", "")
_APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5173").rstrip("/")


def send_notification_email(
    task_id: str,
    email: str,
    status: str,
    filename: str = "document.pdf",
) -> None:
    """Envoie un email de notification (succès ou erreur) à l'utilisateur.

    Si SMTP_HOST est absent, log un warning et retourne silencieusement.
    Toujours synchrone (appelé depuis le worker RQ).
    """
    if not _SMTP_HOST:
        logger.warning(
            "[{}] Notification email ignorée : SMTP_HOST non configuré", task_id
        )
        return

    if status == "completed":
        subject = f"Histoolbox — Transcription terminée : {filename}"
        body_html = _template_success(task_id, filename)
        body_text = (
            f"La transcription de « {filename} » est terminée.\n"
            f"Accédez à votre document : {_APP_BASE_URL}/ocr/toolbox/{task_id}\n"
        )
    else:
        subject = f"Histoolbox — Erreur de transcription : {filename}"
        body_html = _template_error(task_id, filename)
        body_text = (
            f"La transcription de « {filename} » a échoué.\n"
            f"Vous pouvez soumettre à nouveau ce document depuis : {_APP_BASE_URL}\n"
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = _SMTP_FROM or _SMTP_USER
    msg["To"] = email
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if _SMTP_USER and _SMTP_PASSWORD:
                server.login(_SMTP_USER, _SMTP_PASSWORD)
            server.sendmail(msg["From"], [email], msg.as_string())
        logger.info("[{}] Email de notification envoyé → {}", task_id, email)
    except Exception as exc:
        logger.error(
            "[{}] Échec envoi email → {} : {}", task_id, email, exc
        )


# --------------------------------------------------------------------------- #
# Templates HTML                                                               #
# --------------------------------------------------------------------------- #

_BASE_STYLE = """
    body { font-family: Georgia, serif; background: #fdfbf7; color: #262626; margin: 0; padding: 0; }
    .container { max-width: 520px; margin: 40px auto; padding: 32px; background: #fff;
                 border: 1px solid #e8e4dc; border-radius: 8px; }
    h1 { font-size: 20px; margin: 0 0 16px; }
    p  { line-height: 1.6; margin: 0 0 16px; color: #444; }
    .btn { display: inline-block; padding: 12px 24px; background: #262626; color: #fff;
           text-decoration: none; border-radius: 6px; font-size: 14px; }
    .footer { margin-top: 32px; font-size: 12px; color: #aaa; }
"""


def _template_success(task_id: str, filename: str) -> str:
    url = f"{_APP_BASE_URL}/ocr/toolbox/{task_id}"
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><style>{_BASE_STYLE}</style></head>
<body><div class="container">
  <h1>✓ Transcription terminée</h1>
  <p>La transcription de <strong>{filename}</strong> est prête.</p>
  <p><a href="{url}" class="btn">Ouvrir le document</a></p>
  <p class="footer">Histoolbox · Cet email a été envoyé parce que vous avez fourni
  votre adresse lors de l'upload.</p>
</div></body></html>"""


def _template_error(task_id: str, filename: str) -> str:
    url = _APP_BASE_URL
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><style>{_BASE_STYLE}</style></head>
<body><div class="container">
  <h1>✕ Erreur de transcription</h1>
  <p>La transcription de <strong>{filename}</strong> a échoué.</p>
  <p>Vous pouvez soumettre à nouveau ce document depuis l'application.</p>
  <p><a href="{url}" class="btn">Retour à Histoolbox</a></p>
  <p class="footer">Histoolbox · Référence tâche : {task_id}</p>
</div></body></html>"""
