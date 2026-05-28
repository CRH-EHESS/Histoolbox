import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { DropZone } from "../components/DropZone";
import { UploadQueue, type PendingUploadItem } from "../components/UploadQueue";
import { api } from "../lib/apiClient";
import { db, createProject } from "../db";

/**
 * Page d'upload PDF — supporte un ou plusieurs fichiers.
 *
 * Comportement post-envoi :
 * - 1 fichier → navigation vers /ocr/waiting/:taskId
 * - 2+ fichiers → navigation vers /ocr/history (statuts visibles dans l'historique)
 * - Tout échoué → reste sur la page, erreurs affichées dans la file
 */
export function OCRUploadPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<PendingUploadItem[]>([]);
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  /** Ajoute les fichiers déposés à la file locale (pas encore envoyés). */
  function handleFiles(files: File[]) {
    const newItems: PendingUploadItem[] = files.map((f) => ({
      localId: `${f.name}-${f.size}-${Date.now()}-${Math.random()}`,
      file: f,
      status: "ready",
    }));
    setItems((prev) => [...prev, ...newItems]);
  }

  function handleRemove(localId: string) {
    setItems((prev) => prev.filter((i) => i.localId !== localId));
  }

  function handleClear() {
    setItems([]);
    setGlobalError(null);
  }

  /**
   * Envoie les fichiers au backend un par un (séquentiel intentionnel :
   * évite de saturer le backend et préserve l'ordre visuel).
   */
  async function handleSubmit() {
    if (items.length === 0 || submitting) return;
    setSubmitting(true);
    setGlobalError(null);

    const launched: string[] = [];

    for (const item of items) {
      if (item.status === "queued") {
        // Déjà envoyé (re-soumission partielle après erreur) — on le compte.
        continue;
      }

      setItems((prev) =>
        prev.map((i) =>
          i.localId === item.localId ? { ...i, status: "uploading" } : i
        )
      );

      const tempId = `local-${Date.now()}-${Math.random()}`;
      try {
        // 1. Sauvegarder en IndexedDB avant l'appel réseau
        await createProject({
          id: tempId,
          fileName: item.file.name,
          pdfBlob: item.file,
          markdownContent: "",
          status: "pending",
        });

        // 2. Envoyer au backend
        const { task_id } = await api.uploadPdf(
          item.file,
          email.trim() || undefined
        );

        // 3. Remplacer l'entrée temporaire par le vrai task_id
        //    (Dexie ne supporte pas le rename de PK)
        await db.ocr_projects.delete(tempId);
        await createProject({
          id: task_id,
          fileName: item.file.name,
          pdfBlob: item.file,
          markdownContent: "",
          status: "pending",
        });

        launched.push(task_id);
        setItems((prev) =>
          prev.map((i) =>
            i.localId === item.localId ? { ...i, status: "queued" } : i
          )
        );
      } catch (err) {
        await db.ocr_projects.delete(tempId).catch(() => {});
        const msg =
          err instanceof Error ? err.message : "Erreur lors de l'envoi.";
        setItems((prev) =>
          prev.map((i) =>
            i.localId === item.localId
              ? { ...i, status: "error", errorMessage: msg }
              : i
          )
        );
      }
    }

    setSubmitting(false);

    if (launched.length === 1) {
      navigate(`/ocr/waiting/${launched[0]}`);
    } else if (launched.length > 1) {
      navigate("/ocr/history");
    }
    // Si launched.length === 0 : tout a échoué → les erreurs restent visibles
  }

  const hasReady = items.some(
    (i) => i.status === "ready" || i.status === "error"
  );

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold mb-2">OCR & Transcription diplomatique</h1>
      <p className="text-stone-500 mb-6 text-sm">
        Déposez un ou plusieurs documents PDF. Ils sont conservés localement et
        traités par le moteur Chandra.
        <br />
        <span className="text-stone-400">
          Pour de grands volumes (plus de {20} fichiers), utilisez le client CLI.
        </span>
      </p>

      <DropZone onFiles={handleFiles} disabled={submitting} />

      {items.length > 0 && (
        <>
          <UploadQueue
            items={items}
            submitting={submitting}
            onRemove={handleRemove}
          />

          <div className="mt-4">
            <label
              htmlFor="notify-email"
              className="block text-sm text-stone-700 mb-1"
            >
              Être notifié par email à la fin du traitement (optionnel)
            </label>
            <input
              id="notify-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="historien@exemple.fr"
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-stone-400"
              disabled={submitting}
            />
          </div>

          <div className="mt-4 flex gap-3">
            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitting || !hasReady}
              className="rounded-lg bg-stone-800 px-5 py-2 text-sm font-medium text-white hover:bg-stone-700 disabled:opacity-50 disabled:pointer-events-none transition-colors"
            >
              {submitting
                ? "Envoi en cours…"
                : items.length === 1
                ? "Lancer la transcription"
                : `Lancer les ${items.length} transcriptions`}
            </button>

            {!submitting && (
              <button
                type="button"
                onClick={handleClear}
                className="rounded-lg border border-stone-300 px-4 py-2 text-sm text-stone-600 hover:bg-stone-50 transition-colors"
              >
                Vider la liste
              </button>
            )}
          </div>
        </>
      )}

      {globalError && (
        <p className="mt-4 text-sm text-red-600">{globalError}</p>
      )}
    </div>
  );
}
