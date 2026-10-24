"""
Couche d'accès SQLite (sqlite3 stdlib, zéro ORM).

Table :
    tasks(
        id              TEXT PRIMARY KEY,
        status          TEXT NOT NULL,  -- pending | processing | completed | error
        pdf_path        TEXT NOT NULL,
        output_dir      TEXT NOT NULL,
        created_at      INTEGER NOT NULL,
        updated_at      INTEGER NOT NULL,
        error_message   TEXT,
        progress_step   INTEGER,
        progress_total  INTEGER,
        progress_label  TEXT,
        email           TEXT,           -- adresse pour notification (nullable)
        filename        TEXT            -- nom d'origine assaini, affichage et email (nullable)
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
                id              TEXT PRIMARY KEY,
                status          TEXT NOT NULL,
                pdf_path        TEXT NOT NULL,
                output_dir      TEXT NOT NULL,
                created_at      INTEGER NOT NULL,
                updated_at      INTEGER NOT NULL,
                error_message   TEXT,
                progress_step   INTEGER,
                progress_total  INTEGER,
                progress_label  TEXT
            )
            """
        )
        # Migrations additives sur une DB existante
        for col, definition in [
            ("error_message",  "TEXT"),
            ("progress_step",  "INTEGER"),
            ("progress_total", "INTEGER"),
            ("progress_label", "TEXT"),
            ("email",          "TEXT"),
            ("filename",       "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE tasks ADD COLUMN {col} {definition}")
            except Exception:
                pass  # colonne déjà présente
        # Tâches en cours d'inférence (processing) au moment du crash → error.
        # Les tâches 'pending' sont conservées telles quelles : le worker RQ les
        # ré-enqueuera via requeue_pending_tasks() au prochain démarrage.
        conn.execute(
            "UPDATE tasks SET status = 'error', "
            "error_message = 'Traitement interrompu par un redémarrage du serveur.', "
            "updated_at = ? WHERE status = 'processing'",
            (int(time.time()),),
        )
        conn.commit()


def create_task(
    task_id: str,
    pdf_path: str,
    output_dir: str,
    email: Optional[str] = None,
    filename: Optional[str] = None,
) -> None:
    now = int(time.time())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO tasks (id, status, pdf_path, output_dir, created_at, updated_at, email, filename) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (task_id, "pending", pdf_path, output_dir, now, now, email, filename),
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


def touch_task(task_id: str) -> None:
    """Rafraîchit updated_at — renouvelle le TTL de la tâche."""
    with _connect() as conn:
        conn.execute(
            "UPDATE tasks SET updated_at = ? WHERE id = ?",
            (int(time.time()), task_id),
        )
        conn.commit()


def update_task_progress(task_id: str, label: str, step: int, total: int) -> None:
    """Met à jour l'avancement de l'inférence (label + numéro d'étape)."""
    with _connect() as conn:
        conn.execute(
            "UPDATE tasks SET progress_label = ?, progress_step = ?, progress_total = ?, updated_at = ? WHERE id = ?",
            (label, step, total, int(time.time()), task_id),
        )
        conn.commit()


def get_queue_position(task_id: str) -> Optional[int]:
    """Retourne la position dans la file pour une tâche pending/processing (1 = en cours).

    Compte le nombre de tâches pending/processing soumises avant ou en même temps
    que celle-ci. Retourne None si la tâche est completed ou error.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT status, created_at FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None or row["status"] not in ("pending", "processing"):
            return None
        count = conn.execute(
            "SELECT COUNT(*) FROM tasks "
            "WHERE status IN ('pending', 'processing') "
            "AND (created_at < ? OR (created_at = ? AND id <= ?))",
            (row["created_at"], row["created_at"], task_id),
        ).fetchone()[0]
        return count


def get_pending_tasks() -> list:
    """Retourne toutes les tâches en statut 'pending' (pour requeue au démarrage du worker)."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM tasks WHERE status = 'pending' ORDER BY created_at"
        ).fetchall()


def get_expired_tasks(cutoff: int) -> list:
    """Retourne les tâches terminées dont updated_at est antérieur à cutoff (timestamp Unix).

    Les tâches pending et processing n'expirent jamais : updated_at n'avance pas
    pendant l'inférence, qui peut durer des heures.
    """
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM tasks WHERE status IN ('completed', 'error') AND updated_at < ?",
            (cutoff,),
        ).fetchall()


def delete_task(task_id: str) -> None:
    """Supprime l'entrée SQLite d'une tâche."""
    with _connect() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
