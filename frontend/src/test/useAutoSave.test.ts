import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAutoSave } from "../hooks/useAutoSave";

// Moquer updateProject pour ne pas toucher IndexedDB dans les tests de hooks
vi.mock("../db", () => ({
  updateProject: vi.fn().mockResolvedValue(undefined),
}));

import { updateProject } from "../db";

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useAutoSave", () => {
  it("ne sauvegarde pas immédiatement (debounce)", () => {
    renderHook(() => useAutoSave("task-99", "contenu initial"));
    expect(updateProject).not.toHaveBeenCalled();
  });

  it("sauvegarde après 1 seconde de debounce", async () => {
    renderHook(() => useAutoSave("task-99", "nouveau contenu"));
    await act(async () => { vi.advanceTimersByTime(1000); });
    expect(updateProject).toHaveBeenCalledWith("task-99", {
      markdownContent: "nouveau contenu",
    });
  });

  it("repose le timer si le contenu change avant 1s", async () => {
    const { rerender } = renderHook(
      ({ content }: { content: string }) => useAutoSave("task-99", content),
      { initialProps: { content: "brouillon" } }
    );

    await act(async () => { vi.advanceTimersByTime(500); });
    rerender({ content: "version finale" });
    // Le timer redémarre — pas encore sauvegardé à t=500ms après le rerender
    await act(async () => { vi.advanceTimersByTime(500); });
    expect(updateProject).not.toHaveBeenCalled();

    await act(async () => { vi.advanceTimersByTime(500); });
    expect(updateProject).toHaveBeenCalledWith("task-99", {
      markdownContent: "version finale",
    });
  });

  it("ne fait rien si taskId est null", () => {
    expect(() => renderHook(() => useAutoSave(null, "texte"))).not.toThrow();
    expect(updateProject).not.toHaveBeenCalled();
  });
});
