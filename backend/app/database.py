"""
Couche d'accès SQLite (sqlite3 stdlib, zéro ORM).

Table :
    tasks(
        id            TEXT PRIMARY KEY,
        status        TEXT NOT NULL,          -- pending | processing | completed | error
        pdf_path      TEXT NOT NULL,
        output_dir    TEXT NOT NULL,
        created_at    INTEGER NOT NULL,
        updated_at    INTEGER NOT NULL,
        error_message TEXT
    )
"""

import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

# Permet de surcharger le chemin de la DB via variable d'environnement (utile pour les tests)
_default_db = Path(__file__).parent.parent / "tasks.db"
DB_PATH = Path(os.environ.get("HISTOOLBOX_DB_PATH", str(_default_db)))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Crée la table si elle n'existe pas et corrige les tâches bloquées."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id            TEXT PRIMARY KEY,
                status        TEXT NOT NULL,
                pdf_path      TEXT NOT NULL,
                output_dir    TEXT NOT NULL,
                created_at    INTEGER NOT NULL,
                updated_at    INTEGER NOT NULL,
                error_message TEXT
            )
            """
        )
        # Migration additive : ajoute la colonne sur une DB existante sans error_message
        try:
            conn.execute("ALTER TABLE tasks ADD COLUMN error_message TEXT")
        except Exception:
            pass  # colonne déjà présente
        # Tâches bloquées en 'processing' lors d'un crash précédent → error
        conn.execute(
            "UPDATE tasks SET status = 'error', updated_at = ? WHERE status = 'processing'",
            (int(time.time()),),
        )
        conn.commit()


def create_task(task_id: str, pdf_path: str, output_dir: str) -> None:
    now = int(time.time())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO tasks (id, status, pdf_path, output_dir, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, "pending", pdf_path, output_dir, now, now),
        )
        conn.commit()


def update_task_status(task_id: str, status: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, int(time.time()), task_id),
        )
        conn.commit()


def update_task_error(task_id: str, message: str) -> None:
    """Marque une tâche comme 'error' en persistant le message d'erreur."""
    with _connect() as conn:
        conn.execute(
            "UPDATE tasks SET status = 'error', error_message = ?, updated_at = ? WHERE id = ?",
            (message, int(time.time()), task_id),
        )
        conn.commit()


def get_task(task_id: str) -> Optional[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
