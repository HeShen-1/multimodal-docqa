import { Copy, Share2 } from "lucide-react";

import type { DocumentsPageState } from "@/features/documents/use-documents-page";
import { formatDateTime } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Loading } from "@/shared/ui/loading";

export function DocumentsSharePanel({ state }: { state: DocumentsPageState }) {
  const {
    createShareMutation,
    handleCopyShare,
    revokeShareMutation,
    selectedDocument,
    selectedDocumentId,
    setShareForm,
    shareForm,
    sharesQuery,
  } = state;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Share2 className="h-5 w-5" />
          分享管理
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-2xl border border-border bg-black/10 p-4">
          <p className="text-sm text-muted-foreground">
            当前文档：<span className="text-foreground">{selectedDocument?.fileName ?? "未选择文档"}</span>
          </p>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="space-y-2">
            <Label>有效期（小时）</Label>
            <Input
              type="number"
              min={1}
              value={shareForm.expiresInHours}
              onChange={(event) =>
                setShareForm((previous) => ({
                  ...previous,
                  expiresInHours: Number(event.target.value) || 24,
                }))
              }
            />
          </div>
          <div className="space-y-2">
            <Label>最大访问次数</Label>
            <Input
              type="number"
              min={1}
              value={shareForm.maxAccessCount}
              onChange={(event) =>
                setShareForm((previous) => ({
                  ...previous,
                  maxAccessCount: event.target.value,
                }))
              }
              placeholder="留空表示不限"
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label>访问密码</Label>
          <Input
            type="text"
            value={shareForm.password}
            onChange={(event) =>
              setShareForm((previous) => ({
                ...previous,
                password: event.target.value,
              }))
            }
            placeholder="可选"
          />
        </div>

        <label className="flex items-center gap-3 text-sm text-foreground">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-border accent-amber-500"
            checked={shareForm.allowDownload}
            onChange={(event) =>
              setShareForm((previous) => ({
                ...previous,
                allowDownload: event.target.checked,
              }))
            }
          />
          允许下载原文件
        </label>

        <Button onClick={() => createShareMutation.mutate()} disabled={!selectedDocumentId || createShareMutation.isPending}>
          生成分享链接
        </Button>

        <div className="space-y-3">
          {(sharesQuery.data ?? []).map((share) => (
            <div key={share.id} className="rounded-2xl border border-border bg-black/10 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="truncate text-sm font-medium text-foreground">{share.shareUrl}</p>
                  <p className="text-xs text-muted-foreground">
                    到期时间 {formatDateTime(share.expiresAt)} · 访问 {share.accessCount}
                    {share.maxAccessCount ? ` / ${share.maxAccessCount}` : ""}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="secondary" onClick={() => void handleCopyShare(share.shareUrl)}>
                    <Copy className="h-4 w-4" />
                    复制
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={() => revokeShareMutation.mutate(share.id)}
                    disabled={revokeShareMutation.isPending}
                  >
                    撤销
                  </Button>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge variant={share.allowDownload ? "default" : "secondary"}>
                  {share.allowDownload ? "允许下载" : "仅可查看"}
                </Badge>
                {share.hasPassword ? <Badge variant="secondary">已设置密码</Badge> : null}
              </div>
            </div>
          ))}
          {sharesQuery.isLoading ? <Loading text="正在加载分享记录..." /> : null}
          {selectedDocumentId && !sharesQuery.isLoading && !(sharesQuery.data ?? []).length ? (
            <div className="rounded-2xl border border-dashed border-border bg-black/10 p-4 text-sm text-muted-foreground">
              当前文档还没有分享链接。
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
