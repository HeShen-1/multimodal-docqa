import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  createOptimisticUserMessage,
  isAbortError,
} from "@/features/workspace/message-utils";
import {
  getAssistantMessages,
  getSelectedAssistantMessage,
  mergeMessagesWithDraft,
} from "@/features/workspace/workspace-view-model";
import { workspaceApi } from "@/features/workspace/workspace-api";
import { normalizeApiError } from "@/shared/api/errors";
import { createEmptyStreamSnapshot, useWorkspaceStore } from "@/shared/store/workspace-store";
import type { ConversationDetail } from "@/shared/types/conversation";

export function useWorkspacePage() {
  const queryClient = useQueryClient();
  const mountedRef = useRef(true);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const [messageInput, setMessageInput] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");

  const selectedConversationId = useWorkspaceStore((state) => state.selectedConversationId);
  const selectedModel = useWorkspaceStore((state) => state.selectedModel);
  const activeStreamConversationId = useWorkspaceStore((state) => state.activeStreamConversationId);
  const activeStreamController = useWorkspaceStore((state) => state.activeStreamController);
  const streamSnapshots = useWorkspaceStore((state) => state.streamSnapshotsByConversation);
  const selectedAssistantIds = useWorkspaceStore((state) => state.selectedAssistantMessageIdByConversation);
  const setSelectedConversationId = useWorkspaceStore((state) => state.setSelectedConversationId);
  const setSelectedModel = useWorkspaceStore((state) => state.setSelectedModel);
  const setInspectorMessageId = useWorkspaceStore((state) => state.setInspectorMessageId);
  const setStreamSnapshot = useWorkspaceStore((state) => state.setStreamSnapshot);
  const clearStreamSnapshot = useWorkspaceStore((state) => state.clearStreamSnapshot);
  const setActiveStream = useWorkspaceStore((state) => state.setActiveStream);
  const stopActiveStream = useWorkspaceStore((state) => state.stopActiveStream);

  const currentSnapshot = selectedConversationId ? streamSnapshots[selectedConversationId] ?? null : null;
  const streaming = Boolean(
    selectedConversationId &&
      activeStreamConversationId === selectedConversationId &&
      activeStreamController &&
      currentSnapshot &&
      !currentSnapshot.completed &&
      !currentSnapshot.error,
  );

  useEffect(() => () => void (mountedRef.current = false), []);

  const listQuery = useQuery({
    queryKey: ["conversations"],
    queryFn: () => workspaceApi.listConversations({ skip: 0, limit: 50 }),
  });

  useEffect(() => {
    const conversations = listQuery.data?.conversations ?? [];
    if (!conversations.length) {
      setSelectedConversationId(null);
      return;
    }

    if (!selectedConversationId || !conversations.some((item) => item.id === selectedConversationId)) {
      setSelectedConversationId(conversations[0].id);
    }
  }, [listQuery.data?.conversations, selectedConversationId, setSelectedConversationId]);

  const detailQuery = useQuery({
    queryKey: ["conversation", selectedConversationId],
    queryFn: () => workspaceApi.getConversation(selectedConversationId!),
    enabled: Boolean(selectedConversationId),
  });

  const selectedConversation = useMemo(
    () => listQuery.data?.conversations.find((item) => item.id === selectedConversationId) ?? null,
    [listQuery.data?.conversations, selectedConversationId],
  );

  const createMutation = useMutation({
    mutationFn: () => workspaceApi.createConversation({}),
    onSuccess: async (conversation) => {
      toast.success("已创建新的会话窗口");
      setSelectedConversationId(conversation.id);
      setInspectorMessageId(conversation.id, null);
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  const renameMutation = useMutation({
    mutationFn: ({ conversationId, title }: { conversationId: string; title: string }) =>
      workspaceApi.renameConversation(conversationId, title),
    onSuccess: async (_, vars) => {
      toast.success("会话标题已更新");
      setEditingId(null);
      setEditingTitle("");
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
      await queryClient.invalidateQueries({ queryKey: ["conversation", vars.conversationId] });
    },
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  const deleteMutation = useMutation({
    mutationFn: async (conversationId: string) => {
      if (activeStreamConversationId === conversationId) {
        stopActiveStream();
      }
      clearStreamSnapshot(conversationId);
      await workspaceApi.deleteConversation(conversationId);
      return conversationId;
    },
    onSuccess: async (conversationId) => {
      toast.success("会话已删除");
      if (selectedConversationId === conversationId) {
        setSelectedConversationId(null);
      }
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
      await queryClient.invalidateQueries({ queryKey: ["conversation"] });
    },
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  const appendOptimisticUserMessage = (conversationId: string, content: string) => {
    const optimisticMessage = createOptimisticUserMessage(conversationId, content);

    queryClient.setQueryData<ConversationDetail | undefined>(["conversation", conversationId], (previous) => {
      if (previous) {
        return {
          ...previous,
          messageCount: previous.messageCount + 1,
          lastMessage: content,
          messages: [...previous.messages, optimisticMessage],
        };
      }

      if (!selectedConversation || selectedConversation.id !== conversationId) {
        return previous;
      }

      return {
        ...selectedConversation,
        messageCount: selectedConversation.messageCount + 1,
        lastMessage: content,
        messages: [optimisticMessage],
      };
    });
  };

  const mergedMessages = useMemo(
    () => mergeMessagesWithDraft(detailQuery.data?.messages ?? [], selectedConversationId, currentSnapshot),
    [detailQuery.data?.messages, selectedConversationId, currentSnapshot],
  );

  const assistantMessages = useMemo(() => getAssistantMessages(mergedMessages), [mergedMessages]);

  const selectedAssistantId = selectedConversationId ? selectedAssistantIds[selectedConversationId] ?? null : null;
  const selectedAssistantMessage = useMemo(
    () => getSelectedAssistantMessage(assistantMessages, selectedAssistantId),
    [assistantMessages, selectedAssistantId],
  );

  useEffect(() => {
    if (!selectedConversationId) return;
    if (!assistantMessages.length) {
      setInspectorMessageId(selectedConversationId, null);
      return;
    }
    if (!selectedAssistantMessage) {
      setInspectorMessageId(selectedConversationId, assistantMessages.at(-1)?.id ?? null);
    }
  }, [assistantMessages, selectedAssistantMessage, selectedConversationId, setInspectorMessageId]);

  useEffect(() => {
    if (!selectedConversationId || !currentSnapshot?.completed || currentSnapshot.error) return;

    const latestAssistant = [...(detailQuery.data?.messages ?? [])].reverse().find((item) => item.role === "assistant");
    if (!latestAssistant) return;
    if (currentSnapshot.answer.trim() && latestAssistant.content.trim() !== currentSnapshot.answer.trim()) return;

    clearStreamSnapshot(selectedConversationId);
    setInspectorMessageId(selectedConversationId, latestAssistant.id);
  }, [detailQuery.data?.messages, selectedConversationId, currentSnapshot, clearStreamSnapshot, setInspectorMessageId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: streaming ? "smooth" : "auto" });
  }, [mergedMessages, currentSnapshot?.answer, streaming]);

  const onSend = async () => {
    const conversationId = selectedConversationId;
    const content = messageInput.trim();
    if (!conversationId || !content) return;

    appendOptimisticUserMessage(conversationId, content);
    if (mountedRef.current) {
      setMessageInput("");
    }

    if (activeStreamConversationId && activeStreamConversationId !== conversationId) {
      stopActiveStream();
    }

    const controller = new AbortController();
    setActiveStream(conversationId, controller);
    setStreamSnapshot(conversationId, createEmptyStreamSnapshot());
    setInspectorMessageId(conversationId, `draft:${conversationId}`);

    try {
      await workspaceApi.streamMessage(
        conversationId,
        {
          content,
          topK: 5,
          enableThinking: true,
          temperature: 0.7,
          model: selectedModel,
        },
        {
          signal: controller.signal,
          onEvent: (event) => {
            if (!event) return;

            const store = useWorkspaceStore.getState();
            store.updateStreamSnapshot(conversationId, (previous) => {
              const next = { ...previous, events: [...previous.events, event] };

              if (event.type === "thinking") {
                return {
                  ...next,
                  thinking: [
                    ...previous.thinking,
                    {
                      step: String(event.step ?? "思考"),
                      content: String(event.content ?? ""),
                    },
                  ],
                };
              }

              if (event.type === "answer") {
                return {
                  ...next,
                  answer: `${previous.answer}${String(event.content ?? "")}`,
                };
              }

              if (event.type === "source") {
                return {
                  ...next,
                  sources: [...previous.sources, event],
                };
              }

              if (event.type === "done") {
                return { ...next, completed: true, error: undefined };
              }

              if (event.type === "error") {
                return {
                  ...next,
                  completed: true,
                  error: String(event.content ?? "流式会话失败"),
                };
              }

              return next;
            });

            if (event.type === "error") {
              store.setActiveStream(null, null);
              toast.error(String(event.content ?? "流式会话失败"));
            }
          },
          onComplete: async () => {
            useWorkspaceStore.getState().setActiveStream(null, null);
            if (useWorkspaceStore.getState().streamSnapshotsByConversation[conversationId]?.error) return;
            await queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
            await queryClient.invalidateQueries({ queryKey: ["conversations"] });
          },
          onError: (error) => {
            if (isAbortError(error)) return;

            const message = normalizeApiError(error).message;
            const store = useWorkspaceStore.getState();
            store.updateStreamSnapshot(conversationId, (previous) => ({
              ...previous,
              completed: true,
              error: message,
            }));
            store.setActiveStream(null, null);
            toast.error(message);
          },
        },
      );
    } catch (error) {
      if (isAbortError(error)) return;

      const message = normalizeApiError(error).message;
      const store = useWorkspaceStore.getState();
      store.updateStreamSnapshot(conversationId, (previous) => ({
        ...previous,
        completed: true,
        error: message,
      }));
      store.setActiveStream(null, null);
      toast.error(message);
    }
  };

  const onStop = () => {
    const conversationId = useWorkspaceStore.getState().activeStreamConversationId;
    if (!conversationId) return;

    useWorkspaceStore.getState().updateStreamSnapshot(conversationId, (previous) => ({
      ...previous,
      completed: true,
      error: previous.error ?? "已停止生成",
    }));
    stopActiveStream();
  };

  return {
    bottomRef,
    messageInput,
    setMessageInput,
    editingId,
    setEditingId,
    editingTitle,
    setEditingTitle,
    selectedConversationId,
    selectedModel,
    activeStreamConversationId,
    streamSnapshots,
    listQuery,
    detailQuery,
    createMutation,
    renameMutation,
    deleteMutation,
    mergedMessages,
    assistantMessages,
    selectedAssistantMessage,
    selectedConversation,
    streaming,
    onSend,
    onStop,
    setSelectedConversationId,
    setSelectedModel,
    setInspectorMessageId,
  };
}

export type WorkspacePageState = ReturnType<typeof useWorkspacePage>;
