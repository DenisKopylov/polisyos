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
    if (request.channel.startsWith("runs.")) {
      return getSseRealtimeTransport().subscribe(request, handlers);
    }
    return getWebSocketRealtimeTransport().subscribe(request, handlers);
  }
}

let sharedRealtimeClient: DefaultRealtimeClient | null = null;

export function getRealtimeClient() {
  if (!sharedRealtimeClient) {
    sharedRealtimeClient = new DefaultRealtimeClient();
  }
  return sharedRealtimeClient;
}
