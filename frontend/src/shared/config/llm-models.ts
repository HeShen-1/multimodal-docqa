export const DEFAULT_LLM_MODEL = "qwen3-vl:2b-thinking-q4_K_M";

export const LLM_MODEL_OPTIONS = [
  {
    label: "Qwen3-VL（本地 Ollama）",
    value: DEFAULT_LLM_MODEL,
  },
  {
    label: "DeepSeek（API）",
    value: "deepseek",
  },
] as const;

export type LlmModelValue = (typeof LLM_MODEL_OPTIONS)[number]["value"];
