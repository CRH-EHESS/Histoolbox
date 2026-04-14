import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { SplitView } from "../components/SplitView";
import { PDFPanel } from "../components/PDFPanel";
import { MarkdownEditor } from "../components/MarkdownEditor";
import { useAutoSave } from "../hooks/useAutoSave";
import { getProjectById } from "../db";
import type { OCRProject } from "../db";
import { exportMarkdown, exportDocx } from "../lib/exportUtils";

/**
 * Toolbox principale : PDF à gauche, éditeur Markdown à droite.
 * - Auto-save vers IndexedDB (debounce 1s).
 * - Export .md et .docx.
 * - Sync-scroll par ratio de progression.
 */
export function OCRToolboxPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<OCRProject | null>(null);
  const [content, setContent] = useState("");

  useAutoSave(taskId ?? null, content);

  // Chargement initial depuis IndexedDB
  useEffect(() => {
    if (!taskId) return;
    getProjectById(taskId).then((p) => {
      if (!p) { navigate("/"); return; }
      setProject(p);
      setContent(p.markdownContent);
    });
  }, [taskId, navigate]);

  const handleScrollRatio = useCallback(
    (_ratio: number) => {
      // TODO Phase 7 complète : synchroniser le scroll de l'éditeur
    },
    []
  );

  if (!project) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-8 h-8 rounded-full border-4 border-stone-200 border-t-stone-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Barre d'outils */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-stone-200 bg-white">
        <span className="text-sm font-medium text-stone-700 flex-1 truncate">
          {project.fileName}
        </span>
        <button
          onClick={() => exportMarkdown(content, project.fileName)}
          className="text-xs px-3 py-1.5 rounded-md border border-stone-300 hover:bg-stone-50 transition-colors"
        >
          Exporter .md
        </button>
        <button
          onClick={() => exportDocx(content, project.fileName)}
          className="text-xs px-3 py-1.5 rounded-md border border-stone-300 hover:bg-stone-50 transition-colors"
        >
          Exporter .docx
        </button>
      </div>

      {/* Split view */}
      <div className="flex-1 overflow-hidden">
        <SplitView
          left={
            <PDFPanel
              pdfBlob={project.pdfBlob}
              onScrollRatioChange={handleScrollRatio}
            />
          }
          right={
            <MarkdownEditor value={content} onChange={setContent} />
          }
        />
      </div>
    </div>
  );
}
