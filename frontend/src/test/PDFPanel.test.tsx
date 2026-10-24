import { describe, it, expect, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import type { PdfJs } from "@react-pdf-viewer/core";
import { PDFPanel } from "../components/PDFPanel";

// Viewer remplacé par un espion : on vérifie les paramètres transmis à pdf.js
const viewerProps = vi.fn();

vi.mock("@react-pdf-viewer/core", () => ({
  Worker: ({ children }: { children: ReactNode }) => <>{children}</>,
  Viewer: (props: unknown) => {
    viewerProps(props);
    return null;
  },
}));

vi.mock("@react-pdf-viewer/default-layout", () => ({
  defaultLayoutPlugin: () => ({}),
}));

describe("PDFPanel", () => {
  it("désactive isEvalSupported dans les paramètres de pdf.js (CVE-2024-4367)", async () => {
    render(<PDFPanel pdfBlob={new Blob(["%PDF-1.4"])} />);
    await waitFor(() => expect(viewerProps).toHaveBeenCalled());

    const { transformGetDocumentParams } = viewerProps.mock.calls[0][0] as {
      transformGetDocumentParams: (p: PdfJs.GetDocumentParams) => PdfJs.GetDocumentParams;
    };
    const params = transformGetDocumentParams({ url: "doc.pdf" });
    expect(params).toEqual({ url: "doc.pdf", isEvalSupported: false });
  });
});
