/**
 * Base de données locale IndexedDB via Dexie.js
 *
 * Table `ocr_projects` : stocke chaque projet OCR avec son PDF (Blob),
 * la transcription Markdown, et les métadonnées de statut.
 */

import Dexie, { type EntityTable } from "dexie";
import type { BlockItem, PageInfo, TaskStatus } from "../lib/apiClient";

export type { TaskStatus };

/** Représente un projet OCR complet stocké localement. */
export interface OCRProject {
  /** task_id retourné par le backend FastAPI */
  id: string;
  fileName: string;
  /** Fichier PDF original — conservé dans IndexedDB pour le viewer */
  pdfBlob: Blob;
  /** Transcription Markdown éditée par l'utilisateur */
  markdownContent: string;
  status: TaskStatus;
  createdAt: number;
  updatedAt: number;
  /** Blocs de layout extraits par Chandra (bbox normalisées, label, markdown) */
  blocks?: BlockItem[];
  /** Informations par page (dimensions, token count) */
  pages?: PageInfo[];
}

class HistoolboxDB extends Dexie {
  ocr_projects!: EntityTable<OCRProject, "id">;

  constructor() {
    super("HistoolboxDB");
    this.version(1).stores({
      // Index : id (PK), status (pour le recovery au démarrage)
      ocr_projects: "id, status, createdAt",
    });
    // v2 : ajout des champs blocks/pages (optionnels, aucune migration nécessaire)
    this.version(2).stores({
      ocr_projects: "id, status, createdAt",
    });
  }
}

export const db = new HistoolboxDB();

// ─── Helpers CRUD ────────────────────────────────────────────────────────────

export async function createProject(
  project: Omit<OCRProject, "createdAt" | "updatedAt">
): Promise<void> {
  const now = Date.now();
  await db.ocr_projects.add({ ...project, createdAt: now, updatedAt: now });
}

export async function updateProject(
  id: string,
  changes: Partial<Omit<OCRProject, "id" | "createdAt">>
): Promise<void> {
  await db.ocr_projects.update(id, { ...changes, updatedAt: Date.now() });
}

export async function getProjectById(
  id: string
): Promise<OCRProject | undefined> {
  return db.ocr_projects.get(id);
}

export async function getAllProjects(): Promise<OCRProject[]> {
  return db.ocr_projects.orderBy("createdAt").reverse().toArray();
}

/** Retourne toutes les tâches dont le statut correspond (utile pour le recovery). */
export async function getProjectsByStatus(
  status: TaskStatus
): Promise<OCRProject[]> {
  return db.ocr_projects.where("status").equals(status).toArray();
}
