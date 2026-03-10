export type RealtimeChannel =
  | "review.cursor"
  | "review.lock"
  | "review.presence"
  | "runs.byId"
  | "runs.global";

export type RealtimeEvent = MessageEvent<string>;

export type RealtimeSubscription = {
  close: () => void;
  send?: (payload: unknown) => void;
};

export type RealtimeParticipant = {
  accentColor?: string | null;
  displayName: string;
  participantId: string;
};

export type RealtimeSubscriptionHandlers = {
  onError?: (event: Event) => void;
  onMessage?: (event: RealtimeEvent) => void;
  onOpen?: (event: Event) => void;
};

export type RealtimeSubscriptionRequest = {
  channel: RealtimeChannel;
  cursor?: string | null;
  participant?: RealtimeParticipant;
  reviewId?: string;
  runId?: string;
};

export type ReviewPresenceSnapshot = {
  channel: "review.presence";
  participants: Array<{
    accent_color: string;
    display_name: string;
    last_seen_at: string;
    participant_id: string;
    session_count: number;
  }>;
  review_id: string;
  type: "presence.snapshot";
};

export type ReviewCursorSnapshot = {
  channel: "review.cursor";
  cursors: Array<{
    accent_color: string;
    display_name: string;
    participant_id: string;
    updated_at: string;
    x: number;
    y: number;
  }>;
  review_id: string;
  type: "cursor.snapshot";
};

export type ReviewLockSnapshot = {
  channel: "review.lock";
  lock: {
    accent_color: string;
    acquired_at: string;
    display_name: string;
    expires_at: string;
    participant_id: string;
  } | null;
  review_id: string;
  type: "lock.snapshot";
};

export interface RealtimeTransport {
  subscribe(
    request: RealtimeSubscriptionRequest,
    handlers: RealtimeSubscriptionHandlers,
  ): RealtimeSubscription;
}
