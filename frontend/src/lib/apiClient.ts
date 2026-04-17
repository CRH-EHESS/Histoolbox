/**
 * Client HTTP pour l'API FastAPI.
 * En dev, Vite proxie /ocr/* vers http://localhost:8001.
 * En prod, VITE_API_URL permet de cibler un backend distant.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, init);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`[${res.status}] ${detail}`);
  }
  return res.json() as Promise<T>;
}

export interface UploadResponse {
  task_id: string;
}

export interface StatusResponse {
  task_id: string;
  status: "pending" | "processing" | "completed" | "error";
  error_message: string | null;
}

export interface ResultResponse {
  task_id: string;
  markdown: string;
  html: string;
  metadata: Record<string, unknown>;
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
