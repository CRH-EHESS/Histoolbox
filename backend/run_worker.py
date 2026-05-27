"""
Point d'entrée du worker RQ — Histoolbox.

Lance la ré-enqueue des tâches pending (recovery après crash Redis),
puis démarre le worker RQ sur la queue 'ocr'.

Usage :
    uv run python run_worker.py

Variables d'environnement :
    REDIS_URL   — URL de connexion Redis (défaut : redis://localhost:6379/0)
"""

import os
import sys
from pathlib import Path

# Ajoute le répertoire courant (backend/) au path pour les imports app.*
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from redis import Redis
from rq import Queue, Worker

from app.database import init_db
from app.worker import requeue_pending_tasks

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

if __name__ == "__main__":
    logger.info("Worker RQ démarrage | redis={}", REDIS_URL)

    # Initialise la DB (crée la table si besoin, corrige les tâches processing)
    init_db()

    conn = Redis.from_url(REDIS_URL)
    queue = Queue("ocr", connection=conn)

    # Recovery : ré-enqueue les tâches pending perdues lors d'un crash Redis
    requeue_pending_tasks(queue)

    logger.info("Worker RQ prêt — en attente de jobs sur la queue 'ocr'")
    worker = Worker([queue], connection=conn)
    worker.work(with_scheduler=False)
