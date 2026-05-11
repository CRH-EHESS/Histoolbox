import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { HistoryItem, TaskStatus } from "../lib/apiClient";

interface HistoryPageProps {
  title: string;
  items: HistoryItem[];
  loading?: boolean;
  onDelete: (id: string) => Promise<void>;
}

const STATUS_BADGE: Record<TaskStatus, { label: string; classes: string }> = {
  completed:  { label: "Terminé",    classes: "bg-green-100 text-green-800" },
  processing: { label: "En cours",   classes: "bg-blue-100 text-blue-800 animate-pulse" },
  pending:    { label: "En attente", classes: "bg-stone-100 text-stone-600" },
  error:      { label: "Erreur",     classes: "bg-red-100 text-red-700" },
};

function StatusBadge({ status }: { status: TaskStatus }) {
  const { label, classes } = STATUS_BADGE[status];
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${classes}`}>
      {label}
    </span>
  );
}

/**
 * Vue historique générique — affiche une liste de HistoryItem.
 * Chaque tool fournit ses propres items via un adapter (page mince).
 */
export function HistoryPage({ title, items, loading = false, onDelete }: HistoryPageProps) {
  const navigate = useNavigate();
  // id en attente de confirmation de suppression
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function handleDelete(id: string) {
    if (pendingDeleteId !== id) {
      // Premier clic → demande confirmation
      setPendingDeleteId(id);
      return;
    }
    // Second clic → suppression effective
    setDeletingId(id);
    setPendingDeleteId(null);
    try {
      await onDelete(id);
    } finally {
      setDeletingId(null);
    }
  }

  function handleCancelDelete() {
    setPendingDeleteId(null);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-8 h-8 rounded-full border-4 border-stone-200 border-t-stone-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-3xl mx-auto px-8 py-10">
        <h1 className="text-xl font-bold mb-6">{title}</h1>

        {items.length === 0 ? (
          <div className="text-center py-20 text-stone-400">
            <div className="text-4xl mb-3">🗂️</div>
            <p className="text-sm">Aucun traitement enregistré.</p>
          </div>
        ) : (
          <ul className="space-y-2">
            {items.map((item) => {
              const isConfirming = pendingDeleteId === item.id;
              const isDeleting = deletingId === item.id;

              return (
                <li
                  key={item.id}
                  className="flex items-center gap-4 rounded-lg border border-stone-200 bg-white px-4 py-3 shadow-sm"
                >
                  {/* Libellé + date */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{item.label}</p>
                    <p className="text-xs text-stone-400 mt-0.5">
                      {new Date(item.createdAt).toLocaleString("fr-FR", {
                        day: "2-digit",
                        month: "2-digit",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>

                  {/* Badge statut */}
                  <StatusBadge status={item.status} />

                  {/* Actions */}
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => navigate(item.reloadPath)}
                      className="text-xs px-3 py-1.5 rounded-md border border-stone-300 hover:bg-stone-50 transition-colors"
                    >
                      Ouvrir
                    </button>

                    {isConfirming ? (
                      <>
                        <button
                          onClick={() => handleDelete(item.id)}
                          disabled={isDeleting}
                          className="text-xs px-3 py-1.5 rounded-md bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-50"
                        >
                          Confirmer
                        </button>
                        <button
                          onClick={handleCancelDelete}
                          className="text-xs px-3 py-1.5 rounded-md border border-stone-300 hover:bg-stone-50 transition-colors"
                        >
                          Annuler
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => handleDelete(item.id)}
                        disabled={isDeleting}
                        className="text-xs px-3 py-1.5 rounded-md text-red-600 border border-red-200 hover:bg-red-50 transition-colors disabled:opacity-50"
                      >
                        Supprimer
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
