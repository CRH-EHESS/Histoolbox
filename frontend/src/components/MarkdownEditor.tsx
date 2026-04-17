import { useState, useMemo, useEffect, useRef } from "react";
import CodeMirror, { type ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { StateEffect, StateField } from "@codemirror/state";
import { Decoration, EditorView, type DecorationSet } from "@codemirror/view";
import { markdown } from "@codemirror/lang-markdown";
import { oneDark } from "@codemirror/theme-one-dark";
import { marked } from "marked";
import DOMPurify from "dompurify";
import type { BlockItem } from "../lib/apiClient";
import { getBlockCharRange } from "../lib/blockUtils";

type ViewMode = "source" | "preview" | "json";

// ─── CodeMirror extension : surbrillance du bloc actif ───────────────────────

const setActiveRange = StateEffect.define<{ from: number; to: number } | null>();

const activeBlockField = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(deco, tr) {
    deco = deco.map(tr.changes);
    for (const effect of tr.effects) {
      if (effect.is(setActiveRange)) {
        if (effect.value) {
          const { from, to } = effect.value;
          // Clamp to document length
          const docLen = tr.newDoc.length;
          const clampedFrom = Math.min(from, docLen);
          const clampedTo = Math.min(to, docLen);
          if (clampedFrom < clampedTo) {
            deco = Decoration.set([
              Decoration.mark({ class: "cm-active-block" }).range(clampedFrom, clampedTo),
            ]);
          } else {
            deco = Decoration.none;
          }
        } else {
          deco = Decoration.none;
        }
      }
    }
    return deco;
  },
  provide: (f) => EditorView.decorations.from(f),
});

const activeBlockTheme = EditorView.baseTheme({
  ".cm-active-block": {
    backgroundColor: "rgba(250, 204, 21, 0.25)",  // yellow-400 / 25%
    borderRadius: "2px",
  },
});

// ─── Couleur de fond pour les blocs en mode Aperçu ───────────────────────────

function blockBgColor(label: string, active: boolean): string {
  const alpha = active ? "0.18" : "0";
  switch (label) {
    case "Text":              return `rgba(59,130,246,${alpha})`;
    case "Section-Header":
    case "Page-Header":       return `rgba(139,92,246,${alpha})`;
    case "Table":             return `rgba(34,197,94,${alpha})`;
    case "Figure":
    case "Image":             return `rgba(249,115,22,${alpha})`;
    default:                  return `rgba(100,116,139,${alpha})`;
  }
}

// ─── Composant MarkdownEditor ─────────────────────────────────────────────────

interface MarkdownEditorProps {
  value: string;
  onChange: (value: string) => void;
  blocks?: BlockItem[];
  hoveredBlockId?: string | null;
  onBlockHover?: (id: string | null) => void;
  onBlockClick?: (id: string) => void;
}

/**
 * Éditeur Markdown avec trois onglets : Source / Aperçu / JSON.
 * - Source : CodeMirror 6 avec surbrillance du bloc actif.
 * - Aperçu : blocs originaux Chandra rendus individuellement (cohérence bbox).
 * - JSON   : structure complète des blocs extraits.
 */
export function MarkdownEditor({
  value,
  onChange,
  blocks = [],
  hoveredBlockId = null,
  onBlockHover,
  onBlockClick,
}: MarkdownEditorProps) {
  const [mode, setMode] = useState<ViewMode>("source");
  const cmRef = useRef<ReactCodeMirrorRef>(null);

  const hasBlocks = blocks.length > 0;

  // ── Surbrillance CodeMirror quand hoveredBlockId change ──────────────────
  useEffect(() => {
    const view = cmRef.current?.view;
    if (!view) return;

    const range = hoveredBlockId ? getBlockCharRange(blocks, hoveredBlockId) : null;
    view.dispatch({ effects: setActiveRange.of(range) });

    if (range) {
      // Scroll vers le début du bloc
      const from = Math.min(range.from, view.state.doc.length);
      view.dispatch({ effects: EditorView.scrollIntoView(from, { y: "nearest" }) });
    }
  }, [hoveredBlockId, blocks]);

  // ── Rendu Aperçu (full markdown, utilisé quand pas de blocs) ──────────────
  const previewHtml = useMemo(() => {
    if (mode !== "preview" || hasBlocks) return "";
    const raw = marked.parse(value) as string;
    return DOMPurify.sanitize(raw);
  }, [mode, value, hasBlocks]);

  const PROSE_CLASSES = `flex-1 overflow-auto p-6 bg-[#fdfbf7] text-[#262626]
    [&_h1]:text-2xl [&_h1]:font-bold [&_h1]:mb-4 [&_h1]:mt-6
    [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:mb-3 [&_h2]:mt-5
    [&_h3]:text-lg [&_h3]:font-semibold [&_h3]:mb-2 [&_h3]:mt-4
    [&_p]:mb-3 [&_p]:leading-relaxed
    [&_strong]:font-semibold [&_em]:italic
    [&_ul]:list-disc [&_ul]:ml-5 [&_ul]:mb-3
    [&_ol]:list-decimal [&_ol]:ml-5 [&_ol]:mb-3
    [&_li]:mb-1
    [&_code]:font-mono [&_code]:bg-stone-100 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-sm
    [&_pre]:bg-stone-100 [&_pre]:p-4 [&_pre]:rounded-lg [&_pre]:overflow-auto [&_pre]:mb-3
    [&_blockquote]:border-l-4 [&_blockquote]:border-stone-300 [&_blockquote]:pl-4 [&_blockquote]:text-stone-600 [&_blockquote]:italic [&_blockquote]:mb-3
    [&_hr]:border-stone-200 [&_hr]:my-6
    [&_a]:text-blue-700 [&_a]:underline
    [&_table]:w-full [&_table]:border-collapse [&_table]:mb-3
    [&_th]:border [&_th]:border-stone-300 [&_th]:px-3 [&_th]:py-1.5 [&_th]:bg-stone-100 [&_th]:text-left
    [&_td]:border [&_td]:border-stone-300 [&_td]:px-3 [&_td]:py-1.5`;

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Barre d'onglets */}
      <div className="flex gap-1 px-3 py-1.5 border-b border-stone-200 bg-white shrink-0">
        {(["source", "preview", ...(hasBlocks ? ["json"] : [])] as ViewMode[]).map((m) => (
          <button
            key={m}
            className={`text-xs px-3 py-1 rounded-md transition-colors capitalize ${
              mode === m
                ? "bg-stone-800 text-white"
                : "text-stone-500 hover:bg-stone-100"
            }`}
            onClick={() => setMode(m)}
          >
            {m === "source" ? "Source" : m === "preview" ? "Aperçu" : "JSON"}
          </button>
        ))}
      </div>

      {/* ── Source ──────────────────────────────────────────────────────── */}
      {mode === "source" && (
        <div className="flex-1 overflow-auto font-mono text-sm">
          <CodeMirror
            ref={cmRef}
            value={value}
            height="100%"
            extensions={[markdown(), activeBlockField, activeBlockTheme]}
            theme={oneDark}
            onChange={onChange}
            basicSetup={{
              lineNumbers: true,
              highlightActiveLine: true,
              foldGutter: false,
            }}
          />
        </div>
      )}

      {/* ── Aperçu avec blocs ────────────────────────────────────────────── */}
      {mode === "preview" && hasBlocks && (
        <div className={PROSE_CLASSES}>
          {blocks.map((block) => {
            const isActive = hoveredBlockId === block.id;
            const blockHtml = DOMPurify.sanitize(marked.parse(block.markdown) as string);
            return (
              <div
                key={block.id}
                data-block-id={block.id}
                style={{
                  backgroundColor: blockBgColor(block.label, isActive),
                  borderRadius: 3,
                  transition: "background-color 0.15s",
                  cursor: "pointer",
                  padding: isActive ? "2px 4px" : undefined,
                  marginBottom: 2,
                }}
                onMouseEnter={() => onBlockHover?.(block.id)}
                onMouseLeave={() => onBlockHover?.(null)}
                onClick={() => onBlockClick?.(block.id)}
                dangerouslySetInnerHTML={{ __html: blockHtml }}
              />
            );
          })}
        </div>
      )}

      {/* ── Aperçu sans blocs (fallback markdown brut) ──────────────────── */}
      {mode === "preview" && !hasBlocks && (
        <div
          className={PROSE_CLASSES}
          dangerouslySetInnerHTML={{ __html: previewHtml }}
        />
      )}

      {/* ── JSON ─────────────────────────────────────────────────────────── */}
      {mode === "json" && hasBlocks && (
        <div className="flex-1 overflow-auto bg-[#fdfbf7] p-4">
          <pre className="text-xs font-mono text-stone-700 whitespace-pre-wrap break-words">
            {JSON.stringify(blocks, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

