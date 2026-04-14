/**
 * Hook useAutoSave — sauvegarde le contenu Markdown dans IndexedDB
 * avec un debounce de 1 seconde pour éviter des écritures trop fréquentes.
 */

import { useEffect, useRef } from "react";
import { updateProject } from "../db";

const DEBOUNCE_MS = 1_000;

export function useAutoSave(taskId: string | null, content: string) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!taskId) return;

    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
    }

    timerRef.current = setTimeout(() => {
      updateProject(taskId, { markdownContent: content });
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current !== null) clearTimeout(timerRef.current);
    };
  }, [taskId, content]);
}
