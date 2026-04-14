import { useCallback, useRef } from "react";

interface DropZoneProps {
  onFile: (file: File) => void;
  disabled?: boolean;
}

/**
 * Zone de dépôt PDF (drag & drop + clic).
 * Filtre strictement les fichiers .pdf.
 */
export function DropZone({ onFile, disabled = false }: DropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const file = files[0];
      if (file.type !== "application/pdf") {
        alert("Seuls les fichiers PDF sont acceptés.");
        return;
      }
      onFile(file);
    },
    [onFile]
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
        Glissez votre fichier PDF ici
      </p>
      <p className="text-stone-400 text-sm">ou cliquez pour parcourir</p>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  );
}
