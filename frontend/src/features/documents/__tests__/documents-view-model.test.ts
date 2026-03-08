import { describe, expect, it } from "vitest";

import {
  filterDocumentChunks,
  getNextSelectedDocumentId,
  getTextPreview,
} from "@/features/documents/documents-view-model";
import type { DocumentChunk, DocumentDetail, DocumentItem } from "@/shared/types/document";

const textDocument: DocumentDetail = {
  id: "doc-text",
  fileName: "notes.md",
  fileType: "text/markdown",
  status: "completed",
};

const pdfDocument: DocumentDetail = {
  id: "doc-pdf",
  fileName: "report.pdf",
  fileType: "application/pdf",
  status: "completed",
};

const chunks: DocumentChunk[] = [
  {
    id: "chunk-1",
    content: "Alpha overlap",
    page: 1,
    chunkIndex: 0,
    length: 13,
    type: "text",
  },
  {
    id: "chunk-2",
    content: "overlap beta",
    page: 2,
    chunkIndex: 3,
    length: 12,
    type: "summary",
  },
];

describe("documents view model", () => {
  it("prefers trimmed preview text for previewable documents", () => {
    expect(getTextPreview(textDocument, "  direct preview  ", chunks)).toBe("direct preview");
  });

  it("falls back to merged chunks for previewable documents", () => {
    expect(getTextPreview(textDocument, "   ", chunks)).toBe("Alpha overlap beta");
    expect(getTextPreview(pdfDocument, "ignored", chunks)).toBe("");
  });

  it("filters chunks by content and metadata", () => {
    expect(filterDocumentChunks(chunks, "summary")).toEqual([chunks[1]]);
    expect(filterDocumentChunks(chunks, "2")).toEqual([chunks[1]]);
    expect(filterDocumentChunks(chunks, "")).toEqual(chunks);
  });

  it("resolves the next selected document from current page items", () => {
    const items: DocumentItem[] = [
      {
        id: "doc-1",
        fileName: "one.txt",
        status: "completed",
      },
      {
        id: "doc-2",
        fileName: "two.txt",
        status: "processing",
      },
    ];

    expect(getNextSelectedDocumentId(items, "doc-2")).toBe("doc-2");
    expect(getNextSelectedDocumentId(items, "missing")).toBe("doc-1");
    expect(getNextSelectedDocumentId([], "doc-1")).toBeNull();
  });
});
