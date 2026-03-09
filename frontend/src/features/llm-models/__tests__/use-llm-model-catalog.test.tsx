import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import {
  resolveSelectedLlmModel,
  useLlmModelCatalog,
} from "@/features/llm-models/use-llm-model-catalog";
import { getFallbackLlmModelCatalog } from "@/shared/config/llm-models";

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
            value: "docqa-lora",
            label: "docqa-lora（本地 LoRA）",
            provider: "local_lora",
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

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("useLlmModelCatalog", () => {
  beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());

  it("returns backend model options", async () => {
    const { result } = renderHook(() => useLlmModelCatalog("chat"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.options.map((item) => item.value)).toEqual([
        "qwen3-vl:2b-thinking-q4_K_M",
        "docqa-lora",
      ]);
    });
  });

  it("falls back to safe static options when request fails", async () => {
    server.use(
      http.get(`${baseUrl}/models`, async () => HttpResponse.json({ message: "boom" }, { status: 500 })),
    );

    const { result } = renderHook(() => useLlmModelCatalog("analysis"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.catalog).toEqual(getFallbackLlmModelCatalog());
    });
  });

  it("resets invalid selected model to backend default", () => {
    const catalog = {
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
      ],
    };

    expect(resolveSelectedLlmModel(catalog, "chat", "docqa-lora")).toBe("qwen3-vl:2b-thinking-q4_K_M");
  });
});
