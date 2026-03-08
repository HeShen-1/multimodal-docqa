import { describe, expect, it } from "vitest";

import {
  getAssistantMessages,
  getSelectedAssistantMessage,
  mergeMessagesWithDraft,
} from "@/features/workspace/workspace-view-model";
import type { Message, StreamSnapshot } from "@/shared/types/conversation";

const baseMessages: Message[] = [
  {
    id: "message-user",
    conversationId: "conv-1",
    role: "user",
    content: "Question",
  },
  {
    id: "message-assistant",
    conversationId: "conv-1",
    role: "assistant",
    content: "Saved answer",
    thinking: [{ step: "search", content: "Looking up context" }],
    sources: [{ fileName: "notes.md", page: 2 }],
  },
];

const activeSnapshot: StreamSnapshot = {
  answer: "Streaming answer",
  thinking: [{ step: "draft", content: "Building response" }],
  sources: [{ fileName: "report.pdf", page: 5 }],
  events: [],
  completed: false,
};

describe("workspace view model", () => {
  it("appends a draft assistant message while streaming", () => {
    const merged = mergeMessagesWithDraft(baseMessages, "conv-1", activeSnapshot);

    expect(merged).toHaveLength(3);
    expect(merged.at(-1)?.id).toBe("draft:conv-1");
    expect(merged.at(-1)?.content).toBe("Streaming answer");
  });

  it("avoids duplicating the last assistant answer after completion", () => {
    const completedSnapshot: StreamSnapshot = {
      ...activeSnapshot,
      answer: "Saved answer",
      completed: true,
    };

    expect(mergeMessagesWithDraft(baseMessages, "conv-1", completedSnapshot)).toEqual(baseMessages);
  });

  it("picks the requested assistant message and falls back to the latest one", () => {
    const merged = mergeMessagesWithDraft(baseMessages, "conv-1", activeSnapshot);
    const assistantMessages = getAssistantMessages(merged);

    expect(getSelectedAssistantMessage(assistantMessages, "message-assistant")?.id).toBe("message-assistant");
    expect(getSelectedAssistantMessage(assistantMessages, "missing")?.id).toBe("draft:conv-1");
    expect(getSelectedAssistantMessage(getAssistantMessages(baseMessages), null)?.id).toBe("message-assistant");
  });
});
