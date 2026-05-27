import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { usePolling } from "../hooks/usePolling";

// Moquer api et updateProject — pas de vrai réseau ni IndexedDB dans ces tests
vi.mock("../lib/apiClient", () => ({
  api: {
    getStatus: vi.fn(),
    getResult: vi.fn(),
  },
}));

vi.mock("../db", () => ({
  updateProject: vi.fn().mockResolvedValue(undefined),
}));

import { api } from "../lib/apiClient";
import { updateProject } from "../db";

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter initialEntries={["/ocr/waiting/task-42"]}>{children}</MemoryRouter>;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  class MockNotification {
    static permission = "granted";
    constructor(_title: string, _options?: NotificationOptions) {}
  }
  vi.stubGlobal("Notification", MockNotification);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("usePolling", () => {
  it("appelle getStatus immédiatement au montage", async () => {
    vi.mocked(api.getStatus).mockResolvedValue({
      task_id: "task-42", status: "processing",
      error_message: null, created_at: 0, updated_at: 0,
      progress_step: null, progress_total: null, progress_label: null,
      queue_position: 1,
    });

    renderHook(() => usePolling("task-42"), { wrapper });
    // Flush les microtasks (le premier poll() est appelé sans timer)
    await act(async () => { await Promise.resolve(); });

    expect(api.getStatus).toHaveBeenCalledTimes(1);
    expect(api.getStatus).toHaveBeenCalledWith("task-42");
  });

  it("rappelle getStatus après l'intervalle de 5s", async () => {
    vi.mocked(api.getStatus).mockResolvedValue({
      task_id: "task-42", status: "processing",
      error_message: null, created_at: 0, updated_at: 0,
      progress_step: null, progress_total: null, progress_label: null,
      queue_position: 1,
    });

    renderHook(() => usePolling("task-42"), { wrapper });
    await act(async () => { await Promise.resolve(); });
    expect(api.getStatus).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(5000);
      await Promise.resolve();
    });
    expect(api.getStatus).toHaveBeenCalledTimes(2);
  });

  it("appelle updateProject avec status=completed et le markdown", async () => {
    vi.mocked(api.getStatus).mockResolvedValue({
      task_id: "task-42", status: "completed",
      error_message: null, created_at: 0, updated_at: 1,
      progress_step: 4, progress_total: 4, progress_label: "Assemblage du document…",
      queue_position: null,
    });
    vi.mocked(api.getResult).mockResolvedValue({
      task_id: "task-42",
      filename: "doc.pdf",
      created_at: 0,
      completed_at: 1,
      markdown: "# Résultat",
      blocks: [],
      num_pages: 1,
      total_token_count: 10,
      pages: [],
    });

    renderHook(() => usePolling("task-42"), { wrapper });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve(); // deux ticks pour getStatus + getResult
    });

    expect(updateProject).toHaveBeenCalledWith("task-42", {
      markdownContent: "# Résultat",
      status: "completed",
      blocks: [],
      pages: [],
    });
  });

  it("appelle updateProject avec status=error en cas d'erreur", async () => {
    vi.mocked(api.getStatus).mockResolvedValue({
      task_id: "task-42", status: "error",
      error_message: "vLLM error", created_at: 0, updated_at: 1,
      progress_step: null, progress_total: null, progress_label: null,
      queue_position: null,
    });

    renderHook(() => usePolling("task-42"), { wrapper });
    await act(async () => { await Promise.resolve(); });

    expect(updateProject).toHaveBeenCalledWith("task-42", { status: "error" });
  });

  it("ne plante pas si taskId est null", () => {
    expect(() => renderHook(() => usePolling(null), { wrapper })).not.toThrow();
    expect(api.getStatus).not.toHaveBeenCalled();
  });

  // -------------------------------------------------------------------------
  // Gestion des erreurs réseau consécutives (Bug 2)
  // -------------------------------------------------------------------------

  it("arrête le polling et passe à error après 3 erreurs réseau consécutives", async () => {
    vi.mocked(api.getStatus).mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => usePolling("task-42"), { wrapper });

    // Poll 1 : immédiat
    await act(async () => { await Promise.resolve(); });
    // Poll 2 : +5s
    await act(async () => { vi.advanceTimersByTime(5000); await Promise.resolve(); });
    // Poll 3 : +10s — 3e erreur consécutive, déclenche l'abandon
    await act(async () => { vi.advanceTimersByTime(5000); await Promise.resolve(); });

    expect(result.current.status).toBe("error");
    expect(result.current.errorMessage).toMatch(/inaccessible/);
    expect(updateProject).toHaveBeenCalledWith("task-42", { status: "error" });
  });

  it("n'arrête pas le polling avant 3 erreurs consécutives", async () => {
    vi.mocked(api.getStatus).mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => usePolling("task-42"), { wrapper });

    // Seulement 2 erreurs
    await act(async () => { await Promise.resolve(); });
    await act(async () => { vi.advanceTimersByTime(5000); await Promise.resolve(); });

    // Pas encore à error
    expect(result.current.status).not.toBe("error");
    expect(updateProject).not.toHaveBeenCalledWith("task-42", { status: "error" });
  });

  it("réinitialise le compteur d'erreurs après un appel réussi", async () => {
    // 2 échecs, puis 1 succès : le compteur est remis à zéro, pas de status error
    vi.mocked(api.getStatus)
      .mockRejectedValueOnce(new Error("fail 1"))
      .mockRejectedValueOnce(new Error("fail 2"))
      .mockResolvedValue({
        task_id: "task-42", status: "processing",
        error_message: null, created_at: 0, updated_at: 0,
        progress_step: 1, progress_total: 4, progress_label: "Vérification du service vLLM…",
        queue_position: 1,
      });

    const { result } = renderHook(() => usePolling("task-42"), { wrapper });

    await act(async () => { await Promise.resolve(); });           // fail 1
    await act(async () => { vi.advanceTimersByTime(5000); await Promise.resolve(); }); // fail 2
    await act(async () => { vi.advanceTimersByTime(5000); await Promise.resolve(); }); // succès

    expect(result.current.status).toBe("processing");
    expect(updateProject).not.toHaveBeenCalledWith("task-42", { status: "error" });
  });

  it("met à jour la position dans la file", async () => {
    vi.mocked(api.getStatus).mockResolvedValue({
      task_id: "task-42", status: "pending",
      error_message: null, created_at: 0, updated_at: 0,
      progress_step: null, progress_total: null, progress_label: null,
      queue_position: 3,
    });

    const { result } = renderHook(() => usePolling("task-42"), { wrapper });
    await act(async () => { await Promise.resolve(); });

    expect(result.current.queuePosition).toBe(3);
  });
});
