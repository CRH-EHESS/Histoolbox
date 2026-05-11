/**
 * Registre des tools de la Histoolbox.
 *
 * Ajouter un tool = créer un fichier src/tools/<mon-tool>.tsx,
 * puis ajouter son entrée dans le tableau `tools` ci-dessous.
 * App.tsx, HomePage et AppShell sont génériques et n'ont pas à être modifiés.
 */

import type { ComponentType } from "react";
import type { RouteObject } from "react-router-dom";

export interface ToolDefinition {
  /** Identifiant unique (utilisé comme clé React). */
  id: string;
  /** Emoji ou chemin vers une icône. */
  icon: string;
  /** Libellé affiché dans la nav et sur la carte. */
  label: string;
  /** Description courte affichée sur la carte d'accueil. */
  description: string;
  /** Route d'entrée principale (utilisée pour la carte et le lien de nav). */
  entryPath: string;
  /** Routes React Router déclarées par ce tool. */
  routes: RouteObject[];
  /** Si false, la carte est affichée en mode "bientôt disponible". */
  available: boolean;
  /**
   * Route vers la page historique du tool (optionnel).
   * Si présent, un lien "Historique" est affiché dans la nav à côté du tool.
   */
  historyPath?: string;
  /**
   * Composant null-render monté au démarrage de l'app (dans le BrowserRouter).
   * Permet à chaque tool de déclarer sa propre logique de recovery/initialisation
   * sans coupler le shell à la logique métier du tool.
   */
  Recovery?: ComponentType;
}

// Chargement différé pour éviter les imports circulaires et garder App.tsx léger.
// Chaque tool est importé ici comme seule source de vérité.
import { ocrTool } from "./ocr";

export const tools: ToolDefinition[] = [
  ocrTool,
  // Futurs tools :
  // classificationTool,
  // alignmentTool,
];
