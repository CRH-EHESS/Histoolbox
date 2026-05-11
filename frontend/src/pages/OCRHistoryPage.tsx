import { useState, useEffect, useCallback } from "react";
import { HistoryPage } from "../components/HistoryPage";
import { getAllProjects, db } from "../db";
import type { HistoryItem } from "../lib/apiClient";

/** Mappe un OCRProject vers un HistoryItem générique. */
function toHistoryItem(project: { id: string; fileName: string; status: import("../lib/apiClient").TaskStatus; createdAt: number }): HistoryItem {
  const reloadPath =
    project.status === "completed"
      ? `/ocr/toolbox/${project.id}`
      : `/ocr/waiting/${project.id}`;

  return {
    id: project.id,
    label: project.fileName,
    status: project.status,
    createdAt: project.createdAt,
    reloadPath,
  };
}

/** Page historique du tool OCR — adapter entre OCRProject et HistoryPage. */
export function OCRHistoryPage() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const projects = await getAllProjects();
    setItems(projects.map(toHistoryItem));
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleDelete(id: string) {
    await db.ocr_projects.delete(id);
    setItems((prev) => prev.filter((item) => item.id !== id));
  }

  return (
    <HistoryPage
      title="Historique OCR & Transcription"
      items={items}
      loading={loading}
      onDelete={handleDelete}
    />
  );
}
