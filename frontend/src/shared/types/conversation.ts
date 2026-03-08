import type { SSEEvent } from "@/shared/types/api";

export interface Conversation {
  id: string;
  userId: string;
  title: string;
  documentIds: string[];
  messageCount: number;
  lastMessage?: string | null;
  createdAt?: string;
  updatedAt?: string;
}

export interface Message {
  id: string;
  conversationId: string;
  role: "user" | "assistant";
  content: string;
  thinking?: Array<{ step: string; content: string }> | null;
  sources?: Array<Record<string, unknown>> | null;
  createdAt?: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface ConversationList {
  total: number;
  conversations: Conversation[];
}

export interface SendMessageRequest {
  content: string;
  topK?: number;
  enableThinking?: boolean;
  temperature?: number;
  model?: string;
}

export interface SendMessageResponse {
  userMessage: Message;
  assistantMessage: Message;
}

export interface StreamSnapshot {
  answer: string;
  thinking: Array<{ step: string; content: string }>;
  sources: Array<Record<string, unknown>>;
  events: SSEEvent[];
  completed: boolean;
  error?: string;
}
