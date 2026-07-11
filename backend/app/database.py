"""
Couche d'accès SQLite (sqlite3 stdlib, zéro ORM).

Tables :
    tasks(
        id              TEXT PRIMARY KEY,
        status          TEXT NOT NULL,  -- pending_upload | pending | processing | completed | error
        pdf_path        TEXT NOT NULL,
        output_dir      TEXT NOT NULL,
        created_at      INTEGER NOT NULL,
        updated_at      INTEGER NOT NULL,
        error_message   TEXT,
        progress_step   INTEGER,
        progress_total  INTEGER,
        progress_label  TEXT,
        email           TEXT            -- adresse pour notification (nullable)
    )
    upload_chunks(
        task_id         TEXT    NOT NULL,
        chunk_index     INTEGER NOT NULL,
        PRIMARY KEY (task_id, chunk_index)
    )

Statuts de tasks :
    pending_upload  — le fichier est en cours de réception par chunks (pas encore enqueued)
    pending         — fichier complet, en attente dans la queue RQ
    processing      — en cours d'inférence par le worker
    completed       — traitement terminé avec succès
    error           — erreur (inférence, timeout ou upload interrompu)

Note : au redémarrage de l'API, pending_upload ET processing sont basculés en error
(l'inférence et l'assemblage ne peuvent pas reprendre à mi-chemin).
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
    """Crée les tables si elles n'existent pas et corrige les tâches bloquées."""
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS upload_chunks (
                task_id     TEXT    NOT NULL,
                chunk_index INTEGER NOT NULL,
                PRIMARY KEY (task_id, chunk_index)
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
        ]:
            try:
                conn.execute(f"ALTER TABLE tasks ADD COLUMN {col} {definition}")
            except Exception:
                pass  # colonne déjà présente
        # Tâches dont l'inférence était en cours au moment du crash → error.
        # Tâches dont l'upload par chunks était en cours → error (assemblage
        # impossible à reprendre à mi-chemin).
        # Les tâches 'pending' sont conservées : le worker RQ les ré-enqueuera
        # via requeue_pending_tasks() au prochain démarrage.
        conn.execute(
            "UPDATE tasks SET status = 'error', "
            "error_message = 'Traitement interrompu par un redémarrage du serveur.', "
            "updated_at = ? WHERE status IN ('processing', 'pending_upload')",
            (int(time.time()),),
        )
        conn.commit()


def create_task(
    task_id: str, pdf_path: str, output_dir: str, email: Optional[str] = None
) -> None:
    now = int(time.time())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO tasks (id, status, pdf_path, output_dir, created_at, updated_at, email) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (task_id, "pending", pdf_path, output_dir, now, now, email),
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
    """Retourne les tâches dont updated_at est antérieur à cutoff (timestamp Unix)."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM tasks WHERE updated_at < ?", (cutoff,)
        ).fetchall()


def delete_task(task_id: str) -> None:
    """Supprime l'entrée SQLite d'une tâche."""
    with _connect() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# Helpers upload par chunks
# ---------------------------------------------------------------------------

def create_task_pending_upload(
    task_id: str, pdf_path: str, output_dir: str, email: Optional[str] = None
) -> None:
    """Crée une tâche en statut 'pending_upload' (fichier pas encore complet)."""
    now = int(time.time())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO tasks (id, status, pdf_path, output_dir, created_at, updated_at, email) "
            "VALUES (?, 'pending_upload', ?, ?, ?, ?, ?)",
            (task_id, pdf_path, output_dir, now, now, email),
        )
        conn.commit()


def register_chunk(task_id: str, chunk_index: int) -> None:
    """Enregistre la réception d'un chunk (idempotent : INSERT OR IGNORE)."""
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO upload_chunks (task_id, chunk_index) VALUES (?, ?)",
            (task_id, chunk_index),
        )
        conn.commit()


def get_received_chunks_count(task_id: str) -> int:
    """Retourne le nombre de chunks déjà reçus pour une tâche."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM upload_chunks WHERE task_id = ?", (task_id,)
        ).fetchone()
        return row[0] if row else 0


def delete_upload_chunks(task_id: str) -> None:
    """Supprime les entrées upload_chunks une fois l'assemblage terminé."""
    with _connect() as conn:
        conn.execute("DELETE FROM upload_chunks WHERE task_id = ?", (task_id,))
        conn.commit()
