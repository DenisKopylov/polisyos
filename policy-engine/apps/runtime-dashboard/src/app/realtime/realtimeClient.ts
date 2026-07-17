import { getSseRealtimeTransport } from "@/app/realtime/sseTransport";
import type {
  RealtimeSubscription,
  RealtimeSubscriptionHandlers,
  RealtimeSubscriptionRequest,
  RealtimeTransport,
} from "@/app/realtime/types";
import { getWebSocketRealtimeTransport } from "@/app/realtime/websocketTransport";

class DefaultRealtimeClient implements RealtimeTransport {
  subscribe(
    request: RealtimeSubscriptionRequest,
    handlers: RealtimeSubscriptionHandlers,
  ): RealtimeSubscription {
    switch (request.channel) {
      case "runs.global":
      case "runs.byId":
        return getSseRealtimeTransport().subscribe(request, handlers);
      case "review.cursor":
      case "review.lock":
      case "review.presence":
        return getWebSocketRealtimeTransport().subscribe(request, handlers);
      default:
        return assertNever(request);
    }
  }
}

function assertNever(value: never): never {
  throw new Error(
    `Unsupported realtime subscription channel: ${JSON.stringify(value)}`,
  );
}

let sharedRealtimeClient: DefaultRealtimeClient | null = null;

export function getRealtimeClient() {
  if (!sharedRealtimeClient) {
    sharedRealtimeClient = new DefaultRealtimeClient();
  }
  return sharedRealtimeClient;
}

/** Reset the shared singleton — useful for tests and HMR. */
export function resetRealtimeClient() {
  sharedRealtimeClient = null;
}
