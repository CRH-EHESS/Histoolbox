/**
 * Client HTTP pour l'API FastAPI.
 * En dev, Vite proxie /ocr/* vers http://localhost:8001.
 * En prod, VITE_API_URL permet de cibler un backend distant.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

const TOKEN_KEY = "histoolbox_api_key";

/** Lit le token stocké dans localStorage (null si absent). */
export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

/** Persiste le token dans localStorage. */
export function storeToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

/** Supprime le token stocké (logout). */
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getStoredToken();
  return token ? { "X-API-Key": token } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`[${res.status}] ${detail}`);
  }
  return res.json() as Promise<T>;
}

export type TaskStatus = "pending" | "processing" | "completed" | "error";

export interface UploadResponse {
  task_id: string;
}

export interface StatusResponse {
  task_id: string;
  status: TaskStatus;
  error_message: string | null;
  created_at: number;
  updated_at: number;
}

export interface BlockItem {
  id: string;           // "{page}_{block_index}"
  page: number;         // 0-indexed
  block_index: number;
  label: string;        // "Text" | "Table" | "Image" | "Figure" | "Page-Header" | …
  bbox_norm: number[];  // [x1, y1, x2, y2] normalisé dans [0, 1]
  markdown: string;
}

export interface PageInfo {
  page_num: number;
  page_box: number[];   // [0, 0, width_px, height_px]
  token_count: number;
  num_blocks: number;
}

export interface ResultResponse {
  task_id: string;
  filename: string;
  created_at: number;
  completed_at: number;
  markdown: string;
  blocks: BlockItem[];
  num_pages: number;
  total_token_count: number;
  pages: PageInfo[];
}

/**
 * Type normalisé pour la vue historique — outil-agnostique.
 * Chaque tool mappe ses propres données vers cette interface.
 */
export interface HistoryItem {
  id: string;
  /** Libellé affiché dans la liste (ex : nom du fichier). */
  label: string;
  status: TaskStatus;
  createdAt: number;
  /** Route vers laquelle naviguer pour recharger ce traitement. */
  reloadPath: string;
}

export const api = {
  uploadPdf(file: File): Promise<UploadResponse> {
    const form = new FormData();
    form.append("file", file);
    return request<UploadResponse>("/ocr/upload", { method: "POST", body: form });
  },

  getStatus(taskId: string): Promise<StatusResponse> {
    return request<StatusResponse>(`/ocr/status/${taskId}`);
  },

  getResult(taskId: string): Promise<ResultResponse> {
    return request<ResultResponse>(`/ocr/result/${taskId}`);
  },
};
