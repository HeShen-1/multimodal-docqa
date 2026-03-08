import { apiClient } from "@/shared/api/client";
import { adaptAuthTokens, adaptUserProfile } from "@/shared/api/adapters/auth-adapter";
import type { AuthTokens, LoginRequest, RegisterRequest, UserProfile } from "@/shared/types/auth";

export const authApi = {
  async register(payload: RegisterRequest) {
    const response = await apiClient.post("/auth/register", payload);
    return adaptUserProfile(response.data);
  },

  async login(payload: LoginRequest): Promise<AuthTokens> {
    const response = await apiClient.post("/auth/login", payload);
    return adaptAuthTokens(response.data);
  },

  async refresh(refreshToken: string): Promise<AuthTokens> {
    const response = await apiClient.post("/auth/refresh", { refresh_token: refreshToken });
    return adaptAuthTokens(response.data);
  },

  async getMe(): Promise<UserProfile> {
    const response = await apiClient.get("/auth/me");
    return adaptUserProfile(response.data);
  },

  async logout() {
    await apiClient.post("/auth/logout");
  },
};

