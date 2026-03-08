import { FileText, Layers3 } from "lucide-react";

import { getFileExtension, isTerminalStatus, renderHighlightedText } from "@/features/documents/preview-utils";
import type { DocumentsPageState } from "@/features/documents/use-documents-page";
import { cn, formatBytes, formatDateTime } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Loading } from "@/shared/ui/loading";

export function DocumentDetailPanel({ state }: { state: DocumentsPageState }) {
  const {
    chunkSearch,
    chunksQuery,
    detailQuery,
    detailTab,
    filteredChunks,
    pdfPreviewQuery,
    previewUrl,
    selectedDocument,
    selectedDocumentId,
    setChunkSearch,
    setDetailTab,
    statusBadge,
    statusDetail,
    textPreview,
  } = state;
  const processingSummary = detailQuery.data?.processingSummary ?? selectedDocument?.processingSummary ?? null;

  return (
    <Card className="flex min-h-[calc(100vh-7rem)] flex-col overflow-hidden">
      <CardHeader className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-2">
            <CardTitle className="truncate">{selectedDocument?.fileName ?? "文档详情"}</CardTitle>
            <div className="flex flex-wrap gap-2">
              <Badge variant={statusBadge.variant}>{statusBadge.label}</Badge>
              {selectedDocument ? <Badge variant="secondary">{formatBytes(selectedDocument.fileSize)}</Badge> : null}
              {selectedDocument?.fileType ? <Badge variant="secondary">{selectedDocument.fileType}</Badge> : null}
            </div>
          </div>
          {selectedDocument ? (
            <div className="text-right text-xs text-muted-foreground">
              <p>创建于 {formatDateTime(selectedDocument.createdAt)}</p>
              <p>更新于 {formatDateTime(selectedDocument.updatedAt ?? selectedDocument.createdAt)}</p>
            </div>
          ) : null}
        </div>

        {statusDetail && !isTerminalStatus(statusDetail.status) ? (
          <div className="rounded-2xl border border-border bg-black/10 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-medium text-foreground">处理进度</p>
              <span className="text-sm text-muted-foreground">{statusDetail.progress}%</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-black/30">
              <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${statusDetail.progress}%` }} />
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              {statusDetail.currentStep || statusDetail.message || "正在处理中，请稍候..."}
            </p>
          </div>
        ) : null}

        {selectedDocument ? (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div className="rounded-2xl border border-border bg-black/10 p-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">页数</p>
              <p className="mt-2 text-lg font-semibold text-foreground">
                {processingSummary?.pageCount ?? selectedDocument.pageCount ?? 0}
              </p>
            </div>
            <div className="rounded-2xl border border-border bg-black/10 p-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">切块</p>
              <p className="mt-2 text-lg font-semibold text-foreground">
                {processingSummary?.chunkCount ?? selectedDocument.chunkCount ?? 0}
              </p>
            </div>
            <div className="rounded-2xl border border-border bg-black/10 p-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">图片</p>
              <p className="mt-2 text-lg font-semibold text-foreground">{selectedDocument.imageCount ?? 0}</p>
            </div>
            <div className="rounded-2xl border border-border bg-black/10 p-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">扩展名</p>
              <p className="mt-2 text-lg font-semibold text-foreground">{getFileExtension(selectedDocument.fileName) || "-"}</p>
            </div>
          </div>
        ) : null}

        {selectedDocument ? (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div className="rounded-2xl border border-border bg-black/10 p-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">提取方式</p>
              <p className="mt-2 text-sm font-semibold text-foreground">{processingSummary?.extractMethod ?? "未记录"}</p>
            </div>
            <div className="rounded-2xl border border-border bg-black/10 p-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">OCR</p>
              <p className="mt-2 text-sm font-semibold text-foreground">{processingSummary?.ocrUsed ? "已启用" : "未启用"}</p>
            </div>
            <div className="rounded-2xl border border-border bg-black/10 p-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">表格</p>
              <p className="mt-2 text-sm font-semibold text-foreground">{processingSummary?.hasTables ? "包含" : "无"}</p>
            </div>
            <div className="rounded-2xl border border-border bg-black/10 p-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">来源类型</p>
              <p className="mt-2 text-sm font-semibold text-foreground">{processingSummary?.sourceType ?? "text"}</p>
            </div>
          </div>
        ) : null}

        {selectedDocument?.description ? (
          <div className="rounded-2xl border border-border bg-black/10 p-4 text-sm leading-6 text-muted-foreground">
            {selectedDocument.description}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setDetailTab("preview")}
            className={cn(
              "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition-colors",
              detailTab === "preview"
                ? "border-primary bg-primary/15 text-primary"
                : "border-border bg-black/10 text-muted-foreground hover:text-foreground",
            )}
          >
            <FileText className="h-4 w-4" />
            文档预览
          </button>
          <button
            type="button"
            onClick={() => setDetailTab("chunks")}
            className={cn(
              "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition-colors",
              detailTab === "chunks"
                ? "border-primary bg-primary/15 text-primary"
                : "border-border bg-black/10 text-muted-foreground hover:text-foreground",
            )}
          >
            <Layers3 className="h-4 w-4" />
            文档切块
          </button>
        </div>
      </CardHeader>

      <CardContent className="min-h-0 flex-1 overflow-hidden">
        {!selectedDocumentId ? (
          <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-border bg-black/10 text-muted-foreground">
            请先从左侧选择一个文档。
          </div>
        ) : detailQuery.isLoading ? (
          <Loading text="正在加载文档详情..." />
        ) : detailTab === "preview" ? (
          <div className="h-full overflow-auto rounded-2xl border border-border bg-black/10 p-4">
            {pdfPreviewQuery.isLoading ? <Loading text="正在加载 PDF 预览..." /> : null}
            {previewUrl ? (
              <iframe
                title={selectedDocument?.fileName ?? "文档预览"}
                src={previewUrl}
                className="h-[70vh] w-full rounded-xl border border-border bg-white"
              />
            ) : null}
            {!previewUrl && textPreview ? (
              <pre className="max-h-[70vh] whitespace-pre-wrap break-words rounded-xl border border-border bg-black/20 p-4 text-sm leading-7 text-slate-100">
                {textPreview}
              </pre>
            ) : null}
            {!previewUrl && !textPreview && !pdfPreviewQuery.isLoading ? (
              <div className="flex h-[50vh] items-center justify-center rounded-xl border border-dashed border-border bg-black/10 text-sm text-muted-foreground">
                当前文件暂不支持在线预览，可切换到“文档切块”查看解析结果。
              </div>
            ) : null}
          </div>
        ) : (
          <div className="flex h-full flex-col gap-3 overflow-hidden">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_180px]">
              <Input
                value={chunkSearch}
                onChange={(event) => setChunkSearch(event.target.value)}
                placeholder="按内容、页码或块索引搜索切块"
              />
              <div className="rounded-xl border border-border bg-black/10 px-3 py-2 text-sm text-muted-foreground">
                共 {filteredChunks.length} / {(chunksQuery.data ?? []).length} 个切块
              </div>
            </div>

            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto rounded-2xl border border-border bg-black/10 p-3">
              {chunksQuery.isLoading ? <Loading text="正在加载切块..." /> : null}
              {!chunksQuery.isLoading && !filteredChunks.length ? (
                <div className="rounded-xl border border-dashed border-border bg-black/10 p-4 text-sm text-muted-foreground">
                  没有匹配的切块内容。
                </div>
              ) : null}
              {filteredChunks.map((chunk) => (
                <div key={chunk.id} className="rounded-2xl border border-border bg-black/20 p-4">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary">P.{chunk.page}</Badge>
                    <Badge variant="secondary">块 {chunk.chunkIndex}</Badge>
                    {chunk.type ? <Badge variant="secondary">{chunk.type}</Badge> : null}
                    <Badge variant="secondary">{chunk.length} 字符</Badge>
                  </div>
                  <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-slate-100">
                    {renderHighlightedText(chunk.content, chunkSearch)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
