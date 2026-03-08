import { fetchEventSource } from "@microsoft/fetch-event-source";

import {
  adaptConversationDetail,
  adaptConversationList,
  adaptSendMessage,
  adaptSingleConversation,
} from "@/shared/api/adapters/conversation-adapter";
import { adaptStreamEvent } from "@/shared/api/adapters/stream-adapter";
import { apiClient } from "@/shared/api/client";
import { getAccessToken } from "@/shared/store/auth-store";
import type {
  Conversation,
  ConversationDetail,
  ConversationList,
  SendMessageRequest,
  SendMessageResponse,
} from "@/shared/types/conversation";

export const workspaceApi = {
  async createConversation(payload: { title?: string; documentIds?: string[] }): Promise<Conversation> {
    const response = await apiClient.post("/conversations", {
      title: payload.title,
      document_ids: payload.documentIds,
    });
    return adaptSingleConversation(response.data);
  },

  async listConversations(params: { skip?: number; limit?: number } = {}): Promise<ConversationList> {
    const response = await apiClient.get("/conversations", { params });
    return adaptConversationList(response.data);
  },

  async getConversation(conversationId: string): Promise<ConversationDetail> {
    const response = await apiClient.get(`/conversations/${conversationId}`);
    return adaptConversationDetail(response.data);
  },

  async sendMessage(conversationId: string, payload: SendMessageRequest): Promise<SendMessageResponse> {
    const response = await apiClient.post(`/conversations/${conversationId}/messages`, {
      content: payload.content,
      top_k: payload.topK ?? 5,
      enable_thinking: payload.enableThinking ?? true,
      temperature: payload.temperature ?? 0.7,
      model: payload.model,
    });
    return adaptSendMessage(response.data);
  },

  async renameConversation(conversationId: string, title: string) {
    await apiClient.patch(`/conversations/${conversationId}/title`, { title });
  },

  async deleteConversation(conversationId: string) {
    await apiClient.delete(`/conversations/${conversationId}`);
  },

  async exportConversation(conversationId: string, format: "markdown" | "json" | "pdf") {
    const response = await apiClient.get(`/conversations/${conversationId}/export`, {
      params: { format, include_thinking: true, include_sources: true },
      responseType: "blob",
    });
    return response.data;
  },

  async streamMessage(
    conversationId: string,
    payload: SendMessageRequest,
    handlers: {
      onEvent: (event: ReturnType<typeof adaptStreamEvent>) => void;
      onComplete: () => void;
      onError: (error: unknown) => void;
      signal?: AbortSignal;
    },
  ) {
    const token = getAccessToken();
    const endpoint = `${import.meta.env.VITE_API_BASE_URL}/conversations/${conversationId}/messages/stream`;

    await fetchEventSource(endpoint, {
      method: "POST",
      signal: handlers.signal,
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        content: payload.content,
        top_k: payload.topK ?? 5,
        enable_thinking: payload.enableThinking ?? true,
        temperature: payload.temperature ?? 0.7,
        model: payload.model,
      }),
      onmessage(message) {
        const event = adaptStreamEvent(message.data);
        if (event) {
          handlers.onEvent(event);
        }
      },
      onclose() {
        handlers.onComplete();
      },
      onerror(error) {
        handlers.onError(error);
        throw error;
      },
      openWhenHidden: true,
    });
  },
};
