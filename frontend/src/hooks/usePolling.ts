/**
 * Hook usePolling — interroge GET /ocr/status/:taskId toutes les 5 secondes.
 *
 * - Nettoie l'intervalle au démontage du composant.
 * - À `completed` : récupère le résultat, met à jour IndexedDB, navigue vers la toolbox.
 * - À `error` : met à jour IndexedDB, s'arrête et retourne le message d'erreur.
 * - Utilisé aussi par le mécanisme de recovery au démarrage de l'app.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/apiClient";
import { updateProject } from "../db";

const POLL_INTERVAL_MS = 5_000;

export interface PollingState {
  status: "pending" | "processing" | "completed" | "error" | null;
  errorMessage: string | null;
}

/** Nombre d'erreurs réseau consécutives avant d'abandonner le polling. */
const MAX_CONSECUTIVE_ERRORS = 3;

export function usePolling(taskId: string | null): PollingState {
  const navigate = useNavigate();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const consecutiveErrors = useRef(0);
  const [pollingState, setPollingState] = useState<PollingState>({
    status: null,
    errorMessage: null,
  });

  const stop = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const poll = useCallback(async () => {
    if (!taskId) return;
    try {
      const { status, error_message } = await api.getStatus(taskId);
      consecutiveErrors.current = 0; // réinitialise le compteur sur tout appel réussi
      setPollingState({ status, errorMessage: error_message });

      if (status === "completed") {
        stop();
        const result = await api.getResult(taskId);
        await updateProject(taskId, {
          markdownContent: result.markdown,
          status: "completed",
          blocks: result.blocks,
          pages: result.pages,
        });
        navigate(`/ocr/toolbox/${taskId}`);
      } else if (status === "error") {
        stop();
        await updateProject(taskId, { status: "error" });
      }
    } catch {
      // Erreur réseau : on tolère jusqu'à MAX_CONSECUTIVE_ERRORS erreurs consécutives
      // (transitoires : coupure réseau, redémarrage du backend…).
      // Au-delà, on arrête le polling et on surface l'erreur à l'utilisateur.
      consecutiveErrors.current += 1;
      if (consecutiveErrors.current >= MAX_CONSECUTIVE_ERRORS) {
        stop();
        setPollingState({
          status: "error",
          errorMessage: "Le serveur est inaccessible après plusieurs tentatives.",
        });
        if (taskId) await updateProject(taskId, { status: "error" });
      }
    }
  }, [taskId, navigate, stop]);

  useEffect(() => {
    if (!taskId) return;
    // Premier appel immédiat, puis toutes les POLL_INTERVAL_MS
    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return stop;
  }, [taskId, poll, stop]);

  return pollingState;
}
