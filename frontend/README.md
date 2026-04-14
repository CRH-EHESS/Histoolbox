# Histoolbox — Frontend

Interface web de la plateforme de traitement de documents anciens. Module OCR complet avec visualiseur PDF, éditeur Markdown et persistance locale.

## Stack

| Outil | Version | Rôle |
|---|---|---|
| React | 19 | UI |
| TypeScript | 6 | Types |
| Vite | 8 | Build / dev server |
| Tailwind CSS | 4 | Styling |
| React Router | 7 | Navigation |
| Dexie.js | 4 | IndexedDB (persistance locale) |
| @react-pdf-viewer | 3.12 | Affichage PDF |
| pdfjs-dist | **3.4.120** | Worker PDF (version fixée) |
| @uiw/react-codemirror | 4 | Éditeur Markdown |
| marked | 15 | Rendu Markdown (mode aperçu) |
| dompurify | 3 | Assainissement XSS du HTML rendu |
| docx | 9 | Export .docx côté client |

| Vitest | 4 | Tests unitaires |

```bash
npm install
npm run dev   # http://localhost:5173
```

> **Prérequis :** le backend FastAPI doit tourner sur `http://localhost:8001`.  
> Vite proxie automatiquement `/ocr/upload`, `/ocr/status/*`, `/ocr/result/*` vers le backend.
> Toutes les routes inconnues sont redirigées vers `index.html` (SPA fallback).

> **Note** : toujours utiliser `pdfjs-dist@3.4.120` avec `@react-pdf-viewer@3.12`. Ne pas mettre à jour pdfjs-dist sans tester la compatibilité.

## Scripts

| Commande | Description |
|---|---|
| `npm run dev` | Serveur de développement Vite (HMR) |
| `npm run build` | Build de production (TypeScript + Vite) |
| `npm run preview` | Prévisualisation du build de production |
| `npm test` | Tests unitaires (Vitest, mode run) |
| `npm run test:watch` | Tests en mode watch |

## Structure

```
src/
├── db/
│   └── index.ts            # Dexie DB + interface OCRProject + helpers CRUD
├── hooks/
│   ├── usePolling.ts        # Polling GET /ocr/status toutes les 5s + recovery
│   └── useAutoSave.ts       # Debounce 1s → write IndexedDB
├── components/
│   ├── AppShell.tsx         # Layout : header fixe + <main> pleine largeur
│   ├── SplitView.tsx        # Panneau divisé, séparateur draggable (responsive)
│   ├── PDFPanel.tsx         # Wrapper @react-pdf-viewer (worker local, données Uint8Array)
│   ├── MarkdownEditor.tsx   # Wrapper CodeMirror 6 + toggle source/aperçu
│   └── DropZone.tsx         # Drag & drop PDF
├── pages/
│   ├── HomePage.tsx         # Grille de cartes d'outils
│   ├── OCRUploadPage.tsx    # Upload PDF → création projet IndexedDB
│   ├── OCRWaitingPage.tsx   # Spinner polling pendant traitement Chandra
│   └── OCRToolboxPage.tsx   # Split view PDF + éditeur + export
├── lib/
│   ├── apiClient.ts         # Fetch wrapper (BASE_URL configurable via VITE_API_URL)
│   └── exportUtils.ts       # Export .md et .docx (côté client)
└── test/
    ├── setup.ts             # Polyfill IndexedDB (fake-indexeddb/auto)
    ├── db.test.ts           # Tests CRUD Dexie
    ├── useAutoSave.test.ts  # Tests hook debounce
    ├── usePolling.test.tsx  # Tests hook polling + recovery
    └── exportUtils.test.ts  # Tests export .md / .docx
```

## Variables d'environnement

| Variable | Défaut | Description |
|---|---|---|
| `VITE_API_URL` | `""` (vide) | URL absolue du backend en production. En dév, le proxy Vite gère le routage. |

En production, créer un fichier `.env.local` :
```
VITE_API_URL=https://api.monsite.fr
```

## Architecture de persistance locale

Chaque projet OCR est stocké dans IndexedDB (Dexie) :

```typescript
interface OCRProject {
  id: string;           // task_id retourné par le backend
  fileName: string;
  pdfBlob: Blob;        // PDF original (pour le viewer)
  markdownContent: string;
  status: 'pending' | 'processing' | 'completed' | 'error';
  createdAt: number;
  updatedAt: number;
}
```

**Recovery automatique** : au démarrage de l'app, `RecoveryWatcher` scanne les projets en statut `processing` et relance le polling depuis l'état réel du backend.

## Tests (23 tests)

```
src/test/db.test.ts              7 tests  — CRUD Dexie (fake-indexeddb)
src/test/useAutoSave.test.ts     4 tests  — debounce save
src/test/usePolling.test.tsx     5 tests  — polling + completed/error
src/test/exportUtils.test.ts     2 tests  — export .md/.docx
src/test/MarkdownEditor.test.tsx 5 tests  — toggle source/aperçu
```
