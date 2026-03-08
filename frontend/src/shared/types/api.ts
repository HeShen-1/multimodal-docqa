export interface ApiEnvelope<T> {
  code: number;
  message: string;
  data: T;
  timestamp?: string;
}

export interface ApiError {
  code?: number;
  message: string;
  status?: number;
  requestId?: string;
  details?: unknown;
}

export interface Pagination<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export type SSEEventType = "status" | "thinking" | "answer" | "source" | "done" | "error";

export interface SSEEvent {
  type: SSEEventType;
  content?: string;
  step?: string;
  fileName?: string;
  page?: number;
  [key: string]: unknown;
}

export interface PagedQuery {
  page?: number;
  pageSize?: number;
}
