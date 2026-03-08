import { isTextPreviewable, mergeChunkTexts } from "@/features/documents/preview-utils";
import type { DocumentChunk, DocumentDetail, DocumentItem } from "@/shared/types/document";

export function getTextPreview(
  document: Pick<DocumentDetail, "fileName" | "fileType"> | null | undefined,
  previewText: string | null | undefined,
  chunks: DocumentChunk[],
) {
  if (!document || !isTextPreviewable(document)) return "";

  const normalizedPreview = previewText?.trim();
  if (normalizedPreview) return normalizedPreview;

  return mergeChunkTexts(chunks);
}

export function filterDocumentChunks(chunks: DocumentChunk[], chunkSearch: string) {
  const normalizedSearch = chunkSearch.trim().toLowerCase();
  if (!normalizedSearch) return chunks;

  return chunks.filter((chunk) => {
    const searchable = `${chunk.content} ${chunk.page} ${chunk.chunkIndex} ${chunk.type ?? ""}`.toLowerCase();
    return searchable.includes(normalizedSearch);
  });
}

export function getNextSelectedDocumentId(items: DocumentItem[], selectedDocumentId: string | null) {
  if (!items.length) return null;
  if (!selectedDocumentId || !items.some((item) => item.id === selectedDocumentId)) {
    return items[0].id;
  }
  return selectedDocumentId;
}
