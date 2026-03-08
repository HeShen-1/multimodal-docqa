import type { ReactNode } from "react";

import type { BatchStatus, DocumentChunk } from "@/shared/types/document";

const textPreviewExtensions = new Set(["txt", "md", "markdown", "json", "csv", "xml", "html", "htm"]);

export const statusOptions = [
  { label: "全部状态", value: "all" },
  { label: "处理中", value: "processing" },
  { label: "已完成", value: "completed" },
  { label: "失败", value: "failed" },
];

export function normalizeStatus(status?: string | null) {
  return String(status ?? "").trim().toLowerCase();
}

export function isTerminalStatus(status?: string | null) {
  const normalized = normalizeStatus(status);
  return normalized === "completed" || normalized === "failed";
}

export function mapStatusBadge(status?: string | null) {
  const normalized = normalizeStatus(status);
  if (normalized === "completed") {
    return { label: "已完成", variant: "default" as const };
  }
  if (normalized === "failed") {
    return { label: "失败", variant: "destructive" as const };
  }
  return { label: "处理中", variant: "secondary" as const };
}

export function getFileExtension(fileName?: string | null) {
  if (!fileName?.includes(".")) return "";
  return fileName.split(".").pop()?.toLowerCase() ?? "";
}

export function isPdfDocument(document?: { fileName?: string | null; fileType?: string | null }) {
  const fileType = String(document?.fileType ?? "").toLowerCase();
  return fileType.includes("pdf") || getFileExtension(document?.fileName) === "pdf";
}

export function isTextPreviewable(document?: { fileName?: string | null; fileType?: string | null }) {
  const fileType = String(document?.fileType ?? "").toLowerCase();
  if (fileType.startsWith("text/") || fileType.includes("json")) return true;
  return textPreviewExtensions.has(getFileExtension(document?.fileName));
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function findOverlapLength(previous: string, next: string) {
  const max = Math.min(previous.length, next.length, 160);
  for (let length = max; length >= 2; length -= 1) {
    if (previous.slice(-length) === next.slice(0, length)) {
      return length;
    }
  }
  return 0;
}

export function mergeChunkTexts(chunks: DocumentChunk[]) {
  return chunks
    .map((chunk) => chunk.content.trim())
    .filter(Boolean)
    .reduce((merged, current) => {
      if (!merged) return current;
      const overlap = findOverlapLength(merged, current);
      return overlap > 0 ? `${merged}${current.slice(overlap)}` : `${merged}\n\n${current}`;
    }, "");
}

export function renderHighlightedText(text: string, keyword: string): ReactNode {
  const normalizedKeyword = keyword.trim();
  if (!normalizedKeyword) return text;

  const pattern = new RegExp(`(${escapeRegExp(normalizedKeyword)})`, "ig");
  return text.split(pattern).map((part, index) =>
    part.toLowerCase() === normalizedKeyword.toLowerCase() ? (
      <mark key={`${part}-${index}`} className="rounded bg-primary/25 px-1 text-primary">
        {part}
      </mark>
    ) : (
      <span key={`${part}-${index}`}>{part}</span>
    ),
  );
}

export function isBatchRunning(batch?: BatchStatus) {
  if (!batch) return false;
  return batch.processing > 0 || batch.completed + batch.failed < batch.totalFiles;
}
