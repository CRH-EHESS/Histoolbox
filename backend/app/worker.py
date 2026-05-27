"""
Worker RQ — Histoolbox.

Fonction de traitement OCR exécutée par le worker RQ dans un process séparé.
Toutes les fonctions sont synchrones (RQ n'est pas async).

Utilisation :
    uv run python run_worker.py
"""

import shutil
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from app.database import (
    get_pending_tasks,
    update_task_error,
    update_task_status,
)
from app.services.chandra_service import run_chandra_sync
from app.services.email_service import send_notification_email


def process_ocr_job(
    task_id: str,
    pdf_path: str,
    output_dir: str,
    email: Optional[str] = None,
) -> None:
    """Traite un PDF via Chandra et met à jour le statut en base.

    Appelée par le worker RQ. Toujours synchrone.
    - Marque la tâche 'processing' en début de traitement.
    - Appelle run_chandra_sync (qui met à jour les progress steps).
    - Marque 'completed' ou 'error' selon le résultat.
    - Envoie un email de notification si l'adresse est fournie.
    - Supprime le répertoire upload dans tous les cas (finally).
    """
    filename = Path(pdf_path).name
    logger.info("[{}] Démarrage traitement | pdf={}", task_id, pdf_path)
    update_task_status(task_id, "processing")
    t0 = time.monotonic()

    try:
        run_chandra_sync(pdf_path, output_dir, task_id=task_id)
        elapsed = time.monotonic() - t0
        update_task_status(task_id, "completed")
        logger.success("[{}] Traitement terminé en {:.1f}s", task_id, elapsed)

        if email:
            send_notification_email(
                task_id=task_id,
                email=email,
                status="completed",
                filename=filename,
            )

    except Exception as exc:
        elapsed = time.monotonic() - t0
        error_msg = str(exc)
        logger.error("[{}] Erreur Chandra après {:.1f}s : {}", task_id, elapsed, error_msg)
        update_task_error(task_id, error_msg)

        if email:
            send_notification_email(
                task_id=task_id,
                email=email,
                status="error",
                filename=filename,
            )

    finally:
        # Suppression immédiate du PDF brut — le client le conserve dans IndexedDB
        upload_dir = Path(pdf_path).parent
        shutil.rmtree(upload_dir, ignore_errors=True)
        logger.debug("[{}] Répertoire upload supprimé : {}", task_id, upload_dir)


def requeue_pending_tasks(queue) -> int:
    """Ré-enqueue les tâches SQLite en statut 'pending' absentes de la queue Redis.

    Appelée au démarrage du worker pour récupérer les tâches perdues lors d'un
    crash Redis ou d'un redémarrage serveur.

    Retourne le nombre de tâches ré-enqueuées.
    """
    pending = get_pending_tasks()
    if not pending:
        return 0

    existing_ids = set(queue.job_ids)
    requeued = 0
    for row in pending:
        task_id = row["id"]
        if task_id in existing_ids:
            logger.debug("[{}] Déjà dans la queue Redis, skip", task_id)
            continue
        queue.enqueue(
            process_ocr_job,
            task_id,
            row["pdf_path"],
            row["output_dir"],
            row["email"],
            job_id=task_id,
        )
        requeued += 1
        logger.info("[{}] Ré-enqueuée (tâche pending retrouvée en SQLite)", task_id)

    if requeued:
        logger.info("{} tâche(s) pending ré-enqueuée(s) au démarrage du worker", requeued)
    return requeued
