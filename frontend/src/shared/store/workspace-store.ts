import { create } from "zustand";

import { DEFAULT_LLM_MODEL } from "@/shared/config/llm-models";
import type { SSEEvent } from "@/shared/types/api";
import type { StreamSnapshot } from "@/shared/types/conversation";

function createSnapshot(
  snapshot?: Partial<Omit<StreamSnapshot, "events">> & { events?: SSEEvent[] },
): StreamSnapshot {
  return {
    answer: snapshot?.answer ?? "",
    thinking: snapshot?.thinking ?? [],
    sources: snapshot?.sources ?? [],
    responseMeta: snapshot?.responseMeta ?? null,
    events: snapshot?.events ?? [],
    completed: snapshot?.completed ?? false,
    error: snapshot?.error,
  };
}

type WorkspaceState = {
  selectedConversationId: string | null;
  selectedModel: string;
  enableStream: boolean;
  activeStreamConversationId: string | null;
  activeStreamController: AbortController | null;
  selectedAssistantMessageIdByConversation: Record<string, string | null>;
  streamSnapshotsByConversation: Record<string, StreamSnapshot>;
  setSelectedConversationId: (conversationId: string | null) => void;
  setSelectedModel: (model: string) => void;
  setEnableStream: (enabled: boolean) => void;
  setInspectorMessageId: (conversationId: string, messageId: string | null) => void;
  setStreamSnapshot: (conversationId: string, snapshot: StreamSnapshot | null) => void;
  updateStreamSnapshot: (conversationId: string, updater: (snapshot: StreamSnapshot) => StreamSnapshot) => void;
  clearStreamSnapshot: (conversationId: string) => void;
  setActiveStream: (conversationId: string | null, controller: AbortController | null) => void;
  stopActiveStream: () => void;
};

export function createEmptyStreamSnapshot(snapshot?: Partial<StreamSnapshot>) {
  return createSnapshot(snapshot);
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  selectedConversationId: null,
  selectedModel: DEFAULT_LLM_MODEL,
  enableStream: true,
  activeStreamConversationId: null,
  activeStreamController: null,
  selectedAssistantMessageIdByConversation: {},
  streamSnapshotsByConversation: {},
  setSelectedConversationId: (selectedConversationId) => set({ selectedConversationId }),
  setSelectedModel: (selectedModel) => set({ selectedModel }),
  setEnableStream: (enableStream) => set({ enableStream }),
  setInspectorMessageId: (conversationId, messageId) =>
    set((state) => ({
      selectedAssistantMessageIdByConversation: {
        ...state.selectedAssistantMessageIdByConversation,
        [conversationId]: messageId,
      },
    })),
  setStreamSnapshot: (conversationId, snapshot) =>
    set((state) => {
      const nextSnapshots = { ...state.streamSnapshotsByConversation };
      if (snapshot) {
        nextSnapshots[conversationId] = createSnapshot(snapshot);
      } else {
        delete nextSnapshots[conversationId];
      }
      return { streamSnapshotsByConversation: nextSnapshots };
    }),
  updateStreamSnapshot: (conversationId, updater) =>
    set((state) => ({
      streamSnapshotsByConversation: {
        ...state.streamSnapshotsByConversation,
        [conversationId]: updater(createSnapshot(state.streamSnapshotsByConversation[conversationId])),
      },
    })),
  clearStreamSnapshot: (conversationId) =>
    set((state) => {
      const nextSnapshots = { ...state.streamSnapshotsByConversation };
      delete nextSnapshots[conversationId];
      return { streamSnapshotsByConversation: nextSnapshots };
    }),
  setActiveStream: (activeStreamConversationId, activeStreamController) =>
    set({ activeStreamConversationId, activeStreamController }),
  stopActiveStream: () => {
    get().activeStreamController?.abort();
    set({ activeStreamConversationId: null, activeStreamController: null });
  },
}));
