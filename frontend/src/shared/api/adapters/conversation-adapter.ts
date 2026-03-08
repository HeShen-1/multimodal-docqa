import { unwrapApiEnvelope } from "@/shared/api/adapters/envelope";
import type {
  Conversation,
  ConversationDetail,
  ConversationList,
  Message,
  ResponseMeta,
  SendMessageResponse,
} from "@/shared/types/conversation";

type AnyRecord = Record<string, unknown>;

function normalizeMessage(raw: AnyRecord): Message {
  const extraData = (raw.extra_data ?? raw.extraData ?? raw.response_meta ?? raw.responseMeta) as
    | Record<string, unknown>
    | undefined;
  const responseMeta: ResponseMeta | null = extraData
    ? {
        modelName: extraData.model_name as string | undefined,
        latencyMs: Number(extraData.latency_ms ?? 0) || undefined,
        retrievedChunks: Number(extraData.retrieved_chunks ?? 0) || undefined,
        citationCount: Number(extraData.citation_count ?? 0) || undefined,
        fallbackReason: (extraData.fallback_reason as string | null | undefined) ?? null,
        retrievalStrategy: extraData.retrieval_strategy as string | undefined,
        rewrittenQuery: extraData.rewritten_query as string | undefined,
        topScore: Number(extraData.top_score ?? 0) || undefined,
        evidenceCoverage: Number(extraData.evidence_coverage ?? 0) || undefined,
        rerankApplied: typeof extraData.rerank_applied === "boolean" ? (extraData.rerank_applied as boolean) : undefined,
      }
    : null;

  return {
    id: String(raw.id ?? ""),
    conversationId: String(raw.conversation_id ?? raw.conversationId ?? ""),
    role: (raw.role as "user" | "assistant") ?? "assistant",
    content: String(raw.content ?? ""),
    thinking: (raw.thinking as Array<{ step: string; content: string }> | undefined) ?? null,
    sources: (raw.sources as Array<Record<string, unknown>> | undefined) ?? null,
    responseMeta,
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
