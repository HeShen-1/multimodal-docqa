import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { modelsApi } from "@/features/llm-models/models-api";

const baseUrl = "http://127.0.0.1:8000/api/v1";

const server = setupServer(
  http.get(`${baseUrl}/models`, async () =>
    HttpResponse.json({
      code: 100000,
      message: "ok",
      data: {
        defaultModel: "qwen3-vl:2b-thinking-q4_K_M",
        models: [
          {
            value: "qwen3-vl:2b-thinking-q4_K_M",
            label: "Qwen3-VL（本地 Ollama）",
            provider: "ollama",
            enabled: true,
            isDefault: true,
            supportsChat: true,
            supportsAnalysis: true,
          },
          {
            value: "deepseek",
            label: "DeepSeek（API）",
            provider: "deepseek",
            enabled: true,
            isDefault: false,
            supportsChat: true,
            supportsAnalysis: true,
          },
        ],
      },
    }),
  ),
);

describe("modelsApi (MSW)", () => {
  beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());

  it("loads dynamic model catalog from backend", async () => {
    const result = await modelsApi.list();

    expect(result.defaultModel).toBe("qwen3-vl:2b-thinking-q4_K_M");
    expect(result.models.map((item) => item.value)).toEqual([
      "qwen3-vl:2b-thinking-q4_K_M",
      "deepseek",
    ]);
    expect(result.models[0]?.isDefault).toBe(true);
  });
});
