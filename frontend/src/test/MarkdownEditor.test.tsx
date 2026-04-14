import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MarkdownEditor } from "../components/MarkdownEditor";

// CodeMirror ne fonctionne pas dans JSDOM — on le remplace par un textarea simple
vi.mock("@uiw/react-codemirror", () => ({
  default: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <textarea
      data-testid="codemirror"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));

describe("MarkdownEditor", () => {
  it("affiche le mode source par défaut", () => {
    render(<MarkdownEditor value="# Titre" onChange={() => {}} />);
    expect(screen.getByTestId("codemirror")).toBeTruthy();
    expect(screen.queryByRole("article")).toBeNull();
  });

  it("le bouton Source est actif par défaut", () => {
    render(<MarkdownEditor value="# Titre" onChange={() => {}} />);
    const sourceBtn = screen.getByRole("button", { name: "Source" });
    const previewBtn = screen.getByRole("button", { name: /aperçu/i });
    expect(sourceBtn.className).toContain("bg-stone-800");
    expect(previewBtn.className).not.toContain("bg-stone-800");
  });

  it("passe en mode aperçu au clic sur Aperçu", () => {
    render(<MarkdownEditor value="# Bonjour" onChange={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /aperçu/i }));
    // L'éditeur source disparaît
    expect(screen.queryByTestId("codemirror")).toBeNull();
    // Le rendu HTML apparaît avec le contenu
    expect(screen.getByText("Bonjour")).toBeTruthy();
  });

  it("retourne en mode source au clic sur Source depuis l'aperçu", () => {
    render(<MarkdownEditor value="# Titre" onChange={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /aperçu/i }));
    fireEvent.click(screen.getByRole("button", { name: "Source" }));
    expect(screen.getByTestId("codemirror")).toBeTruthy();
  });

  it("appelle onChange lorsqu'on édite le contenu", () => {
    const onChange = vi.fn();
    render(<MarkdownEditor value="initial" onChange={onChange} />);
    fireEvent.change(screen.getByTestId("codemirror"), {
      target: { value: "modifié" },
    });
    expect(onChange).toHaveBeenCalledWith("modifié");
  });
});
