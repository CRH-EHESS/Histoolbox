import type { BlockItem } from "../lib/apiClient";
import { getBlocksByPage } from "../lib/blockUtils";

/** Couleur par label Chandra. */
function labelColor(label: string): { border: string; bg: string } {
  switch (label) {
    case "Text":
      return { border: "rgba(59,130,246,0.8)", bg: "rgba(59,130,246,0.15)" };
    case "Section-Header":
    case "Page-Header":
      return { border: "rgba(139,92,246,0.8)", bg: "rgba(139,92,246,0.15)" };
    case "Table":
      return { border: "rgba(34,197,94,0.8)", bg: "rgba(34,197,94,0.15)" };
    case "Figure":
    case "Image":
      return { border: "rgba(249,115,22,0.8)", bg: "rgba(249,115,22,0.15)" };
    default:
      return { border: "rgba(100,116,139,0.8)", bg: "rgba(100,116,139,0.15)" };
  }
}

interface BlockOverlayProps {
  pageIndex: number;
  /** Dimensions réelles du viewport de la page (en px) */
  width: number;
  height: number;
  blocks: BlockItem[];
  hoveredBlockId: string | null;
  onBlockHover: (id: string | null) => void;
  onBlockClick: (id: string) => void;
}

/**
 * Overlay SVG/div superposé sur une page du viewer PDF.
 * Le conteneur est pointer-events:none ; chaque bloc est pointer-events:auto.
 * Affiche un contour léger au repos, fond coloré au survol / quand actif.
 */
export function BlockOverlay({
  pageIndex,
  width,
  height,
  blocks,
  hoveredBlockId,
  onBlockHover,
  onBlockClick,
}: BlockOverlayProps) {
  const pageBlocks = getBlocksByPage(blocks, pageIndex);

  if (pageBlocks.length === 0) return null;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        zIndex: 10,
      }}
    >
      {pageBlocks.map((block) => {
        const [x1n, y1n, x2n, y2n] = block.bbox_norm;
        const left = x1n * width;
        const top = y1n * height;
        const w = (x2n - x1n) * width;
        const h = (y2n - y1n) * height;
        const { border, bg } = labelColor(block.label);
        const isActive = hoveredBlockId === block.id;

        return (
          <div
            key={block.id}
            title={`[${block.label}] ${block.markdown.slice(0, 60)}…`}
            style={{
              position: "absolute",
              left,
              top,
              width: w,
              height: h,
              border: `${isActive ? 2 : 1}px solid ${border}`,
              backgroundColor: isActive ? bg : "transparent",
              borderRadius: 2,
              cursor: "pointer",
              pointerEvents: "auto",
              transition: "background-color 0.1s, border-width 0.1s",
              boxSizing: "border-box",
            }}
            onMouseEnter={() => onBlockHover(block.id)}
            onMouseLeave={() => onBlockHover(null)}
            onClick={() => onBlockClick(block.id)}
          />
        );
      })}
    </div>
  );
}
