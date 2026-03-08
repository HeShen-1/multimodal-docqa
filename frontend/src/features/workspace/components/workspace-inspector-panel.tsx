import { cn } from "@/shared/lib/utils";
import type { WorkspacePageState } from "@/features/workspace/use-workspace-page";
import { summarize } from "@/features/workspace/message-utils";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";

export function WorkspaceInspectorPanel({ state }: { state: WorkspacePageState }) {
  const { assistantMessages, selectedAssistantMessage, selectedConversationId, setInspectorMessageId } = state;

  return (
    <Card className="flex h-[calc(100vh-7rem)] flex-col overflow-hidden">
      <CardHeader className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle>Thinking & Sources</CardTitle>
          {selectedAssistantMessage?.id.startsWith("draft:") ? <Badge variant="secondary">流式草稿</Badge> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {assistantMessages.map((message, index) => (
            <button
              key={message.id}
              type="button"
              className={cn(
                "rounded-full border px-3 py-1 text-xs",
                message.id === selectedAssistantMessage?.id
                  ? "border-primary bg-primary/15 text-primary"
                  : "border-border bg-black/10 text-muted-foreground",
              )}
              onClick={() => selectedConversationId && setInspectorMessageId(selectedConversationId, message.id)}
            >
              {message.id.startsWith("draft:") ? "当前流式回复" : `回复 ${index + 1}`}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 space-y-4 overflow-y-auto text-sm">
        {selectedAssistantMessage ? (
          <>
            <div className="rounded-xl border border-border bg-black/10 p-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">当前查看</p>
              <p className="mt-2 line-clamp-3 text-foreground">{summarize(selectedAssistantMessage.content)}</p>
            </div>

            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Response Meta</p>
              {selectedAssistantMessage.responseMeta ? (
                <div className="rounded-xl border border-border bg-black/20 p-3 text-muted-foreground">
                  <div className="flex flex-wrap gap-2">
                    {selectedAssistantMessage.responseMeta.modelName ? (
                      <Badge variant="secondary">{selectedAssistantMessage.responseMeta.modelName}</Badge>
                    ) : null}
                    {selectedAssistantMessage.responseMeta.retrievalStrategy ? (
                      <Badge variant="secondary">{selectedAssistantMessage.responseMeta.retrievalStrategy}</Badge>
                    ) : null}
                    {selectedAssistantMessage.responseMeta.rerankApplied ? <Badge variant="secondary">Rerank</Badge> : null}
                  </div>
                  <p className="mt-2 leading-6">
                    {(selectedAssistantMessage.responseMeta.latencyMs ?? 0) > 0
                      ? `耗时 ${Math.round(selectedAssistantMessage.responseMeta.latencyMs ?? 0)} ms`
                      : "耗时未记录"}
                    {" · "}
                    命中 {selectedAssistantMessage.responseMeta.retrievedChunks ?? 0} 段
                    {" · "}
                    引用 {selectedAssistantMessage.responseMeta.citationCount ?? 0} 条
                  </p>
                  {selectedAssistantMessage.responseMeta.rewrittenQuery ? (
                    <p className="mt-2 leading-6">改写查询：{selectedAssistantMessage.responseMeta.rewrittenQuery}</p>
                  ) : null}
                  {selectedAssistantMessage.responseMeta.fallbackReason ? (
                    <p className="mt-2 leading-6 text-amber-300">
                      兜底原因：{selectedAssistantMessage.responseMeta.fallbackReason}
                    </p>
                  ) : null}
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-border bg-black/10 p-3 text-muted-foreground">
                  当前这轮回复没有记录响应元数据。
                </div>
              )}
            </div>

            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Thinking</p>
              {(selectedAssistantMessage.thinking ?? []).length ? (
                (selectedAssistantMessage.thinking ?? []).map((step, index) => (
                  <div key={`${step.step}-${index}`} className="rounded-xl border border-border bg-black/20 p-3">
                    <p className="font-medium text-primary">{step.step}</p>
                    <p className="mt-2 whitespace-pre-wrap leading-6 text-muted-foreground">{step.content}</p>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-border bg-black/10 p-3 text-muted-foreground">
                  当前这轮回复没有记录 Thinking。
                </div>
              )}
            </div>

            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Sources</p>
              {(selectedAssistantMessage.sources ?? []).length ? (
                (selectedAssistantMessage.sources ?? []).map((source, index) => (
                  <div key={`source-${index}`} className="rounded-xl border border-border bg-black/20 p-3">
                    <div className="flex flex-wrap gap-2">
                      {source.fileName || source.document_name ? (
                        <Badge variant="secondary">{String(source.fileName ?? source.document_name)}</Badge>
                      ) : null}
                      {source.page != null ? <Badge variant="secondary">P.{String(source.page)}</Badge> : null}
                    </div>
                    <p className="mt-2 whitespace-pre-wrap text-xs leading-6 text-muted-foreground">
                      {String(source.content ?? "")}
                    </p>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-border bg-black/10 p-3 text-muted-foreground">
                  当前这轮回复没有关联来源。
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="rounded-xl border border-dashed border-border bg-black/10 p-4 text-muted-foreground">
            选择一条 AI 回复后，这里会展示对应的 Thinking 与 Sources。
          </div>
        )}
      </CardContent>
    </Card>
  );
}
