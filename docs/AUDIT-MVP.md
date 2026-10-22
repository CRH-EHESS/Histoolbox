# Audit Histoolbox — du PoC au MVP

_Version 2 — 2026-10-22 · Code audité : `82e272b` (main) · Voir [Révisions](#révisions) en fin de document_

## Contexte

Histoolbox est un client léger pour historiens. On dépose un PDF, souvent volumineux ; un worker l'envoie à un VLM **Chandra** servi par vLLM sur une machine de calcul distante ; on relit et corrige ensuite la transcription dans une vue côte à côte PDF / Markdown. Le projet est un PoC : 27 commits, environ 1 000 lignes de Python et 1 600 lignes de TS/TSX. L'objectif est d'en faire un **MVP** fiable pour de vrais utilisateurs.

**Méthode.** J'ai lu l'intégralité du backend (`backend/app/**`, Dockerfile, Compose, Caddy), du frontend (`frontend/src/**`, configuration Vite, workflow GitHub Pages) et des tests. J'ai aussi lu le **code des bibliothèques dont dépendent les mécanismes critiques** : `rq` 2.9 (`timeouts.py`, `worker/worker_classes.py`, `worker/base.py`), `tenacity`, `concurrent.futures`, `starlette/formparsers.py`, `python_multipart`, `uvicorn/config.py`, `chandra-ocr` 0.2.0 (`input.py`, `model/vllm.py`, `model/__init__.py`, `settings.py`) et `@react-pdf-viewer/core`. Enfin, j'ai lancé `npm audit --omit=dev` et `npm ls`.

Sévérité : 🔴 critique (bloque le MVP) · 🟠 majeur · 🟡 mineur

---

## 1. État des lieux

### 1.1 Architecture actuelle

```
GitHub Pages (SPA React)  ──HTTPS + X-API-Key──▶  Caddy ─▶ FastAPI (:8001) ──enqueue──▶ Redis ──▶ RQ worker (×1)
       │ IndexedDB (PDF + transcription)                │ SQLite tasks.db                         │ load_file → N images PIL
       │                                                │ data/uploads, data/outputs               │ ThreadPool(≤64) → vLLM /v1 (VPN)
       └─ polling /ocr/status toutes les 5 s           └─ boucle de nettoyage TTL (1 h)           └─ SMTP (optionnel)
```

### 1.2 Points forts (à conserver)

- **Séparation API / worker** via RQ : l'inférence ne bloque pas FastAPI, et `job_id=task_id` déduplique naturellement les jobs.
- **« Client-Side First »**, une approche pertinente pour des archives : le PDF reste dans IndexedDB, et le serveur supprime le PDF brut juste après le traitement (`worker.py`, bloc `finally`).
- **Registre d'outils** (`frontend/src/tools/registry.ts`) : un point d'extension propre pour la future « toolbox ».
- **Blocs de layout avec bbox normalisées** (`_assemble_and_persist`) et survol / clic croisé entre le PDF et le Markdown. C'est la fonctionnalité la plus différenciante.
- Une documentation sérieuse (`ARCHITECTURE.md` et sa matrice de scénarios), des logs loguru, des retries tenacity, un rendu Markdown passé dans DOMPurify, 44 tests backend et 40 tests frontend. Les README annoncent encore 17 et 23 tests.

### 1.3 Diagnostic général

L'architecture convient à un MVP. Les fragilités se concentrent **dans les cas limites et aux jonctions entre composants** : déploiement Docker, cycle de vie des tâches, gros PDF, reprise côté client, dépendance au vLLM distant. Plusieurs défauts **cassent la production** ou **perdent le travail de l'utilisateur sans le dire**. Et le cas d'usage visé, des PDF volumineux traités pendant des heures, est précisément celui qui les déclenche.

> **Le scénario le plus parlant.** Un historien qui **ferme l'onglet** pendant un long traitement, ou qui **lance 2 fichiers ou plus**, perd en pratique ses résultats. Personne n'interroge alors le statut : la reprise automatique ne se déclenche jamais (F6) et l'historique ne fait pas de polling (N3). Le nettoyage TTL efface donc la tâche au bout d'1 h, même en attente ou en cours (F2). L'utilisateur peut quand même recevoir un email « terminé », qui pointe vers une tâche supprimée.

---

## 2. Constats détaillés

### 2.1 Fiabilité et cycle de vie des tâches

| # | Sév. | Constat | Preuve |
|---|---|---|---|
| F1 | 🔴 | **Sous Docker Compose, l'API et le worker n'utilisent pas la même base SQLite.** `DB_PATH` vaut par défaut `/app/tasks.db`, hors du volume `./data:/app/data`. Chaque conteneur a donc son propre `tasks.db` éphémère. Les UPDATE du worker visent une ligne qui n'existe pas chez lui (aucun effet, aucune erreur) et l'API voit la tâche `pending` pour toujours. La base est aussi perdue à chaque recréation de conteneur. | `app/database.py:27-28`, `docker-compose.yml` (volumes), `.env.example` (pas de `HISTOOLBOX_DB_PATH`) |
| F2 | 🔴 | **Le nettoyage TTL supprime des tâches en attente ou en cours.** `get_expired_tasks` ne filtre pas sur le statut. `updated_at` n'avance qu'avec le polling ou les 4 étapes de progression, et l'étape 3 (inférence) peut durer des heures. Sans polling (voir F6, N3), la tâche et ses fichiers sont effacés au bout d'1 h. Ensuite, soit le worker échoue (PDF disparu), soit il recrée le dossier de sortie, met à jour une ligne qui n'existe plus et **envoie l'email « terminé » vers un lien mort**. Un résultat terminé expire lui aussi 1 h après la fin si personne ne le récupère. | `main.py:_cleanup_expired_tasks`, `database.py:get_expired_tasks`, `worker.py` |
| N3 | 🔴 | **Le multi-upload aggrave F2.** À partir de 2 fichiers, l'utilisateur est redirigé vers `/ocr/history`, **qui ne fait aucun polling**. Avec un seul worker, chaque fichier qui attend son tour plus d'1 h est supprimé avant même d'être traité. | `OCRUploadPage.tsx` (navigation après envoi), `OCRHistoryPage.tsx` (lecture IndexedDB seule) |
| F3 | 🔴 | **Une tâche reste bloquée en `processing` pour toujours dès que le horse RQ est tué** (timeout, OOM, SIGKILL). Le cas du timeout se déroule ainsi : RQ lève `JobTimeoutException`, une sous-classe d'`Exception`, dans le horse via SIGALRM. **Tenacity l'intercepte** (`except BaseException`, et sa règle de retry ne l'exclut pas), puis **relance l'inférence**. Le processus parent RQ tue alors le horse à `timeout + 60 s`. Le `except` de `process_ocr_job` ne s'exécute jamais, et RQ **n'appelle pas** les callbacks `on_failure` dans ce cas : il ne passe que par `handle_work_horse_killed`. | `worker.py`, `chandra_service.py:@retry`, rq `worker/worker_classes.py:95`, `worker/base.py:1314` |
| F4 | 🔴 | **Les jobs ré-enfilés n'ont pas de `job_timeout`.** Ils prennent donc le défaut RQ (`Queue.DEFAULT_TIMEOUT = 180`) : toute tâche récupérée après un redémarrage est tuée au bout d'environ 4 min, puis tombe dans F3. | `worker.py:requeue_pending_tasks` (à comparer avec `_RQ_JOB_TIMEOUT` dans `routers/ocr.py`) |
| F5 | 🟠 | **Un redémarrage de l'API casse les traitements en cours.** `init_db()`, appelé au démarrage de l'API, passe toutes les tâches `processing` en `error`, alors que le worker, qui est un autre processus, continue de travailler. L'utilisateur voit une erreur et son polling s'arrête, puis la tâche repasse `completed` côté serveur. **En développement, c'est systématique** : `start.sh` lance `uvicorn --reload`, donc chaque sauvegarde de fichier déclenche le problème. | `database.py:init_db`, `main.py:lifespan`, `start.sh` |
| F6 | 🟠 | **La reprise côté client ne fonctionne pas.** `OCRRecovery` cherche les projets en statut `processing` dans IndexedDB, mais le frontend n'écrit jamais ce statut : il passe directement de `pending` à `completed` ou `error`. La « reprise automatique » annoncée ne se déclenche donc jamais. Et quand elle tourne, elle n'enregistre ni `blocks` ni `pages`. | `tools/ocr.tsx:34`, `OCRUploadPage.tsx`, `hooks/usePolling.ts` |
| F7 | 🟠 | **Une coupure réseau de 15 s suffit à passer un projet en erreur.** Trois échecs de polling consécutifs marquent le projet `error` dans IndexedDB, même si le serveur continue de traiter : un redémarrage du backend ou un Wi-Fi instable suffit. Un 404 (tâche nettoyée) est traité comme une erreur réseau. La page d'erreur ne propose pas de « Réessayer » ; il faut repasser par l'historique (« Ouvrir » relance le polling). | `hooks/usePolling.ts` (bloc `catch`), `OCRWaitingPage.tsx` |
| N4 | 🟠 | **La page d'attente peut rester bloquée indéfiniment.** Quand le statut passe à `completed`, `stop()` est appelé **avant** `getResult`. Si `getResult` échoue une seule fois, ou si `new Notification()` lève une exception (constructeur interdit sur Chrome Android), le `catch` incrémente le compteur (1 < 3) et plus rien ne relance le polling : le spinner « Transcription en cours » tourne pour toujours. Accessoirement, l'icône `/favicon.ico` n'existe pas et ignore le base path. | `hooks/usePolling.ts` |
| F8 | 🟠 | **L'upload n'est pas atomique.** Le PDF est écrit et la ligne SQLite créée avant de vérifier la disponibilité de Redis. En cas de 503, ou si `enqueue` lève une exception, il reste des fichiers et une tâche `pending` orphelins. Le worker les ré-enfile ensuite à son démarrage, et le GPU les traite sans que personne ne les attende. Côté client, la double écriture (id temporaire, puis id définitif) n'est pas atomique non plus. | `routers/ocr.py:upload_pdf`, `OCRUploadPage.tsx:handleSubmit` |
| F9 | 🟡 | `queue_position` est calculée depuis SQLite (`created_at`) et non depuis RQ. Elle devient incohérente après un requeue ou en présence de tâches fantômes (F1, F8). | `database.py:get_queue_position` |
| F10 | 🟡 | **Code mort et commentaires trompeurs.** `run_chandra` (async, avec `asyncio.Lock`) n'est jamais appelé. Le commentaire « vLLM traite en série » est faux : vLLM fait du batching continu et Chandra ouvre jusqu'à 64 requêtes concurrentes. `CHANDRA_INFERENCE_TIMEOUT` ne sert en pratique qu'à calculer `_RQ_JOB_TIMEOUT`, lequel est contourné par tenacity (F3). | `services/chandra_service.py`, `routers/ocr.py` |

### 2.2 Traitement des PDF volumineux et dépendance au vLLM distant

| # | Sév. | Constat | Preuve |
|---|---|---|---|
| N2 | 🔴 | **Une coupure du vLLM vide toute la file en erreurs.** `ChandraVllmUnavailableError` est volontairement exclue des retries : pendant la coupure, chaque job en attente échoue en quelques secondes et envoie un email d'erreur. Sur une infra de calcul distante (coupure VPN, redémarrage d'un nœud GPU, fin d'allocation HPC), 10 minutes d'indisponibilité suffisent à annuler les travaux de tous les utilisateurs. | `chandra_service.py:_check_vllm_available` et `@retry`, `worker.py` (bloc `except`) |
| V1 | 🔴 | **Toutes les pages sont rastérisées en mémoire avant l'inférence.** `load_file` rend chaque page à 192 DPI minimum (`settings.IMAGE_DPI`). Une page A4 occupe environ 10 Mo en RGB, soit **environ 5 Go de RAM pour 500 pages**, auxquels s'ajoutent les encodages PNG/base64 en cours d'envoi. Sur un VPS modeste, le worker est tué par l'OOM killer, ce qui renvoie à F3. | `chandra/input.py:load_pdf_images`, `chandra_service.py:_chandra_with_retry` |
| V2 | 🔴 | **Tout ou rien.** Une seule page en erreur fait échouer tout le document (`RuntimeError`), et tenacity relance **le document entier**, jusqu'à 3 fois. Pour un document de 4 h, cela peut faire 12 h de GPU sans aucun résultat. Il n'existe ni checkpoint par page ni résultat partiel. Les retries s'empilent en plus : tenacity (×3), au-dessus de Chandra (6 retries par page avec hausse de température), au-dessus du SDK OpenAI (2 retries, timeout de 600 s par requête). | `chandra_service.py` (`page_errors`, `@retry`), `chandra/model/vllm.py`, `chandra/settings.py:MAX_VLLM_RETRIES` |
| V3 | 🟠 | **Aucune progression visible pendant l'inférence.** La progression se résume à 4 étapes fixes, et l'étape 3 reste figée pendant des heures, sans « page x/N » ni estimation de durée. Pour un historien, l'outil semble planté. | `chandra_service.py:_progress`, `OCRWaitingPage.tsx` |
| V4 | 🟠 | **Pas d'annulation.** On ne peut ni annuler une tâche ni la retirer de la file. La suppression dans l'historique n'efface que la copie locale : le GPU continue de travailler. | `routers/ocr.py`, `OCRHistoryPage.tsx:handleDelete` |
| V5 | 🟠 | **Un seul worker et une file FIFO globale** : le document de 800 pages d'un utilisateur bloque tous les autres pendant des heures. Il n'y a ni quota, ni équité entre utilisateurs, ni limite de pages. Ajouter des workers n'augmente pas le débit, borné par le GPU (un job de plus de 64 pages le sature déjà), et multiplie la RAM consommée (V1). | `docker-compose.yml`, `run_worker.py`, `chandra/model/vllm.py:max_workers` |
| V6 | 🟡 | **Upload sans plafond de taille.** `upload_pdf` charge le fichier entier en mémoire (`await file.read()`), et aucune taille maximale n'est fixée, ni dans Caddy, ni dans l'API. | `routers/ocr.py` |

### 2.3 Sécurité

| # | Sév. | Constat | Preuve |
|---|---|---|---|
| S1 | 🔴 | **Path traversal à l'upload, avec écriture et suppression arbitraires, jusqu'à la RCE.** Le chemin est construit comme `UPLOAD_ROOT / task_id / file.filename`, sans aucun assainissement : python-multipart ne retire que les chemins Windows d'IE6 et Starlette ne nettoie rien. Avec un nom absolu, pathlib ignore la racine (`Path("a") / "/x"` donne `/x`). **Écriture** : n'importe quel fichier, en root dans le conteneur, sans contrainte d'extension. Un `.pth` déposé dans `/app/.venv/…/site-packages/` est exécuté au prochain démarrage de Python, ce qui donne une RCE. **Suppression** : le `finally` du worker et la boucle de nettoyage font `rmtree(Path(pdf_path).parent)`. Avec `filename="../x.pdf"`, c'est **tout `data/uploads/`, donc les PDF en file de tous les utilisateurs**, qui est supprimé ; avec un chemin absolu, n'importe quel répertoire. | `routers/ocr.py:pdf_path`, `worker.py` (`finally`), `main.py:_cleanup_expired_tasks`, `python_multipart/multipart.py:180` |
| S2 | 🔴 | **pdf.js 3.4.120 est vulnérable à CVE-2024-4367** : un PDF piégé exécute du JavaScript arbitraire à son ouverture. `@react-pdf-viewer` ne désactive pas `isEvalSupported`. Le script s'exécute dans l'origine de l'application, où il peut lire **la clé d'API partagée** (`localStorage`) et tout IndexedDB ; combinée à S1, la faille mène jusqu'au serveur. Le correctif officiel est trivial (voir §3.0). Par ailleurs, `@react-pdf-viewer` n'est plus maintenu, ce qui bloque toute montée de version de pdf.js. | `package.json`, `PDFPanel.tsx`, `@react-pdf-viewer/core/lib/index.d.ts:568` (`transformGetDocumentParams`) |
| S3 | 🟠 | **Une seule clé d'API partagée**, stockée en `localStorage`, comparée sans `hmac.compare_digest`, sans rotation ni révocation par utilisateur. Le `task_id` devient la seule barrière entre utilisateurs. `TokenGate` ne valide jamais la clé et `clearToken` n'est appelé nulle part : avec une mauvaise clé, l'utilisateur reste bloqué. | `main.py:api_key_middleware`, `TokenGate.tsx`, `apiClient.ts` |
| S4 | 🟠 | **Le rate limiting ne marche pas derrière Caddy.** uvicorn ne fait confiance à `X-Forwarded-For` que pour `127.0.0.1` (`FORWARDED_ALLOW_IPS`), alors que Caddy tourne dans un autre conteneur. Toutes les requêtes semblent donc venir de la même IP, et la limite de 10 uploads par minute devient **globale**. Même en local, un multi-upload de 20 petits fichiers reçoit un 429 dès le 11ᵉ. | `limiter.py`, `Dockerfile` (CMD), uvicorn `config.py:340`, `UploadQueue` |
| S5 | 🟠 | **Emails et données personnelles.** Le nom de fichier est inséré sans échappement dans le template HTML. Toute personne qui a la clé peut donc faire envoyer, par le SMTP du projet, **du HTML arbitraire à n'importe quelle adresse** : un relais de phishing. L'email n'est validé que par la présence d'un `@`. Les adresses sont stockées en clair, sans durée de conservation. Côté RGPD, les documents transitent vers une infra de calcul distante, et rien n'en informe l'utilisateur. | `email_service.py:_template_*`, `routers/ocr.py` |
| S6 | 🟠 | **Validation du PDF insuffisante.** Seul le `Content-Type` déclaré par le client est vérifié, et `application/octet-stream` est aussi accepté. Il n'y a ni contrôle des octets magiques ni limite de pages. Chandra traite d'ailleurs comme une image tout fichier qui n'est pas un PDF. | `routers/ocr.py`, `chandra/input.py:load_file` |
| S7 | 🟡 | **Durcissement manquant.** `str(exc)` est renvoyé tel quel à l'utilisateur et peut exposer l'URL interne du vLLM. Le conteneur tourne en root. L'image `uv:latest` n'est pas épinglée. `allow_credentials=True` ne sert à rien ici. Le vLLM n'a pas de clé (`VLLM_API_KEY="EMPTY"`). | `worker.py`, `Dockerfile`, `main.py` |
| S8 | 🟡 | **Le reste de `npm audit` relève de l'hygiène.** Le « critique » `tar` vient d'une dépendance optionnelle de pdfjs (`canvas`, côté Node uniquement) **qui n'est même pas installée** (`npm ls --omit=dev`). Les CVE de react-router visent le mode framework/SSR (turbo-stream, `__manifest`), inutilisé dans une SPA statique. Le mode `IN_PLACE` de DOMPurify n'est pas utilisé. Il reste un DoS de `marked` sur un Markdown malicieux, à faible risque. Un `npm audit fix` suffit. | `npm audit --omit=dev`, `npm ls` |

### 2.4 Frontend et expérience utilisateur

| # | Sév. | Constat | Preuve |
|---|---|---|---|
| U1 | 🔴 | **Le lien envoyé par email est inutilisable.** Une SPA en `BrowserRouter` sur GitHub Pages n'a pas de fallback (pas de `404.html`), donc toute URL profonde renvoie une 404. De plus, `/ocr/toolbox/:id` lit IndexedDB : depuis un autre appareil, la page redirige vers l'accueil sans explication, et après le TTL d'1 h le résultat n'existe plus côté serveur. | `App.tsx`, `frontend/public/`, `email_service.py`, `OCRToolboxPage.tsx` |
| U2 | 🟠 | **Les corrections ne vivent que dans IndexedDB.** Une purge du navigateur, la navigation privée ou une éviction de stockage les efface. Il n'y a ni `navigator.storage.persist()`, ni sauvegarde serveur, ni export/import de projet. Pour plusieurs heures de relecture, ce n'est pas acceptable. | `db/index.ts` |
| U3 | 🟠 | **Le lien bloc ↔ texte casse dès la première correction.** `getBlockCharRange` calcule les positions sur le Markdown d'origine, et l'onglet « Aperçu » affiche `block.markdown`, c'est-à-dire le texte **non corrigé** : l'utilisateur ne voit pas ses corrections dans l'aperçu. | `lib/blockUtils.ts`, `MarkdownEditor.tsx` |
| U4 | 🟠 | **L'export `.docx` est naïf.** La conversion se fait ligne par ligne : tableaux, italiques, listes et notes sont perdus ou laissés en syntaxe Markdown brute. C'est pourtant un format clé pour les historiens. | `lib/exportUtils.ts` |
| U5 | 🟡 | **L'autosave perd la dernière seconde de saisie.** Le cleanup annule le timer de debounce **sans enregistrer**, et il n'y a pas de handler `pagehide` / `beforeunload` : ce qui a été tapé dans la seconde précédant un départ de page est perdu. Par ailleurs, `setInterval` peut chevaucher des appels quand le réseau est lent, et le PDF est recopié entièrement en `Uint8Array` à chaque ouverture. | `hooks/useAutoSave.ts`, `hooks/usePolling.ts`, `PDFPanel.tsx` |
| N9 | 🟡 | **L'upload de gros fichiers manque de garde-fous.** Aucune progression d'envoi n'est affichée (`fetch` n'en fournit pas). Le blob est écrit deux fois dans IndexedDB. `MAX_FILES = 20` s'applique par dépôt et se contourne en déposant plusieurs fois. L'interface renvoie vers un « client CLI » qui n'existe pas. | `OCRUploadPage.tsx`, `DropZone.tsx:4` |

### 2.5 Industrialisation, qualité, exploitation

| # | Sév. | Constat |
|---|---|---|
| I1 | 🟠 | **Pas de CI de tests ni de lint.** Le seul workflow déploie Pages (avec un type-check via `tsc -b`, mais sans tests). Il n'y a ni build ni déploiement automatisés pour le backend. |
| I2 | 🟠 | **Les tests couvrent surtout le chemin nominal.** Rien sur les crashs du worker, les timeouts RQ, le nettoyage TTL appliqué à des tâches actives, le path traversal, la reprise client, ni sur un vrai déploiement Compose. Aucun test end-to-end dans un navigateur. |
| I3 | 🟠 | **Pas d'observabilité.** `/health` ne vérifie ni Redis, ni SQLite, ni le vLLM. Il n'y a aucune métrique (durée par page, longueur de file, taux d'erreur), des logs non structurés et aucune alerte. |
| I4 | 🟡 | **Socle technique fragile.** La configuration est lue via `os.getenv` à l'import dans 5 modules, donc difficile à tester. Les migrations SQLite reposent sur des `ALTER` dans des try/except. Les I/O SQLite sont synchrones dans des handlers `async`. Chaque poll déclenche une écriture en base (`touch_task`). |
| I5 | 🟡 | **Restes de scaffold et documentation à jour.** `backend/main.py` affiche « Hello from backend », la `description` du `pyproject` est restée par défaut, les assets Vite par défaut sont là, et les README annoncent des nombres de tests faux ainsi qu'un « MVP v0.1.0 ». Il n'y a pas de licence, ce qui bloque une diffusion académique. |

### 2.6 Configuration et déploiement

| # | Sév. | Constat | Preuve |
|---|---|---|---|
| N5 | 🟠 | **L'API reste en 503 pour toujours si Redis n'est pas prêt à son démarrage.** Le `lifespan` met `rq_queue = None` et ne retente jamais. `depends_on` n'attend pas que Redis soit prêt, et comme l'API ne plante pas, `restart: unless-stopped` ne la relance pas. | `main.py:lifespan`, `docker-compose.yml` |
| N6 | 🟠 | **La configuration de production fournie ne marche pas telle quelle.** `ALLOWED_ORIGINS=https://username.github.io/histoolbox` ne correspondra jamais, car un en-tête `Origin` ne contient pas de chemin : CORS refuse toutes les requêtes. `.env.example` ne contient ni `APP_BASE_URL` (les emails pointent alors vers `localhost:5173`), ni `SMTP_*`, ni `HISTOOLBOX_DB_PATH` (F1). Un `API_KEY` vide **désactive l'authentification sans le signaler**, et la valeur d'exemple est `changeme`. | `backend/.env.example`, `main.py` |
| N8 | 🟠 | **Le démarrage des conteneurs n'est pas reproductible.** `CMD ["uv","run",…]`, utilisé pour l'API comme pour le worker, resynchronise l'environnement au lancement, **groupe `dev` compris** (comportement par défaut de `uv run`), alors que l'image est construite en `--no-dev`. Le démarrage dépend donc de PyPI et installe pytest et fakeredis en production. | `backend/Dockerfile`, `docker-compose.yml` |

---

## 3. Préconisations priorisées

### 3.0 Correctifs immédiats (≤ 1 jour, moins de 10 lignes chacun)

Ces correctifs suppriment une bonne part des 🔴 avant tout chantier de fond :

1. `HISTOOLBOX_DB_PATH=/app/data/tasks.db` dans `docker-compose.yml` et `.env.example` (F1).
2. Nom de fichier côté serveur figé à `input.pdf` ; le nom d'origine, assaini, n'est conservé qu'en base (S1).
3. `transformGetDocumentParams={(p) => ({ ...p, isEvalSupported: false })}` sur le `<Viewer>`, plus une CSP `<meta>` sans `unsafe-eval` dans `index.html` (S2).
4. Le nettoyage TTL ne touche plus que les tâches `completed` et `error` (F2, N3).
5. Une seule fonction `enqueue_ocr()`, qui fixe `job_timeout`, appelée par l'upload **et** par le requeue (F4).
6. `JobTimeoutException` (`rq.timeouts.BaseTimeoutException`) exclue des retries tenacity (F3).
7. `.env.example` corrigé : origine sans chemin, ajout d'`APP_BASE_URL` et `SMTP_*` ; refus de démarrer en production si `API_KEY` est vide ou vaut `changeme` (N6).
8. `--proxy-headers --forwarded-allow-ips=<sous-réseau Compose>` pour uvicorn (S4).
9. Sur `completed`, n'arrêter le polling qu'**après** un `getResult` réussi, et isoler `new Notification` dans un try/catch (N4).
10. Dockerfile : environnement installé au build, puis `CMD [".venv/bin/uvicorn", …]` (ou `UV_NO_SYNC=1`) (N8).

### 3.1 P0 : bloquants avant l'ouverture aux utilisateurs (≈ 1 à 2 semaines)

1. **Persistance et état** (F1, F5) : SQLite en WAL avec `busy_timeout`. **La base est la source de vérité de l'état métier ; RQ ne sert que de transport** (ses données sont éphémères : `DEFAULT_RESULT_TTL = 500 s`). `init_db()` ne réécrit plus les statuts au démarrage de l'API : c'est le worker, à son propre démarrage, qui réconcilie ses tâches.
2. **Une machine à états robuste côté worker** (F2, F3, F4) :
   - un heartbeat du worker (`updated_at` à chaque lot de pages) ;
   - `Worker(work_horse_killed_handler=…)` (rq `worker/base.py:150`) pour passer la tâche en `error` quand le horse est tué, puisque `on_failure` n'est **pas** appelé dans ce cas ;
   - un **reaper** périodique qui passe en `error` les tâches `processing` absentes de `StartedJobRegistry`, pour couvrir aussi la mort du conteneur entier.
3. **Tenir face aux coupures du vLLM** (N2) : une indisponibilité ne doit jamais faire échouer une tâche. Le worker suspend la consommation de la file (circuit breaker : sondage de `/health` avec backoff) et ne reprend qu'au retour du vLLM. La page d'attente affiche « moteur temporairement indisponible ». Seules les erreurs propres à un document le font échouer.
4. **Pipeline par tranches de pages avec checkpoint** (V1, V2, V3) : abandonner le chargement du PDF entier. Itérer par lots alignés sur la concurrence vLLM (32 à 64 pages, soit environ 350 à 700 Mo), avec `chandra.input.load_pdf_images(path, page_range)` puis `InferenceManager.generate(batch, max_workers=…)`. Variante plus efficace : un producteur/consommateur borné, qui rastérise le lot suivant pendant l'inférence du lot courant. **Écrire chaque page sur disque** (`pages/0001.json`), mettre à jour `progress = page/N`, ne relancer que les pages manquantes, et marquer une page en échec (« [page illisible] ») plutôt que de faire échouer le document. Supprimer la couche tenacity redondante avec les retries de Chandra.
5. **Sécuriser l'upload** (S1, S6, V6, F8) : vérifier les octets magiques `%PDF` et ouvrir le fichier avec pypdfium2 ; plafonner la taille (`request_body max_size` dans Caddy, lecture en flux par morceaux côté API) et le nombre de pages. Garder l'ordre ligne en base, puis enqueue, **avec compensation** en cas d'échec (suppression de la ligne et des fichiers). Inverser l'ordre créerait une course, le worker pouvant démarrer avant que la ligne existe.
6. **Reprise côté client** (F6, F7, N3) : écrire dans IndexedDB les statuts `pending` / `processing` reçus du serveur. La reprise couvre les deux statuts. **L'historique interroge le statut de tous les projets non terminés.** Distinguer l'erreur réseau (backoff exponentiel, polling sans limite mais espacé, bandeau « serveur injoignable ») de l'erreur métier (`error`, ou 404, signe d'une tâche expirée). Ajouter un bouton « Réessayer ».
7. **Démarrage robuste** (N5) : connexion Redis retentée avec backoff, ou création paresseuse de la queue ; healthchecks Compose et `depends_on: condition: service_healthy`.

### 3.2 P1 : nécessaire pour un MVP crédible (≈ 2 à 4 semaines)

8. **Identité minimale** (S3) : **une clé par utilisateur** (table `users`, clés hachées, révocation), ou un lien magique par email. Chaque tâche porte un `owner_id`, vérifié sur `/status` et `/result`. Comparaison en temps constant. `TokenGate` valide la clé via `GET /auth/me` et propose de se déconnecter.
9. **Le texte doit survivre au navigateur** (U1, U2, F2) : conserver côté serveur `markdown`, `blocks` et les révisions de l'utilisateur pendant une durée explicite et configurable (par exemple 30 jours après la fin), pour que le lien de l'email fonctionne depuis n'importe quel appareil. Côté client : `navigator.storage.persist()` et un export/import de projet (`.zip` contenant le PDF et le JSON). Le principe « Client-Side First » doit être tranché explicitement : **le PDF peut rester local, le texte doit survivre au navigateur**. Les sources peuvent être sensibles (archives non publiées), d'où une décision produit à acter dans un ADR.
10. **Fallback SPA** (U1) : copier `index.html` en `404.html` au build, ou passer à `HashRouter`. Le lien de l'email est construit depuis `APP_BASE_URL`, base path compris.
11. **Annulation et équité** (V4, V5) : `DELETE /ocr/tasks/{id}` (annulation du job RQ, `send_stop_job_command`). **Découper chaque document en jobs par tranches de pages**, ordonnancés en tourniquet par utilisateur : un petit document passe entre deux tranches d'un gros, sans ajouter de worker. Plafonner les pages par tâche et les tâches actives par utilisateur.
12. **Progression réelle** (V3) : `page x/N`, débit en pages par minute, heure de fin estimée, affichage progressif des pages déjà transcrites. Le pipeline du P0-4 rend tout cela possible.
13. **Synchronisation des blocs après correction** (U3) : stocker les plages de blocs dans un `StateField` CodeMirror qui **suit les éditions** (`tr.changes.mapPos`), persister les plages remappées, et construire l'aperçu par blocs à partir des tranches du document **corrigé**. Pas besoin de refondre le modèle de données.
14. **Exports fidèles** (U4) : passer du Markdown à un AST (`marked.lexer`), puis au docx, en gérant titres, listes, tableaux et emphase. Ajouter ensuite un export TEI, attendu en humanités numériques. ALTO, PAGE-XML ou un PDF cherchable restent limités, car Chandra ne fournit que des bbox **par bloc**, pas par ligne.
15. **Remplacer le viewer PDF** (S2) : migrer vers `react-pdf` (wojtekmaj, maintenu, pdf.js ≥ 4) avec une virtualisation des pages pour les gros documents, en réimplémentant l'overlay de blocs.
16. **Upload et relance** (N9, F8) : progression d'envoi (XHR) ; **identifiant généré côté client**, servant à la fois de clé IndexedDB et de clé d'idempotence envoyée au serveur (une seule écriture du blob, renvois idempotents) ; bouton « Relancer » qui renvoie le PDF local après une erreur ; plafond de fichiers appliqué à toute la file ; retrait de la mention du « client CLI ».
17. **CI** (I1, I2) : GitHub Actions avec ruff, mypy, pytest, eslint, `tsc`, vitest, `npm audit` et `pip-audit` sur chaque PR ; image backend publiée sur GHCR avec des tags immuables ; tests de non-régression pour F2 à F5, S1, N2, N4 et la reprise client.
18. **Observabilité minimale** (I3) : `/health/live` et `/health/ready` (Redis, base, vLLM), logs JSON corrélés par `task_id`, `rq-dashboard`, alerte en cas de vLLM injoignable.
19. **Emails** (S5) : templates Jinja2 avec auto-échappement, validation via `email-validator`, adresse conservée seulement pendant la durée de vie de la tâche, mention RGPD (y compris le traitement sur une infra distante), envoi dans une tâche RQ distincte avec retry.

### 3.3 P2 : consolidation et dette (en continu)

20. **Configuration centralisée** avec `pydantic-settings` (un seul objet `Settings`, validé au démarrage) ; nettoyage de F10.
21. **Couche de persistance** : SQLAlchemy Core ou SQLModel avec **Alembic**, dès que le schéma dépasse la table `tasks` (utilisateurs, révisions) ; I/O hors de la boucle événementielle ; `last_seen` mis en tampon au lieu d'une écriture à chaque poll. Passage à Postgres si le nombre d'utilisateurs grandit.
22. **Durcissement du conteneur** : utilisateur non root, `uv` épinglé, sauvegarde du volume `data/`.
23. **Métriques Prometheus** (longueur de file, durée par page, taux d'erreur), une fois l'usage établi.
24. **Abstraction du moteur OCR** : une interface `OcrEngine` (Chandra-vLLM aujourd'hui, d'autres modèles ou Kraken/eScriptorium demain), qui découple le worker de `chandra.*`.
25. **Hygiène** (I5, S8) : `npm audit fix`, suppression des restes de scaffold, README à jour (nombre de tests, statut « PoC »), choix d'une licence, `CHANGELOG`.

---

## 4. Architecture cible MVP (synthèse)

```
SPA (Pages + 404.html, CSP) ── clé utilisateur ──▶ FastAPI
                                                   ├─ Settings (pydantic-settings, fail-closed)
                                                   ├─ Auth / ownership
                                                   ├─ Base = source de vérité (SQLite WAL → Postgres), volume data/
                                                   └─ enqueue_ocr() ─▶ Redis/RQ (transport) ─▶ worker
                                                                                               ├─ jobs par tranches de pages,
                                                                                               │  tourniquet par utilisateur
                                                                                               ├─ checkpoint par page sur disque
                                                                                               ├─ circuit breaker vLLM
                                                                                               └─ heartbeat + work_horse_killed_handler
                                                   Reaper : réconcilie la base avec les registres RQ
Stockage serveur : résultats + révisions (TTL long, configurable) ; PDF supprimé après l'OCR
Client : IndexedDB = cache + PDF local ; storage.persist() ; export/import de projet ; polling de tous les projets non terminés
```

Décisions à formaliser en ADR (`docs/adr/`) :
1. **L'état** : la base fait foi, RQ ne sert qu'au transport, le reaper réconcilie.
2. **Le lieu de stockage des transcriptions** : révision du principe « Client-Side First », à mettre en regard de la sensibilité des sources.
3. **Le modèle d'identité** : clés par utilisateur ou lien magique.
4. **L'unité d'ordonnancement** : la tranche de pages plutôt que le document.

---

## 5. Feuille de route suggérée

| Sprint | Contenu | Critère de sortie |
|---|---|---|
| S0 (1 jour) | Correctifs immédiats (§3.0) | `docker compose up` avec l'exemple de configuration : un PDF va au bout et le lien de l'email est correct ; `filename=../x.pdf` est neutralisé |
| S1 | P0-1, 2, 5, 7, plus tests et CI de base | Tuer le worker : la tâche passe en `error` en moins de 2 min ; redémarrer l'API ne casse aucun traitement en cours |
| S2 | P0-3, 4, 6 | Mémoire du worker < 1 Go sur 500 pages ; une page en échec n'annule pas le document ; vLLM coupé 10 min : la file survit ; 3 fichiers lancés puis onglet fermé pendant 2 h : aucune perte |
| S3 | P1-8 à 11, 15 | Lien de l'email fonctionnel depuis un autre appareil ; annulation ; clés par utilisateur ; un petit document n'attend plus derrière un gros |
| S4 | P1-12 à 14, 16 à 19 | Progression par page ; synchronisation des blocs après correction ; docx fidèle ; tableau de bord RQ |

---

## 6. Reproduire les constats critiques

- **F1** : `docker compose up`, envoyer un PDF, puis comparer `docker compose exec api sqlite3 /app/tasks.db 'select status from tasks'` avec la même commande sur `rq_worker`.
- **S1** : `curl -H "X-API-Key: …" -F "file=@x.pdf;filename=../x.pdf;type=application/pdf" …/ocr/upload`. Après le traitement, `data/uploads/` a disparu. Variante écriture : `filename=/app/data/pwn.pdf`.
- **F2 / N3** : avec `CLEANUP_TTL_SECONDS=60 CLEANUP_INTERVAL_SECONDS=30`, lancer 2 PDF de plus de 2 min chacun et rester sur l'historique : les lignes et les fichiers disparaissent avant ou pendant le traitement.
- **F3 / F4** : redémarrer le worker avec une tâche `pending` dont l'inférence dure plus de 4 min. Le job ré-enfilé est tué à `180 s + 60 s` et la tâche reste `processing`.
- **N2** : arrêter le vLLM avec 3 tâches en file : les 3 passent en `error` en quelques secondes.
- **F6** : envoyer un PDF, fermer l'onglet, rouvrir `/` : aucune redirection, et `getProjectsByStatus("processing")` renvoie `[]`.
- **N4** : dans les DevTools, bloquer `/ocr/result/*` au moment du passage en `completed` : le spinner tourne indéfiniment.
- **N6** : `curl -i -X OPTIONS -H "Origin: https://username.github.io" -H "Access-Control-Request-Method: POST" …/ocr/upload` avec l'`ALLOWED_ORIGINS` d'exemple : la réponse ne contient pas `access-control-allow-origin`.
- **S2** : `npm audit --omit=dev` (pdfjs-dist, CVE-2024-4367), puis ouvrir un PDF de preuve de concept public.
- **V1** : `/usr/bin/time -v` sur le worker avec un PDF de 200 pages (pic de RSS).

---

## Révisions

**v2 (2026-10-22)** : relecture contradictoire de la v1, confrontée au code de l'application et à celui des bibliothèques.

- **Corrigé** :
  - mécanisme de F3 (tenacity absorbe `JobTimeoutException`, et `on_failure` n'est pas appelé quand le horse est tué) ;
  - F10 (`CHANDRA_INFERENCE_TIMEOUT` fixe bien le timeout RQ) ;
  - portée de `npm audit` (seul pdf.js est réellement exposé, le reste passe en S8) ;
  - F7 (une relance est possible via l'historique) ;
  - U5 (le vrai défaut est l'absence de flush, pas l'écrasement par `""`) ;
  - nombre de tests frontend (40) ;
  - suppression d'une affirmation non fondée sur les versions de Node.
- **Recommandations revues** :
  - la base devient la source de vérité (au lieu de RQ) ;
  - compensation au lieu d'un enqueue avant l'écriture en base ;
  - lots de 32 à 64 pages au lieu de 8 à 16 ;
  - jobs par tranches de pages au lieu de workers supplémentaires ;
  - remappage CodeMirror au lieu d'une refonte en blocs ;
  - réserves sur ALTO et le PDF cherchable ;
  - Prometheus repoussé en P2 ;
  - migration du viewer en P1, le correctif `isEvalSupported` restant en §3.0.
- **Ajouté** :
  - S1 aggravé (suppression arbitraire, RCE) ;
  - N2 (une coupure du vLLM vide la file) ;
  - N3 (le multi-upload sans polling mène à la perte des résultats) ;
  - N4 (page d'attente bloquée) ;
  - N5 (Redis au démarrage) ;
  - N6 (configuration de production fournie inopérante) ;
  - F5 en développement (`--reload`) ;
  - N8 (`uv run` au démarrage) ;
  - N9 (UX d'upload) ;
  - empilement des retries (V2), relais de phishing et RGPD (S5) ;
  - §3.0 « correctifs immédiats », §2.6, ADR révisés.

**v1 (2026-10-21)** : audit initial.
