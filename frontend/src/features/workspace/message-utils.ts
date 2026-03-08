import type { Message, StreamSnapshot } from "@/shared/types/conversation";

export function isAbortError(error: unknown) {
  return error instanceof DOMException
    ? error.name === "AbortError"
    : typeof error === "object" &&
        error !== null &&
        "name" in error &&
        (error as { name?: unknown }).name === "AbortError";
}

export function summarize(text?: string | null) {
  const normalized = String(text ?? "").replace(/\s+/g, " ").trim();
  if (!normalized) return "暂无内容";
  return normalized.length > 64 ? `${normalized.slice(0, 64)}…` : normalized;
}

export function buildDraftMessage(conversationId: string, snapshot: StreamSnapshot | null): Message | null {
  if (!snapshot) return null;
  if (!snapshot.answer && !snapshot.thinking.length && !snapshot.sources.length && !snapshot.error) return null;

  return {
    id: `draft:${conversationId}`,
    conversationId,
    role: "assistant",
    content: snapshot.error || snapshot.answer || (snapshot.thinking.length ? "正在整理答案…" : "正在思考…"),
    thinking: snapshot.thinking,
    sources: snapshot.sources,
    createdAt: new Date().toISOString(),
  };
}

export function createOptimisticUserMessage(conversationId: string, content: string): Message {
  return {
    id: `optimistic:${conversationId}:${Date.now()}`,
    conversationId,
    role: "user",
    content,
    createdAt: new Date().toISOString(),
  };
}
