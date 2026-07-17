import { buildRuntimeWebSocketUrl } from "@/api/url";
import type {
  RealtimeSubscription,
  RealtimeSubscriptionHandlers,
  RealtimeTransport,
  ReviewRealtimeSubscriptionRequest,
  WebSocketRealtimeSubscriptionRequest,
} from "@/app/realtime/types";

function resolveReviewUrl(request: ReviewRealtimeSubscriptionRequest) {
  return buildRuntimeWebSocketUrl("/api/v1/review/live", {
    accent_color: request.participant.accentColor ?? undefined,
    channel: request.channel,
    display_name: request.participant.displayName,
    participant_id: request.participant.participantId,
    review_id: request.reviewId,
    run_id: request.runId ?? undefined,
  });
}

function resolveWebSocketUrl(request: WebSocketRealtimeSubscriptionRequest) {
  return resolveReviewUrl(request);
}

class WebSocketSubscription implements RealtimeSubscription {
  constructor(private readonly socket: WebSocket) {}

  close() {
    if (
      this.socket.readyState === WebSocket.CONNECTING ||
      this.socket.readyState === WebSocket.OPEN
    ) {
      this.socket.close();
    }
  }

  send(payload: unknown) {
    if (this.socket.readyState !== WebSocket.OPEN) {
      return;
    }
    this.socket.send(JSON.stringify(payload));
  }
}

export class WebSocketRealtimeTransport implements RealtimeTransport<WebSocketRealtimeSubscriptionRequest> {
  subscribe(
    request: WebSocketRealtimeSubscriptionRequest,
    handlers: RealtimeSubscriptionHandlers,
  ): RealtimeSubscription {
    if (typeof WebSocket === "undefined") {
      throw new Error("WebSocket is not available in this environment");
    }

    const socket = new WebSocket(resolveWebSocketUrl(request));

    socket.onopen = (event) => {
      handlers.onOpen?.(event);
    };
    socket.onclose = (event) => {
      handlers.onClose?.(event);
    };
    socket.onerror = (event) => {
      handlers.onError?.(event);
    };
    socket.onmessage = (event) => {
      handlers.onMessage?.({
        data: event.data,
        lastEventId: "",
      } as MessageEvent<string>);
    };

    return new WebSocketSubscription(socket);
  }
}

let sharedWebSocketTransport: WebSocketRealtimeTransport | null = null;

export function getWebSocketRealtimeTransport() {
  if (!sharedWebSocketTransport) {
    sharedWebSocketTransport = new WebSocketRealtimeTransport();
  }
  return sharedWebSocketTransport;
}

/** Reset the shared singleton — useful for tests and HMR. */
export function resetWebSocketRealtimeTransport() {
  sharedWebSocketTransport = null;
}
