"""
Service Chandra : invoque le CLI `chandra <pdf_path> <output_dir> --method vllm`
en subprocess non-bloquant (asyncio.to_thread) et lit les fichiers produits.

Chandra (vLLM) crée un sous-répertoire output_dir/<stem>/ contenant :
  <stem>.md
  <stem>.html
  <stem>_metadata.json
"""

import asyncio
import json
import subprocess
from pathlib import Path


async def run_chandra(pdf_path: str, output_dir: str) -> dict:
    """
    Lance `chandra pdf_path output_dir --method vllm` dans un thread séparé
    pour ne pas bloquer la boucle événementielle FastAPI.

    Retourne un dict {markdown, html, metadata} ou lève une exception.
    """
    await asyncio.to_thread(
        subprocess.run,
        ["chandra", pdf_path, output_dir, "--method", "vllm"],
        check=True,          # lève CalledProcessError si code retour != 0
        capture_output=True,
    )
    stem = Path(pdf_path).stem
    # Chandra crée output_dir/<stem>/ comme répertoire de sortie effectif
    return _read_outputs(stem, Path(output_dir) / stem)


def _read_outputs(stem: str, output_dir: Path) -> dict:
    """Lit les trois fichiers produits par Chandra et retourne leur contenu."""
    md_file = output_dir / f"{stem}.md"
    html_file = output_dir / f"{stem}.html"
    meta_file = output_dir / f"{stem}_metadata.json"

    markdown = md_file.read_text(encoding="utf-8") if md_file.exists() else ""
    html = html_file.read_text(encoding="utf-8") if html_file.exists() else ""
    metadata: dict = {}
    if meta_file.exists():
        metadata = json.loads(meta_file.read_text(encoding="utf-8"))

    return {"markdown": markdown, "html": html, "metadata": metadata}
