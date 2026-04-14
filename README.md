# 📜 Histoolbox

Plateforme modulaire de traitement de documents anciens pour les historiens, inspirée de l'ergonomie de PDF24. Chaque outil est indépendant — une tuile = un outil.

## ✨ Fonctionnalités (MVP — v0.1.0)

- **OCR & Transcription diplomatique** : upload d'un PDF, traitement asynchrone par le moteur [Chandra](https://github.com/datalab-to/chandra) (vLLM), visualiseur PDF côte-à-côte avec l'éditeur Markdown
- **Persistance locale** : les fichiers PDF et les transcriptions sont stockés dans IndexedDB (Dexie.js) — resilience au rechargement et aux pannes
- **Reprise automatique** : si l'onglet est fermé pendant un traitement, le polling reprend automatiquement à la réouverture
- **Export** : téléchargement de la transcription en `.md` et `.docx`
- **Toggle source / aperçu** : bascule entre le Markdown brut et son rendu HTML

## 🏗️ Architecture

```
histoolbox/
├── backend/     # FastAPI + Python 3.11 + uv + SQLite + Chandra CLI
└── frontend/    # React 19 + TypeScript + Vite + Tailwind 4 + Dexie.js
```

## 🚀 Démarrage rapide

### Prérequis

- Python 3.11+, [`uv`](https://docs.astral.sh/uv/)
- Node.js 20+
- [`chandra-ocr`](https://github.com/datalab-to/chandra) installé dans le venv backend
- Une instance vLLM Chandra tournant sur le port 8000 (`chandra_vllm`)

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

### Chandra vLLM (dans un terminal séparé)

```bash
chandra_vllm   # lance le conteneur Docker vLLM sur le port 8000
```

## 🧪 Tests

```bash
# Backend — 17 tests
cd backend && uv run python -m pytest -v

# Frontend — 23 tests
cd frontend && npm test
```

## 🛠️ Stack technique

| Couche | Technologies |
|---|---|
| Frontend | React 19, TypeScript, Vite 8, Tailwind 4, React Router 7 |
| Persistance locale | Dexie.js (IndexedDB) |
| Viewer PDF | @react-pdf-viewer 3.12 + pdfjs-dist 3.4.120 |
| Éditeur Markdown | CodeMirror 6 + marked + DOMPurify |
| Backend | FastAPI, Python 3.11, uv, Uvicorn |
| Persistance serveur | SQLite (stdlib) |
| OCR | Chandra OCR 2 (vLLM) |
| Tests backend | pytest, httpx, pytest-asyncio |
| Tests frontend | Vitest, @testing-library/react |

## 📂 Structure détaillée

Voir les READMEs individuels : [backend/README.md](backend/README.md) · [frontend/README.md](frontend/README.md)

## 📄 Licence

À définir.
