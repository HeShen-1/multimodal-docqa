import axios from "axios";

import type { ApiError } from "@/shared/types/api";

function isApiErrorLike(error: unknown): error is ApiError {
  return typeof error === "object" && error !== null && "message" in error && typeof (error as { message?: unknown }).message === "string";
}

export function normalizeApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    const payload = error.response?.data as Record<string, unknown> | undefined;
    const code = typeof payload?.code === "number" ? payload.code : undefined;
    const requestId = (error.response?.headers?.["x-request-id"] as string | undefined) ?? undefined;
    const detail = typeof payload?.detail === "string" ? payload.detail : undefined;
    const message =
      detail ||
      (typeof payload?.message === "string" ? payload.message : undefined) ||
      error.message ||
      "请求失败";

    return {
      code,
      status,
      message,
      requestId,
      details: payload,
    };
  }

  if (isApiErrorLike(error)) {
    return {
      code: typeof error.code === "number" ? error.code : undefined,
      status: typeof error.status === "number" ? error.status : undefined,
      message: error.message,
      requestId: typeof error.requestId === "string" ? error.requestId : undefined,
      details: error.details,
    };
  }

  if (error instanceof Error) {
    return { message: error.message };
  }

  return { message: "未知错误" };
}

export function getFriendlyMessage(error: ApiError) {
  if (error.status === 429) return "系统繁忙，请稍后重试。";
  if (error.status === 503) return "系统降级中，部分功能暂不可用。";
  if (error.status === 401) return "登录状态失效，请重新登录。";
  return error.message || "操作失败，请稍后再试。";
}
