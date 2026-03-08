import { describe, expect, it } from "vitest";

import { mergeChunkTexts, normalizeStatus } from "@/features/documents/preview-utils";

describe("documents preview utils", () => {
  it("normalizes status consistently", () => {
    expect(normalizeStatus(" COMPLETED ")).toBe("completed");
    expect(normalizeStatus(undefined)).toBe("");
  });

  it("merges chunk text without duplicating overlap", () => {
    const merged = mergeChunkTexts([
      {
        id: "1",
        content: "第一段内容与结尾",
        page: 1,
        chunkIndex: 0,
        length: 8,
      },
      {
        id: "2",
        content: "结尾继续扩展第二段",
        page: 1,
        chunkIndex: 1,
        length: 9,
      },
    ]);

    expect(merged).toBe("第一段内容与结尾继续扩展第二段");
  });
});
