import type { LlmModelCapability, LlmModelCatalog, LlmModelOption } from "@/shared/types/llm-model";

export const DEFAULT_LLM_MODEL = "qwen3-vl:2b-thinking-q4_K_M";

export const FALLBACK_LLM_MODEL_OPTIONS: LlmModelOption[] = [
  {
    label: "Qwen3-VL（本地 Ollama）",
    value: DEFAULT_LLM_MODEL,
    provider: "ollama",
    enabled: true,
    isDefault: true,
    supportsChat: true,
    supportsAnalysis: true,
  },
  {
    label: "DeepSeek（API）",
    value: "deepseek",
    provider: "deepseek",
    enabled: true,
    isDefault: false,
    supportsChat: true,
    supportsAnalysis: true,
  },
];

export const LLM_MODEL_OPTIONS = FALLBACK_LLM_MODEL_OPTIONS;

export type LlmModelValue = (typeof FALLBACK_LLM_MODEL_OPTIONS)[number]["value"];

export function getFallbackLlmModelCatalog(): LlmModelCatalog {
  return {
    defaultModel: DEFAULT_LLM_MODEL,
    models: FALLBACK_LLM_MODEL_OPTIONS.map((item) => ({ ...item })),
  };
}

export function filterLlmModelsByCapability(
  catalog: LlmModelCatalog,
  capability: LlmModelCapability,
): LlmModelOption[] {
  return catalog.models.filter((item) => {
    if (!item.enabled) return false;
    return capability === "chat" ? item.supportsChat : item.supportsAnalysis;
  });
}

export function resolveSelectedLlmModelFromCatalog(
  catalog: LlmModelCatalog,
  capability: LlmModelCapability,
  selectedModel?: string,
): string {
  const options = filterLlmModelsByCapability(catalog, capability);
  if (selectedModel && options.some((item) => item.value === selectedModel)) {
    return selectedModel;
  }

  return options.find((item) => item.isDefault)?.value ?? catalog.defaultModel ?? DEFAULT_LLM_MODEL;
}
