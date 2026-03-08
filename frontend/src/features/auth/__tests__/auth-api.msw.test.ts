import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { authApi } from "@/features/auth/auth-api";

const baseUrl = "http://127.0.0.1:8000/api/v1";

const server = setupServer(
  http.post(`${baseUrl}/auth/login`, async () =>
    HttpResponse.json({
      access_token: "access-token",
      refresh_token: "refresh-token",
      token_type: "bearer",
      expires_in: 3600,
    }),
  ),
);

describe("authApi (MSW)", () => {
  beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());

  it("parses login token payload", async () => {
    const result = await authApi.login({
      username: "demo",
      password: "password123",
    });

    expect(result.accessToken).toBe("access-token");
    expect(result.refreshToken).toBe("refresh-token");
    expect(result.expiresIn).toBe(3600);
  });
});

