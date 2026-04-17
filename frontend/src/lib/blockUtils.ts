import type { BlockItem } from "./apiClient";

/** Retourne les blocs appartenant à une page donnée (0-indexé). */
export function getBlocksByPage(blocks: BlockItem[], pageIndex: number): BlockItem[] {
  return blocks.filter((b) => b.page === pageIndex);
}

/**
 * Calcule les offsets (from, to) en caractères du bloc dans le markdown
 * global concaténé par "\n\n" (convention identique à _assemble_and_persist).
 *
 * Retourne null si le bloc n'est pas trouvé.
 */
export function getBlockCharRange(
  blocks: BlockItem[],
  blockId: string
): { from: number; to: number } | null {
  let offset = 0;
  for (const block of blocks) {
    const len = block.markdown.length;
    if (block.id === blockId) {
      return { from: offset, to: offset + len };
    }
    // +2 pour le "\n\n" séparateur (sauf pour les blocs vides)
    offset += len + (len > 0 ? 2 : 0);
  }
  return null;
}
