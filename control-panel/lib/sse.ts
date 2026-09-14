/** SSE live subscription for run-status / queue deltas (PBI-017 stream, PBI-018 UI). */

export interface StreamDelta {
  type: string;
  run_id?: string;
  approval_id?: number;
  node?: string;
  status?: string;
}

export type StreamStatus = "live" | "unavailable";

/**
 * Subscribe to `GET /api/stream/runs`. Returns an unsubscribe function.
 * Calls `onStatus("unavailable")` when EventSource is missing or the stream
 * errors — callers fall back to manual refresh (never silent polling).
 */
export function subscribeToRuns(
  onEvent: (event: StreamDelta) => void,
  onStatus: (status: StreamStatus) => void,
): () => void {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
  if (typeof EventSource === "undefined") {
    onStatus("unavailable");
    return () => {};
  }
  let source: EventSource;
  try {
    source = new EventSource(`${base}/api/stream/runs`, { withCredentials: true });
  } catch {
    onStatus("unavailable");
    return () => {};
  }
  const handle = (event: MessageEvent) => {
    try {
      onEvent(JSON.parse(event.data) as StreamDelta);
    } catch {
      // Malformed push: ignore, the next refetch reconciles.
    }
  };
  source.addEventListener("run.status", handle as EventListener);
  source.addEventListener("queue.delta", handle as EventListener);
  source.addEventListener("heartbeat", () => onStatus("live"));
  source.onerror = () => onStatus("unavailable");
  source.onopen = () => onStatus("live");
  return () => source.close();
}
