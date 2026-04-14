/**
 * Utilitaires d'exportation — côté client uniquement.
 */

import { Document, Packer, Paragraph, TextRun } from "docx";

/** Télécharge le contenu Markdown brut en fichier .md */
export function exportMarkdown(content: string, originalFileName: string): void {
  const stem = originalFileName.replace(/\.pdf$/i, "");
  const blob = new Blob([content], { type: "text/markdown; charset=utf-8" });
  triggerDownload(blob, `${stem}.md`);
}

/**
 * Convertit le Markdown en .docx via la bibliothèque `docx`.
 * Conversion simple ligne par ligne (MVP) — chaque ligne = un paragraphe.
 */
export async function exportDocx(content: string, originalFileName: string): Promise<void> {
  const stem = originalFileName.replace(/\.pdf$/i, "");

  const paragraphs = content.split("\n").map((line) => {
    // Titres Markdown → gras
    const headingMatch = line.match(/^(#{1,6})\s+(.*)/);
    if (headingMatch) {
      return new Paragraph({
        children: [new TextRun({ text: headingMatch[2], bold: true, size: 28 })],
        spacing: { after: 120 },
      });
    }
    return new Paragraph({
      children: [new TextRun({ text: line })],
      spacing: { after: 80 },
    });
  });

  const doc = new Document({
    sections: [{ properties: {}, children: paragraphs }],
  });

  const blob = await Packer.toBlob(doc);
  triggerDownload(blob, `${stem}.docx`);
}

function triggerDownload(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}
