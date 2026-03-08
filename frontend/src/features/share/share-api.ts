import { apiClient } from "@/shared/api/client";
import { unwrapApiEnvelope } from "@/shared/api/adapters/envelope";
import type { ShareAccessResult } from "@/shared/types/share";

export const shareApi = {
  async access(token: string, password?: string): Promise<ShareAccessResult> {
    const response = await apiClient.post(`/share/${token}/access`, { password: password || undefined });
    return unwrapApiEnvelope<ShareAccessResult>(response.data);
  },
};

