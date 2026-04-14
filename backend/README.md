# Histoolbox — Backend

API FastAPI pour l'OCR diplomatique des documents anciens via le moteur **Chandra**.

## Stack

| Composant        | Technologie                  |
|------------------|------------------------------|
| Langage          | Python 3.11+                 |
| Framework API    | FastAPI 0.135                |
| Serveur ASGI     | Uvicorn                      |
| Gestionnaire pkg | **uv** (pas pip)             |
| Persistance      | SQLite stdlib (`sqlite3`)    |
| OCR              | Chandra CLI (local, vLLM)    |
| Tests            | pytest + httpx + pytest-asyncio |

## Démarrage rapide

```bash
# Installer les dépendances
uv sync

# Lancer le serveur de développement
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Le serveur est accessible sur `http://localhost:8001`.  
La documentation interactive est disponible sur `http://localhost:8001/docs`.

## Endpoints API

### `GET /health`
Vérifie que le service est opérationnel.

```json
{ "status": "ok" }
```

### `POST /ocr/upload`
Upload d'un fichier PDF pour traitement OCR.

- **Body** : `multipart/form-data` avec un champ `file` (PDF)
- **Réponse** : `202 Accepted`

```json
{ "task_id": "550e8400-e29b-41d4-a716-446655440000" }
```

Le traitement est lancé en tâche de fond (BackgroundTask). Le PDF est stocké dans `data/uploads/<task_id>/`.

### `GET /ocr/status/{task_id}`
Récupère l'état d'une tâche OCR.

```json
{
  "task_id": "550e8400...",
  "status": "processing",
  "created_at": 1720000000.0,
  "updated_at": 1720000042.0
}
```

Valeurs possibles de `status` : `pending`, `processing`, `completed`, `error`.

### `GET /ocr/result/{task_id}`
Récupère le résultat d'une tâche terminée.

- Retourne **409** si la tâche n'est pas encore `completed`.
- Retourne **404** si la tâche est inconnue.

```json
{
  "task_id": "550e8400...",
  "status": "completed",
  "markdown": "# Transcription diplomatique\n...",
  "html": "<h1>Transcription diplomatique</h1>...",
  "metadata": { "pages": 12, "language": "fr", ... }
}
```

## Structure du projet

```
backend/
├── app/
│   ├── main.py                    # App FastAPI + CORS + lifespan
│   ├── database.py                # SQLite brut (sqlite3 stdlib)
│   ├── routers/
│   │   └── ocr.py                 # POST /ocr/upload, GET /ocr/status, GET /ocr/result
│   ├── services/
│   │   └── chandra_service.py     # asyncio.to_thread subprocess Chandra CLI
│   └── models/
│       └── schemas.py             # Schémas Pydantic (UploadResponse, StatusResponse, ResultResponse)
├── tests/
│   ├── conftest.py                # Fixtures pytest (client, clean_db)
│   ├── test_ocr.py                # 7 tests d'intégration des endpoints
│   ├── test_database.py           # 5 tests CRUD SQLite
│   └── test_chandra_service.py    # 5 tests du service Chandra (subprocess mocké)
├── data/                          # Créé automatiquement au démarrage
│   ├── uploads/                   # PDFs reçus (uploads/<task_id>/fichier.pdf)
│   └── outputs/                   # Fichiers Chandra (outputs/<task_id>/<stem>.md/.html/_metadata.json)
├── tasks.db                       # Base SQLite (créée automatiquement)
├── pytest.ini
└── pyproject.toml
```

## Configuration

| Variable d'environnement | Valeur par défaut    | Usage                                              |
|--------------------------|----------------------|----------------------------------------------------|
| `HISTOOLBOX_DB_PATH`     | `./tasks.db`         | Chemin du fichier SQLite (isolation des tests)     |

Le CORS est configuré pour autoriser `http://localhost:5173` (frontend Vite en développement).

## Stockage des données

Les fichiers sont organisés par `task_id` :

```
data/uploads/<task_id>/document.pdf             ← PDF original reçu
data/outputs/<task_id>/<stem>/<stem>.md         ← Transcription Markdown
data/outputs/<task_id>/<stem>/<stem>.html       ← Transcription HTML
data/outputs/<task_id>/<stem>/<stem>_metadata.json ← Métadonnées Chandra
```

Au démarrage (`lifespan`), les tâches bloquées en état `processing` sont automatiquement basculées à `error` pour permettre un re-traitement.

## Intégration Chandra

Chandra est appelé en CLI avec la méthode vLLM :

```bash
chandra <pdf_path> <output_dir> --method vllm
```

Le service `chandra_service.py` exécute cette commande via `asyncio.to_thread(subprocess.run, ...)` pour ne pas bloquer la boucle d'événements.

Chandra crée un **sous-répertoire** `output_dir/<stem>/` pour chaque fichier traité. Les fichiers de sortie sont donc :

```
data/outputs/<task_id>/<stem>/<stem>.md
data/outputs/<task_id>/<stem>/<stem>.html
data/outputs/<task_id>/<stem>/<stem>_metadata.json
```

Les fichiers sont ensuite lus et retournés par l'endpoint `/ocr/result`.

## Tests

```bash
# Lancer tous les tests
uv run pytest -v

# Avec couverture de code
uv run pytest --cov=app --cov-report=term-missing
```

**Résultat attendu : 17/17 tests passent.**

```
tests/test_database.py             5 tests  — CRUD SQLite (create/update/get)
tests/test_ocr.py                  7 tests  — endpoints upload/status/result
tests/test_chandra_service.py      5 tests  — service Chandra (subprocess mocké)
```

Les tests utilisent une base SQLite temporaire (via `HISTOOLBOX_DB_PATH`) pour l'isolation complète.

> **Prérequis :** `chandra_vllm` doit être lancé en local (port 8000) pour que le traitement OCR fonctionne.
> Les tests ne nécessitent pas de vLLM — le subprocess est mocké.
