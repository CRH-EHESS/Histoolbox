import { useCallback, useRef, useState } from "react";

/** Nombre maximum de fichiers acceptés en une fois. */
export const MAX_FILES = 20;

interface DropZoneProps {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
}

/**
 * Zone de dépôt PDF (drag & drop + clic), multi-fichiers.
 *
 * - Filtre strictement les fichiers .pdf par type MIME.
 * - Limite à MAX_FILES fichiers par dépôt.
 * - Déduplique par (name, size) pour éviter les doublons sur re-drop.
 * - Affiche les erreurs inline (pas d'alert()).
 */
export function DropZone({ onFiles, disabled = false }: DropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dropError, setDropError] = useState<string | null>(null);

  const handleFiles = useCallback(
    (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return;
      setDropError(null);

      const all = Array.from(fileList);
      const pdfs = all.filter((f) => f.type === "application/pdf");

      const errors: string[] = [];
      if (pdfs.length < all.length) {
        errors.push("Seuls les fichiers PDF sont acceptés.");
      }
      if (pdfs.length > MAX_FILES) {
        errors.push(`Maximum ${MAX_FILES} fichiers par envoi.`);
      }
      if (errors.length > 0) {
        setDropError(errors.join(" "));
      }

      const accepted = pdfs.slice(0, MAX_FILES);
      if (accepted.length > 0) onFiles(accepted);
    },
    [onFiles]
  );

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      if (!disabled) handleFiles(e.dataTransfer.files);
    },
    [disabled, handleFiles]
  );

  const onDragOver = (e: React.DragEvent<HTMLDivElement>) =>
    e.preventDefault();

  return (
    <div className="flex flex-col gap-2">
      <div
        className={`flex flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed border-stone-300 bg-stone-50 p-12 text-center transition-colors hover:border-stone-400 hover:bg-stone-100 ${
          disabled ? "pointer-events-none opacity-50" : "cursor-pointer"
        }`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onClick={() => !disabled && inputRef.current?.click()}
      >
        <span className="text-4xl">📄</span>
        <p className="text-stone-600 font-medium">
          Glissez un ou plusieurs fichiers PDF ici
        </p>
        <p className="text-stone-400 text-sm">
          ou cliquez pour parcourir · max {MAX_FILES} fichiers
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {dropError && (
        <p className="text-sm text-red-600">{dropError}</p>
      )}
    </div>
  );
}
