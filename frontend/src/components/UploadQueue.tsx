/**
 * Composant de présentation pure — file d'upload locale.
 *
 * Aucun appel API ni logique d'état ici : tout est piloté par la page parente
 * (OCRUploadPage) via les props.
 */

/** Statut local d'un item en attente d'upload. */
export type UploadItemStatus = "ready" | "uploading" | "queued" | "error";

/** Représente un fichier ajouté à la file locale avant envoi au backend. */
export interface PendingUploadItem {
  /** Identifiant local temporaire (crypto.randomUUID). */
  localId: string;
  file: File;
  status: UploadItemStatus;
  errorMessage?: string;
  /** Progression de l'upload par chunks (absent pour les petits fichiers < 5 Mo). */
  uploadProgress?: { sent: number; total: number };
}

interface UploadQueueProps {
  items: PendingUploadItem[];
  /** Vrai pendant la séquence d'envoi — désactive le bouton de suppression. */
  submitting: boolean;
  onRemove: (localId: string) => void;
}

/** Formate une taille en octets en chaîne lisible (ex : "14,2 Mo"). */
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

const STATUS_ICON: Record<UploadItemStatus, string> = {
  ready: "⏳",
  uploading: "🔄",
  queued: "✅",
  error: "❌",
};

/**
 * Liste les fichiers ajoutés à la file locale.
 * Chaque ligne affiche le nom, la taille, le statut, et un bouton de retrait
 * (désactivé pendant l'envoi ou une fois le fichier accepté).
 */
export function UploadQueue({ items, submitting, onRemove }: UploadQueueProps) {
  return (
    <ul className="mt-4 flex flex-col gap-2">
      {items.map((item) => {
        const canRemove = !submitting && item.status !== "queued";
        return (
          <li
            key={item.localId}
            className="flex items-center gap-3 rounded-lg border border-stone-200 bg-white px-4 py-3 text-sm"
          >
            <span
              className={`text-base ${item.status === "uploading" ? "animate-spin" : ""}`}
              aria-hidden="true"
            >
              {STATUS_ICON[item.status]}
            </span>

            <div className="flex-1 min-w-0">
              <p className="truncate font-medium text-stone-800">{item.file.name}</p>
              <p className="text-stone-400 text-xs">{formatSize(item.file.size)}</p>
              {item.status === "uploading" && item.uploadProgress && item.uploadProgress.total > 1 && (
                <div className="mt-1">
                  <div className="h-1 w-full rounded-full bg-stone-100 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-stone-500 transition-all duration-200"
                      style={{ width: `${Math.round((item.uploadProgress.sent / item.uploadProgress.total) * 100)}%` }}
                    />
                  </div>
                  <p className="text-stone-400 text-xs mt-0.5">
                    {item.uploadProgress.sent}/{item.uploadProgress.total} chunks
                  </p>
                </div>
              )}
              {item.status === "error" && item.errorMessage && (
                <p className="text-red-600 text-xs mt-0.5">{item.errorMessage}</p>
              )}
            </div>

            <button
              type="button"
              onClick={() => onRemove(item.localId)}
              disabled={!canRemove}
              className="shrink-0 text-stone-400 hover:text-stone-600 disabled:pointer-events-none disabled:opacity-30 transition-colors"
              aria-label={`Retirer ${item.file.name}`}
            >
              ✕
            </button>
          </li>
        );
      })}
    </ul>
  );
}
