import { unwrapApiEnvelope } from "@/shared/api/adapters/envelope";
import { apiClient } from "@/shared/api/client";
import type { LlmModelCatalog } from "@/shared/types/llm-model";

export const modelsApi = {
  async list(): Promise<LlmModelCatalog> {
    const response = await apiClient.get("/models");
    return unwrapApiEnvelope<LlmModelCatalog>(response.data);
  },
};
