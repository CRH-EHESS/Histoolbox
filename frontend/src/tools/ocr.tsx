/**
 * Définition du tool OCR & Transcription diplomatique.
 *
 * Ce fichier est la seule source de vérité pour :
 * - les métadonnées affichées dans la nav et sur la carte d'accueil,
 * - les routes React Router du tool,
 * - la logique de recovery au démarrage (OCRRecovery).
 */

import { useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { OCRUploadPage } from "../pages/OCRUploadPage";
import { OCRWaitingPage } from "../pages/OCRWaitingPage";
import { OCRToolboxPage } from "../pages/OCRToolboxPage";
import { OCRHistoryPage } from "../pages/OCRHistoryPage";
import { getProjectsByStatus, updateProject } from "../db";
import { api } from "../lib/apiClient";
import type { ToolDefinition } from "./registry";

/**
 * Composant null-render : au démarrage de l'app, vérifie les tâches OCR
 * encore en statut `processing` dans IndexedDB et reprend le polling ou
 * navigue vers la toolbox si le traitement est déjà terminé.
 */
function OCRRecovery() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  // Capture le pathname au montage — la recovery ne doit tourner qu'une seule fois.
  const initialPathname = useRef(pathname);

  useEffect(() => {
    const currentPath = initialPathname.current;
    async function recover() {
      const processing = await getProjectsByStatus("processing");
      for (const project of processing) {
        try {
          const { status } = await api.getStatus(project.id);
          if (status === "completed") {
            const result = await api.getResult(project.id);
            await updateProject(project.id, {
              markdownContent: result.markdown,
              status: "completed",
            });
            if (currentPath.includes(project.id)) {
              navigate(`/ocr/toolbox/${project.id}`);
            }
          } else if (status === "error") {
            await updateProject(project.id, { status: "error" });
          } else {
            // Toujours en cours → naviguer vers la page d'attente pour relancer le poll
            if (!currentPath.includes(project.id)) {
              navigate(`/ocr/waiting/${project.id}`);
            }
          }
        } catch {
          // Backend inaccessible — on laisse la tâche en processing
        }
      }
    }
    recover();
  }, [navigate]); // navigate est stable → l'effet ne tourne qu'une seule fois au montage

  return null;
}

export const ocrTool: ToolDefinition = {
  id: "ocr",
  icon: "🔍",
  label: "OCR & Transcription",
  description:
    "Transcription diplomatique de documents manuscrits et imprimés anciens via le moteur Chandra.",
  entryPath: "/ocr/upload",
  historyPath: "/ocr/history",
  available: true,
  Recovery: OCRRecovery,
  routes: [
    { path: "/ocr/upload", element: <OCRUploadPage /> },
    { path: "/ocr/waiting/:taskId", element: <OCRWaitingPage /> },
    { path: "/ocr/toolbox/:taskId", element: <OCRToolboxPage /> },
    { path: "/ocr/history", element: <OCRHistoryPage /> },
  ],
};
