import { describe, expect, it } from "vitest";

import { buildDraftMessage, createOptimisticUserMessage, summarize } from "@/features/workspace/message-utils";

describe("workspace message utils", () => {
  it("creates optimistic user messages", () => {
    const message = createOptimisticUserMessage("conv-1", "你好");

    expect(message.id.startsWith("optimistic:conv-1:")).toBe(true);
    expect(message.conversationId).toBe("conv-1");
    expect(message.role).toBe("user");
    expect(message.content).toBe("你好");
  });

  it("builds assistant draft messages from stream snapshot", () => {
    const message = buildDraftMessage("conv-1", {
      answer: "这是草稿答案",
      thinking: [{ step: "检索", content: "正在检索文档" }],
      sources: [{ fileName: "demo.pdf", page: 2 }],
      responseMeta: {
        modelName: "qwen-local",
        latencyMs: 128,
        retrievedChunks: 2,
      },
      events: [],
      completed: false,
    });

    expect(message).not.toBeNull();
    expect(message?.id).toBe("draft:conv-1");
    expect(message?.role).toBe("assistant");
    expect(message?.sources).toHaveLength(1);
    expect(message?.responseMeta?.modelName).toBe("qwen-local");
  });

  it("summarizes text into a single line", () => {
    expect(summarize(" 第一行 \n 第二行 ")).toBe("第一行 第二行");
    expect(summarize("")).toBe("暂无内容");
  });
});
