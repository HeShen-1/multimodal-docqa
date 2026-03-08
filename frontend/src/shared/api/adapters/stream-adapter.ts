import type { SSEEvent } from "@/shared/types/api";

export function adaptStreamEvent(data: string): SSEEvent | null {
  if (!data) return null;
  try {
    const raw = JSON.parse(data) as Record<string, unknown>;
    const type = String(raw.type ?? "");
    if (!type) return null;
    const mapped: SSEEvent = { type: type as SSEEvent["type"], ...raw };

    if (!mapped.fileName && typeof raw.document_name === "string") {
      mapped.fileName = raw.document_name;
    }

    if (!mapped.modelName && typeof raw.model_name === "string") {
      mapped.modelName = raw.model_name;
    }
    if (mapped.latencyMs == null && raw.latency_ms != null) {
      mapped.latencyMs = Number(raw.latency_ms);
    }
    if (mapped.retrievedChunks == null && raw.retrieved_chunks != null) {
      mapped.retrievedChunks = Number(raw.retrieved_chunks);
    }
    if (mapped.citationCount == null && raw.citation_count != null) {
      mapped.citationCount = Number(raw.citation_count);
    }
    if (mapped.fallbackReason == null && "fallback_reason" in raw) {
      mapped.fallbackReason = (raw.fallback_reason as string | null | undefined) ?? null;
    }
    if (!mapped.retrievalStrategy && typeof raw.retrieval_strategy === "string") {
      mapped.retrievalStrategy = raw.retrieval_strategy;
    }
    if (!mapped.rewrittenQuery && typeof raw.rewritten_query === "string") {
      mapped.rewrittenQuery = raw.rewritten_query;
    }
    if (mapped.topScore == null && raw.top_score != null) {
      mapped.topScore = Number(raw.top_score);
    }
    if (mapped.evidenceCoverage == null && raw.evidence_coverage != null) {
      mapped.evidenceCoverage = Number(raw.evidence_coverage);
    }
    if (mapped.rerankApplied == null && typeof raw.rerank_applied === "boolean") {
      mapped.rerankApplied = raw.rerank_applied;
    }

    return mapped;
  } catch {
    return {
      type: "answer",
      content: data,
    };
  }
}
