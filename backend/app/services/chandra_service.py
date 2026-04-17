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
from typing import List

import httpx
from loguru import logger
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

# Singleton InferenceManager initialisé au chargement du module.
# Pour la méthode "vllm", __init__ se borne à poser deux attributs (self.method,
# self.model = None) — aucun modèle chargé, coût négligeable.
_manager = InferenceManager(method="vllm")
logger.debug("Chandra | InferenceManager(method='vllm') initialisé")


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
    retry=retry_if_not_exception_type(ChandraVllmUnavailableError),
    before_sleep=_log_retry,
    reraise=True,
)
def _chandra_with_retry(pdf_path: str) -> List[BatchOutputItem]:
    """
    Pre-flight vLLM + chargement du PDF + inférence avec retry automatique.
    Retourne la liste des BatchOutputItem (un par page).
    Ne réessaie PAS si ChandraVllmUnavailableError (vLLM absent = inutile d'attendre).
    """
    _check_vllm_available()

    t_load = time.monotonic()
    images = load_file(pdf_path, {})
    logger.debug(
        "Chandra | PDF chargé en {:.2f}s | {} page(s) | pdf={}",
        time.monotonic() - t_load,
        len(images),
        pdf_path,
    )

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

    # Vérification des erreurs par page retournées par le vLLM
    page_errors = [(i, r.error) for i, r in enumerate(results) if r.error]
    if page_errors:
        err_summary = "; ".join(f"page {i}: {e}" for i, e in page_errors)
        raise RuntimeError(
            f"Chandra vLLM a retourné des erreurs sur "
            f"{len(page_errors)}/{len(results)} page(s) : {err_summary}"
        )

    return results


async def run_chandra(pdf_path: str, output_dir: str) -> dict:
    """
    Lance l'inférence Chandra via l'API Python dans un thread séparé pour
    ne pas bloquer la boucle événementielle FastAPI.

    - Pre-flight check vLLM avant toute inférence.
    - Retry automatique (tenacity) sur erreurs transitoires.
    - Lève ChandraVllmUnavailableError si vLLM est absent.
    - Lève RuntimeError si le vLLM retourne des erreurs sur certaines pages.
    - Persiste les fichiers de sortie sur disque (compatibilité avec /ocr/result).

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

    results: List[BatchOutputItem] = await asyncio.to_thread(
        _chandra_with_retry, pdf_path
    )

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
