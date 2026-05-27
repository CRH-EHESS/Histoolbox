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
      if (processing.length === 0) return;

      const stillProcessingIds: string[] = [];

      for (const project of processing) {
        try {
          const { status } = await api.getStatus(project.id);
          if (status === "completed") {
            const result = await api.getResult(project.id);
            await updateProject(project.id, {
              markdownContent: result.markdown,
              status: "completed",
            });
            // Naviguer vers la toolbox uniquement si l'utilisateur était
            // déjà sur la page d'attente de cette tâche spécifique.
            if (currentPath.includes(project.id)) {
              navigate(`/ocr/toolbox/${project.id}`);
              return; // une seule navigation à la fois
            }
          } else if (status === "error") {
            await updateProject(project.id, { status: "error" });
          } else {
            stillProcessingIds.push(project.id);
          }
        } catch {
          // Backend inaccessible — on conserve la tâche en processing
          stillProcessingIds.push(project.id);
        }
      }

      // Navigation uniquement si l'utilisateur n'est pas déjà sur une page d'attente.
      // Plusieurs tâches en cours : l'historique est le point d'entrée le plus neutre.
      if (currentPath.startsWith("/ocr/waiting/")) return;
      if (stillProcessingIds.length === 1) {
        navigate(`/ocr/waiting/${stillProcessingIds[0]}`);
      } else if (stillProcessingIds.length > 1) {
        navigate("/ocr/history");
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
