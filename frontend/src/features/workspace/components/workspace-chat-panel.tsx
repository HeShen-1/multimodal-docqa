import { RefreshCcw } from "lucide-react";

import { MessageBubble } from "@/features/workspace/components/message-bubble";
import type { WorkspacePageState } from "@/features/workspace/use-workspace-page";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Loading } from "@/shared/ui/loading";
import { Select } from "@/shared/ui/select";
import { Textarea } from "@/shared/ui/textarea";

export function WorkspaceChatPanel({ state }: { state: WorkspacePageState }) {
  const {
    activeStreamConversationId,
    bottomRef,
    detailQuery,
    listQuery,
    mergedMessages,
    messageInput,
    onSend,
    onStop,
    selectedAssistantMessage,
    selectedConversationId,
    selectedModel,
    modelOptions,
    setInspectorMessageId,
    setMessageInput,
    setSelectedModel,
    streaming,
  } = state;

  return (
    <Card className="flex h-[calc(100vh-7rem)] flex-col overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <CardTitle>{detailQuery.data?.title ?? "请选择会话"}</CardTitle>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Select
            className="w-52"
            value={selectedModel}
            options={modelOptions}
            onChange={(event) => setSelectedModel(event.target.value)}
          />
          <Button variant="secondary" size="sm" onClick={() => void listQuery.refetch()}>
            <RefreshCcw className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto rounded-xl border border-border bg-black/15 p-4">
          {detailQuery.isLoading ? (
            <Loading text="正在加载消息..." />
          ) : (
            mergedMessages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                selected={message.role === "assistant" && message.id === selectedAssistantMessage?.id}
                onInspect={
                  message.role === "assistant" && selectedConversationId
                    ? () => setInspectorMessageId(selectedConversationId, message.id)
                    : undefined
                }
              />
            ))
          )}
          <div ref={bottomRef} />
        </div>
        <div className="mt-3 space-y-3">
          <Textarea
            value={messageInput}
            onChange={(event) => setMessageInput(event.target.value)}
            placeholder="输入问题，例如：请总结这份文档的核心结论。"
            className="min-h-[104px]"
          />
          <div className="flex justify-end">
            <div className="flex flex-wrap justify-end gap-2">
              {streaming ? (
                <Button variant="destructive" onClick={onStop}>
                  停止生成
                </Button>
              ) : null}
              <Button onClick={() => void onSend()} disabled={!selectedConversationId || !messageInput.trim() || Boolean(activeStreamConversationId)}>
                发送消息
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
