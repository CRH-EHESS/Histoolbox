import { useRef, useState, useCallback, type ReactNode } from "react";

interface SplitViewProps {
  left: ReactNode;
  right: ReactNode;
}

/**
 * Panneau divisé avec séparateur draggable.
 * - Mobile (< md) : empilé verticalement, PDF 45 % / éditeur 55 %.
 * - Desktop (md+) : côte à côte, draggable entre 25 % et 75 %.
 */
export function SplitView({ left, right }: SplitViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [leftPercent, setLeftPercent] = useState(48);
  const dragging = useRef(false);

  const onPointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    dragging.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, []);

  const onPointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging.current || !containerRef.current) return;
    const { left: containerLeft, width } =
      containerRef.current.getBoundingClientRect();
    const newPercent = ((e.clientX - containerLeft) / width) * 100;
    // Min 25 % / Max 75 % pour que chaque panneau garde une largeur lisible
    setLeftPercent(Math.min(75, Math.max(25, newPercent)));
  }, []);

  const onPointerUp = useCallback(() => {
    dragging.current = false;
  }, []);

  return (
    <div
      ref={containerRef}
      className="flex flex-col md:flex-row h-full w-full overflow-hidden"
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      {/* Panneau gauche / haut */}
      <div
        className="overflow-auto h-[45%] md:h-full"
        style={{ flex: `0 0 ${leftPercent}%` }}
      >
        {left}
      </div>

      {/* Séparateur — visible uniquement en desktop */}
      <div
        className="
          hidden md:flex
          w-1.5 h-full cursor-col-resize flex-shrink-0
          bg-stone-200 hover:bg-stone-400 transition-colors select-none
          items-center justify-center
        "
        onPointerDown={onPointerDown}
      />

      {/* Séparateur horizontal — mobile seulement */}
      <div className="md:hidden h-px bg-stone-200 shrink-0" />

      {/* Panneau droit / bas */}
      <div className="flex-1 overflow-auto min-h-0">
        {right}
      </div>
    </div>
  );
}
