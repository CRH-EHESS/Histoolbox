# Suivi des sprints

Relevé de clôture, un bloc par sprint. Il garde une **trace durable, hors PR**, de la vérification de fin de sprint demandée au §5.2 du [protocole](DEVELOPPEMENT.md) : réalisations effectuées, critères de sortie (§5 de l'[audit](AUDIT-MVP.md)) et reproductions rejouées (§6 de l'audit, §5.1 du protocole). Il **complète** la colonne « Statut » du §3.1 et les descriptions de PR, sans les remplacer.

Résultat : ✓ vérifié · ✗ échec · ⚠️ vérifié autrement (voir note). Les dates sont absolues.

---

## S0 — Correctifs immédiats

- **Branche / PR** : `fix/3.0-correctifs-immediats` → [PR #3](https://github.com/CRH-EHESS/Histoolbox/pull/3)
- **Statut §3.1** : `fusionnée (#3)` (posé avant la fusion, comme prescrit ; **clôture effective au *squash merge***)
- **Vérification** : recette `docker compose up` le 2026-10-24, stack complète avec faux vLLM (OpenAI-compatible) et Mailpit.
- **Tests** : backend 63 (+19), frontend 44 (+4), build + lint OK.

### Réalisations (§3.0 de l'audit)

| # | Constat | Correctif | Fait |
|---|---------|-----------|------|
| 1 | F1 | base SQLite unique dans le volume partagé (`HISTOOLBOX_DB_PATH`) | ✓ |
| 2 | S1 | PDF en `input.pdf` ; nom d'origine assaini en base (`filename`) | ✓ |
| 3 | S2 | `isEvalSupported: false` + CSP `<meta>` sans `unsafe-eval` | ✓ |
| 4 | F2, N3 | nettoyage limité aux tâches terminées ; conservation 24 h | ✓ |
| 5 | F4 | `enqueue_ocr()` fixe `job_timeout` (upload + requeue) | ✓ |
| 6 | F3 | timeout RQ exclu des retries tenacity | ✓ |
| 7 | N6 | `.env.example` corrigé ; démarrage refusé sans vraie clé en prod | ✓ |
| 8 | S4 | uvicorn `--proxy-headers` + sous-réseau Compose fixe | ✓ |
| 9 | N4 | polling arrêté après `getResult` ; `Notification` isolée ; icône PNG | ✓ |
| 10 | N8 | conteneurs lancés depuis le venv du build | ✓ |

### Critères de sortie (§5.2 du protocole / §5 de l'audit)

| Critère | Branche | Résultat | Preuve |
|---|---|---|---|
| `docker compose up` avec l'exemple de config : un PDF va au bout | 3.0 | ✓ | upload → OCR → `/ocr/result` complet (2 blocs, 1 page) |
| Le lien de l'email est correct (URL : domaine + base path d'`APP_BASE_URL`) | 3.0 | ✓ | email Mailpit → `https://username.github.io/Histoolbox/ocr/toolbox/<id>` (ne **s'ouvre** qu'avec 3.2.10, S3) |
| `filename=../x.pdf` est neutralisé | 3.0 | ✓ | PDF écrit en `input.pdf` ; `data/uploads/` et le PDF d'un autre utilisateur intacts |

### Reproductions rejouées (§6 de l'audit / §5.1 du protocole)

| Reproduction | Résultat | Note |
|---|---|---|
| F1 — deux `tasks.db` | ✓ | API et worker lisent le même `/app/data/tasks.db` ; `/app/tasks.db` absent |
| S1 — `filename=../x.pdf`, chemin absolu | ✓ | rien écrit ni supprimé hors du dossier de tâche |
| F2 / N3 — TTL court, 2 PDF, aucun polling | ✓ | `pending`/`processing` jamais supprimées ; nettoyage seulement après fin + TTL |
| F3 / F4 — requeue + inférence 300 s | ✓ | job ré-enfilé avec `job_timeout=14700` (≠ 180) ; 300 s menés au bout, jamais tué |
| N4 — `/ocr/result` bloqué au passage à `completed` | ✓ | 1er `GET` échoué → retenté au tick suivant → toolbox atteinte, PDF rendu |
| N6 — préflight CORS, origine d'exemple | ✓ | `changeme` → démarrage refusé ; préflight `https://username.github.io` accepté |
| S2 — pdf.js, PDF de preuve de concept | ⚠️ | **PoC d'exploit non rejoué.** Vérifié autrement : `isEvalSupported: false` transmis (test unitaire) ; CSP `<meta>` réellement appliquée (script inline et handler `onclick` bloqués) ; PDF légitime rendu. La suppression du pdfjs vulnérable relève de 3.2.15 (viewer) et 3.2.17a (`npm audit fix`). |

Hors reproductions du §6, également vérifiés en recette : S4 (IP réelle du client derrière Caddy ; 11ᵉ upload → 429 ; autre client non pénalisé) et N8 (image démarrée sans réseau, sans `pytest`/`fakeredis` ; l'ancienne commande `uv run` échoue hors-ligne).

**Clôture S0** : critères de sortie et reproductions vérifiés ; reste la fusion de la PR #3 (revue + *squash merge*).
