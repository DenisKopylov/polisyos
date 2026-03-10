import { buildRuntimeStreamUrl } from "@/api/stream";
import type {
  RealtimeSubscription,
  RealtimeSubscriptionHandlers,
  RealtimeSubscriptionRequest,
  RealtimeTransport,
} from "@/app/realtime/types";

function resolveSseUrl(request: RealtimeSubscriptionRequest) {
  switch (request.channel) {
    case "runs.global":
      return buildRuntimeStreamUrl("/api/v1/runs/live", {
        cursor: request.cursor ?? undefined,
      });
    case "runs.byId":
      if (!request.runId) {
        throw new Error("runs.byId channel requires runId");
      }
      return buildRuntimeStreamUrl(`/api/v1/runs/${request.runId}/live`, {
        cursor: request.cursor ?? undefined,
      });
    case "review.cursor":
    case "review.lock":
    case "review.presence":
      throw new Error(
        `SSE transport does not support collaboration channel ${request.channel}`,
      );
  }
}

class EventSourceSubscription implements RealtimeSubscription {
  constructor(private readonly source: EventSource) {}

  close() {
    this.source.close();
  }
}

export class SseRealtimeTransport implements RealtimeTransport {
  subscribe(
    request: RealtimeSubscriptionRequest,
    handlers: RealtimeSubscriptionHandlers,
  ): RealtimeSubscription {
    const source = new EventSource(resolveSseUrl(request), {
      withCredentials: true,
    });

    if (handlers.onOpen) {
      source.onopen = handlers.onOpen;
    }
    if (handlers.onError) {
      source.onerror = handlers.onError;
    }
    if (handlers.onMessage) {
      const listener = handlers.onMessage as unknown as EventListener;
      source.addEventListener("snapshot", listener);
      source.onmessage = handlers.onMessage;
    }

    return new EventSourceSubscription(source);
  }
}

let sharedSseTransport: SseRealtimeTransport | null = null;

export function getSseRealtimeTransport() {
  if (!sharedSseTransport) {
    sharedSseTransport = new SseRealtimeTransport();
  }
  return sharedSseTransport;
}
