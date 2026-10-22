# Protocole de développement

Ce protocole encadre la mise en œuvre des préconisations de l'[audit MVP](AUDIT-MVP.md) (section 3). L'audit est un document daté : il n'est pas réécrit. Les compléments, les découpages et les écarts sont consignés ici, au §3.

## 1. Une branche par préconisation

Chaque point de la section 3 de l'audit est traité dans **sa propre branche**, créée depuis `main`. Seul le bloc **3.0** (correctifs immédiats) est regroupé dans une branche unique. Seule la préconisation **3.2.17** (CI) est coupée en deux branches, une par sprint (voir §3.3).

### Nommage

```
<type>/<n° de préconisation>-<intitulé-court>
```

- `<type>` : `feat`, `fix`, `refactor`, `ci`, `chore`, `docs` (cohérent avec les préfixes de commit).
- `<n° de préconisation>` : position dans l'audit, au format `3.<sous-section>.<n° du point>`. La numérotation des points reprend celle de l'audit, qui est continue de 1 à 25 (ex. `3.2.8` pour le point 8 « Identité minimale », appelé aussi P1-8 dans la feuille de route ; `3.1.n` correspond à P0-n). Un point coupé en deux prend un suffixe `a` / `b` (`3.2.17a`, `3.2.17b`).
- `<intitulé-court>` : quelques mots en kebab-case, sans accents.

Exemples : `fix/3.0-correctifs-immediats`, `feat/3.1.1-persistance-etat`, `ci/3.2.17a-integration-continue`.

**Travail hors audit** (bug découvert en cours de route, petite évolution) : branche `<type>/<intitulé-court>` sans numéro, commits sans portée numérotée. Si le défaut relève d'une préconisation existante, il est traité dans la branche de celle-ci et ajouté à sa ligne du tableau du §3.

### Description de branche

La préconisation correspondante est attachée à la branche de deux façons :

1. **Commit d'ouverture**, vide (`git commit --allow-empty`), au format :
   ```
   🚧 chore(<n°>): ouverture de la branche — <intitulé>

   [<n°>] <intitulé>

   Préconisation <n°> de docs/AUDIT-MVP.md :

   <texte de la préconisation, copié de l'audit>

   Compléments (docs/DEVELOPPEMENT.md §3) :
   - <constats ajoutés, dépendances, ADR, recette, contrat d'API>
   ```
   Il voyage avec la branche et devient visible sur GitHub dès qu'elle est poussée.
2. **Description git locale** (`git config branch.<nom>.description`) : le même texte, sans la ligne de titre. Elle se consulte avec :
   ```bash
   git config branch.feat/3.1.1-persistance-etat.description
   ```

La description de la Pull Request reprend ce texte, complété des choix d'implémentation et des tests ajoutés. Si le tableau du §3 évolue (constat ajouté, dépendance découverte), le commit d'ouverture et la description sont mis à jour dans la même foulée.

## 2. Cycle de vie d'une branche

1. **Démarrage** : se resynchroniser avec `main`, les branches ayant été créées en amont, puis publier la branche.
   ```bash
   git switch feat/3.1.1-persistance-etat
   git rebase main
   git push -u origin feat/3.1.1-persistance-etat
   ```
   Avant de démarrer, vérifier dans le tableau du §3 que les branches dont elle dépend sont fusionnées (sinon, voir l'étape 6).
2. **Développement** : commits atomiques, au format gitmoji déjà en usage :
   `✨ feat(3.1.1): …`, `🐛 fix(3.0): …`, `♻️ refactor(3.3.20): …`, `✅ test(3.1.2): …`, `📝 docs: …`.
   Le numéro de préconisation en portée (`(3.1.1)`) permet de tracer chaque commit jusqu'à l'audit ; les constats traités terminent le sujet quand c'est utile : `🐛 fix(3.0): nettoyage TTL limité aux tâches terminées (F2, N3)`. Dans la branche `3.0`, chacun des 10 correctifs fait l'objet d'**un commit distinct**.
   Une branche qui porte un ADR (§4) le rédige **en premier**, juste après le commit d'ouverture.
3. **Tests et recette** : tout correctif d'un constat (F2, S1, N4…) s'accompagne si possible d'un test de non-régression. Avant la PR :
   ```bash
   (cd backend && uv run pytest)
   (cd frontend && npm run lint && npm run build && npm test)
   ```
   `npm run build` inclut `tsc -b` et vérifie aussi le build Vite. Une fois `3.2.17a` fusionnée, la CI fait foi : elle ajoute ruff, mypy et les audits de dépendances, et cette liste est mise à jour dans la même PR.
   Si la branche corrige un constat du §6 de l'audit, la reproduction correspondante est rejouée et ne doit plus reproduire le défaut (voir §5).
4. **Pull Request** vers `main`, intitulée `[3.1.1] Persistance et état`. La description liste les constats traités, le critère de sortie de la feuille de route (§5 de l'audit) qu'elle fait avancer, le résultat de la recette, et indique si elle modifie le contrat d'API (voir §6). Tout écart à la préconisation y est justifié ; s'il touche une décision d'architecture, il passe par un ADR. La PR met à jour sa ligne dans le tableau du §3 (colonne « Statut » : `fusionnée (#n)`).
5. **Fusion** en *squash merge* : un commit par préconisation sur `main`, ce qui fait aussi disparaître le commit d'ouverture vide.
6. **Branches dépendantes**. Le plus simple est de n'en commencer le développement qu'après la fusion de la branche dont elle dépend : un `git rebase main` suffit alors. Si elle doit démarrer avant, elle est **empilée** sur sa branche parente (`git rebase <parente>`). Après le *squash merge* de la parente, ses commits n'existent plus sur `main` sous la même forme : un `git rebase main` les rejouerait et produirait des conflits. On retire donc explicitement les commits de la parente :
   ```bash
   git switch main && git pull --ff-only
   git rebase --onto main <parente> <dépendante>
   git push --force-with-lease
   ```
   Cette commande s'appuie sur la référence locale `<parente>` (sa tête avant la fusion) : **ne supprimer la branche parente qu'une fois toutes ses dépendantes rebasées**.
7. **Nettoyage** : `git branch -D <branche>` (`-D`, car git ne reconnaît pas une branche fusionnée en squash) et `git push origin --delete <branche>`.

`main` ne reçoit pas de commit direct : tout passe par une branche et une PR. **Seule exception** : le commit d'amorçage `📝 docs: audit MVP et protocole de développement par préconisation`, qui crée l'audit et ce protocole, a été poussé directement sur `main`, car toutes les branches en partent.

## 3. Branches, constats et dépendances

### 3.1 Tableau de suivi

Les constats marqués ¹ ne figurent pas dans le texte de la préconisation de l'audit : ils sont rattachés à la branche par ce protocole (§3.3). La colonne « Dépend de » liste les branches à fusionner avant ; « — » signifie aucune dépendance autre que `3.0`, à fusionner avant toute autre branche.

| N° | Branche | Sprint | Constats traités | Dépend de | Statut |
|---|---|---|---|---|---|
| 3.0 | `fix/3.0-correctifs-immediats` | S0 | F1, S1, S2, F2, N3, F4, F3, N6, S4, N4 (+ icône¹), N8 | — | à faire |
| 3.1.1 | `feat/3.1.1-persistance-etat` | S1 | F1, F5 | — | à faire |
| 3.1.2 | `feat/3.1.2-machine-etats-worker` | S1 | F2, F3, F4 | 3.1.1 | à faire |
| 3.1.3 | `feat/3.1.3-resilience-vllm` | S2 | N2 | 3.1.4 | à faire |
| 3.1.4 | `feat/3.1.4-pipeline-tranches-checkpoint` | S2 | V1, V2, V3 | 3.1.2 | à faire |
| 3.1.5 | `fix/3.1.5-securisation-upload` | S1 | S1, S6, V6, F8 | — | à faire |
| 3.1.6 | `feat/3.1.6-reprise-client` | S2 | F6 (+ blocs¹), F7, N3, U5¹ | — | à faire |
| 3.1.7 | `fix/3.1.7-demarrage-robuste` | S1 | N5 | — | à faire |
| 3.2.8 | `feat/3.2.8-identite-utilisateur` | S3 | S3 | 3.3.21 | à faire |
| 3.2.9 | `feat/3.2.9-persistance-texte-serveur` | S3 | U1, U2, F2 | 3.2.8, 3.3.21 | à faire |
| 3.2.10 | `fix/3.2.10-fallback-spa` | S3 | U1 | — | à faire |
| 3.2.11 | `feat/3.2.11-annulation-equite` | S3 | V4 (+ historique¹), V5, F9¹ | 3.1.4, 3.2.8 | à faire |
| 3.2.12 | `feat/3.2.12-progression-reelle` | S4 | V3 | 3.1.4 | à faire |
| 3.2.13 | `fix/3.2.13-synchro-blocs-correction` | S4 | U3 | 3.2.9, 3.2.15 | à faire |
| 3.2.14 | `feat/3.2.14-exports-fideles` | S4 | U4 | — | à faire |
| 3.2.15 | `refactor/3.2.15-viewer-react-pdf` | S3 | S2, U5¹ | — | à faire |
| 3.2.16 | `feat/3.2.16-upload-relance` | S4 | N9, F8, S4¹ | 3.1.5, 3.2.8 | à faire |
| 3.2.17a | `ci/3.2.17a-integration-continue` | S1 | I1, I2 | — | à faire |
| 3.2.17b | `ci/3.2.17b-publication-image` | S4 | I1, I2¹ | 3.2.17a | à faire |
| 3.2.18 | `feat/3.2.18-observabilite` | S4 | I3 | 3.1.3, 3.1.7 | à faire |
| 3.2.19 | `feat/3.2.19-emails` | S4 | S5 | 3.2.9, 3.2.10 | à faire |
| 3.3.20 | `refactor/3.3.20-configuration-centralisee` | S1 | F10, I4 | — | à faire |
| 3.3.21 | `refactor/3.3.21-couche-persistance` | S3 | I4 | 3.1.1 | à faire |
| 3.3.22 | `chore/3.3.22-durcissement-conteneur` | Continu | S7 (en partie dans l'audit, reste¹) | — | à faire |
| 3.3.23 | `feat/3.3.23-metriques-prometheus` | Continu | I3 | 3.2.18 | à faire |
| 3.3.24 | `refactor/3.3.24-abstraction-moteur-ocr` | Continu | — (évolutivité) | 3.1.3, 3.1.4 | à faire |
| 3.3.25 | `chore/3.3.25-hygiene` | Continu | I5, S8 | — | à faire |

### 3.2 Ordre de traitement

L'ordre suit la feuille de route de l'audit (§5), complétée des dépendances ci-dessus. La flèche indique un ordre imposé ; la virgule, des branches indépendantes.

| Sprint | Branches |
|---|---|
| S0 | `3.0` |
| S1 | `3.2.17a` → `3.3.20` → `3.1.1` → `3.1.2` ; `3.1.5`, `3.1.7` |
| S2 | `3.1.4` → `3.1.3` ; `3.1.6` |
| S3 | `3.3.21` → `3.2.8` → `3.2.9`, `3.2.11` ; `3.2.10`, `3.2.15` |
| S4 | `3.2.13`, `3.2.12`, `3.2.14`, `3.2.16`, `3.2.17b`, `3.2.18`, `3.2.19` |
| Continu | `3.3.22` ; `3.3.23` après `3.2.18` ; `3.3.24` après S2 ; `3.3.25` en dernier (README, nombre de tests) |

Le graphe de dépendances est acyclique, et chaque dépendance est fusionnée dans un sprint antérieur ou plus tôt dans le même sprint.

**Justification des dépendances** :

- `3.2.17a` ouvre S1 pour que toutes les PR suivantes passent par la CI.
- `3.3.20` (configuration centralisée) est avancée de « Continu » à S1 : presque toutes les branches suivantes ajoutent des paramètres (taille des lots, plafonds, backoff, durée de conservation). Les centraliser d'abord évite de multiplier les `os.getenv`. Elle reprend la vérification `API_KEY` de `3.0`.
- `3.1.2` après `3.1.1` : le reaper et la réconciliation au démarrage du worker supposent que la base est la source de vérité et que `init_db()` ne réécrit plus les statuts.
- `3.1.4` après `3.1.2` : le heartbeat de `3.1.2` est d'abord **périodique** (un thread qui met à jour `updated_at` pendant le job), puisque les lots de pages n'existent pas encore ; `3.1.4` le rattache ensuite à chaque lot.
- `3.1.3` après `3.1.4` : les deux branches modifient les retries de `chandra_service.py`. De plus, une coupure du vLLM **en cours de document** ne doit pas tout faire recommencer : la reprise s'appuie sur le checkpoint par page de `3.1.4`.
- `3.3.21` (Alembic) est avancée de « Continu » à S3 : l'audit la déclenche « dès que le schéma dépasse la table `tasks` », ce que font `3.2.8` (table `users`) et `3.2.9` (révisions).
- `3.2.9` après `3.2.8` : les transcriptions stockées côté serveur appartiennent à un utilisateur (`owner_id`).
- `3.2.11` après `3.1.4` (découpage en tranches) et `3.2.8` (tourniquet et plafonds **par utilisateur**).
- `3.2.12` après `3.1.4` : la progression par page vient du pipeline par tranches.
- `3.2.13` après `3.2.9` (persistance des plages remappées côté serveur) et `3.2.15` (overlay de blocs réimplémenté dans le nouveau viewer).
- `3.2.15` doit conserver le correctif `isEvalSupported: false` et la CSP de `3.0`.
- `3.2.16` après `3.1.5` (lecture en flux, plafonds et compensation, que l'idempotence prolonge) et `3.2.8` (limitation par utilisateur, §3.3).
- `3.2.18` après `3.1.3` (la sonde vLLM du circuit breaker sert à `/health/ready`) et `3.1.7` (les healthchecks Compose passent sur `/health/live` et `/health/ready`).
- `3.2.19` après `3.2.9` (la durée de conservation de l'adresse suit celle de la tâche) et `3.2.10` (lien de l'email).
- `3.3.23` après `3.2.18`, `3.3.24` après `3.1.3` et `3.1.4` : l'interface `OcrEngine` s'extrait d'un pipeline stabilisé.

### 3.3 Compléments à l'audit

L'analyse croisée des constats (§2 de l'audit) et des préconisations (§3) fait apparaître des constats, ou des parties de constats, qu'aucune préconisation ne traite. Ils sont rattachés aux branches suivantes :

| Constat | Partie non couverte par l'audit | Branche |
|---|---|---|
| N4 | L'icône de notification `/favicon.ico` n'existe pas et ignore le base path | `3.0` (avec le point 9) |
| F6 | `OCRRecovery` n'enregistre ni `blocks` ni `pages` | `3.1.6` |
| U5 | Flush de l'autosave au cleanup et sur `pagehide` ; polling sans chevauchement (`setTimeout` chaîné au lieu de `setInterval`) | `3.1.6` |
| U5 | Le PDF n'est plus recopié entièrement en `Uint8Array` à chaque ouverture | `3.2.15` |
| F9 | `queue_position` calculée par l'ordonnanceur (tourniquet), cohérente avec l'ordre réel de traitement | `3.2.11` |
| V4 | La suppression d'un projet dans l'historique annule aussi la tâche côté serveur | `3.2.11` |
| S4 | La limite d'upload (10/min) est incompatible avec le multi-upload (`MAX_FILES = 20`) : la limite porte sur l'utilisateur et la file d'envoi la respecte | `3.2.16` |
| S7 | `str(exc)` renvoyé à l'utilisateur (message générique, détail dans les logs), `allow_credentials=True` retiré, clé d'API sur le vLLM | `3.3.22` (en plus du non-root et de l'épinglage d'`uv`) |
| I2 | Test d'un vrai déploiement Compose et test end-to-end navigateur (parcours upload → relecture, vLLM simulé) | `3.2.17b` |

**Découpage de 3.2.17.** La feuille de route de l'audit place la « CI de base » en S1 et la préconisation 17 en S4. Elle est coupée en deux branches, sans cycle de dépendance (`3.2.17b` ne dépend que de `3.2.17a`, et aucune branche antérieure ne dépend de `3.2.17b`) :

- **`3.2.17a` (S1)** : GitHub Actions avec ruff, mypy, pytest, eslint, `tsc`, vitest, `npm audit` et `pip-audit` sur chaque PR. Le code existant est mis en conformité, ou une base de référence est fixée. Les tests de non-régression de F2 à F5, S1, N2, N4 et de la reprise client sont livrés par les branches qui corrigent ces constats ; la CI les exécute.
- **`3.2.17b` (S4)** : image backend publiée sur GHCR avec des tags immuables ; test de déploiement Compose et test end-to-end en CI (I2¹) ; vérification que les tests de non-régression ci-dessus existent tous.

**Branche `feature/chunked-upload`** (distante, antérieure au protocole, non fusionnée). Elle implémente l'upload par morceaux de 5 Mo avec reprise, un `task_id` généré côté client et une barre de progression : c'est une bonne part de `3.2.16` (et de la lecture en flux de `3.1.5`). Elle n'est **pas fusionnable telle quelle** : elle réintroduit le path traversal S1 (`task_upload_dir / filename`), son statut `assembling` est remis en `error` au démarrage (même schéma que F5), et elle date d'avant `3.0`. Elle sert de base de travail à `3.2.16` (cherry-pick ou réécriture), puis est supprimée.

### 3.4 Couverture des constats

Chaque constat de l'audit est traité par au moins une branche dont le commit d'ouverture et la description documentent la préconisation correspondante :

| Constats | Branches |
|---|---|
| F1 | 3.0, 3.1.1 |
| F2 | 3.0, 3.1.2, 3.2.9 |
| F3, F4 | 3.0, 3.1.2 |
| F5 | 3.1.1 |
| F6, F7 | 3.1.6 |
| F8 | 3.1.5, 3.2.16 |
| F9 | 3.2.11¹ |
| F10 | 3.3.20 |
| N2 | 3.1.3 |
| N3 | 3.0, 3.1.6 |
| N4 | 3.0 |
| N5 | 3.1.7 |
| N6, N8 | 3.0 |
| N9 | 3.2.16 |
| V1, V2 | 3.1.4 |
| V3 | 3.1.4, 3.2.12 |
| V4, V5 | 3.2.11 |
| V6 | 3.1.5 |
| S1 | 3.0, 3.1.5 |
| S2 | 3.0, 3.2.15 |
| S3 | 3.2.8 |
| S4 | 3.0, 3.2.16¹ |
| S5 | 3.2.19 |
| S6 | 3.1.5 |
| S7 | 3.3.22 |
| S8 | 3.3.25 |
| U1 | 3.2.9, 3.2.10 |
| U2 | 3.2.9 |
| U3 | 3.2.13 |
| U4 | 3.2.14 |
| U5 | 3.1.6¹, 3.2.15¹ |
| I1, I2 | 3.2.17a, 3.2.17b |
| I3 | 3.2.18, 3.3.23 |
| I4 | 3.3.20, 3.3.21 |
| I5 | 3.3.25 |

## 4. Décisions d'architecture (ADR)

Les quatre décisions demandées par l'audit (§4) sont rédigées dans `docs/adr/`, chacune dans la branche qui la met en œuvre, **avant le code** :

| ADR | Décision | Branche |
|---|---|---|
| `0001-etat-base-source-de-verite.md` | La base fait foi, RQ ne sert qu'au transport, le reaper réconcilie | `3.1.1` |
| `0002-stockage-des-transcriptions.md` | Révision du principe « Client-Side First » au regard de la sensibilité des sources | `3.2.9` |
| `0003-modele-identite.md` | Clés par utilisateur ou lien magique | `3.2.8` |
| `0004-unite-ordonnancement.md` | La tranche de pages plutôt que le document | `3.2.11` |

Format : `Statut` (proposé, accepté, remplacé par …), `Contexte`, `Décision`, `Conséquences`, `Constats liés`. L'ADR 0002 est une **décision produit** : la PR de `3.2.9` est ouverte en brouillon dès le commit de l'ADR, et le code ne commence qu'une fois l'ADR accepté. Une décision qui en remplace une autre fait l'objet d'un nouvel ADR, l'ancien passant à « remplacé par ».

## 5. Recette : reproductions de l'audit

Le §6 de l'audit (« Reproduire les constats critiques ») sert de recette. Avant la PR, la branche rejoue les reproductions des constats qu'elle corrige ; le défaut ne doit plus apparaître. Le résultat figure dans la description de la PR.

| Reproduction (§6 de l'audit) | Branches |
|---|---|
| F1 (deux `tasks.db`) | 3.0, 3.1.1 |
| S1 (`filename=../x.pdf`, chemin absolu) | 3.0, 3.1.5 |
| F2 / N3 (TTL court, 2 PDF, historique ouvert) | 3.0, 3.1.6 |
| F3 / F4 (requeue tué à 180 s + 60 s) | 3.0, 3.1.2 |
| N2 (vLLM arrêté avec 3 tâches en file) | 3.1.3 |
| F6 (onglet fermé puis rouvert) | 3.1.6 |
| N4 (`/ocr/result/*` bloqué) | 3.0 |
| N6 (préflight CORS) | 3.0 |
| S2 (`npm audit`, PDF de preuve de concept) | 3.0, 3.2.15 |
| V1 (pic de RSS sur 200 pages) | 3.1.4 |

Pour les constats sans reproduction (F5 par exemple : redémarrer l'API pendant un traitement), la PR décrit le scénario vérifié. Chaque fin de sprint vérifie le critère de sortie correspondant (§5 de l'audit).

## 6. Déploiement continu

- **Frontend** : le workflow `deploy-pages.yml` déploie GitHub Pages à chaque push sur `main` touchant `frontend/**`. Les branches de travail ne déclenchent aucun déploiement ; une fusion dans `main` vaut mise en production.
- **Backend** : déploiement manuel (`docker compose up -d --build`) jusqu'à la préconisation `3.2.17b`, qui publie les images sur GHCR avec des tags immuables.
- Chaque fusion d'une branche touchant le backend est suivie d'une vérification du critère de sortie du sprint correspondant (§5 de l'audit).

**Contrat d'API.** La fusion déploie le frontend en quelques minutes, alors que le backend se déploie à la main : une branche qui modifie le contrat entre les deux casserait la production entre les deux déploiements. Pour une telle branche :

1. le backend reste **rétrocompatible** avec le frontend en production : on ajoute des champs, des endpoints ou des statuts sans retirer l'ancien comportement (pour `3.2.8`, la clé partagée reste acceptée pendant la transition) ;
2. le backend est déployé **depuis la branche, juste avant la fusion** ; le *squash merge* ayant le même contenu, `main` correspond ensuite à ce qui tourne ;
3. la fusion déploie le frontend ;
4. l'ancien comportement est retiré plus tard, dans une PR dédiée.

Branches concernées a priori (la PR le confirme) : `3.1.3` (statut « moteur indisponible »), `3.1.4` (progression par page), `3.1.5` (plafonds, 413), `3.2.8` (authentification), `3.2.9` (révisions côté serveur), `3.2.10` (format du lien de l'email), `3.2.11` (annulation, position en file), `3.2.12` (progression), `3.2.16` (upload par morceaux, idempotence).

## 7. Branches antérieures au protocole

- `feat/deployment` (locale et distante) : déjà fusionnée dans `main` (`2c234d4`), à supprimer.
- `feature/chunked-upload` (distante) : reprise dans `3.2.16`, voir §3.3.
