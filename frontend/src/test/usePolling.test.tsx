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
});

afterEach(() => {
  vi.useRealTimers();
});

describe("usePolling", () => {
  it("appelle getStatus immédiatement au montage", async () => {
    vi.mocked(api.getStatus).mockResolvedValue({
      task_id: "task-42", status: "processing",
      error_message: null, created_at: 0, updated_at: 0,
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
    });

    renderHook(() => usePolling("task-42"), { wrapper });
    await act(async () => { await Promise.resolve(); });

    expect(updateProject).toHaveBeenCalledWith("task-42", { status: "error" });
  });

  it("ne plante pas si taskId est null", () => {
    expect(() => renderHook(() => usePolling(null), { wrapper })).not.toThrow();
    expect(api.getStatus).not.toHaveBeenCalled();
  });
});
