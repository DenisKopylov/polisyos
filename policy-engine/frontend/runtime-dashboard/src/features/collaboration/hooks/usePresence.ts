import { useMemo } from "react";

import { useCollaborationStore } from "../state/useCollaborationStore";
import type { CollaborationParticipant } from "../types";

type PresenceInfo = {
  /** All participants including self. */
  all: CollaborationParticipant[];
  /** Only online participants (excluding self). */
  others: CollaborationParticipant[];
  /** Self participant info. */
  self: CollaborationParticipant | undefined;
  /** Online count (excluding self). */
  onlineCount: number;
  /** Whether the session is connected. */
  isConnected: boolean;
};

/**
 * Derives presence information from the collaboration store.
 * Pure selector hook — no side-effects.
 */
export function usePresence(): PresenceInfo {
  const participants = useCollaborationStore((s) => s.participants);
  const status = useCollaborationStore((s) => s.status);

  return useMemo(() => {
    const self = participants.find((p) => p.isSelf);
    const others = participants.filter((p) => !p.isSelf && p.isOnline);
    return {
      all: participants,
      others,
      self,
      onlineCount: others.length,
      isConnected: status === "connected",
    };
  }, [participants, status]);
}
