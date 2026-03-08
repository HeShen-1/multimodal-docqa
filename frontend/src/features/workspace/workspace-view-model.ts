import { buildDraftMessage } from "@/features/workspace/message-utils";
import type { Message, StreamSnapshot } from "@/shared/types/conversation";

export function mergeMessagesWithDraft(
  messages: Message[],
  conversationId: string | null,
  snapshot: StreamSnapshot | null,
) {
  const draft = conversationId ? buildDraftMessage(conversationId, snapshot) : null;
  if (!draft) return messages;

  const latestAssistant = [...messages].reverse().find((item) => item.role === "assistant");
  if (snapshot?.completed && !snapshot.error && latestAssistant?.content.trim() === snapshot.answer.trim()) {
    return messages;
  }

  return [...messages, draft];
}

export function getAssistantMessages(messages: Message[]) {
  return messages.filter((item) => item.role === "assistant");
}

export function getSelectedAssistantMessage(messages: Message[], selectedAssistantId: string | null) {
  return messages.find((item) => item.id === selectedAssistantId) ?? messages.at(-1) ?? null;
}
