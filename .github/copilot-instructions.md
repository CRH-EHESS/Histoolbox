
# Cahier des Charges : Histoolbox

## 1. Vision du Projet
L'objectif est de créer une plateforme modulaire de traitement de documents anciens pour les historiens, inspirée de l'ergonomie de PDF24. L'application est une "Toolbox" où chaque outil est indépendant. Le premier module critique est l'**OCR & Transcription Diplomatique** utilisant le moteur **Chandra**.

**Principes clés :**
- **Indépendance des outils :** Une tuile = Un outil.
- **Client-Side First :** Les fichiers lourds (PDF) restent dans le navigateur de l'utilisateur.
- **Résilience locale :** Utilisation intensive d'IndexedDB pour sauvegarder l'état en cas de crash ou fermeture.
- **Transcription Diplomatique :** Fidélité absolue au texte source.

---

## 2. Stack Technique Imposée
- **Frontend :** React 19, TypeScript.
- **Styling :** Tailwind CSS 4.
- **Base de données locale :** Dexie.js (IndexedDB).
- **Rendu PDF :** PDF.js (via `react-pdf-viewer`).
- **Éditeur de texte :** CodeMirror (mode Markdown).
- **Backend :** Python 3.11+, FastAPI.
- **Communication :** Polling asynchrone pour les tâches longues.

---

## 3. Architecture des Données (Local)
Chaque projet est stocké localement via Dexie.js :
```typescript
interface OCRProject {
  id: string;           // Task ID généré par le backend
  fileName: string;
  pdfBlob: Blob;        // Fichier original complet
  markdownContent: string; // Transcription éditée par l'utilisateur
  status: 'pending' | 'processing' | 'completed' | 'error';
  createdAt: number;
  updatedAt: number;
}
```

---

## 4. Spécifications Fonctionnelles (Module OCR)

### A. Landing Page & Ingestion
- Interface en grille (Cards) présentant les outils.
- Au clic sur "OCR & Transcription", ouverture d'une zone de Drag & Drop.
- Lors de l'upload :
  1. Stockage immédiat du PDF dans IndexedDB.
  2. Envoi du fichier à l'API FastAPI `/ocr/upload`.
  3. Réception d'un `task_id`.

### B. Gestion de l'Attente (Polling)
- Le traitement par Chandra pouvant durer plusieurs heures, l'interface doit afficher un écran de chargement persistant.
- Le frontend interroge `/ocr/status/{task_id}` à intervalles réguliers.
- Si l'utilisateur quitte le site et revient, le système vérifie les tâches en statut `processing` dans IndexedDB et relance le polling.

### C. La Toolbox (Interface d'édition)
Une vue en écran divisé (Split View) :
- **Panneau Gauche :** Visionneuse PDF haute performance.
  - Défilement continu (seamless).
  - Rendu haute résolution pour permettre la lecture des détails manuscrits.
- **Panneau Droit :** Éditeur Markdown (CodeMirror).
  - Chargement du contenu retourné par Chandra.
  - Édition fluide.
  - **Auto-save :** Sauvegarde dans IndexedDB à chaque modification.
- **Synchronisation :** Implémenter un "Sync-Scroll" basé sur le ratio de progression (pourcentage) dans le document.

### D. Exportation
- Boutons permettant de télécharger le texte corrigé en :
  1. `.md` (Markdown brut).
  2. `.docx` (via conversion client-side ou serveur).

Note sur PDF.js : Toujours utiliser pdfjs-dist@3.4.120 avec @react-pdf-viewer pour éviter les conflits de peer-dependencies. Utiliser --legacy-peer-deps si nécessaire lors de l'install.

---

## 5. Spécifications Backend (FastAPI)

### API Endpoints :
- `POST /ocr/upload` : 
  - Reçoit le PDF.
  - Lance le processus Chandra (asynchrone).
  - Retourne le `task_id`.
- `GET /ocr/status/{task_id}` :
  - Retourne l'état : `pending`, `processing`, `completed`.
- `GET /ocr/result/{task_id}` :
  - Retourne un objet JSON contenant : le texte Markdown, le HTML et les métadonnées.

---

## 6. Design & UI (Tailwind 4)
- **Palette :** Tons académiques/historiques (fond crème `#fdfbf7`, texte noir charbon `#262626`).
- **Composants :** - Cartes d'outils avec ombres légères et hover states clairs.
  - Header horizontal fixe pour la navigation entre les outils (remplace la sidebar).
  - Zone de contenu à 90 % de largeur centrée.
  - Barre de progression minimaliste et élégante.

---

## 7. Instructions pour le codage (Coding Assistant)
1. **Initialiser le projet** avec Vite, React (TS) et Tailwind 4.
2. **Configurer Dexie.js** pour la persistance des fichiers PDF et des textes.
3. **Créer le Layout principal** avec une Sidebar et la grille d'outils.
4. **Développer le composant de Split-View** assurant la coexistence de `pdf.js` et `CodeMirror`.
5. **Implémenter la logique de polling** robuste capable de reprendre après un rafraîchissement de page.
6. **Prioriser la performance :** ne pas bloquer le thread principal lors de la manipulation de gros Blobs PDF.

### Décisions techniques actées lors du développement MVP
- **Gestionnaire de paquets Python :** `uv` (pas pip, pas de requirements.txt)
- **Chandra API Python :** `InferenceManager(method="vllm")` instancié une fois au démarrage du module (`self.model = None`, zéro cold-start) ; `load_file` rastérise le PDF, `generate()` appelle le vLLM via HTTP ; les fichiers `.md`/`.html`/`_metadata.json` sont écrits dans `<output_dir>/<stem>/` par `_assemble_and_persist`
- **Chandra vLLM :** `chandra_vllm` à lancer séparément en local (port 8000 par défaut) ; `VLLM_BASE_URL` (défaut `http://localhost:8000`) contrôle l'URL utilisée par le pre-flight et l'inférence
- **Logging backend :** `loguru` — niveau contrôlé par `LOG_LEVEL` (défaut `INFO`) ; en `DEBUG`, chaque étape est tracée : pre-flight, chargement PDF, durée inférence par page
- **Persistance backend :** SQLite sans ORM (module `sqlite3` stdlib) — fichier `tasks.db`
- **Export .docx :** client-side via `docx` (npm)
- **Navigation :** React Router v7
- **Structure :** deux dossiers dans le monorepo — `frontend/` et `backend/`
- **Port backend :** 8001 (pour ne pas entrer en conflit avec le vLLM sur 8000)
- **Proxy Vite :** `/ocr/(upload|status|result)` proxifié vers `http://localhost:8001` ; `historyApiFallback: true` pour les routes SPA
- **URLs API :** relatives (BASE_URL vide par défaut) — `VITE_API_URL` pour la production
- **Rendu Markdown :** `marked` + `DOMPurify` pour le mode aperçu (sécurisation XSS)
- **Worker PDF.js :** référencé localement via `new URL("pdfjs-dist/build/pdf.worker.min.js", import.meta.url)` pour éviter les restrictions cross-origin
- **Layout :** header horizontal fixe (pas de sidebar) ; zone de contenu 90 % de largeur, centrée

### Structure du projet implémentée
```
histoolbox/
├── frontend/                    # Vite + React 19 + TS + Tailwind 4
│   └── src/
│       ├── db/index.ts          # Dexie DB + interface OCRProject + CRUD helpers
│       ├── hooks/
│       │   ├── usePolling.ts    # Polling toutes les 5s + recovery
│       │   └── useAutoSave.ts   # Debounce 1s → IndexedDB
│       ├── components/
        │   ├── AppShell.tsx     # Layout : header fixe + <main> 90 % largeur
        │   ├── SplitView.tsx    # Panneau divisé draggable (responsive)
        │   ├── PDFPanel.tsx     # @react-pdf-viewer (worker local, Uint8Array)
        │   ├── MarkdownEditor.tsx # CodeMirror 6 + toggle source/aperçu
│       │   └── DropZone.tsx     # Drag & drop PDF
│       ├── pages/
│       │   ├── HomePage.tsx     # Grille de cartes outils
│       │   ├── OCRUploadPage.tsx
│       │   ├── OCRWaitingPage.tsx
│       │   └── OCRToolboxPage.tsx
│       └── lib/
│           ├── apiClient.ts     # Fetch wrapper centralisé
│           └── exportUtils.ts   # Export .md et .docx
└── backend/                     # FastAPI + Python 3.11 + uv
    └── app/
        ├── main.py              # App FastAPI + CORS + lifespan
        ├── database.py          # SQLite raw (sqlite3 stdlib)
        ├── routers/ocr.py       # POST /ocr/upload, GET /ocr/status, GET /ocr/result
        ├── services/chandra_service.py  # asyncio.to_thread subprocess
        └── models/schemas.py    # Pydantic schemas
```


---

## 8. Règles de Conception
- **Modularité :** Chaque composant doit être autonome et réutilisable.
- **Keep It Simple :** Favoriser la simplicité et la clarté du code. Le plus simple est souvent le meilleur !
- **Documentation :** Commenter les fonctions complexes et fournir des JSDoc pour les interfaces
- **Don't Repeat Yourself (DRY) :** Éviter la duplication de code, créer des fonctions utilitaires si nécessaire.
- **Don't Over-engineer :** Ne pas anticiper des fonctionnalités futures non définies dans ce cahier des charges.
- **Testing :** Écrire des tests unitaires pour les fonctions critiques (ex. gestion de l'état, logique de polling).
- **Performance :** Optimiser le rendu PDF et l'édition Markdown pour les documents volumineux.

---

## 9. Convention de commits (Gitmoji + type)

Format : `<gitmoji> <type>: <description courte>`

| Gitmoji | Type | Usage |
|---------|------|-------|
| ✨ | `feat` | Nouvelle fonctionnalité |
| 🐛 | `fix` | Correction de bug |
| ♻️ | `refactor` | Refactoring sans changement de comportement |
| ✅ | `test` | Ajout ou modification de tests |
| 📝 | `docs` | Documentation (README, copilot-instructions, commentaires) |
| 🔧 | `chore` | Configuration, dépendances, outillage |

Exemples :
- `✨ feat: ajout de l'export .docx côté client`
- `🐛 fix: correction du chemin de sortie Chandra (sous-répertoire)`
- `📝 docs: mise à jour du README backend (port 8001)`
