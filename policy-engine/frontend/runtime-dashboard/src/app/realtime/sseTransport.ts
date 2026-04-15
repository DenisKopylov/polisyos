import { buildRuntimeStreamUrl } from "@/api/stream";
import type {
  RealtimeSubscription,
  RealtimeSubscriptionHandlers,
  RealtimeTransport,
  RunsRealtimeSubscriptionRequest,
} from "@/app/realtime/types";

function assertNever(value: never): never {
  throw new Error(`Unhandled realtime channel: ${String(value)}`);
}

function resolveSseUrl(request: RunsRealtimeSubscriptionRequest) {
  switch (request.channel) {
    case "runs.global":
      return buildRuntimeStreamUrl("/api/v1/runs/live", {
        cursor: request.cursor ?? undefined,
      });
    case "runs.byId":
      return buildRuntimeStreamUrl(`/api/v1/runs/${request.runId}/live`, {
        cursor: request.cursor ?? undefined,
      });
    default:
      return assertNever(request);
  }
}

class EventSourceSubscription implements RealtimeSubscription {
  constructor(private readonly source: EventSource) {}

  close() {
    this.source.close();
  }
}

export class SseRealtimeTransport
  implements RealtimeTransport<RunsRealtimeSubscriptionRequest>
{
  subscribe(
    request: RunsRealtimeSubscriptionRequest,
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
