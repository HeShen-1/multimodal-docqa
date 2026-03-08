import { isApiEnvelope, unwrapApiEnvelope } from "@/shared/api/adapters/envelope";

export interface HealthStatus {
  status: string;
  version: string;
  services: Record<string, string>;
  timestamp?: string;
}

export function adaptHealthStatus(payload: unknown): HealthStatus {
  if (!isApiEnvelope<unknown>(payload)) {
    const raw = payload as Record<string, unknown>;
    return {
      status: String(raw.status ?? "unknown"),
      version: String(raw.version ?? ""),
      services: (raw.services as Record<string, string>) ?? {},
      timestamp: raw.timestamp as string | undefined,
    };
  }

  const raw = unwrapApiEnvelope<Record<string, unknown>>(payload);
  return {
    status: String(raw.status ?? "unknown"),
    version: String(raw.version ?? ""),
    services: (raw.services as Record<string, string>) ?? {},
    timestamp: raw.timestamp as string | undefined,
  };
}

