import { apiClient } from "@/shared/api/client";
import { unwrapApiEnvelope } from "@/shared/api/adapters/envelope";
import type {
  DocumentChunk,
  DocumentDetail,
  BatchStatus,
  BatchUploadResult,
  DocumentItem,
  DocumentPage,
  DocumentStatusDetail,
} from "@/shared/types/document";
import type { ShareLink } from "@/shared/types/share";
import type { Tag } from "@/shared/types/tag";

type AnyRecord = Record<string, unknown>;

function normalizeDocument(raw: AnyRecord): DocumentItem {
  return {
    id: String(raw.id ?? raw.documentId ?? ""),
    fileName: String(raw.fileName ?? raw.file_name ?? "未知文件"),
    fileType: (raw.fileType ?? raw.file_type) as string | undefined,
    fileSize: Number(raw.fileSize ?? raw.file_size ?? 0),
    status: String(raw.status ?? "processing") as DocumentItem["status"],
    description: (raw.description as string | null | undefined) ?? null,
    pageCount: Number(raw.pageCount ?? raw.page_count ?? 0),
    chunkCount: Number(raw.chunkCount ?? raw.chunk_count ?? 0),
    imageCount: Number(raw.imageCount ?? raw.image_count ?? 0),
    createdAt: (raw.createdAt ?? raw.created_at) as string | number | undefined,
    updatedAt: (raw.updatedAt ?? raw.updated_at) as string | number | undefined,
  };
}

function normalizeDocumentDetail(raw: AnyRecord): DocumentDetail {
  return {
    ...normalizeDocument(raw),
    metadata: (raw.metadata as Record<string, unknown> | undefined) ?? {},
    previewText: (raw.previewText ?? raw.preview_text) as string | null | undefined,
  };
}

export const documentsApi = {
  async list(params: {
    page?: number;
    pageSize?: number;
    status?: string;
    keyword?: string;
  }): Promise<DocumentPage> {
    const response = await apiClient.get("/documents", { params });
    const raw = unwrapApiEnvelope<AnyRecord>(response.data);
    const items = ((raw.items ?? []) as AnyRecord[]).map(normalizeDocument);
    return {
      items,
      total: Number(raw.total ?? items.length),
      page: Number(raw.page ?? params.page ?? 1),
      pageSize: Number(raw.pageSize ?? params.pageSize ?? 10),
      totalPages: Number(raw.totalPages ?? 1),
    };
  },

  async upload(file: File, description?: string) {
    const form = new FormData();
    form.append("file", file);
    if (description) {
      form.append("description", description);
    }
    const response = await apiClient.post("/documents/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return unwrapApiEnvelope<Record<string, unknown>>(response.data);
  },

  async batchUpload(files: File[], description?: string): Promise<BatchUploadResult> {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    if (description) {
      form.append("description", description);
    }
    const response = await apiClient.post("/documents/batch-upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return unwrapApiEnvelope<BatchUploadResult>(response.data);
  },

  async getStatus(documentId: string): Promise<DocumentStatusDetail> {
    const response = await apiClient.get(`/documents/${documentId}/status`);
    const raw = unwrapApiEnvelope<AnyRecord>(response.data);
    return {
      documentId: String(raw.documentId ?? documentId),
      status: String(raw.status ?? "processing") as DocumentStatusDetail["status"],
      progress: Number(raw.progress ?? 0),
      currentStep: String(raw.currentStep ?? ""),
      message: (raw.message as string | undefined) ?? undefined,
    };
  },

  async getDetail(documentId: string): Promise<DocumentDetail> {
    const response = await apiClient.get(`/documents/${documentId}`);
    const raw = unwrapApiEnvelope<AnyRecord>(response.data);
    return normalizeDocumentDetail(raw);
  },

  async getChunks(documentId: string): Promise<DocumentChunk[]> {
    const response = await apiClient.get(`/documents/${documentId}/chunks`);
    const raw = unwrapApiEnvelope<AnyRecord[]>(response.data);
    return raw.map((item) => ({
      id: String(item.id ?? ""),
      content: String(item.content ?? ""),
      page: Number(item.page ?? 1),
      chunkIndex: Number(item.chunkIndex ?? item.chunk_index ?? 0),
      parentChunkIndex: Number(item.parentChunkIndex ?? item.parent_chunk_index ?? -1),
      type: (item.type as string | undefined) ?? "text",
      length: Number(item.length ?? String(item.content ?? "").length),
    }));
  },

  async getFileBlob(documentId: string): Promise<Blob> {
    const response = await apiClient.get(`/documents/${documentId}/file`, {
      responseType: "blob",
    });
    return response.data as Blob;
  },

  async getBatchStatus(batchId: string): Promise<BatchStatus> {
    const response = await apiClient.get(`/documents/batch/${batchId}/status`);
    return unwrapApiEnvelope<BatchStatus>(response.data);
  },

  async remove(documentId: string) {
    await apiClient.delete(`/documents/${documentId}`);
  },

  async getDocumentTags(documentId: string): Promise<Tag[]> {
    const response = await apiClient.get(`/documents/${documentId}/tags`);
    const raw = unwrapApiEnvelope<AnyRecord[]>(response.data);
    return raw.map((item) => ({
      id: String(item.id),
      name: String(item.name),
      color: item.color as string | undefined,
    }));
  },

  async setDocumentTags(documentId: string, tagIds: string[]) {
    const response = await apiClient.post(`/documents/${documentId}/tags`, {
      tagIds,
    });
    return unwrapApiEnvelope(response.data);
  },

  async removeDocumentTags(documentId: string, tagIds: string[]) {
    const response = await apiClient.delete(`/documents/${documentId}/tags`, {
      data: { tagIds },
    });
    return unwrapApiEnvelope(response.data);
  },

  async listTags(keyword?: string): Promise<Tag[]> {
    const response = await apiClient.get("/tags", {
      params: { page: 1, pageSize: 50, keyword },
    });
    const raw = unwrapApiEnvelope<AnyRecord>(response.data);
    const items = (raw.items ?? []) as AnyRecord[];
    return items.map((item) => ({
      id: String(item.id),
      name: String(item.name),
      color: (item.color as string | undefined) ?? "#3B82F6",
      description: (item.description as string | undefined) ?? "",
      usageCount: Number(item.usageCount ?? item.usage_count ?? 0),
    }));
  },

  async createTag(payload: { name: string; color?: string; description?: string }) {
    const response = await apiClient.post("/tags", payload);
    return unwrapApiEnvelope<Tag>(response.data);
  },

  async createShareLink(
    documentId: string,
    payload: {
      expiresInHours: number;
      password?: string;
      allowDownload: boolean;
      maxAccessCount?: number;
    },
  ): Promise<ShareLink> {
    const response = await apiClient.post(`/share/documents/${documentId}`, payload);
    return unwrapApiEnvelope<ShareLink>(response.data);
  },

  async listShareLinks(documentId: string): Promise<ShareLink[]> {
    const response = await apiClient.get(`/share/documents/${documentId}`);
    return unwrapApiEnvelope<ShareLink[]>(response.data);
  },

  async revokeShare(shareId: string) {
    await apiClient.delete(`/share/${shareId}`);
  },
};
