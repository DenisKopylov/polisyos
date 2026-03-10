import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from "react";

import { useAuthz } from "@/app/authz/AuthzProvider";
import type {
  ReviewCollaborator,
  ReviewCursor,
  ReviewLease,
} from "@/app/realtime/ReviewCollaborationIndicators";
import { getRealtimeClient } from "@/app/realtime/realtimeClient";
import type {
  ReviewCursorSnapshot,
  ReviewLockSnapshot,
  ReviewPresenceSnapshot,
} from "@/app/realtime/types";

type ReviewCollaborationSurfaceOptions = {
  enabled: boolean;
  reviewId?: string | null;
  runId?: string | null;
  surfaceRef?: RefObject<HTMLElement | null>;
};

type ReviewCollaborationSurfaceState = {
  cursors: ReviewCursor[];
  isLockedByAnother: boolean;
  lock: ReviewLease | null;
  participants: ReviewCollaborator[];
  status: "connecting" | "idle" | "live";
};

const INITIAL_STATE: ReviewCollaborationSurfaceState = {
  cursors: [],
  isLockedByAnother: false,
  lock: null,
  participants: [],
  status: "idle",
};

function parseSnapshot<T>(rawValue: string): T | null {
  try {
    return JSON.parse(rawValue) as T;
  } catch {
    return null;
  }
}

export function useReviewCollaborationSurface({
  enabled,
  reviewId,
  runId,
  surfaceRef,
}: ReviewCollaborationSurfaceOptions): ReviewCollaborationSurfaceState {
  const { user } = useAuthz();
  const participant = useMemo(
    () => ({
      accentColor: null,
      displayName: user?.display_name ?? user?.user_id ?? "Reviewer",
      participantId: user?.user_id ?? "reviewer",
    }),
    [user?.display_name, user?.user_id],
  );
  const [state, setState] =
    useState<ReviewCollaborationSurfaceState>(INITIAL_STATE);
  const presenceSendRef = useRef<((payload: unknown) => void) | undefined>(
    undefined,
  );
  const cursorSendRef = useRef<((payload: unknown) => void) | undefined>(
    undefined,
  );
  const lockSendRef = useRef<((payload: unknown) => void) | undefined>(
    undefined,
  );
  const engagedRef = useRef(false);

  const isEnabled =
    enabled &&
    Boolean(reviewId) &&
    typeof WebSocket !== "undefined" &&
    typeof window !== "undefined";

  useEffect(() => {
    if (!isEnabled || !reviewId) {
      setState(INITIAL_STATE);
      return;
    }

    setState((current) => ({
      ...current,
      status: "connecting",
    }));

    const client = getRealtimeClient();
    const subscriptions = [
      client.subscribe(
        {
          channel: "review.presence",
          participant,
          reviewId,
          runId: runId ?? undefined,
        },
        {
          onOpen: () => {
            setState((current) => ({
              ...current,
              status: "live",
            }));
          },
          onError: () => {
            setState((current) => ({
              ...current,
              status: "idle",
            }));
          },
          onMessage: (event) => {
            const snapshot = parseSnapshot<ReviewPresenceSnapshot>(event.data);
            if (!snapshot || snapshot.type !== "presence.snapshot") {
              return;
            }
            setState((current) => ({
              ...current,
              participants: snapshot.participants.map((item) => ({
                accentColor: item.accent_color,
                displayName: item.display_name,
                isSelf: item.participant_id === participant.participantId,
                lastSeenAt: item.last_seen_at,
                participantId: item.participant_id,
                sessionCount: item.session_count,
              })),
            }));
          },
        },
      ),
      client.subscribe(
        {
          channel: "review.cursor",
          participant,
          reviewId,
          runId: runId ?? undefined,
        },
        {
          onError: () => {
            setState((current) => ({
              ...current,
              cursors: [],
            }));
          },
          onMessage: (event) => {
            const snapshot = parseSnapshot<ReviewCursorSnapshot>(event.data);
            if (!snapshot || snapshot.type !== "cursor.snapshot") {
              return;
            }
            setState((current) => ({
              ...current,
              cursors: snapshot.cursors
                .filter(
                  (item) => item.participant_id !== participant.participantId,
                )
                .map((item) => ({
                  accentColor: item.accent_color,
                  displayName: item.display_name,
                  participantId: item.participant_id,
                  updatedAt: item.updated_at,
                  x: item.x,
                  y: item.y,
                })),
            }));
          },
        },
      ),
      client.subscribe(
        {
          channel: "review.lock",
          participant,
          reviewId,
          runId: runId ?? undefined,
        },
        {
          onError: () => {
            setState((current) => ({
              ...current,
              isLockedByAnother: false,
              lock: null,
            }));
          },
          onMessage: (event) => {
            const snapshot = parseSnapshot<ReviewLockSnapshot>(event.data);
            if (!snapshot || snapshot.type !== "lock.snapshot") {
              return;
            }
            const lock = snapshot.lock
              ? {
                  accentColor: snapshot.lock.accent_color,
                  acquiredAt: snapshot.lock.acquired_at,
                  displayName: snapshot.lock.display_name,
                  expiresAt: snapshot.lock.expires_at,
                  isSelf:
                    snapshot.lock.participant_id === participant.participantId,
                  participantId: snapshot.lock.participant_id,
                }
              : null;

            setState((current) => ({
              ...current,
              isLockedByAnother: Boolean(lock && !lock.isSelf),
              lock,
            }));
          },
        },
      ),
    ];

    presenceSendRef.current = subscriptions[0]?.send;
    cursorSendRef.current = subscriptions[1]?.send;
    lockSendRef.current = subscriptions[2]?.send;

    return () => {
      engagedRef.current = false;
      presenceSendRef.current = undefined;
      cursorSendRef.current = undefined;
      lockSendRef.current = undefined;
      subscriptions.forEach((subscription) => subscription.close());
      setState(INITIAL_STATE);
    };
  }, [isEnabled, participant, reviewId, runId]);

  useEffect(() => {
    const element = surfaceRef?.current;
    if (!isEnabled || !reviewId || !element) {
      return;
    }

    const acquireLock = () => {
      engagedRef.current = true;
      lockSendRef.current?.({ type: "lock.acquire" });
    };
    const releaseLock = () => {
      engagedRef.current = false;
      cursorSendRef.current?.({ type: "cursor.leave" });
      lockSendRef.current?.({ type: "lock.release" });
    };
    const handleMouseEnter = () => {
      acquireLock();
    };
    const handleMouseLeave = () => {
      releaseLock();
    };
    const handleMouseMove = (event: MouseEvent) => {
      if (!engagedRef.current) {
        return;
      }
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) {
        return;
      }
      cursorSendRef.current?.({
        type: "cursor.update",
        x: (event.clientX - rect.left) / rect.width,
        y: (event.clientY - rect.top) / rect.height,
      });
    };
    const handleFocusIn = () => {
      acquireLock();
    };
    const handleFocusOut = (event: FocusEvent) => {
      const nextTarget = event.relatedTarget as Node | null;
      if (!nextTarget || !element.contains(nextTarget)) {
        releaseLock();
      }
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        releaseLock();
        return;
      }
      if (engagedRef.current) {
        lockSendRef.current?.({ type: "lock.acquire" });
      }
    };

    element.addEventListener("mouseenter", handleMouseEnter);
    element.addEventListener("mouseleave", handleMouseLeave);
    element.addEventListener("mousemove", handleMouseMove);
    element.addEventListener("focusin", handleFocusIn);
    element.addEventListener("focusout", handleFocusOut);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    const heartbeatTimer = window.setInterval(() => {
      if (!engagedRef.current || document.visibilityState === "hidden") {
        return;
      }
      presenceSendRef.current?.({ type: "presence.heartbeat" });
      lockSendRef.current?.({ type: "lock.renew" });
    }, 10_000);

    return () => {
      window.clearInterval(heartbeatTimer);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      element.removeEventListener("mouseenter", handleMouseEnter);
      element.removeEventListener("mouseleave", handleMouseLeave);
      element.removeEventListener("mousemove", handleMouseMove);
      element.removeEventListener("focusin", handleFocusIn);
      element.removeEventListener("focusout", handleFocusOut);
      releaseLock();
    };
  }, [isEnabled, reviewId, surfaceRef]);

  return state;
}
