import { Tags } from "lucide-react";

import type { DocumentsPageState } from "@/features/documents/use-documents-page";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Loading } from "@/shared/ui/loading";

export function DocumentsTagsPanel({ state }: { state: DocumentsPageState }) {
  const {
    createTagMutation,
    documentTagsQuery,
    handleToggleTag,
    newTagName,
    selectedDocument,
    selectedDocumentId,
    setNewTagName,
    tagsQuery,
  } = state;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Tags className="h-5 w-5" />
          标签管理
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-2xl border border-border bg-black/10 p-4">
          <p className="text-sm text-muted-foreground">
            当前文档：<span className="text-foreground">{selectedDocument?.fileName ?? "未选择文档"}</span>
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {(documentTagsQuery.data ?? []).map((tag) => (
              <Badge key={tag.id} className="gap-2" variant="default">
                <span>{tag.name}</span>
              </Badge>
            ))}
            {selectedDocumentId && !(documentTagsQuery.data ?? []).length ? (
              <span className="text-sm text-muted-foreground">当前文档还没有标签</span>
            ) : null}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
          <Input
            value={newTagName}
            onChange={(event) => setNewTagName(event.target.value)}
            placeholder="输入新标签名称，创建后会自动绑定到当前文档"
          />
          <Button onClick={() => createTagMutation.mutate()} disabled={!newTagName.trim() || createTagMutation.isPending}>
            新建标签
          </Button>
        </div>

        <div className="flex flex-wrap gap-2">
          {(tagsQuery.data ?? []).map((tag) => {
            const attached = (documentTagsQuery.data ?? []).some((item) => item.id === tag.id);
            return (
              <button
                key={tag.id}
                type="button"
                onClick={() => handleToggleTag(tag.id)}
                className={cn(
                  "rounded-full border px-3 py-1 text-sm transition-colors",
                  attached
                    ? "border-primary bg-primary/15 text-primary"
                    : "border-border bg-black/10 text-muted-foreground hover:border-primary/40 hover:text-foreground",
                )}
              >
                {tag.name}
                {typeof tag.usageCount === "number" ? ` · ${tag.usageCount}` : ""}
              </button>
            );
          })}
          {tagsQuery.isLoading ? <Loading text="正在加载标签..." /> : null}
        </div>
      </CardContent>
    </Card>
  );
}
