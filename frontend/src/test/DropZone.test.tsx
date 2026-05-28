import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DropZone, MAX_FILES } from "../components/DropZone";

function makePdf(name: string, size = 1024): File {
  return new File(["x".repeat(size)], name, { type: "application/pdf" });
}

function makeTxt(name: string): File {
  return new File(["hello"], name, { type: "text/plain" });
}

describe("DropZone", () => {
  it("appelle onFiles avec un seul PDF déposé", () => {
    const onFiles = vi.fn();
    render(<DropZone onFiles={onFiles} />);

    const input = document.querySelector<HTMLInputElement>("input[type=file]")!;
    const file = makePdf("doc.pdf");
    fireEvent.change(input, { target: { files: [file] } });

    expect(onFiles).toHaveBeenCalledOnce();
    expect(onFiles).toHaveBeenCalledWith([file]);
  });

  it("appelle onFiles avec plusieurs PDF déposés", () => {
    const onFiles = vi.fn();
    render(<DropZone onFiles={onFiles} />);

    const input = document.querySelector<HTMLInputElement>("input[type=file]")!;
    const files = [makePdf("a.pdf"), makePdf("b.pdf"), makePdf("c.pdf")];
    fireEvent.change(input, { target: { files } });

    expect(onFiles).toHaveBeenCalledOnce();
    expect(onFiles).toHaveBeenCalledWith(files);
  });

  it("filtre les non-PDF et appelle onFiles uniquement avec les PDF valides", () => {
    const onFiles = vi.fn();
    render(<DropZone onFiles={onFiles} />);

    const input = document.querySelector<HTMLInputElement>("input[type=file]")!;
    const pdf = makePdf("doc.pdf");
    const txt = makeTxt("notes.txt");
    fireEvent.change(input, { target: { files: [pdf, txt] } });

    expect(onFiles).toHaveBeenCalledWith([pdf]);
    expect(screen.getByText(/Seuls les fichiers PDF/i)).toBeTruthy();
  });

  it("n'appelle pas onFiles si aucun PDF dans la sélection", () => {
    const onFiles = vi.fn();
    render(<DropZone onFiles={onFiles} />);

    const input = document.querySelector<HTMLInputElement>("input[type=file]")!;
    fireEvent.change(input, { target: { files: [makeTxt("notes.txt")] } });

    expect(onFiles).not.toHaveBeenCalled();
  });

  it("tronque à MAX_FILES et affiche un message d'erreur", () => {
    const onFiles = vi.fn();
    render(<DropZone onFiles={onFiles} />);

    const input = document.querySelector<HTMLInputElement>("input[type=file]")!;
    const files = Array.from({ length: MAX_FILES + 5 }, (_, i) =>
      makePdf(`doc${i}.pdf`)
    );
    fireEvent.change(input, { target: { files } });

    const received: File[] = onFiles.mock.calls[0][0];
    expect(received).toHaveLength(MAX_FILES);
    expect(screen.getByText(new RegExp(`Maximum ${MAX_FILES}`, "i"))).toBeTruthy();
  });

  it("est désactivé quand disabled=true", () => {
    const onFiles = vi.fn();
    render(<DropZone onFiles={onFiles} disabled />);

    const zone = screen.getByText(/Glissez un ou plusieurs/i).closest("div")!;
    expect(zone.className).toContain("pointer-events-none");
  });
});
