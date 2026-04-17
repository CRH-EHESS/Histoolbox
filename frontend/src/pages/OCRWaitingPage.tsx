import { useNavigate, useParams } from "react-router-dom";
import { usePolling } from "../hooks/usePolling";

/**
 * Page d'attente pendant le traitement Chandra.
 * usePolling gère l'intervalle et la navigation automatique.
 */
export function OCRWaitingPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const { status, errorMessage } = usePolling(taskId ?? null);

  if (status === "error") {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-6 text-center p-8">
        <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
          <span className="text-red-600 text-2xl">✕</span>
        </div>
        <div>
          <h1 className="text-xl font-semibold mb-1 text-red-700">Échec du traitement</h1>
          <p className="text-stone-500 text-sm max-w-sm">
            {errorMessage ?? "Une erreur est survenue lors de la transcription."}
          </p>
        </div>
        <button
          onClick={() => navigate("/")}
          className="px-4 py-2 bg-stone-800 text-white rounded-lg text-sm hover:bg-stone-700 transition-colors"
        >
          Retour à l'accueil
        </button>
        <p className="text-xs text-stone-300 font-mono">{taskId}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 text-center p-8">
      {/* Spinner */}
      <div className="w-12 h-12 rounded-full border-4 border-stone-200 border-t-stone-600 animate-spin" />

      <div>
        <h1 className="text-xl font-semibold mb-1">Transcription en cours…</h1>
        <p className="text-stone-500 text-sm max-w-sm">
          Chandra analyse votre document. Cette opération peut prendre plusieurs
          minutes. Vous pouvez fermer cet onglet — le traitement continuera et
          le résultat sera automatiquement récupéré à votre retour.
        </p>
      </div>

      <p className="text-xs text-stone-300 font-mono">{taskId}</p>
    </div>
  );
}
