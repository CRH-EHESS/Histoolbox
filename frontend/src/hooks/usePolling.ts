/**
 * Hook usePolling — interroge GET /ocr/status/:taskId toutes les 5 secondes.
 *
 * - Nettoie l'intervalle au démontage du composant.
 * - À `completed` : récupère le résultat, met à jour IndexedDB, navigue vers la toolbox.
 *   Le polling continue tant que le résultat n'a pas pu être récupéré.
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
  progressStep: number | null;
  progressTotal: number | null;
  progressLabel: string | null;
  queuePosition: number | null;
}

/** Nombre de tours de polling consécutifs en échec avant d'abandonner. */
const MAX_CONSECUTIVE_ERRORS = 3;

/** Icône des notifications, sous le base path (GitHub Pages sert l'app sous /<repo>/). */
const NOTIFICATION_ICON = `${import.meta.env.BASE_URL}icon-192.png`;

/**
 * Notification navigateur si la permission est accordée. Ne doit jamais faire
 * échouer le polling : le constructeur lève une exception là où seul un service
 * worker peut notifier (Chrome Android).
 */
function notifyCompletion(): void {
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
  try {
    new Notification("Transcription terminée !", {
      body: "Votre document est prêt.",
      icon: NOTIFICATION_ICON,
    });
  } catch {
    // Notification indisponible : l'utilisateur est de toute façon redirigé vers la toolbox.
  }
}

export function usePolling(taskId: string | null): PollingState {
  const navigate = useNavigate();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const consecutiveErrors = useRef(0);
  const [pollingState, setPollingState] = useState<PollingState>({
    status: null,
    errorMessage: null,
    progressStep: null,
    progressTotal: null,
    progressLabel: null,
    queuePosition: null,
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
      const { status, error_message, progress_step, progress_total, progress_label, queue_position } = await api.getStatus(taskId);
      setPollingState({
        status,
        errorMessage: error_message,
        progressStep: progress_step,
        progressTotal: progress_total,
        progressLabel: progress_label,
        queuePosition: queue_position,
      });

      if (status === "completed") {
        // Le polling ne s'arrête qu'après un getResult réussi : en cas d'échec,
        // le tick suivant retente au lieu de laisser la page d'attente bloquée.
        const result = await api.getResult(taskId);
        await updateProject(taskId, {
          markdownContent: result.markdown,
          status: "completed",
          blocks: result.blocks,
          pages: result.pages,
        });
        stop();
        notifyCompletion();
        navigate(`/ocr/toolbox/${taskId}`);
      } else if (status === "error") {
        stop();
        await updateProject(taskId, { status: "error" });
      }
      consecutiveErrors.current = 0; // réinitialise le compteur sur tout tour réussi
    } catch {
      // Erreur réseau (getStatus ou getResult) : on tolère jusqu'à MAX_CONSECUTIVE_ERRORS
      // tours consécutifs en échec (transitoires : coupure réseau, redémarrage du backend…).
      // Au-delà, on arrête le polling et on surface l'erreur à l'utilisateur.
      consecutiveErrors.current += 1;
      if (consecutiveErrors.current >= MAX_CONSECUTIVE_ERRORS) {
        stop();
        setPollingState({
          status: "error",
          errorMessage: "Le serveur est inaccessible après plusieurs tentatives.",
          progressStep: null,
          progressTotal: null,
          progressLabel: null,
          queuePosition: null,
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
