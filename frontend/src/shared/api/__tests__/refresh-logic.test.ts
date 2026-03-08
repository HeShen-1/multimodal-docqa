import { AxiosError } from "axios";
import { describe, expect, it } from "vitest";

import { shouldAttemptRefresh } from "@/shared/api/client";
import { useAuthStore } from "@/shared/store/auth-store";

describe("shouldAttemptRefresh", () => {
  it("returns true when 401 and refresh token exists", () => {
    useAuthStore.getState().setTokens({
      accessToken: "a",
      refreshToken: "r",
      tokenType: "bearer",
      expiresIn: 3600,
    });

    const error = new AxiosError("401");
    (error as AxiosError & { response: AxiosError["response"] }).response = {
      status: 401,
      statusText: "Unauthorized",
      headers: {},
      config: { headers: {} } as never,
      data: {},
    };

    expect(
      shouldAttemptRefresh(error, {
        headers: {},
        url: "/documents",
      } as never),
    ).toBe(true);
  });

  it("returns false for refresh endpoint", () => {
    const error = new AxiosError("401");
    (error as AxiosError & { response: AxiosError["response"] }).response = {
      status: 401,
      statusText: "Unauthorized",
      headers: {},
      config: { headers: {} } as never,
      data: {},
    };
    expect(
      shouldAttemptRefresh(error, {
        headers: {},
        url: "/auth/refresh",
      } as never),
    ).toBe(false);
  });

  it("returns false for login endpoint", () => {
    const error = new AxiosError("401");
    (error as AxiosError & { response: AxiosError["response"] }).response = {
      status: 401,
      statusText: "Unauthorized",
      headers: {},
      config: { headers: {} } as never,
      data: {},
    };
    expect(
      shouldAttemptRefresh(error, {
        headers: {},
        url: "/auth/login",
      } as never),
    ).toBe(false);
  });
});
