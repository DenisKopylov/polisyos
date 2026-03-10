import { buildRuntimeWebSocketUrl } from "@/api/url";
import type {
  RealtimeSubscription,
  RealtimeSubscriptionHandlers,
  RealtimeSubscriptionRequest,
  RealtimeTransport,
} from "@/app/realtime/types";

function resolveWebSocketUrl(request: RealtimeSubscriptionRequest) {
  if (!request.reviewId) {
    throw new Error(`${request.channel} channel requires reviewId`);
  }
  if (!request.participant) {
    throw new Error(`${request.channel} channel requires participant details`);
  }
  return buildRuntimeWebSocketUrl("/api/v1/review/live", {
    accent_color: request.participant.accentColor ?? undefined,
    channel: request.channel,
    display_name: request.participant.displayName,
    participant_id: request.participant.participantId,
    review_id: request.reviewId,
    run_id: request.runId ?? undefined,
  });
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

export class WebSocketRealtimeTransport implements RealtimeTransport {
  subscribe(
    request: RealtimeSubscriptionRequest,
    handlers: RealtimeSubscriptionHandlers,
  ): RealtimeSubscription {
    if (typeof WebSocket === "undefined") {
      throw new Error("WebSocket is not available in this environment");
    }

    const socket = new WebSocket(resolveWebSocketUrl(request));

    socket.onopen = (event) => {
      handlers.onOpen?.(event);
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
