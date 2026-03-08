import { create } from "zustand";

import type { AuthTokens, UserProfile } from "@/shared/types/auth";

const AUTH_STORAGE_KEY = "docqa.auth.v1";

type AuthState = {
  hydrated: boolean;
  accessToken: string | null;
  refreshToken: string | null;
  tokenType: string;
  expiresIn: number | null;
  user: UserProfile | null;
  setTokens: (tokens: AuthTokens) => void;
  setUser: (user: UserProfile | null) => void;
  clearAuth: () => void;
  hydrate: () => void;
};

function persistState(snapshot: Pick<AuthState, "accessToken" | "refreshToken" | "tokenType" | "expiresIn" | "user">) {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(snapshot));
}

function readPersistedState() {
  const raw = localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Pick<AuthState, "accessToken" | "refreshToken" | "tokenType" | "expiresIn" | "user">;
  } catch {
    return null;
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  hydrated: false,
  accessToken: null,
  refreshToken: null,
  tokenType: "bearer",
  expiresIn: null,
  user: null,
  setTokens: (tokens) =>
    set((state) => {
      const next = {
        ...state,
        hydrated: true,
        accessToken: tokens.accessToken,
        refreshToken: tokens.refreshToken,
        tokenType: tokens.tokenType,
        expiresIn: tokens.expiresIn,
      };
      persistState(next);
      return next;
    }),
  setUser: (user) =>
    set((state) => {
      const next = { ...state, user };
      persistState(next);
      return next;
    }),
  clearAuth: () =>
    set(() => {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      return {
        hydrated: true,
        accessToken: null,
        refreshToken: null,
        tokenType: "bearer",
        expiresIn: null,
        user: null,
      };
    }),
  hydrate: () =>
    set((state) => {
      const persisted = readPersistedState();
      if (!persisted) {
        return { ...state, hydrated: true };
      }
      return { ...state, ...persisted, hydrated: true };
    }),
}));

export function getAccessToken() {
  return useAuthStore.getState().accessToken;
}

export function getRefreshToken() {
  return useAuthStore.getState().refreshToken;
}

export function clearAuthSession() {
  useAuthStore.getState().clearAuth();
}
