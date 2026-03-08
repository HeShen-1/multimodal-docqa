import { cn, formatDateTime } from "@/shared/lib/utils";
import type { Message } from "@/shared/types/conversation";
import { Badge } from "@/shared/ui/badge";
import { MarkdownContent } from "@/shared/ui/markdown-content";

export function MessageBubble({
  message,
  selected,
  onInspect,
}: {
  message: Message;
  selected?: boolean;
  onInspect?: () => void;
}) {
  const isUser = message.role === "user";
  const thinkingSteps = message.thinking ?? [];
  const sources = message.sources ?? [];
  const isDraft = message.id.startsWith("draft:");

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[88%] rounded-2xl border px-4 py-3 text-sm transition",
          isUser
            ? "border-primary/30 bg-primary/20 text-primary-foreground"
            : "border-border bg-black/15 text-foreground",
          !isUser && selected && "border-primary/70 bg-primary/10 shadow-glow",
        )}
      >
        {!isUser ? (
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
              <span>{isDraft ? "流式草稿" : "AI 回复"}</span>
              {thinkingSteps.length ? <Badge variant="secondary">Thinking {thinkingSteps.length}</Badge> : null}
              {sources.length ? <Badge variant="secondary">Sources {sources.length}</Badge> : null}
            </div>
            {onInspect ? (
              <button
                type="button"
                className="text-[11px] text-primary underline-offset-4 hover:underline"
                onClick={onInspect}
              >
                查看详情
              </button>
            ) : null}
          </div>
        ) : null}

        {isUser ? (
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        ) : (
          <MarkdownContent content={message.content} className="text-slate-50" />
        )}

        <p className="mt-3 text-[11px] text-muted-foreground">{formatDateTime(message.createdAt)}</p>
      </div>
    </div>
  );
}
