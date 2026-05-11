import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { SplitView } from "../components/SplitView";
import { PDFPanel, type PDFPanelHandle } from "../components/PDFPanel";
import { MarkdownEditor } from "../components/MarkdownEditor";
import { useAutoSave } from "../hooks/useAutoSave";
import { getProjectById, updateProject } from "../db";
import type { OCRProject } from "../db";
import { exportMarkdown, exportDocx } from "../lib/exportUtils";
import { api } from "../lib/apiClient";
import type { BlockItem } from "../lib/apiClient";

/**
 * Toolbox principale : PDF à gauche, éditeur Markdown à droite.
 * - Auto-save vers IndexedDB (debounce 1s).
 * - Export .md et .docx.
 * - Visualisation des blocs de layout (hover PDF ↔ highlight Markdown, clic bidirectionnel).
 */
export function OCRToolboxPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<OCRProject | null>(null);
  const [content, setContent] = useState("");
  const [blocks, setBlocks] = useState<BlockItem[]>([]);
  const [hoveredBlockId, setHoveredBlockId] = useState<string | null>(null);
  const pdfPanelRef = useRef<PDFPanelHandle>(null);

  useAutoSave(taskId ?? null, content);

  // Chargement initial depuis IndexedDB
  useEffect(() => {
    if (!taskId) return;
    getProjectById(taskId).then(async (p) => {
      if (!p) { navigate("/"); return; }
      setProject(p);
      setContent(p.markdownContent);

      if (p.blocks && p.blocks.length > 0) {
        // Blocs déjà en cache IndexedDB
        setBlocks(p.blocks);
      } else {
        // Fallback : récupère les blocs depuis l'API (projets avant v2 IndexedDB)
        try {
          const result = await api.getResult(taskId);
          if (result.blocks?.length > 0) {
            setBlocks(result.blocks);
            await updateProject(taskId, { blocks: result.blocks, pages: result.pages });
          }
        } catch {
          // Blocs non disponibles — fonctionnement dégradé sans overlay
        }
      }
    });
  }, [taskId, navigate]);

  // ── Handlers inter-panneaux ───────────────────────────────────────────────

  const handleBlockHover = useCallback((id: string | null) => {
    setHoveredBlockId(id);
  }, []);

  /** Clic depuis le Markdown → le PDF saute à la page du bloc. */
  const handleBlockClickFromMarkdown = useCallback((id: string) => {
    setHoveredBlockId(id);
    const block = blocks.find((b) => b.id === id);
    if (block !== undefined) {
      pdfPanelRef.current?.jumpToPage(block.page);
    }
  }, [blocks]);

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
              ref={pdfPanelRef}
              pdfBlob={project.pdfBlob}
              blocks={blocks}
              hoveredBlockId={hoveredBlockId}
              onBlockHover={handleBlockHover}
              onBlockClick={setHoveredBlockId}
            />
          }
          right={
            <MarkdownEditor
              value={content}
              onChange={setContent}
              blocks={blocks}
              hoveredBlockId={hoveredBlockId}
              onBlockHover={handleBlockHover}
              onBlockClick={handleBlockClickFromMarkdown}
            />
          }
        />
      </div>
    </div>
  );
}
