export type RealtimeChannel =
  | "collab.activity"
  | "collab.comments"
  | "collab.cursors"
  | "collab.presence"
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
  onClose?: (event: CloseEvent | Event) => void;
  onError?: (event: Event) => void;
  onMessage?: (event: RealtimeEvent) => void;
  onOpen?: (event: Event) => void;
};

type RealtimeSubscriptionRequestBase<TChannel extends RealtimeChannel> = {
  channel: TChannel;
  cursor?: string | null;
};

export type RunsRealtimeSubscriptionRequest =
  | RealtimeSubscriptionRequestBase<"runs.global">
  | (RealtimeSubscriptionRequestBase<"runs.byId"> & {
      runId: string;
    });

export type CollaborationRealtimeSubscriptionRequest =
  RealtimeSubscriptionRequestBase<
    "collab.activity" | "collab.comments" | "collab.cursors" | "collab.presence"
  > & {
    participant: RealtimeParticipant;
    sessionId: string;
  };

export type ReviewRealtimeSubscriptionRequest = RealtimeSubscriptionRequestBase<
  "review.cursor" | "review.lock" | "review.presence"
> & {
  participant: RealtimeParticipant;
  reviewId: string;
  runId?: string;
};

export type WebSocketRealtimeSubscriptionRequest =
  | CollaborationRealtimeSubscriptionRequest
  | ReviewRealtimeSubscriptionRequest;

export type RealtimeSubscriptionRequest =
  | RunsRealtimeSubscriptionRequest
  | WebSocketRealtimeSubscriptionRequest;

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

export type CollabPresenceSnapshot = {
  channel: "collab.presence";
  participants: Array<{
    accent_color: string;
    avatar_url?: string;
    display_name: string;
    is_online: boolean;
    last_seen_at: string;
    participant_id: string;
    role: "editor" | "viewer";
  }>;
  session_id: string;
  type: "collab.presence.snapshot";
};

export type CollabCursorSnapshot = {
  channel: "collab.cursors";
  cursors: Array<{
    accent_color: string;
    display_name: string;
    participant_id: string;
    updated_at: string;
    x: number;
    y: number;
  }>;
  session_id: string;
  type: "collab.cursors.snapshot";
};

export type CollabCommentEvent = {
  channel: "collab.comments";
  comment: {
    anchor_id: string;
    anchor_position?: { x: number; y: number };
    anchor_type: string;
    author_accent_color: string;
    author_id: string;
    author_name: string;
    body: string;
    created_at: string;
    id: string;
    parent_id?: string;
    resolved_at?: string;
    resolved_by?: string;
    updated_at?: string;
  };
  session_id: string;
  type:
    | "collab.comment.added"
    | "collab.comment.resolved"
    | "collab.comment.updated";
};

export type CollabActivityEvent = {
  channel: "collab.activity";
  event: {
    actor_accent_color: string;
    actor_id: string;
    actor_name: string;
    id: string;
    metadata?: Record<string, unknown>;
    occurred_at: string;
    summary: string;
    target_id?: string;
    target_type?: string;
    type: string;
  };
  session_id: string;
  type: "collab.activity.event";
};

export interface RealtimeTransport<
  TRequest extends RealtimeSubscriptionRequest = RealtimeSubscriptionRequest,
> {
  subscribe(
    request: TRequest,
    handlers: RealtimeSubscriptionHandlers,
  ): RealtimeSubscription;
}
