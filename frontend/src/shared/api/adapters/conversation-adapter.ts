import { unwrapApiEnvelope } from "@/shared/api/adapters/envelope";
import type {
  Conversation,
  ConversationDetail,
  ConversationList,
  Message,
  SendMessageResponse,
} from "@/shared/types/conversation";

type AnyRecord = Record<string, unknown>;

function normalizeMessage(raw: AnyRecord): Message {
  return {
    id: String(raw.id ?? ""),
    conversationId: String(raw.conversation_id ?? raw.conversationId ?? ""),
    role: (raw.role as "user" | "assistant") ?? "assistant",
    content: String(raw.content ?? ""),
    thinking: (raw.thinking as Array<{ step: string; content: string }> | undefined) ?? null,
    sources: (raw.sources as Array<Record<string, unknown>> | undefined) ?? null,
    createdAt: (raw.created_at ?? raw.createdAt) as string | undefined,
  };
}

function normalizeConversation(raw: AnyRecord): Conversation {
  return {
    id: String(raw.id ?? ""),
    userId: String(raw.user_id ?? raw.userId ?? ""),
    title: String(raw.title ?? "未命名会话"),
    documentIds: (raw.document_ids ?? raw.documentIds ?? []) as string[],
    messageCount: Number(raw.message_count ?? raw.messageCount ?? 0),
    lastMessage: (raw.last_message ?? raw.lastMessage) as string | null | undefined,
    createdAt: (raw.created_at ?? raw.createdAt) as string | undefined,
    updatedAt: (raw.updated_at ?? raw.updatedAt) as string | undefined,
  };
}

export function adaptConversationList(payload: unknown): ConversationList {
  const raw = unwrapApiEnvelope<AnyRecord>(payload);
  const conversations = ((raw.conversations ?? []) as AnyRecord[]).map(normalizeConversation);
  return {
    total: Number(raw.total ?? conversations.length),
    conversations,
  };
}

export function adaptConversationDetail(payload: unknown): ConversationDetail {
  const raw = unwrapApiEnvelope<AnyRecord>(payload);
  const base = normalizeConversation(raw);
  return {
    ...base,
    messages: ((raw.messages ?? []) as AnyRecord[]).map(normalizeMessage),
  };
}

export function adaptSingleConversation(payload: unknown): Conversation {
  const raw = unwrapApiEnvelope<AnyRecord>(payload);
  return normalizeConversation(raw);
}

export function adaptSendMessage(payload: unknown): SendMessageResponse {
  const raw = payload as AnyRecord;
  return {
    userMessage: normalizeMessage((raw.user_message ?? raw.userMessage ?? {}) as AnyRecord),
    assistantMessage: normalizeMessage((raw.assistant_message ?? raw.assistantMessage ?? {}) as AnyRecord),
  };
}

