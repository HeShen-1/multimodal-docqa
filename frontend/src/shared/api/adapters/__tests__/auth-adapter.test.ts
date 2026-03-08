import { describe, expect, it } from "vitest";

import { adaptAuthTokens } from "@/shared/api/adapters/auth-adapter";

describe("adaptAuthTokens", () => {
  it("supports direct token payload", () => {
    const result = adaptAuthTokens({
      access_token: "a",
      refresh_token: "b",
      token_type: "bearer",
      expires_in: 3600,
    });

    expect(result).toEqual({
      accessToken: "a",
      refreshToken: "b",
      tokenType: "bearer",
      expiresIn: 3600,
    });
  });

  it("supports enveloped payload", () => {
    const result = adaptAuthTokens({
      code: 100000,
      message: "ok",
      data: {
        accessToken: "aaa",
        refreshToken: "bbb",
        tokenType: "Bearer",
        expiresIn: 7200,
      },
    });

    expect(result.tokenType).toBe("bearer");
    expect(result.accessToken).toBe("aaa");
    expect(result.refreshToken).toBe("bbb");
    expect(result.expiresIn).toBe(7200);
  });
});

