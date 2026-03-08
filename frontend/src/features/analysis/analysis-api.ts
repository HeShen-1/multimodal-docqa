import { apiClient } from "@/shared/api/client";
import { unwrapApiEnvelope } from "@/shared/api/adapters/envelope";
import type {
  CompareResult,
  KeywordsResult,
  SimilarAnalysisResult,
  SummaryResult,
} from "@/shared/types/analysis";

export const analysisApi = {
  async summary(payload: {
    documentId: string;
    method?: "extractive" | "generative" | "hybrid";
    maxLength?: number;
    style?: "简洁" | "详细" | "concise" | "detailed";
    model?: string;
  }): Promise<SummaryResult> {
    const response = await apiClient.post("/analysis/summary", payload);
    return unwrapApiEnvelope<SummaryResult>(response.data);
  },

  async keywords(payload: {
    documentId: string;
    method?: "tfidf" | "textrank" | "llm" | "hybrid";
    topK?: number;
    model?: string;
  }): Promise<KeywordsResult> {
    const response = await apiClient.post("/analysis/keywords", payload);
    return unwrapApiEnvelope<KeywordsResult>(response.data);
  },

  async compare(payload: {
    documentIdA: string;
    documentIdB: string;
    topK?: number;
  }): Promise<CompareResult> {
    const response = await apiClient.post("/analysis/compare", payload);
    return unwrapApiEnvelope<CompareResult>(response.data);
  },

  async similar(documentId: string, params?: { limit?: number; minSimilarity?: number }): Promise<SimilarAnalysisResult> {
    const response = await apiClient.get(`/analysis/similar/${documentId}`, { params });
    return unwrapApiEnvelope<SimilarAnalysisResult>(response.data);
  },
};
