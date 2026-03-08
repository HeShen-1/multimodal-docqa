import { UploadCloud } from "lucide-react";

import { isBatchRunning } from "@/features/documents/preview-utils";
import type { DocumentsPageState } from "@/features/documents/use-documents-page";
import { formatBytes } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Textarea } from "@/shared/ui/textarea";

export function DocumentsUploadPanel({ state }: { state: DocumentsPageState }) {
  const {
    batchFiles,
    batchStatusQuery,
    batchUploadMutation,
    description,
    setBatchFiles,
    selectedFile,
    setDescription,
    setSelectedFile,
    uploadMutation,
  } = state;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <UploadCloud className="h-5 w-5" />
          上传管理
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="space-y-3 rounded-2xl border border-border bg-black/10 p-4">
          <div className="space-y-2">
            <Label>单文件上传</Label>
            <Input
              type="file"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              accept=".pdf,.doc,.docx,.txt,.md,.csv,.json"
            />
          </div>
          <div className="space-y-2">
            <Label>文档描述</Label>
            <Textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="为新上传的文档补充摘要、用途或业务背景"
              className="min-h-[96px]"
            />
          </div>
          <Button onClick={() => uploadMutation.mutate()} disabled={!selectedFile || uploadMutation.isPending}>
            上传并开始处理
          </Button>
        </div>

        <div className="space-y-3 rounded-2xl border border-border bg-black/10 p-4">
          <div className="space-y-2">
            <Label>批量上传</Label>
            <Input
              type="file"
              multiple
              onChange={(event) => setBatchFiles(Array.from(event.target.files ?? []))}
              accept=".pdf,.doc,.docx,.txt,.md,.csv,.json"
            />
            <p className="text-xs text-muted-foreground">
              已选择 {batchFiles.length} 个文件
              {batchFiles.length ? `，共 ${formatBytes(batchFiles.reduce((total, file) => total + file.size, 0))}` : ""}
            </p>
          </div>
          <Button onClick={() => batchUploadMutation.mutate()} disabled={!batchFiles.length || batchUploadMutation.isPending}>
            创建批量任务
          </Button>

          {batchStatusQuery.data ? (
            <div className="rounded-xl border border-border bg-black/20 p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium text-foreground">批量任务进度</p>
                <Badge variant={isBatchRunning(batchStatusQuery.data) ? "secondary" : "default"}>
                  {isBatchRunning(batchStatusQuery.data) ? "进行中" : "已结束"}
                </Badge>
              </div>
              <p className="mt-2 text-muted-foreground">
                已完成 {batchStatusQuery.data.completed} / {batchStatusQuery.data.totalFiles}，失败 {batchStatusQuery.data.failed}
              </p>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-black/30">
                <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${batchStatusQuery.data.progress}%` }} />
              </div>
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
