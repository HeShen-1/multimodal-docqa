import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { modelsApi } from "@/features/llm-models/models-api";
import {
  filterLlmModelsByCapability,
  getFallbackLlmModelCatalog,
  resolveSelectedLlmModelFromCatalog,
} from "@/shared/config/llm-models";
import type { LlmModelCapability, LlmModelCatalog } from "@/shared/types/llm-model";

export function resolveSelectedLlmModel(
  catalog: LlmModelCatalog,
  capability: LlmModelCapability,
  selectedModel?: string,
): string {
  return resolveSelectedLlmModelFromCatalog(catalog, capability, selectedModel);
}

export function useLlmModelCatalog(capability: LlmModelCapability = "chat") {
  const query = useQuery({
    queryKey: ["llm-model-catalog"],
    queryFn: async () => {
      try {
        return await modelsApi.list();
      } catch {
        return getFallbackLlmModelCatalog();
      }
    },
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const catalog = query.data ?? getFallbackLlmModelCatalog();
  const options = useMemo(() => filterLlmModelsByCapability(catalog, capability), [catalog, capability]);

  return {
    ...query,
    catalog,
    options,
  };
}
