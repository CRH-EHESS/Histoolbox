import { describe, it, expect, vi, beforeEach } from "vitest";
import { exportMarkdown, exportDocx } from "../lib/exportUtils";

// Mock URL.createObjectURL / URL.revokeObjectURL
const createObjectURL = vi.fn(() => "blob:mock-url");
const revokeObjectURL = vi.fn();
Object.defineProperty(globalThis, "URL", {
  value: { createObjectURL, revokeObjectURL },
  writable: true,
});

// Mock <a>.click pour capturer le download
let lastAnchor: HTMLAnchorElement;
const origCreate = document.createElement.bind(document);
vi.spyOn(document, "createElement").mockImplementation((tag) => {
  const el = origCreate(tag);
  if (tag === "a") {
    vi.spyOn(el as HTMLAnchorElement, "click").mockImplementation(() => {});
    lastAnchor = el as HTMLAnchorElement;
  }
  return el;
});

beforeEach(() => {
  createObjectURL.mockClear();
  revokeObjectURL.mockClear();
});

describe("exportMarkdown", () => {
  it("déclenche un téléchargement avec l'extension .md", () => {
    exportMarkdown("# Hello\nMonde", "document.pdf");
    expect(lastAnchor.download).toBe("document.md");
    expect(createObjectURL).toHaveBeenCalledOnce();
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toContain("text/markdown");
  });
});

describe("exportDocx", () => {
  it("déclenche un téléchargement avec l'extension .docx", async () => {
    await exportDocx("# Titre\nCorps du texte", "rapport.pdf");
    expect(lastAnchor.download).toBe("rapport.docx");
    expect(createObjectURL).toHaveBeenCalledOnce();
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    // docx produit un zip (application/vnd.openxmlformats...)
    expect(blob).toBeInstanceOf(Blob);
  });
});
