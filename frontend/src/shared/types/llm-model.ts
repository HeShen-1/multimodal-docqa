export type LlmModelCapability = "chat" | "analysis";

export interface LlmModelOption {
  value: string;
  label: string;
  provider: string;
  enabled: boolean;
  isDefault: boolean;
  supportsChat: boolean;
  supportsAnalysis: boolean;
}

export interface LlmModelCatalog {
  defaultModel: string;
  models: LlmModelOption[];
}
