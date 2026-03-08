import { afterEach, describe, expect, it } from "vitest";

import { useAuthStore } from "@/shared/store/auth-store";

describe("authStore", () => {
  afterEach(() => {
    useAuthStore.getState().clearAuth();
  });

  it("sets and clears token correctly", () => {
    const { setTokens, clearAuth } = useAuthStore.getState();
    setTokens({
      accessToken: "access",
      refreshToken: "refresh",
      tokenType: "bearer",
      expiresIn: 3600,
    });

    expect(useAuthStore.getState().accessToken).toBe("access");
    expect(useAuthStore.getState().refreshToken).toBe("refresh");
    expect(useAuthStore.getState().hydrated).toBe(true);

    clearAuth();
    expect(useAuthStore.getState().accessToken).toBeNull();
  });

  it("hydrates tokens from localStorage", () => {
    localStorage.setItem(
      "docqa.auth.v1",
      JSON.stringify({
        accessToken: "persisted-access",
        refreshToken: "persisted-refresh",
        tokenType: "bearer",
        expiresIn: 3600,
        user: null,
      }),
    );

    useAuthStore.getState().hydrate();

    expect(useAuthStore.getState().hydrated).toBe(true);
    expect(useAuthStore.getState().accessToken).toBe("persisted-access");
    expect(useAuthStore.getState().refreshToken).toBe("persisted-refresh");
  });
});
