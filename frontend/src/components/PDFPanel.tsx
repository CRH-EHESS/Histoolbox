import { useRef, useCallback, useEffect, useState, forwardRef, useImperativeHandle } from "react";
import { Worker, Viewer } from "@react-pdf-viewer/core";
import type { RenderPageProps } from "@react-pdf-viewer/core";
import { defaultLayoutPlugin } from "@react-pdf-viewer/default-layout";
import "@react-pdf-viewer/core/lib/styles/index.css";
import "@react-pdf-viewer/default-layout/lib/styles/index.css";
import { BlockOverlay } from "./BlockOverlay";
import type { BlockItem } from "../lib/apiClient";

// Worker résolu localement par Vite — évite le chargement cross-origin depuis unpkg
// qui bloquerait l'accès aux blob URLs sous Firefox.
const WORKER_URL = new URL(
  "pdfjs-dist/build/pdf.worker.min.js",
  import.meta.url
).href;

export interface PDFPanelHandle {
  jumpToPage: (pageIndex: number) => void;
}

interface PDFPanelProps {
  pdfBlob: Blob;
  onScrollRatioChange?: (ratio: number) => void;
  blocks?: BlockItem[];
  hoveredBlockId?: string | null;
  onBlockHover?: (id: string | null) => void;
  onBlockClick?: (id: string) => void;
}

/**
 * Visualiseur PDF haute résolution basé sur @react-pdf-viewer.
 * - Expose jumpToPage via forwardRef pour la navigation inter-panneaux.
 * - Affiche BlockOverlay sur chaque page quand la souris survole le panneau.
 */
export const PDFPanel = forwardRef<PDFPanelHandle, PDFPanelProps>(function PDFPanel(
  { pdfBlob, onScrollRatioChange, blocks = [], hoveredBlockId = null, onBlockHover, onBlockClick },
  ref
) {
  // defaultLayoutPlugin appelle des hooks React en interne — doit rester au top-level du composant
  const defaultLayout = defaultLayoutPlugin();
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPanelHovered, setIsPanelHovered] = useState(false);

  useImperativeHandle(ref, () => ({
    jumpToPage(pageIndex: number) {
      defaultLayout.toolbarPluginInstance.pageNavigationPluginInstance.jumpToPage(pageIndex);
    },
  }));

  // Convertir le blob en Uint8Array — pas de blob URL, pas de restriction worker
  const [pdfData, setPdfData] = useState<Uint8Array | null>(null);
  useEffect(() => {
    let cancelled = false;
    pdfBlob.arrayBuffer().then((buf) => {
      if (!cancelled) setPdfData(new Uint8Array(buf));
    });
    return () => { cancelled = true; };
  }, [pdfBlob]);

  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    const el = containerRef.current;
    const max = el.scrollHeight - el.clientHeight;
    if (max > 0) onScrollRatioChange?.(el.scrollTop / max);
  }, [onScrollRatioChange]);

  /** renderPage : injecte BlockOverlay (invisible hors survol du panneau). */
  const renderPage = useCallback(
    (props: RenderPageProps) => (
      <>
        {props.canvasLayer.children}
        {props.textLayer.children}
        {props.annotationLayer.children}
        {isPanelHovered && blocks.length > 0 && (
          <BlockOverlay
            pageIndex={props.pageIndex}
            width={props.width}
            height={props.height}
            blocks={blocks}
            hoveredBlockId={hoveredBlockId}
            onBlockHover={onBlockHover ?? (() => {})}
            onBlockClick={onBlockClick ?? (() => {})}
          />
        )}
      </>
    ),
    [isPanelHovered, blocks, hoveredBlockId, onBlockHover, onBlockClick]
  );

  if (!pdfData) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-8 h-8 rounded-full border-4 border-stone-200 border-t-stone-600 animate-spin" />
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="h-full overflow-auto"
      onScroll={handleScroll}
      onMouseEnter={() => setIsPanelHovered(true)}
      onMouseLeave={() => setIsPanelHovered(false)}
    >
      <Worker workerUrl={WORKER_URL}>
        <Viewer
          fileUrl={pdfData}
          plugins={[defaultLayout]}
          renderPage={renderPage}
        />
      </Worker>
    </div>
  );
});
