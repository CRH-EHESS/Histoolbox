"""
Fixtures partagées pour les tests backend.
- Utilise une DB SQLite en mémoire (:memory:) isolée par test.
- Mocke ChandraService pour ne pas invoquer le vrai CLI.
"""

import os
import tempfile
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Rediriger la DB vers un fichier temporaire avant d'importer l'app
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["HISTOOLBOX_DB_PATH"] = _tmp_db.name
_tmp_db.close()


@pytest.fixture(autouse=True)
def clean_db():
    """Réinitialise la base entre chaque test."""
    from app import database
    database.init_db()  # recrée la table proprement
    yield
    # Supprime toutes les tâches après le test
    import sqlite3
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute("DELETE FROM tasks")
        conn.commit()


@pytest_asyncio.fixture
async def client():
    """Client HTTP asynchrone branché directement sur l'app ASGI."""
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
