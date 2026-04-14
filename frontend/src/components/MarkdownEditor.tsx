import { useState, useMemo } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { markdown } from "@codemirror/lang-markdown";
import { oneDark } from "@codemirror/theme-one-dark";
import { marked } from "marked";
import DOMPurify from "dompurify";

interface MarkdownEditorProps {
  value: string;
  onChange: (value: string) => void;
}

/**
 * Éditeur Markdown avec toggle source / aperçu.
 * - Source : CodeMirror 6 avec coloration syntaxique.
 * - Aperçu : HTML rendu par marked, assaini par DOMPurify (OWASP XSS).
 */
export function MarkdownEditor({ value, onChange }: MarkdownEditorProps) {
  const [preview, setPreview] = useState(false);

  const previewHtml = useMemo(() => {
    if (!preview) return "";
    const raw = marked.parse(value) as string;
    return DOMPurify.sanitize(raw);
  }, [preview, value]);

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Barre toggle */}
      <div className="flex gap-1 px-3 py-1.5 border-b border-stone-200 bg-white shrink-0">
        <button
          className={`text-xs px-3 py-1 rounded-md transition-colors ${
            !preview
              ? "bg-stone-800 text-white"
              : "text-stone-500 hover:bg-stone-100"
          }`}
          onClick={() => setPreview(false)}
        >
          Source
        </button>
        <button
          className={`text-xs px-3 py-1 rounded-md transition-colors ${
            preview
              ? "bg-stone-800 text-white"
              : "text-stone-500 hover:bg-stone-100"
          }`}
          onClick={() => setPreview(true)}
        >
          Aperçu
        </button>
      </div>

      {/* Contenu */}
      {preview ? (
        <div
          className="flex-1 overflow-auto p-6 bg-[#fdfbf7] text-[#262626]
            [&_h1]:text-2xl [&_h1]:font-bold [&_h1]:mb-4 [&_h1]:mt-6
            [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:mb-3 [&_h2]:mt-5
            [&_h3]:text-lg [&_h3]:font-semibold [&_h3]:mb-2 [&_h3]:mt-4
            [&_p]:mb-3 [&_p]:leading-relaxed
            [&_strong]:font-semibold
            [&_em]:italic
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
            [&_td]:border [&_td]:border-stone-300 [&_td]:px-3 [&_td]:py-1.5"
          dangerouslySetInnerHTML={{ __html: previewHtml }}
        />
      ) : (
        <div className="flex-1 overflow-auto font-mono text-sm">
          <CodeMirror
            value={value}
            height="100%"
            extensions={[markdown()]}
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
    </div>
  );
}
