import { RefreshCcw, Trash2 } from "lucide-react";

import { mapStatusBadge, statusOptions } from "@/features/documents/preview-utils";
import type { DocumentsPageState } from "@/features/documents/use-documents-page";
import { cn, formatBytes, formatDateTime } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Loading } from "@/shared/ui/loading";
import { Select } from "@/shared/ui/select";

export function DocumentsListPanel({ state }: { state: DocumentsPageState }) {
  const {
    deleteMutation,
    displayStatus,
    keyword,
    listQuery,
    page,
    selectedDocumentId,
    setKeyword,
    setPage,
    setSelectedDocumentId,
    setStatus,
    status,
  } = state;

  return (
    <Card>
      <CardHeader className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle>文档列表</CardTitle>
          <Button variant="secondary" onClick={() => void listQuery.refetch()} disabled={listQuery.isFetching}>
            <RefreshCcw className={cn("h-4 w-4", listQuery.isFetching && "animate-spin")} />
            刷新
          </Button>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_180px]">
          <Input
            value={keyword}
            onChange={(event) => {
              setKeyword(event.target.value);
              setPage(1);
            }}
            placeholder="搜索文件名或描述"
          />
          <Select
            value={status}
            options={statusOptions}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {listQuery.isLoading ? <Loading text="正在加载文档列表..." /> : null}
        {!listQuery.isLoading && !(listQuery.data?.items.length ?? 0) ? (
          <div className="rounded-2xl border border-dashed border-border bg-black/10 p-6 text-sm text-muted-foreground">
            当前条件下没有文档，请先上传文件。
          </div>
        ) : null}

        {listQuery.data?.items.map((document) => {
          const badge = mapStatusBadge(document.id === selectedDocumentId ? displayStatus : document.status);

          return (
            <button
              key={document.id}
              type="button"
              onClick={() => setSelectedDocumentId(document.id)}
              className={cn(
                "w-full rounded-2xl border p-4 text-left transition-all",
                document.id === selectedDocumentId
                  ? "border-primary bg-primary/10 shadow-glow"
                  : "border-border bg-black/10 hover:border-primary/50 hover:bg-black/20",
              )}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate font-medium text-foreground">{document.fileName}</p>
                    <Badge variant={badge.variant}>{badge.label}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {formatBytes(document.fileSize)} · {formatDateTime(document.updatedAt ?? document.createdAt)}
                  </p>
                  <p className="line-clamp-2 text-sm text-muted-foreground">
                    {document.description?.trim() || "暂无描述"}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  className="text-muted-foreground hover:text-destructive"
                  onClick={(event) => {
                    event.stopPropagation();
                    deleteMutation.mutate(document.id);
                  }}
                  disabled={deleteMutation.isPending}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                <span>页数 {document.pageCount ?? 0}</span>
                <span>切块 {document.chunkCount ?? 0}</span>
                <span>图片 {document.imageCount ?? 0}</span>
              </div>
            </button>
          );
        })}

        {listQuery.data?.totalPages && listQuery.data.totalPages > 1 ? (
          <div className="flex items-center justify-between gap-3 border-t border-border pt-3 text-sm">
            <span className="text-muted-foreground">
              第 {listQuery.data.page} / {listQuery.data.totalPages} 页，共 {listQuery.data.total} 条
            </span>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setPage((previous) => Math.max(1, previous - 1))} disabled={page <= 1}>
                上一页
              </Button>
              <Button
                variant="secondary"
                onClick={() => setPage((previous) => previous + 1)}
                disabled={page >= listQuery.data.totalPages}
              >
                下一页
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
