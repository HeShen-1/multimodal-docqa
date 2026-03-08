import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import { adaptAuthTokens } from "@/shared/api/adapters/auth-adapter";
import { normalizeApiError } from "@/shared/api/errors";
import { clearAuthSession, getAccessToken, getRefreshToken, useAuthStore } from "@/shared/store/auth-store";
import type { AuthTokens } from "@/shared/types/auth";

const baseURL = import.meta.env.VITE_API_BASE_URL;

type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean };

let refreshPromise: Promise<AuthTokens> | null = null;

export function shouldAttemptRefresh(error: AxiosError, config?: RetryConfig) {
  const status = error.response?.status;
  const hasRefreshToken = Boolean(getRefreshToken());
  const url = config?.url ?? "";
  const isAuthRequest =
    url.includes("/auth/login") ||
    url.includes("/auth/register") ||
    url.includes("/auth/refresh");
  return status === 401 && hasRefreshToken && !config?._retry && !isAuthRequest;
}

async function requestRefreshToken(refreshToken: string) {
  const response = await axios.post(
    `${baseURL}/auth/refresh`,
    { refresh_token: refreshToken },
    { timeout: 10000 },
  );
  return adaptAuthTokens(response.data);
}

function getRefreshPromise(refreshToken: string) {
  if (!refreshPromise) {
    refreshPromise = requestRefreshToken(refreshToken).finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

function redirectToLogin() {
  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

export const apiClient = axios.create({
  baseURL,
  timeout: 30_000,
});

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  const url = config.url ?? "";
  const isPublicAuthRequest =
    url.includes("/auth/login") ||
    url.includes("/auth/register") ||
    url.includes("/auth/refresh");
  if (token && !isPublicAuthRequest) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetryConfig | undefined;
    if (!config) {
      return Promise.reject(normalizeApiError(error));
    }

    if (!shouldAttemptRefresh(error, config)) {
      return Promise.reject(normalizeApiError(error));
    }

    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      clearAuthSession();
      redirectToLogin();
      return Promise.reject(normalizeApiError(error));
    }

    try {
      config._retry = true;
      const tokens = await getRefreshPromise(refreshToken);
      useAuthStore.getState().setTokens(tokens);
      config.headers.Authorization = `Bearer ${tokens.accessToken}`;
      return apiClient(config);
    } catch (refreshError) {
      clearAuthSession();
      redirectToLogin();
      return Promise.reject(normalizeApiError(refreshError));
    }
  },
);
