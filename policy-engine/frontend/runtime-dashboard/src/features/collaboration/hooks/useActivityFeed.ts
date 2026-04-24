import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useCollaborationStore } from "../state/useCollaborationStore";
import type { ActivityEvent, ActivityEventType } from "../types";

const ACTIVITY_QUERY_KEY = ["collaboration", "activity"] as const;

type UseActivityFeedOptions = {
  sessionId?: string | null;
  /** Filter by event types. */
  filter?: ActivityEventType[];
};

async function fetchActivity(sessionId: string): Promise<ActivityEvent[]> {
  const response = await fetch(`/api/v1/collaboration/${sessionId}/activity`, {
    credentials: "include",
  });
  if (!response.ok) return [];
  const data = await response.json();
  return (data.events ?? []).map(mapServerEvent);
}

function mapServerEvent(raw: Record<string, unknown>): ActivityEvent {
  return {
    id: raw.id as string,
    type: raw.type as ActivityEventType,
    actorId: (raw.actor_id ?? "") as string,
    actorName: (raw.actor_name ?? "") as string,
    actorAccentColor: (raw.actor_accent_color ?? "#6B7280") as string,
    summary: (raw.summary ?? "") as string,
    targetId: raw.target_id as string | undefined,
    targetType: raw.target_type as ActivityEvent["targetType"],
    metadata: raw.metadata as Record<string, unknown> | undefined,
    occurredAt: (raw.occurred_at ?? "") as string,
  };
}

/**
 * Provides activity feed data for a collaboration session.
 * Polls via TanStack Query (10s stale time) and merges with
 * real-time events pushed via the collab.activity WebSocket channel.
 */
export function useActivityFeed({ sessionId, filter }: UseActivityFeedOptions) {
  const storeActivity = useCollaborationStore((s) => s.activity);
  const setSessionId = useCollaborationStore((s) => s.setSessionId);
  const hydrateActivitySnapshot = useCollaborationStore(
    (s) => s.hydrateActivitySnapshot,
  );

  useEffect(() => {
    setSessionId(sessionId ?? null);
  }, [sessionId, setSessionId]);

  const { isLoading } = useQuery({
    queryKey: [...ACTIVITY_QUERY_KEY, sessionId],
    queryFn: async () => {
      if (!sessionId) return [];
      const events = await fetchActivity(sessionId);
      hydrateActivitySnapshot(sessionId, events);
      return events;
    },
    enabled: Boolean(sessionId),
    staleTime: 10_000,
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
  });

  const events = useMemo(() => {
    if (!filter || filter.length === 0) return storeActivity;
    const allowed = new Set(filter);
    return storeActivity.filter((e) => allowed.has(e.type));
  }, [storeActivity, filter]);

  return { events, isLoading };
}
