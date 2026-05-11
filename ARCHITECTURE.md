# Architecture générale — Histoolbox

Histoolbox est un monorepo composé de deux applications indépendantes qui communiquent via une API HTTP.

```
histoolbox/
├── frontend/   — React 19 + TypeScript + Tailwind 4 (Vite)
└── backend/    — Python 3.11 + FastAPI + SQLite
```

---

## Vue d'ensemble du système

```mermaid
graph TD
    subgraph Browser["Navigateur (Client-Side First)"]
        UI["Interface React\n(Vite SPA)"]
        IDB["IndexedDB\n(Dexie.js)\nPDF blob + transcription\n+ statut"]
    end

    subgraph Backend["Serveur backend\n(FastAPI :8001)"]
        API["Router OCR\n/ocr/upload\n/ocr/status/:id\n/ocr/result/:id"]
        BG["BackgroundTask\n_process_task()"]
        DB["SQLite\ntasks.db"]
        FS["Système de fichiers\ndata/uploads/\ndata/outputs/"]
        CL["Boucle de nettoyage\n(asyncio, toutes les 10 min)"]
    end

    subgraph VLLM["Moteur d'inférence\n(chandra_vllm :8000)"]
        VL["vLLM\n(modèle Chandra)"]
    end

    UI -->|"POST /ocr/upload\n(multipart PDF)"| API
    API -->|"202 + task_id"| UI
    UI -->|"GET /ocr/status/:id\n(polling 5s)"| API
    API -->|"status + updated_at"| UI
    UI -->|"GET /ocr/result/:id"| API
    API -->|"markdown + blocs + métadonnées"| UI

    API --> BG
    BG --> DB
    BG --> FS
    BG -->|"HTTP inférence"| VL
    VL -->|"résultats par page"| BG

    API --> DB
    CL --> DB
    CL -->|"shutil.rmtree"| FS

    UI <-->|"Blob PDF\ntranscription\nstatut"| IDB
```

---

## Frontend

### Principe fondateur : Client-Side First

Les fichiers PDF ne quittent pas le navigateur après upload. Ils sont stockés dans **IndexedDB** (Dexie.js) dès la sélection. Le backend ne reçoit le PDF que le temps du traitement ; les résultats (markdown, blocs) sont rapatriés et persistés localement.

### Système de tools (plug-in/plug-out)

Toute la navigation, les cartes d'accueil et les routes sont générées depuis un **registre central** (`src/tools/registry.ts`). Ajouter un outil = créer un fichier + ajouter une ligne dans le registre.

```mermaid
graph TD
    REG["registry.ts\ntools[]"]
    APP["App.tsx\n(générique)"]
    SHELL["AppShell.tsx\n(générique)"]
    HOME["HomePage.tsx\n(générique)"]

    REG -->|"routes[]"| APP
    REG -->|"Recovery?"| APP
    REG -->|"tools.filter(available)"| SHELL
    REG -->|"tools[]"| HOME
```

### Flux OCR — cycle de vie complet

```mermaid
sequenceDiagram
    actor User
    participant DropZone
    participant IndexedDB
    participant Polling as usePolling
    participant Backend

    User->>DropZone: Dépose un PDF
    DropZone->>IndexedDB: Sauvegarde blob PDF (status: pending)
    DropZone->>Backend: POST /ocr/upload
    Backend-->>DropZone: { task_id }
    DropZone->>IndexedDB: Met à jour id + status: processing

    loop Toutes les 5 secondes
        Polling->>Backend: GET /ocr/status/:id
        Backend-->>Polling: { status }
    end

    Backend-->>Polling: status: completed
    Polling->>Backend: GET /ocr/result/:id
    Backend-->>Polling: { markdown, blocks, pages… }
    Polling->>IndexedDB: Sauvegarde markdown + blocs (status: completed)
    Polling->>User: Navigue vers /ocr/toolbox/:id

    Note over User: Édition dans SplitView
    User->>IndexedDB: Auto-save (debounce 1s)
```

### Recovery au redémarrage

Si l'utilisateur ferme le navigateur pendant un traitement, `OCRRecovery` (composant null-render monté au démarrage) vérifie l'IndexedDB et reprend le polling automatiquement.

### Structure des fichiers frontend

```
src/
├── tools/               ← POINT D'ENTRÉE pour ajouter un tool
│   ├── registry.ts      ← interface ToolDefinition + tableau tools[]
│   └── ocr.tsx          ← tool OCR (routes + OCRRecovery)
│
├── pages/
│   ├── HomePage.tsx         ← grille de cartes (générique)
│   ├── OCRUploadPage.tsx    ← drag & drop + upload
│   ├── OCRWaitingPage.tsx   ← écran d'attente + polling
│   ├── OCRToolboxPage.tsx   ← éditeur split-view
│   └── OCRHistoryPage.tsx   ← historique des traitements OCR
│
├── components/
│   ├── AppShell.tsx         ← header + nav (générique)
│   ├── SplitView.tsx        ← panneau divisé draggable
│   ├── PDFPanel.tsx         ← viewer PDF (@react-pdf-viewer)
│   ├── MarkdownEditor.tsx   ← CodeMirror 6 (source / aperçu / blocs)
│   ├── HistoryPage.tsx      ← liste historique générique
│   ├── BlockOverlay.tsx     ← overlay de blocs sur le PDF
│   └── DropZone.tsx         ← drag & drop fichier
│
├── hooks/
│   ├── usePolling.ts        ← polling /ocr/status toutes les 5s
│   └── useAutoSave.ts       ← debounce 1s → IndexedDB
│
├── lib/
│   ├── apiClient.ts         ← fetch wrapper + types partagés
│   ├── blockUtils.ts        ← navigation par blocs
│   └── exportUtils.ts       ← export .md et .docx
│
└── db/
    └── index.ts             ← Dexie.js + OCRProject + CRUD helpers
```

---

## Backend

### Principe fondateur : zéro cold-start

`InferenceManager` (Chandra) est instancié **une seule fois** au chargement du module. L'inférence est lancée via `asyncio.to_thread` pour ne pas bloquer la boucle d'événements FastAPI.

### Flux de traitement

```mermaid
sequenceDiagram
    participant Client
    participant Router as Router OCR
    participant BG as BackgroundTask
    participant DB as SQLite
    participant FS as Fichiers
    participant Chandra

    Client->>Router: POST /ocr/upload (PDF)
    Router->>FS: data/uploads/<id>/fichier.pdf
    Router->>DB: INSERT task (status: pending)
    Router-->>Client: 202 { task_id }
    Router->>BG: _process_task() en arrière-plan

    BG->>DB: UPDATE status: processing
    BG->>Chandra: load_file() + generate() via vLLM HTTP
    Chandra-->>BG: résultats par page
    BG->>FS: data/outputs/<id>/<stem>/{.md, _blocks.json, _metadata.json}
    BG->>DB: UPDATE status: completed
    BG->>FS: shutil.rmtree(data/uploads/<id>/)  ← suppression immédiate

    Client->>Router: GET /ocr/status/:id
    Router->>DB: touch_task()  ← renouvelle le TTL
    Router-->>Client: { status: completed }

    Client->>Router: GET /ocr/result/:id
    Router->>DB: touch_task()
    Router->>FS: lit .md + _blocks.json + _metadata.json
    Router-->>Client: { markdown, blocks, pages… }
```

### Nettoyage automatique (TTL)

```mermaid
graph LR
    LOOP["_cleanup_loop()\ntoutes les 10 min"]
    EXP["get_expired_tasks()\nupdated_at < now - TTL"]
    DEL["shutil.rmtree(output_dir)\n+ delete_task()"]

    LOOP --> EXP --> DEL

    TOUCH["touch_task()\nGET /status ou /result"]
    TOUCH -->|"updated_at = now\nrenouvelle le TTL"| DB["SQLite"]
```

- `CLEANUP_TTL_SECONDS` (défaut : `3600`) — inactivité avant suppression
- `CLEANUP_INTERVAL_SECONDS` (défaut : `600`) — fréquence de la boucle
- Toute lecture (`/status`, `/result`) renouvelle le TTL → une tâche activement consultée n'est jamais supprimée

### Structure des fichiers backend

```
backend/
└── app/
    ├── main.py                    ← FastAPI + lifespan + boucle de nettoyage
    ├── database.py                ← SQLite raw (sqlite3 stdlib), zéro ORM
    ├── routers/
    │   └── ocr.py                 ← endpoints POST/GET + _process_task
    ├── services/
    │   └── chandra_service.py     ← InferenceManager singleton + run_chandra()
    └── models/
        └── schemas.py             ← Pydantic : UploadResponse, StatusResponse, ResultResponse…
```

### Schéma de la base de données

```mermaid
erDiagram
    TASKS {
        TEXT id PK
        TEXT status "pending | processing | completed | error"
        TEXT pdf_path
        TEXT output_dir
        INTEGER created_at
        INTEGER updated_at "refreshed by touch_task()"
        TEXT error_message "nullable"
    }
```

---

## Communication frontend ↔ backend

| Endpoint | Sens | Description |
|---|---|---|
| `POST /ocr/upload` | → | Envoie le PDF, reçoit un `task_id` (202) |
| `GET /ocr/status/:id` | → | Interroge le statut ; renouvelle le TTL |
| `GET /ocr/result/:id` | → | Récupère markdown + blocs (409 si pas completed) |

Toutes les URLs sont **relatives** côté frontend. Le proxy Vite (`/ocr/*` → `http://localhost:8001`) est actif en développement.

---

## Décisions techniques clés

| Décision | Raison |
|---|---|
| IndexedDB (Dexie.js) pour les PDF | Blob lourd — ne pas l'envoyer au serveur à chaque refresh |
| Polling HTTP (pas WebSocket) | Simple, compatible avec tous les proxies, suffisant pour un TTL de plusieurs heures |
| SQLite sans ORM | Zéro dépendance, schéma trivial (1 table), performances largement suffisantes |
| `asyncio.to_thread` pour Chandra | Inférence CPU/GPU bloquante — ne doit pas geler la boucle d'événements |
| `shutil.rmtree(ignore_errors=True)` | Idempotent — la suppression ne lève pas d'exception si les fichiers ont déjà disparu |
| `touch_task()` sur chaque lecture | Le client contrôle implicitement la durée de vie de ses données en continuant à poller |
