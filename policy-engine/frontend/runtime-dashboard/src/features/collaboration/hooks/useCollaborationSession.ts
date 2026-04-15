import { useEffect, useMemo, useRef } from "react";

import { useAuthz } from "@/app/authz/AuthzProvider";
import { getRealtimeClient } from "@/app/realtime/realtimeClient";
import type {
  CollabActivityEvent,
  CollabCommentEvent,
  CollabCursorSnapshot,
  CollabPresenceSnapshot,
  RealtimeSubscription,
} from "@/app/realtime/types";

import { useCollaborationStore } from "../state/useCollaborationStore";
import type {
  ActivityEvent,
  ActivityEventType,
  CollaborationCursor,
  CollaborationParticipant,
  Comment,
} from "../types";

type UseCollaborationSessionOptions = {
  enabled: boolean;
  sessionId?: string | null;
};

function parseSnapshot(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function mapParticipant(
  item: CollabPresenceSnapshot["participants"][number],
  selfId: string,
): CollaborationParticipant {
  return {
    accentColor: item.accent_color,
    avatarUrl: item.avatar_url,
    displayName: item.display_name,
    isOnline: item.is_online,
    isSelf: item.participant_id === selfId,
    lastSeenAt: item.last_seen_at,
    participantId: item.participant_id,
    role: item.role,
  };
}

function mapCursor(
  item: CollabCursorSnapshot["cursors"][number],
): CollaborationCursor {
  return {
    accentColor: item.accent_color,
    displayName: item.display_name,
    participantId: item.participant_id,
    updatedAt: item.updated_at,
    x: item.x,
    y: item.y,
  };
}

function mapComment(raw: CollabCommentEvent["comment"]): Comment {
  return {
    id: raw.id,
    authorId: raw.author_id,
    authorName: raw.author_name,
    authorAccentColor: raw.author_accent_color,
    body: raw.body,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    resolvedAt: raw.resolved_at,
    resolvedBy: raw.resolved_by,
    anchorId: raw.anchor_id,
    anchorType: raw.anchor_type as Comment["anchorType"],
    anchorPosition: raw.anchor_position,
    parentId: raw.parent_id,
  };
}

function mapActivityEvent(raw: CollabActivityEvent["event"]): ActivityEvent {
  return {
    id: raw.id,
    type: raw.type as ActivityEventType,
    actorId: raw.actor_id,
    actorName: raw.actor_name,
    actorAccentColor: raw.actor_accent_color,
    summary: raw.summary,
    targetId: raw.target_id,
    targetType: raw.target_type as ActivityEvent["targetType"],
    metadata: raw.metadata,
    occurredAt: raw.occurred_at,
  };
}

/**
 * Manages the WebSocket connection for a collaboration session.
 * Subscribes to presence, cursors, comments, and activity channels,
 * updating the collaboration store in real time.
 */
export function useCollaborationSession({
  enabled,
  sessionId,
}: UseCollaborationSessionOptions) {
  const { user } = useAuthz();
  const store = useCollaborationStore;

  const participant = useMemo(
    () => ({
      accentColor: null,
      displayName: user?.display_name ?? user?.user_id ?? "User",
      participantId: user?.user_id ?? "anonymous",
    }),
    [user?.display_name, user?.user_id],
  );

  const selfId = participant.participantId;
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const presenceSendRef = useRef<RealtimeSubscription["send"]>(undefined);

  const isEnabled =
    enabled &&
    Boolean(sessionId) &&
    typeof WebSocket !== "undefined" &&
    typeof window !== "undefined";

  useEffect(() => {
    if (!isEnabled || !sessionId) {
      store.getState().reset();
      return;
    }

    store.getState().setSessionId(sessionId);
    store.getState().setStatus("connecting");

    const client = getRealtimeClient();
    const base = { participant, sessionId };

    const subscriptions: RealtimeSubscription[] = [
      // Presence channel
      client.subscribe(
        { ...base, channel: "collab.presence" },
        {
          onOpen: () => store.getState().setStatus("connected"),
          onError: () => store.getState().setStatus("reconnecting"),
          onMessage: (event) => {
            const snapshot = parseSnapshot(
              event.data,
            ) as CollabPresenceSnapshot | null;
            if (!snapshot || snapshot.type !== "collab.presence.snapshot") return;
            store
              .getState()
              .setParticipants(
                snapshot.participants.map((p) => mapParticipant(p, selfId)),
              );
          },
        },
      ),

      // Cursors channel
      client.subscribe(
        { ...base, channel: "collab.cursors" },
        {
          onMessage: (event) => {
            const snapshot = parseSnapshot(
              event.data,
            ) as CollabCursorSnapshot | null;
            if (!snapshot || snapshot.type !== "collab.cursors.snapshot") return;
            store
              .getState()
              .setCursors(
                snapshot.cursors
                  .filter((c) => c.participant_id !== selfId)
                  .map(mapCursor),
              );
          },
        },
      ),

      // Comments channel
      client.subscribe(
        { ...base, channel: "collab.comments" },
        {
          onMessage: (event) => {
            const data = parseSnapshot(
              event.data,
            ) as CollabCommentEvent | null;
            if (!data) return;
            const comment = mapComment(data.comment);
            if (data.type === "collab.comment.added") {
              store.getState().addComment(comment);
            } else if (data.type === "collab.comment.resolved") {
              store.getState().resolveComment(comment);
            } else if (data.type === "collab.comment.updated") {
              store.getState().updateComment(comment);
            }
          },
        },
      ),

      // Activity channel
      client.subscribe(
        { ...base, channel: "collab.activity" },
        {
          onMessage: (event) => {
            const data = parseSnapshot(
              event.data,
            ) as CollabActivityEvent | null;
            if (!data || data.type !== "collab.activity.event") return;
            store.getState().prependActivity(mapActivityEvent(data.event));
          },
        },
      ),
    ];

    presenceSendRef.current = subscriptions[0]?.send;

    // Heartbeat every 15s
    heartbeatRef.current = setInterval(() => {
      if (document.visibilityState === "hidden") return;
      presenceSendRef.current?.({ type: "presence.heartbeat" });
    }, 15_000);

    return () => {
      if (heartbeatRef.current) clearInterval(heartbeatRef.current);
      presenceSendRef.current = undefined;
      subscriptions.forEach((s) => s.close());
      store.getState().reset();
    };
  }, [isEnabled, participant, selfId, sessionId, store]);
}
