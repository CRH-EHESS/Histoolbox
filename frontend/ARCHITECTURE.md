# Architecture frontend — Guide développeur

Ce document explique comment le frontend est structuré et comment ajouter un nouveau tool à la Histoolbox.

---

## Vue d'ensemble

```
┌─────────────────────────────────────────────────────────┐
│                      BrowserRouter                      │
│                                                         │
│   ┌─────────────────┐   ┌──────────────────────────┐   │
│   │  Recovery nodes │   │         AppShell         │   │
│   │  (null-renders) │   │  ┌────────────────────┐  │   │
│   │                 │   │  │  Header / Nav      │  │   │
│   │  <OCRRecovery>  │   │  │  (depuis registry) │  │   │
│   │  <XxxRecovery>  │   │  ├────────────────────┤  │   │
│   │  …              │   │  │  <Routes>          │  │   │
│   └─────────────────┘   │  │  (depuis registry) │  │   │
│                         │  └────────────────────┘  │   │
│                         └──────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

`App.tsx` est **entièrement générique** : il boucle sur le registre des tools pour monter les routes et les composants de recovery. Il n'a connaissance d'aucun tool en particulier.

---

## Le registre des tools

**Fichier :** `src/tools/registry.ts`

C'est la **seule source de vérité** pour la liste des tools. Toute l'UI de navigation et d'accueil en dérive automatiquement.

```typescript
interface ToolDefinition {
  id: string;            // Clé React unique
  icon: string;          // Emoji ou URL d'icône
  label: string;         // Affiché dans la nav et sur la carte
  description: string;   // Affiché sur la carte d'accueil
  entryPath: string;     // Route principale (carte + lien nav)
  routes: RouteObject[]; // Toutes les routes React Router du tool
  available: boolean;    // false → carte grisée "Bientôt disponible"
  Recovery?: ComponentType; // Null-render de démarrage (optionnel)
}
```

### Flux de données depuis le registre

```
tools[] (registry.ts)
    │
    ├──▶ App.tsx
    │       ├── monte <Recovery /> pour chaque tool qui en a un
    │       └── génère les <Route> depuis tool.routes
    │
    ├──▶ AppShell.tsx
    │       └── génère les <NavLink> pour les tools available
    │
    └──▶ HomePage.tsx
            ├── carte cliquable  (available: true)
            └── carte grisée     (available: false)
```

---

## Anatomie d'un tool

Chaque tool vit dans un seul fichier `src/tools/<nom>.tsx`.

```
src/tools/ocr.tsx
│
├── export const ocrTool: ToolDefinition  ← déclaration du tool
│       ├── métadonnées (id, icon, label, description, entryPath)
│       ├── routes: [ upload, waiting, toolbox ]
│       ├── available: true
│       └── Recovery: OCRRecovery        ← logique de démarrage
│
└── function OCRRecovery()               ← null-render (return null)
        └── useEffect au montage : vérifie les tâches IndexedDB
            en statut "processing" et reprend le polling
```

Les **pages** du tool (`OCRUploadPage`, etc.) restent dans `src/pages/` et sont simplement référencées dans `routes`. Le fichier du tool ne fait que les assembler.

---

## Ajouter un nouveau tool — Procédure

### Étape 1 — Créer les pages du tool

```
src/pages/
  MonToolPage.tsx        ← page principale
  MonToolWaitingPage.tsx ← si traitement asynchrone (optionnel)
```

Ces pages sont des composants React normaux, sans connaissance du registre.

### Étape 2 — Créer le fichier tool

```typescript
// src/tools/mon-tool.tsx

import { MonToolPage } from "../pages/MonToolPage";
import type { ToolDefinition } from "./registry";

export const monTool: ToolDefinition = {
  id: "mon-tool",
  icon: "🗂️",
  label: "Mon Tool",
  description: "Ce que fait mon tool.",
  entryPath: "/mon-tool",
  available: true,
  routes: [
    { path: "/mon-tool", element: <MonToolPage /> },
    // autres routes si besoin
  ],
  // Recovery: MonToolRecovery,  ← uniquement si logique de démarrage nécessaire
};
```

### Étape 3 — Déclarer dans le registre

```typescript
// src/tools/registry.ts  — modifier uniquement ces deux lignes

import { monTool } from "./mon-tool";   // ← ajouter l'import

export const tools: ToolDefinition[] = [
  ocrTool,
  monTool,   // ← ajouter ici
];
```

**C'est tout.** La carte d'accueil, le lien de navigation et les routes sont automatiquement générés.

---

## Désactiver / masquer un tool

Passer `available: false` dans la définition. Le tool reste dans le code (routes toujours montées) mais n'apparaît plus dans la nav ni sur la carte d'accueil.

```typescript
export const monTool: ToolDefinition = {
  // ...
  available: false,  // ← carte grisée "Bientôt disponible"
};
```

Pour le **retirer complètement** : supprimer la ligne dans `registry.ts` et le fichier `src/tools/mon-tool.tsx`.

---

## Le composant Recovery (pattern null-render)

Le `Recovery` permet à un tool de déclarer une logique d'initialisation sans coupler le shell applicatif à la logique métier.

```
BrowserRouter
    └── <OCRRecovery />   ← monté une fois, return null, aucun rendu
            └── useEffect  → vérifie IndexedDB au démarrage
                           → reprend le polling si tâches en cours
                           → navigue vers toolbox si déjà terminé
```

Ce pattern est utile pour tout ce qui doit s'exécuter **au démarrage de l'app**, indépendamment de la route active : recovery de session, migration de données locales, pré-chargement, etc.

Un tool sans logique de démarrage n'a simplement pas à déclarer le champ `Recovery`.

---

## Structure complète des fichiers

```
src/
├── App.tsx                  ← générique, ne pas modifier pour un nouveau tool
├── main.tsx
│
├── tools/                   ← POINT D'ENTRÉE des tools
│   ├── registry.ts          ← interface ToolDefinition + tableau tools[]
│   └── ocr.tsx              ← tool OCR (routes + OCRRecovery)
│
├── pages/                   ← pages de chaque tool
│   ├── HomePage.tsx         ← générique (lit registry)
│   ├── OCRUploadPage.tsx
│   ├── OCRWaitingPage.tsx
│   └── OCRToolboxPage.tsx
│
├── components/              ← composants réutilisables (non spécifiques à un tool)
│   ├── AppShell.tsx         ← générique (lit registry pour la nav)
│   ├── SplitView.tsx        ← panneau divisé draggable
│   ├── PDFPanel.tsx         ← viewer PDF (@react-pdf-viewer)
│   ├── MarkdownEditor.tsx   ← éditeur CodeMirror 6
│   ├── BlockOverlay.tsx     ← overlay de blocs sur le PDF
│   └── DropZone.tsx         ← drag & drop fichier
│
├── hooks/
│   ├── usePolling.ts        ← polling /ocr/status toutes les 5s
│   └── useAutoSave.ts       ← debounce 1s → IndexedDB
│
├── lib/
│   ├── apiClient.ts         ← fetch wrapper + types partagés (TaskStatus, BlockItem…)
│   ├── blockUtils.ts        ← navigation par blocs (offsets, filtrage par page)
│   └── exportUtils.ts       ← export .md et .docx
│
└── db/
    └── index.ts             ← Dexie.js + OCRProject + CRUD helpers
```

---

## Conventions

- Les **types partagés entre tools** (`TaskStatus`, `BlockItem`, `PageInfo`) vivent dans `lib/apiClient.ts`.
- Les **composants réutilisables** entre tools vont dans `src/components/`.
- Les **hooks réutilisables** entre tools vont dans `src/hooks/`.
- **Pas de state global** (pas de Context, pas de Zustand) : chaque tool gère son propre état local + IndexedDB.
- **Un tool = un fichier** dans `src/tools/`. Si un tool devient très complexe, un sous-dossier `src/tools/mon-tool/index.tsx` est acceptable.
