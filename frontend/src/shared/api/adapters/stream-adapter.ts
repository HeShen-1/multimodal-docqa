import type { SSEEvent } from "@/shared/types/api";

export function adaptStreamEvent(data: string): SSEEvent | null {
  if (!data) return null;
  try {
    const raw = JSON.parse(data) as Record<string, unknown>;
    const type = String(raw.type ?? "");
    if (!type) return null;
    const mapped: SSEEvent = { type: type as SSEEvent["type"], ...raw };

    if (!mapped.fileName && typeof raw.document_name === "string") {
      mapped.fileName = raw.document_name;
    }

    return mapped;
  } catch {
    return {
      type: "answer",
      content: data,
    };
  }
}

