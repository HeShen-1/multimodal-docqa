import { describe, expect, it } from "vitest";

import { adaptStreamEvent } from "@/shared/api/adapters/stream-adapter";

describe("adaptStreamEvent", () => {
  it("parses json event payload", () => {
    const result = adaptStreamEvent('{"type":"answer","content":"hello"}');
    expect(result?.type).toBe("answer");
    expect(result?.content).toBe("hello");
  });

  it("falls back to answer text for raw token stream", () => {
    const result = adaptStreamEvent("raw-token");
    expect(result?.type).toBe("answer");
    expect(result?.content).toBe("raw-token");
  });
});

