import { unwrapApiEnvelope } from "@/shared/api/adapters/envelope";
import type { AuthTokens, UserProfile } from "@/shared/types/auth";

type AnyRecord = Record<string, unknown>;

export function adaptAuthTokens(payload: unknown): AuthTokens {
  const raw = unwrapApiEnvelope<AnyRecord>(payload);
  const accessToken = (raw.access_token ?? raw.accessToken ?? "") as string;
  const refreshToken = (raw.refresh_token ?? raw.refreshToken ?? "") as string;
  const tokenType = ((raw.token_type ?? raw.tokenType ?? "bearer") as string).toLowerCase();
  const expiresIn = Number(raw.expires_in ?? raw.expiresIn ?? 0);

  if (!accessToken || !refreshToken) {
    throw new Error("无效的 token 响应结构");
  }

  return {
    accessToken,
    refreshToken,
    tokenType,
    expiresIn,
  };
}

export function adaptUserProfile(payload: unknown): UserProfile {
  const raw = unwrapApiEnvelope<AnyRecord>(payload);
  return {
    id: String(raw.id ?? ""),
    username: String(raw.username ?? ""),
    email: String(raw.email ?? ""),
    role: String(raw.role ?? "user"),
    avatar: (raw.avatar as string | null | undefined) ?? null,
    isActive: Boolean(raw.is_active ?? raw.isActive ?? true),
    createdAt: (raw.created_at ?? raw.createdAt) as string | undefined,
    lastLoginAt: (raw.last_login_at ?? raw.lastLoginAt) as string | undefined,
    documentCount: Number(raw.document_count ?? raw.documentCount ?? 0),
    queryCount: Number(raw.query_count ?? raw.queryCount ?? 0),
    storageUsed: Number(raw.storage_used ?? raw.storageUsed ?? 0),
  };
}

