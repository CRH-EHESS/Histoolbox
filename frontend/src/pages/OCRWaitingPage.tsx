import { useNavigate, useParams } from "react-router-dom";
import { usePolling } from "../hooks/usePolling";

/** Étapes fixes du pipeline Chandra — correspondent aux progress_step 1-4 du backend. */
const STEPS = [
  "Vérification du service vLLM",
  "Chargement du PDF",
  "Transcription en cours",
  "Assemblage du document",
] as const;

type StepState = "done" | "active" | "pending";

function StepIcon({ state }: { state: StepState }) {
  if (state === "done")
    return (
      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-stone-700 text-white text-sm">
        ✓
      </span>
    );
  if (state === "active")
    return (
      <span className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-stone-600 border-t-transparent animate-spin" />
    );
  return (
    <span className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-stone-200 text-stone-300 text-sm">
      ○
    </span>
  );
}

/**
 * Page d'attente pendant le traitement Chandra.
 * Affiche une progression étape par étape synchronisée avec le backend.
 */
export function OCRWaitingPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const { status, errorMessage, progressStep } = usePolling(taskId ?? null);

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

  // Étape courante : null / 0 → aucune info encore (en attente du premier poll)
  const currentStep = progressStep ?? 0;

  return (
    <div className="flex flex-col items-center justify-center h-full gap-8 text-center p-8">
      <div>
        <h1 className="text-xl font-semibold mb-1">Transcription en cours…</h1>
        <p className="text-stone-500 text-sm max-w-sm">
          Chandra analyse votre document. Vous pouvez fermer cet onglet — le
          résultat sera automatiquement récupéré à votre retour.
        </p>
      </div>

      {/* Liste des étapes */}
      <ol className="flex flex-col gap-3 w-full max-w-xs text-left">
        {STEPS.map((label, idx) => {
          const stepNum = idx + 1; // 1-indexed, correspond à progress_step
          const state: StepState =
            currentStep > stepNum
              ? "done"
              : currentStep === stepNum
              ? "active"
              : "pending";

          return (
            <li key={label} className="flex items-center gap-3">
              <StepIcon state={state} />
              <span
                className={
                  state === "done"
                    ? "text-stone-700 text-sm"
                    : state === "active"
                    ? "text-stone-900 text-sm font-medium"
                    : "text-stone-300 text-sm"
                }
              >
                {label}
              </span>
            </li>
          );
        })}
      </ol>

      <p className="text-xs text-stone-300 font-mono">{taskId}</p>
    </div>
  );
}
