import { useRef, useCallback, useEffect, useState } from "react";
import { Worker, Viewer } from "@react-pdf-viewer/core";
import { defaultLayoutPlugin } from "@react-pdf-viewer/default-layout";
import "@react-pdf-viewer/core/lib/styles/index.css";
import "@react-pdf-viewer/default-layout/lib/styles/index.css";

// Worker résolu localement par Vite — évite le chargement cross-origin depuis unpkg
// qui bloquerait l'accès aux blob URLs sous Firefox.
const WORKER_URL = new URL(
  "pdfjs-dist/build/pdf.worker.min.js",
  import.meta.url
).href;

interface PDFPanelProps {
  pdfBlob: Blob;
  onScrollRatioChange?: (ratio: number) => void;
  scrollRatio?: number;
}

/**
 * Visualiseur PDF haute résolution basé sur @react-pdf-viewer.
 * - Le blob est converti en Uint8Array pour éviter les restrictions
 *   de sécurité sur les blob URLs dans les workers cross-origin.
 * - Le worker est référencé localement (pdfjs-dist dans node_modules).
 */
export function PDFPanel({ pdfBlob, onScrollRatioChange }: PDFPanelProps) {
  const defaultLayout = defaultLayoutPlugin();
  const containerRef = useRef<HTMLDivElement>(null);

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
    >
      <Worker workerUrl={WORKER_URL}>
        <Viewer fileUrl={pdfData} plugins={[defaultLayout]} />
      </Worker>
    </div>
  );
}
