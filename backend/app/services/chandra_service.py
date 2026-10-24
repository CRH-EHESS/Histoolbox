"""
Service Chandra : utilise l'API Python de chandra-ocr (InferenceManager)
pour éviter le cold-start du subprocess CLI.

Flow :
  load_file(pdf_path) -> List[PIL.Image]
  InferenceManager.generate(batch) -> List[BatchOutputItem]  (appel HTTP direct au vLLM)
  _assemble_and_persist -> dict {markdown, html, metadata} + fichiers sur disque

Avantage vs subprocess : zéro cold-start Python/ML — l'InferenceManager vllm
ne charge aucun modèle en local (self.model = None), seul le vLLM distant est sollicité.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Callable, List, Optional

import httpx
from loguru import logger
from rq.timeouts import BaseTimeoutException
from tenacity import (
    RetryCallState,
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from chandra.input import load_file
from chandra.model import InferenceManager
from chandra.model.schema import BatchInputItem, BatchOutputItem
from chandra.output import parse_markdown as _chandra_parse_md

# URL de base du service vLLM — configurable via variable d'environnement.
# Utilisé tel quel pour le pre-flight (/health, /v1/models).
# L'API d'inférence attend vllm_api_base = VLLM_BASE_URL + "/v1".
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000")

# Nombre de tentatives (configurable via env)
_MAX_ATTEMPTS = int(os.getenv("CHANDRA_RETRY_ATTEMPTS", "3"))

# Timeout global de l'inférence en secondes (configurable via env).
# Protège contre le blocage infini du client HTTP de Chandra quand vLLM
# est coupé sans fermer proprement ses connexions TCP.
# Valeur par défaut : 4 heures (suffisant pour de très grands documents).
INFERENCE_TIMEOUT_SECONDS = int(os.getenv("CHANDRA_INFERENCE_TIMEOUT", str(4 * 3600)))

# Singleton InferenceManager initialisé au chargement du module.
# Pour la méthode "vllm", __init__ se borne à poser deux attributs (self.method,
# self.model = None) — aucun modèle chargé, coût négligeable.
_manager = InferenceManager(method="vllm")
logger.debug("Chandra | InferenceManager(method='vllm') initialisé")

# Verrou asyncio : sérialise les appels concurrents à run_chandra.
# Justification : vLLM traite les requêtes en série ; le singleton _manager n'est
# pas garanti thread-safe. Un Lock asyncio évite toute contention sans bloquer
# la boucle événementielle FastAPI (les coroutines attendent, pas les threads).
_inference_lock = asyncio.Lock()


class ChandraVllmUnavailableError(RuntimeError):
    """Levée quand le service vLLM n'est pas joignable avant l'inférence."""


def _log_retry(retry_state: RetryCallState) -> None:
    """Callback tenacity : loggue chaque tentative avortée avant de réessayer."""
    exc = retry_state.outcome.exception()
    logger.warning(
        "Chandra | tentative {}/{} échouée ({}) — nouvel essai dans {:.0f}s",
        retry_state.attempt_number,
        _MAX_ATTEMPTS,
        type(exc).__name__,
        retry_state.next_action.sleep,  # type: ignore[union-attr]
    )


def _check_vllm_available() -> None:
    """
    Vérifie synchronement que le service vLLM répond sur VLLM_BASE_URL.
    Appelé dans asyncio.to_thread pour ne pas bloquer la boucle asynchrone.
    Teste /health puis /v1/models en fallback.
    Lève ChandraVllmUnavailableError si aucun des deux endpoints ne répond.
    """
    for endpoint in ("/health", "/v1/models"):
        try:
            resp = httpx.get(f"{VLLM_BASE_URL}{endpoint}", timeout=5.0)
            if resp.status_code < 500:
                logger.debug("vLLM | joignable via {}{}", VLLM_BASE_URL, endpoint)
                return
        except httpx.RequestError:
            continue
    raise ChandraVllmUnavailableError(
        f"Le service vLLM n'est pas joignable sur {VLLM_BASE_URL} "
        "(ni /health ni /v1/models ne répondent)."
    )


@retry(
    stop=stop_after_attempt(_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=2, min=10, max=120),
    # Pas de retry sur le timeout RQ (JobTimeoutException, levée par SIGALRM) : le
    # relancer empêcherait le job de se terminer avant que RQ tue le work-horse.
    retry=retry_if_not_exception_type((ChandraVllmUnavailableError, BaseTimeoutException)),
    before_sleep=_log_retry,
    reraise=True,
)
def _chandra_with_retry(
    pdf_path: str,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> List[BatchOutputItem]:
    """
    Pre-flight vLLM + chargement du PDF + inférence avec retry automatique.
    Retourne la liste des BatchOutputItem (un par page).
    Ne réessaie PAS si ChandraVllmUnavailableError (vLLM absent = inutile d'attendre),
    ni sur un timeout RQ (BaseTimeoutException).

    on_progress(label, step, total) : callback optionnel appelé à chaque étape clé.
    """
    def _progress(label: str, step: int, total: int = 4) -> None:
        if on_progress:
            on_progress(label, step, total)

    _progress("Vérification du service vLLM…", 1)
    _check_vllm_available()

    _progress("Chargement du PDF…", 2)
    t_load = time.monotonic()
    images = load_file(pdf_path, {})
    logger.debug(
        "Chandra | PDF chargé en {:.2f}s | {} page(s) | pdf={}",
        time.monotonic() - t_load,
        len(images),
        pdf_path,
    )

    n = len(images)
    _progress(f"Transcription de {n} page{'s' if n > 1 else ''}…", 3)
    batch = [BatchInputItem(image=img, prompt_type="ocr_layout") for img in images]
    vllm_api_base = VLLM_BASE_URL.rstrip("/") + "/v1"
    logger.debug(
        "Chandra | inférence | {} page(s) | vllm_api_base={}",
        len(batch),
        vllm_api_base,
    )

    t_infer = time.monotonic()
    results: List[BatchOutputItem] = _manager.generate(
        batch, vllm_api_base=vllm_api_base
    )
    logger.debug(
        "Chandra | inférence terminée en {:.1f}s | {} résultat(s)",
        time.monotonic() - t_infer,
        len(results),
    )

    _progress("Assemblage du document…", 4)

    # Vérification des erreurs par page retournées par le vLLM
    page_errors = [(i, r.error) for i, r in enumerate(results) if r.error]
    if page_errors:
        err_summary = "; ".join(f"page {i}: {e}" for i, e in page_errors)
        raise RuntimeError(
            f"Chandra vLLM a retourné des erreurs sur "
            f"{len(page_errors)}/{len(results)} page(s) : {err_summary}"
        )

    return results


async def run_chandra(pdf_path: str, output_dir: str, task_id: Optional[str] = None) -> dict:
    """
    Lance l'inférence Chandra via l'API Python dans un thread séparé pour
    ne pas bloquer la boucle événementielle FastAPI.

    - Pre-flight check vLLM avant toute inférence.
    - Retry automatique (tenacity) sur erreurs transitoires.
    - Lève ChandraVllmUnavailableError si vLLM est absent.
    - Lève RuntimeError si le vLLM retourne des erreurs sur certaines pages.
    - Persiste les fichiers de sortie sur disque (compatibilité avec /ocr/result).
    - Si task_id est fourni, met à jour la progression en base à chaque étape.

    Retourne un dict {markdown, blocks, num_pages, total_token_count, pages}.
    """
    logger.info("Chandra | démarrage | pdf={}", pdf_path)
    logger.debug(
        "Chandra | output_dir={} | vllm={} | max_attempts={}",
        output_dir,
        VLLM_BASE_URL,
        _MAX_ATTEMPTS,
    )
    t0 = time.monotonic()

    # Callback de progression : écrit en base depuis le thread d'inférence.
    # update_task_progress est thread-safe (sqlite3 avec WAL ou connexion par appel).
    if task_id:
        from app.database import update_task_progress
        def _on_progress(label: str, step: int, total: int) -> None:
            update_task_progress(task_id, label, step, total)
    else:
        _on_progress = None  # type: ignore[assignment]

    # Le verrou garantit qu'une seule inférence Chandra tourne à la fois.
    # asyncio.wait_for impose un timeout global contre les blocages HTTP.
    async with _inference_lock:
        logger.debug(
            "Chandra | verrou acquis | timeout={}s | pdf={}",
            INFERENCE_TIMEOUT_SECONDS,
            pdf_path,
        )
        try:
            results: List[BatchOutputItem] = await asyncio.wait_for(
                asyncio.to_thread(_chandra_with_retry, pdf_path, _on_progress),
                timeout=INFERENCE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            raise RuntimeError(
                f"Inférence annulée : délai de {INFERENCE_TIMEOUT_SECONDS}s dépassé "
                "(le service vLLM est peut-être inaccessible ou bloqué)."
            ) from exc

    elapsed = time.monotonic() - t0
    logger.success(
        "Chandra | inférence terminée en {:.1f}s | {} page(s) | pdf={}",
        elapsed,
        len(results),
        pdf_path,
    )

    stem = Path(pdf_path).stem
    # Convention : output_dir/<stem>/ comme le CLI Chandra
    return _assemble_and_persist(stem, results, Path(output_dir) / stem)


def _assemble_and_persist(
    stem: str, results: List[BatchOutputItem], chandra_dir: Path
) -> dict:
    """
    Assemble les résultats par page, extrait les blocs de layout avec bbox normalisées,
    persiste sur disque et retourne le dict.

    Fichiers créés :
      chandra_dir/<stem>.md
      chandra_dir/<stem>_blocks.json
      chandra_dir/<stem>_metadata.json
    """
    chandra_dir.mkdir(parents=True, exist_ok=True)

    blocks: list = []
    for page_idx, result in enumerate(results):
        page_w = result.page_box[2] or 1
        page_h = result.page_box[3] or 1

        if result.chunks:
            for block_idx, chunk in enumerate(result.chunks):
                bbox = chunk["bbox"]
                bbox_norm = [
                    round(bbox[0] / page_w, 4),
                    round(bbox[1] / page_h, 4),
                    round(bbox[2] / page_w, 4),
                    round(bbox[3] / page_h, 4),
                ]
                # parse_markdown attend du HTML avec des <div> de premier niveau ;
                # on enveloppe le contenu intérieur du chunk pour respecter ce contrat.
                block_md = _chandra_parse_md(f"<div>{chunk['content']}</div>").strip()
                blocks.append({
                    "id": f"{page_idx}_{block_idx}",
                    "page": page_idx,
                    "block_index": block_idx,
                    "label": chunk.get("label", "Text"),
                    "bbox_norm": bbox_norm,
                    "markdown": block_md,
                })
        else:
            # Fallback : pas de chunks détectés, bloc synthétique couvrant toute la page
            blocks.append({
                "id": f"{page_idx}_0",
                "page": page_idx,
                "block_index": 0,
                "label": "Text",
                "bbox_norm": [0.0, 0.0, 1.0, 1.0],
                "markdown": result.markdown,
            })

    markdown = "\n\n".join(b["markdown"] for b in blocks if b["markdown"].strip())
    pages = [
        {
            "page_num": i,
            "page_box": r.page_box,
            "token_count": r.token_count,
            "num_blocks": sum(1 for b in blocks if b["page"] == i),
        }
        for i, r in enumerate(results)
    ]
    metadata = {
        "num_pages": len(results),
        "total_token_count": sum(r.token_count for r in results),
        "pages": pages,
    }

    (chandra_dir / f"{stem}.md").write_text(markdown, encoding="utf-8")
    (chandra_dir / f"{stem}_blocks.json").write_text(
        json.dumps(blocks, indent=2), encoding="utf-8"
    )
    (chandra_dir / f"{stem}_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    logger.debug(
        "Chandra | fichiers écrits dans {} | markdown={}c | {} bloc(s) | {} page(s)",
        chandra_dir,
        len(markdown),
        len(blocks),
        len(results),
    )
    return {
        "markdown": markdown,
        "blocks": blocks,
        "num_pages": len(results),
        "total_token_count": metadata["total_token_count"],
        "pages": pages,
    }


def run_chandra_sync(
    pdf_path: str, output_dir: str, task_id: Optional[str] = None
) -> dict:
    """Version synchrone de run_chandra, destinée au worker RQ.

    Appelle directement _chandra_with_retry sans asyncio.to_thread ni asyncio.Lock
    (le worker RQ est single-thread ; il n'y a pas de concurrence à gérer).
    Lève RuntimeError ou ChandraVllmUnavailableError en cas d'échec.
    """
    t0 = time.monotonic()

    if task_id:
        from app.database import update_task_progress

        def _on_progress(label: str, step: int, total: int) -> None:
            update_task_progress(task_id, label, step, total)
    else:
        _on_progress = None  # type: ignore[assignment]

    logger.debug(
        "Chandra (sync) | démarrage | timeout={}s | pdf={}",
        INFERENCE_TIMEOUT_SECONDS,
        pdf_path,
    )
    results: List[BatchOutputItem] = _chandra_with_retry(pdf_path, _on_progress)

    elapsed = time.monotonic() - t0
    logger.success(
        "Chandra (sync) | terminé en {:.1f}s | {} page(s) | pdf={}",
        elapsed,
        len(results),
        pdf_path,
    )

    stem = Path(pdf_path).stem
    return _assemble_and_persist(stem, results, Path(output_dir) / stem)
