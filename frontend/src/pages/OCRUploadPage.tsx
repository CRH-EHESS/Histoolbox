import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { DropZone } from "../components/DropZone";
import { api } from "../lib/apiClient";
import { db, createProject } from "../db";

/** Page d'upload PDF — crée le projet IndexedDB et démarre la tâche backend. */
export function OCRUploadPage() {
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setUploading(true);
    setError(null);
    const tempId = `local-${Date.now()}`;
    try {
      // 1. Stocker le PDF en local avant tout appel réseau
      await createProject({
        id: tempId,
        fileName: file.name,
        pdfBlob: file,
        markdownContent: "",
        status: "pending",
      });

      // 2. Envoyer au backend
      const { task_id } = await api.uploadPdf(file);

      // 3. Mettre à jour l'entrée avec le vrai task_id
      //    (Dexie ne supporte pas le rename de PK, on recrée l'entrée)
      await db.ocr_projects.delete(tempId);
      await createProject({
        id: task_id,
        fileName: file.name,
        pdfBlob: file,
        markdownContent: "",
        status: "pending",
      });

      navigate(`/ocr/waiting/${task_id}`);
    } catch (err) {
      // Nettoyage de l'entrée temporaire si l'upload backend a échoué
      await db.ocr_projects.delete(tempId).catch(() => {});
      setError(err instanceof Error ? err.message : "Erreur lors de l'envoi.");
      setUploading(false);
    }
  }

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold mb-2">OCR & Transcription diplomatique</h1>
      <p className="text-stone-500 mb-6 text-sm">
        Déposez un document PDF. Il sera conservé localement et traité par le
        moteur Chandra.
      </p>

      <DropZone onFile={handleFile} disabled={uploading} />

      {uploading && (
        <p className="mt-4 text-center text-stone-500 text-sm animate-pulse">
          Envoi en cours…
        </p>
      )}
      {error && (
        <p className="mt-4 text-center text-red-600 text-sm">{error}</p>
      )}
    </div>
  );
}
