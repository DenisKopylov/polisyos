import { useEffect, useMemo, useRef, useState, type RefObject } from "react";

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

type SurfaceRect = {
  height: number;
  left: number;
  top: number;
  width: number;
};

const CURSOR_DELTA_EPSILON = 0.0025;

function parseSnapshot(rawValue: string): unknown {
  try {
    return JSON.parse(rawValue);
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
  const rectRef = useRef<SurfaceRect | null>(null);
  const pendingPointerRef = useRef<{ clientX: number; clientY: number } | null>(
    null,
  );
  const cursorFrameRef = useRef<number | null>(null);
  const lastCursorRef = useRef<{ x: number; y: number } | null>(null);

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
            const snapshot = parseSnapshot(
              event.data,
            ) as ReviewPresenceSnapshot | null;
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
            const snapshot = parseSnapshot(
              event.data,
            ) as ReviewCursorSnapshot | null;
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
            const snapshot = parseSnapshot(
              event.data,
            ) as ReviewLockSnapshot | null;
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
      updateRect();
      lockSendRef.current?.({ type: "lock.acquire" });
    };
    const releaseLock = () => {
      engagedRef.current = false;
      pendingPointerRef.current = null;
      lastCursorRef.current = null;
      if (cursorFrameRef.current != null) {
        window.cancelAnimationFrame(cursorFrameRef.current);
        cursorFrameRef.current = null;
      }
      cursorSendRef.current?.({ type: "cursor.leave" });
      lockSendRef.current?.({ type: "lock.release" });
    };
    const updateRect = () => {
      const nextRect = element.getBoundingClientRect();
      if (nextRect.width <= 0 || nextRect.height <= 0) {
        rectRef.current = null;
        return null;
      }
      rectRef.current = {
        height: nextRect.height,
        left: nextRect.left,
        top: nextRect.top,
        width: nextRect.width,
      };
      return rectRef.current;
    };
    const flushCursorUpdate = () => {
      cursorFrameRef.current = null;

      if (!engagedRef.current) {
        pendingPointerRef.current = null;
        return;
      }

      const rect = rectRef.current ?? updateRect();
      const pointer = pendingPointerRef.current;
      pendingPointerRef.current = null;

      if (!rect || !pointer) {
        return;
      }

      const x = (pointer.clientX - rect.left) / rect.width;
      const y = (pointer.clientY - rect.top) / rect.height;
      const clampedX = Math.min(Math.max(x, 0), 1);
      const clampedY = Math.min(Math.max(y, 0), 1);
      const last = lastCursorRef.current;

      if (
        last &&
        Math.abs(last.x - clampedX) < CURSOR_DELTA_EPSILON &&
        Math.abs(last.y - clampedY) < CURSOR_DELTA_EPSILON
      ) {
        return;
      }

      lastCursorRef.current = { x: clampedX, y: clampedY };
      cursorSendRef.current?.({
        type: "cursor.update",
        x: clampedX,
        y: clampedY,
      });
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
      pendingPointerRef.current = {
        clientX: event.clientX,
        clientY: event.clientY,
      };
      if (cursorFrameRef.current == null) {
        cursorFrameRef.current =
          window.requestAnimationFrame(flushCursorUpdate);
      }
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
      updateRect();
    };
    const handleViewportChange = () => {
      updateRect();
    };

    element.addEventListener("mouseenter", handleMouseEnter);
    element.addEventListener("mouseleave", handleMouseLeave);
    element.addEventListener("mousemove", handleMouseMove);
    element.addEventListener("focusin", handleFocusIn);
    element.addEventListener("focusout", handleFocusOut);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("resize", handleViewportChange);
    window.addEventListener("scroll", handleViewportChange, true);

    updateRect();

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
      window.removeEventListener("resize", handleViewportChange);
      window.removeEventListener("scroll", handleViewportChange, true);
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
