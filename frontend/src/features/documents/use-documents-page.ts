import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { documentsApi } from "@/features/documents/documents-api";
import {
  filterDocumentChunks,
  getNextSelectedDocumentId,
  getTextPreview,
} from "@/features/documents/documents-view-model";
import { isBatchRunning, isPdfDocument, isTerminalStatus, mapStatusBadge } from "@/features/documents/preview-utils";
import { normalizeApiError } from "@/shared/api/errors";
import type { DocumentStatusDetail } from "@/shared/types/document";

export function useDocumentsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("all");
  const [keyword, setKeyword] = useState("");
  const [description, setDescription] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [batchFiles, setBatchFiles] = useState<File[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState<"preview" | "chunks">("preview");
  const [chunkSearch, setChunkSearch] = useState("");
  const [newTagName, setNewTagName] = useState("");
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null);
  const [batchPolling, setBatchPolling] = useState(false);
  const [shareForm, setShareForm] = useState({
    expiresInHours: 24,
    password: "",
    allowDownload: true,
    maxAccessCount: "",
  });
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const listQuery = useQuery({
    queryKey: ["documents", "list", page, status, keyword],
    queryFn: () =>
      documentsApi.list({
        page,
        pageSize: 8,
        status: status === "all" ? undefined : status,
        keyword: keyword.trim() || undefined,
      }),
  });

  const selectedListDocument = useMemo(
    () => listQuery.data?.items.find((item) => item.id === selectedDocumentId) ?? null,
    [listQuery.data?.items, selectedDocumentId],
  );

  const detailQuery = useQuery({
    queryKey: ["documents", "detail", selectedDocumentId],
    queryFn: () => documentsApi.getDetail(selectedDocumentId!),
    enabled: Boolean(selectedDocumentId),
  });

  const currentStatus = detailQuery.data?.status ?? selectedListDocument?.status;
  const shouldPollSelectedStatus = Boolean(selectedDocumentId && !isTerminalStatus(currentStatus));

  const statusDetailQuery = useQuery({
    queryKey: ["documents", "status", selectedDocumentId],
    queryFn: () => documentsApi.getStatus(selectedDocumentId!),
    enabled: shouldPollSelectedStatus,
    refetchInterval: shouldPollSelectedStatus ? 3000 : false,
  });

  const chunksQuery = useQuery({
    queryKey: ["documents", "chunks", selectedDocumentId],
    queryFn: () => documentsApi.getChunks(selectedDocumentId!),
    enabled: Boolean(selectedDocumentId),
  });

  const tagsQuery = useQuery({
    queryKey: ["documents", "tags"],
    queryFn: () => documentsApi.listTags(),
  });

  const documentTagsQuery = useQuery({
    queryKey: ["documents", "document-tags", selectedDocumentId],
    queryFn: () => documentsApi.getDocumentTags(selectedDocumentId!),
    enabled: Boolean(selectedDocumentId),
  });

  const sharesQuery = useQuery({
    queryKey: ["documents", "shares", selectedDocumentId],
    queryFn: () => documentsApi.listShareLinks(selectedDocumentId!),
    enabled: Boolean(selectedDocumentId),
  });

  const pdfPreviewQuery = useQuery({
    queryKey: ["documents", "preview-file", selectedDocumentId],
    queryFn: () => documentsApi.getFileBlob(selectedDocumentId!),
    enabled: Boolean(selectedDocumentId && detailQuery.data && isPdfDocument(detailQuery.data)),
  });

  const batchStatusQuery = useQuery({
    queryKey: ["documents", "batch-status", activeBatchId],
    queryFn: () => documentsApi.getBatchStatus(activeBatchId!),
    enabled: Boolean(activeBatchId),
    refetchInterval: batchPolling ? 3000 : false,
  });

  const selectedDocument = detailQuery.data ?? selectedListDocument;
  const statusDetail: DocumentStatusDetail | undefined = statusDetailQuery.data;
  const displayStatus = statusDetail?.status ?? selectedDocument?.status;
  const statusBadge = mapStatusBadge(displayStatus);
  const chunks = chunksQuery.data ?? [];

  const textPreview = useMemo(
    () => getTextPreview(selectedDocument, detailQuery.data?.previewText, chunks),
    [chunks, detailQuery.data?.previewText, selectedDocument],
  );

  const filteredChunks = useMemo(() => filterDocumentChunks(chunks, chunkSearch), [chunkSearch, chunks]);

  useEffect(() => {
    const nextSelectedDocumentId = getNextSelectedDocumentId(listQuery.data?.items ?? [], selectedDocumentId);
    if (nextSelectedDocumentId !== selectedDocumentId) {
      setSelectedDocumentId(nextSelectedDocumentId);
    }
  }, [listQuery.data?.items, selectedDocumentId]);

  useEffect(() => {
    setDetailTab("preview");
    setChunkSearch("");
  }, [selectedDocumentId]);

  useEffect(() => {
    if (!statusDetail || !selectedDocumentId || !isTerminalStatus(statusDetail.status)) return;

    void queryClient.invalidateQueries({ queryKey: ["documents", "list"] });
    void queryClient.invalidateQueries({ queryKey: ["documents", "detail", selectedDocumentId] });
    void queryClient.invalidateQueries({ queryKey: ["documents", "chunks", selectedDocumentId] });
  }, [queryClient, selectedDocumentId, statusDetail]);

  useEffect(() => {
    if (!batchStatusQuery.data) return;

    const running = isBatchRunning(batchStatusQuery.data);
    setBatchPolling(running);
    if (!running) {
      void queryClient.invalidateQueries({ queryKey: ["documents", "list"] });
    }
  }, [batchStatusQuery.data, queryClient]);

  useEffect(() => {
    if (!pdfPreviewQuery.data) {
      setPreviewUrl((previous) => {
        if (previous) URL.revokeObjectURL(previous);
        return null;
      });
      return;
    }

    const nextUrl = URL.createObjectURL(pdfPreviewQuery.data);
    setPreviewUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return nextUrl;
    });

    return () => URL.revokeObjectURL(nextUrl);
  }, [pdfPreviewQuery.data]);

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile) {
        throw new Error("请先选择文件");
      }
      return documentsApi.upload(selectedFile, description.trim() || undefined);
    },
    onSuccess: async (result) => {
      const nextDocumentId = String((result as { documentId?: unknown; id?: unknown }).documentId ?? result.id ?? "");
      toast.success("文档已提交处理");
      setSelectedFile(null);
      setDescription("");
      setPage(1);
      if (nextDocumentId) {
        setSelectedDocumentId(nextDocumentId);
      }
      await queryClient.invalidateQueries({ queryKey: ["documents", "list"] });
    },
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  const batchUploadMutation = useMutation({
    mutationFn: async () => {
      if (!batchFiles.length) {
        throw new Error("请先选择批量文件");
      }
      return documentsApi.batchUpload(batchFiles, description.trim() || undefined);
    },
    onSuccess: async (result) => {
      toast.success(`批量任务已创建，共 ${result.acceptedFiles} 个文件`);
      setBatchFiles([]);
      setActiveBatchId(result.batchId);
      setBatchPolling(true);
      setPage(1);
      await queryClient.invalidateQueries({ queryKey: ["documents", "list"] });
    },
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  const deleteMutation = useMutation({
    mutationFn: async (documentId: string) => {
      await documentsApi.remove(documentId);
      return documentId;
    },
    onSuccess: async (documentId) => {
      toast.success("文档已删除");
      if (selectedDocumentId === documentId) {
        setSelectedDocumentId(null);
      }
      await queryClient.invalidateQueries({ queryKey: ["documents", "list"] });
    },
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  const setDocumentTagsMutation = useMutation({
    mutationFn: ({ documentId, tagIds }: { documentId: string; tagIds: string[] }) =>
      documentsApi.setDocumentTags(documentId, tagIds),
    onSuccess: async () => {
      toast.success("标签已更新");
      await queryClient.invalidateQueries({ queryKey: ["documents", "document-tags", selectedDocumentId] });
      await queryClient.invalidateQueries({ queryKey: ["documents", "tags"] });
    },
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  const removeDocumentTagsMutation = useMutation({
    mutationFn: ({ documentId, tagIds }: { documentId: string; tagIds: string[] }) =>
      documentsApi.removeDocumentTags(documentId, tagIds),
    onSuccess: async () => {
      toast.success("标签已移除");
      await queryClient.invalidateQueries({ queryKey: ["documents", "document-tags", selectedDocumentId] });
      await queryClient.invalidateQueries({ queryKey: ["documents", "tags"] });
    },
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  const createTagMutation = useMutation({
    mutationFn: async () => {
      const name = newTagName.trim();
      if (!name) {
        throw new Error("请输入标签名称");
      }
      return documentsApi.createTag({ name, color: "#F59E0B" });
    },
    onSuccess: async (tag) => {
      toast.success("标签已创建");
      setNewTagName("");
      await queryClient.invalidateQueries({ queryKey: ["documents", "tags"] });

      if (!selectedDocumentId) return;
      const currentTagIds = (documentTagsQuery.data ?? []).map((item) => item.id);
      setDocumentTagsMutation.mutate({
        documentId: selectedDocumentId,
        tagIds: Array.from(new Set([...currentTagIds, tag.id])),
      });
    },
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  const createShareMutation = useMutation({
    mutationFn: async () => {
      if (!selectedDocumentId) {
        throw new Error("请先选择文档");
      }
      return documentsApi.createShareLink(selectedDocumentId, {
        expiresInHours: Number(shareForm.expiresInHours) || 24,
        password: shareForm.password.trim() || undefined,
        allowDownload: shareForm.allowDownload,
        maxAccessCount: shareForm.maxAccessCount ? Number(shareForm.maxAccessCount) : undefined,
      });
    },
    onSuccess: async () => {
      toast.success("分享链接已创建");
      setShareForm((previous) => ({
        ...previous,
        password: "",
        maxAccessCount: "",
      }));
      await queryClient.invalidateQueries({ queryKey: ["documents", "shares", selectedDocumentId] });
    },
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  const revokeShareMutation = useMutation({
    mutationFn: (shareId: string) => documentsApi.revokeShare(shareId),
    onSuccess: async () => {
      toast.success("分享已撤销");
      await queryClient.invalidateQueries({ queryKey: ["documents", "shares", selectedDocumentId] });
    },
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  const handleToggleTag = (tagId: string) => {
    if (!selectedDocumentId) {
      toast.error("请先选择文档");
      return;
    }

    const currentTagIds = (documentTagsQuery.data ?? []).map((item) => item.id);
    if (currentTagIds.includes(tagId)) {
      removeDocumentTagsMutation.mutate({ documentId: selectedDocumentId, tagIds: [tagId] });
      return;
    }

    setDocumentTagsMutation.mutate({
      documentId: selectedDocumentId,
      tagIds: Array.from(new Set([...currentTagIds, tagId])),
    });
  };

  const handleCopyShare = async (shareUrl: string) => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      toast.success("分享链接已复制");
    } catch (error) {
      toast.error(normalizeApiError(error).message);
    }
  };

  return {
    page,
    setPage,
    status,
    setStatus,
    keyword,
    setKeyword,
    description,
    setDescription,
    selectedFile,
    setSelectedFile,
    batchFiles,
    setBatchFiles,
    selectedDocumentId,
    setSelectedDocumentId,
    detailTab,
    setDetailTab,
    chunkSearch,
    setChunkSearch,
    newTagName,
    setNewTagName,
    shareForm,
    setShareForm,
    previewUrl,
    listQuery,
    detailQuery,
    statusDetailQuery,
    chunksQuery,
    tagsQuery,
    documentTagsQuery,
    sharesQuery,
    pdfPreviewQuery,
    batchStatusQuery,
    selectedDocument,
    statusDetail,
    displayStatus,
    statusBadge,
    textPreview,
    filteredChunks,
    uploadMutation,
    batchUploadMutation,
    deleteMutation,
    createTagMutation,
    createShareMutation,
    revokeShareMutation,
    handleToggleTag,
    handleCopyShare,
  };
}

export type DocumentsPageState = ReturnType<typeof useDocumentsPage>;
