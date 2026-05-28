import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("../lib/apiClient", () => ({
  api: {
    uploadPdf: vi.fn(),
  },
}));

vi.mock("../db", () => ({
  db: { ocr_projects: { delete: vi.fn().mockResolvedValue(undefined) } },
  createProject: vi.fn().mockResolvedValue(undefined),
}));

// react-router-dom useNavigate capturé pour tester la navigation
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => mockNavigate };
});

import { api } from "../lib/apiClient";
import { createProject } from "../db";
import { OCRUploadPage } from "../pages/OCRUploadPage";

// ── Helpers ───────────────────────────────────────────────────────────────────

function makePdf(name: string): File {
  return new File(["pdf-content"], name, { type: "application/pdf" });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <OCRUploadPage />
    </MemoryRouter>
  );
}

function dropFiles(files: File[]) {
  const input = document.querySelector<HTMLInputElement>("input[type=file]")!;
  fireEvent.change(input, { target: { files } });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
});

describe("OCRUploadPage — mono-fichier", () => {
  it("affiche le bouton 'Lancer la transcription' après dépôt d'un PDF", async () => {
    renderPage();
    dropFiles([makePdf("a.pdf")]);
    expect(await screen.findByText("Lancer la transcription")).toBeTruthy();
  });

  it("navigue vers /ocr/waiting/:id après un upload réussi", async () => {
    vi.mocked(api.uploadPdf).mockResolvedValue({ task_id: "task-001" });
    renderPage();
    dropFiles([makePdf("a.pdf")]);

    fireEvent.click(await screen.findByText("Lancer la transcription"));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/ocr/waiting/task-001");
    });
  });

  it("crée deux entrées IndexedDB (tempId puis task_id)", async () => {
    vi.mocked(api.uploadPdf).mockResolvedValue({ task_id: "task-001" });
    renderPage();
    dropFiles([makePdf("a.pdf")]);

    fireEvent.click(await screen.findByText("Lancer la transcription"));

    await waitFor(() => {
      expect(createProject).toHaveBeenCalledTimes(2);
    });
  });
});

describe("OCRUploadPage — multi-fichiers", () => {
  it("affiche le bon libellé de bouton pour 3 fichiers", async () => {
    renderPage();
    dropFiles([makePdf("a.pdf"), makePdf("b.pdf"), makePdf("c.pdf")]);
    expect(await screen.findByText("Lancer les 3 transcriptions")).toBeTruthy();
  });

  it("navigue vers /ocr/history après N uploads réussis", async () => {
    vi.mocked(api.uploadPdf)
      .mockResolvedValueOnce({ task_id: "task-001" })
      .mockResolvedValueOnce({ task_id: "task-002" });

    renderPage();
    dropFiles([makePdf("a.pdf"), makePdf("b.pdf")]);
    fireEvent.click(await screen.findByText("Lancer les 2 transcriptions"));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/ocr/history");
    });
  });

  it("affiche les erreurs dans la file sans naviguer si tout échoue", async () => {
    vi.mocked(api.uploadPdf).mockRejectedValue(new Error("Réseau indisponible."));

    renderPage();
    dropFiles([makePdf("a.pdf"), makePdf("b.pdf")]);
    fireEvent.click(await screen.findByText("Lancer les 2 transcriptions"));

    await waitFor(() => {
      expect(screen.getAllByText("Réseau indisponible.")).toHaveLength(2);
    });
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("le bouton 'Vider la liste' retire tous les fichiers", async () => {
    renderPage();
    dropFiles([makePdf("a.pdf"), makePdf("b.pdf")]);
    expect(await screen.findByText("Vider la liste")).toBeTruthy();

    fireEvent.click(screen.getByText("Vider la liste"));

    // La liste est vide → bouton et UploadQueue disparaissent
    await waitFor(() => {
      expect(screen.queryByText("Lancer les 2 transcriptions")).toBeNull();
      expect(screen.queryByText("Vider la liste")).toBeNull();
    });
  });
});
