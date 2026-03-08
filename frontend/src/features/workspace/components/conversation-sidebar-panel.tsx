import { Check, MessageSquarePlus, Pencil, Trash2, X } from "lucide-react";

import { summarize } from "@/features/workspace/message-utils";
import type { WorkspacePageState } from "@/features/workspace/use-workspace-page";
import { cn, formatDateTime } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Loading } from "@/shared/ui/loading";

export function ConversationSidebarPanel({ state }: { state: WorkspacePageState }) {
  const {
    activeStreamConversationId,
    createMutation,
    deleteMutation,
    editingId,
    editingTitle,
    listQuery,
    renameMutation,
    selectedConversationId,
    setEditingId,
    setEditingTitle,
    setSelectedConversationId,
    streamSnapshots,
  } = state;

  return (
    <Card className="flex h-[calc(100vh-7rem)] flex-col overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle>会话工作台</CardTitle>
        <Button size="sm" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
          <MessageSquarePlus className="h-4 w-4" />
          新建
        </Button>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 space-y-3 overflow-y-auto">
        {listQuery.isLoading ? (
          <Loading text="正在加载会话..." />
        ) : (
          listQuery.data?.conversations.map((item) => {
            const snapshot = streamSnapshots[item.id];
            const isStreaming =
              activeStreamConversationId === item.id && snapshot && !snapshot.completed && !snapshot.error;

            return (
              <div
                key={item.id}
                className={cn(
                  "rounded-xl border p-3",
                  item.id === selectedConversationId ? "border-primary bg-primary/10" : "border-border bg-black/10",
                )}
              >
                {editingId === item.id ? (
                  <div className="space-y-3">
                    <Input
                      value={editingTitle}
                      onChange={(event) => setEditingTitle(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          renameMutation.mutate({ conversationId: item.id, title: editingTitle.trim() });
                        }
                        if (event.key === "Escape") {
                          setEditingId(null);
                        }
                      }}
                    />
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" size="sm" onClick={() => setEditingId(null)}>
                        <X className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        disabled={!editingTitle.trim() || renameMutation.isPending}
                        onClick={() => renameMutation.mutate({ conversationId: item.id, title: editingTitle.trim() })}
                      >
                        <Check className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <button type="button" className="w-full text-left" onClick={() => setSelectedConversationId(item.id)}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="truncate font-medium">{item.title}</p>
                        <div className="flex gap-2">
                          {isStreaming ? <Badge variant="secondary">流式中</Badge> : null}
                          <Badge variant="secondary">{item.messageCount} 条</Badge>
                        </div>
                      </div>
                      <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">
                        {summarize(snapshot?.answer || item.lastMessage)}
                      </p>
                      <p className="mt-2 text-[11px] text-muted-foreground">{formatDateTime(item.updatedAt)}</p>
                    </button>
                    <div className="mt-3 flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setEditingId(item.id);
                          setEditingTitle(item.title);
                        }}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => deleteMutation.mutate(item.id)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </>
                )}
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
