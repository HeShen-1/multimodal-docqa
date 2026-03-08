import type { Pagination } from "@/shared/types/api";

export type DocumentStatus = "processing" | "completed" | "failed" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface DocumentProcessingSummary {
  extractMethod?: string;
  ocrUsed?: boolean;
  pageCount?: number;
  chunkCount?: number;
  hasTables?: boolean;
  hasImages?: boolean;
  sourceType?: string;
}

export interface DocumentItem {
  id: string;
  fileName: string;
  fileType?: string;
  fileSize?: number;
  status: DocumentStatus;
  description?: string | null;
  pageCount?: number | null;
  chunkCount?: number | null;
  imageCount?: number | null;
  processingSummary?: DocumentProcessingSummary | null;
  createdAt?: string | number;
  updatedAt?: string | number;
}

export interface DocumentDetail extends DocumentItem {
  metadata?: Record<string, unknown>;
  previewText?: string | null;
  processingSummary?: DocumentProcessingSummary | null;
}

export interface DocumentChunk {
  id: string;
  content: string;
  page: number;
  chunkIndex: number;
  parentChunkIndex?: number;
  type?: string;
  length: number;
}

export interface DocumentStatusDetail {
  documentId: string;
  status: DocumentStatus;
  progress: number;
  currentStep: string;
  message?: string;
}

export interface BatchUploadResult {
  batchId: string;
  totalFiles: number;
  acceptedFiles: number;
  rejectedFiles: Array<{ fileName: string; reason: string }>;
  documentIds: string[];
}

export interface BatchStatus {
  batchId: string;
  totalFiles: number;
  completed: number;
  processing: number;
  failed: number;
  progress: number;
  documents: Array<{ documentId: string; status: DocumentStatus; message?: string }>;
}

export type DocumentPage = Pagination<DocumentItem>;
