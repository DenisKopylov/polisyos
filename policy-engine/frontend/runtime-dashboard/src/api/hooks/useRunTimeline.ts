import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import {
  toApiTemporalParams,
  type TemporalScope,
} from "@/app/providers/temporal-scope";
import { useMaybeTemporalCursor } from "@/app/providers/useTemporalCursor";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { runTimelineSchema } from "../validators";

async function fetchRunTimeline(
  runId: string,
  temporalScope?: TemporalScope | null,
) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/timeline",
    {
      params: {
        path: {
          run_id: runId,
        },
        query: toApiTemporalParams(temporalScope),
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to load timeline for ${runId}`,
    );
  }

  const parsed = runTimelineSchema.parse(data);
  return {
    ...parsed,
    timeline: {
      ...parsed.timeline,
      events: parsed.timeline.events ?? [],
      notes: parsed.timeline.notes ?? [],
    },
  };
}

export function runTimelineQueryOptions(
  runId: string,
  temporalScope?: TemporalScope | null,
) {
  return queryOptions({
    queryKey: queryKeys.runTimeline(runId, temporalScope),
    queryFn: () => fetchRunTimeline(runId, temporalScope),
  });
}

export function useRunTimeline(runId: string | undefined, enabled = true) {
  const temporalCursor = useMaybeTemporalCursor();
  const temporalScope = temporalCursor?.committedScope ?? null;
  return useQuery({
    ...runTimelineQueryOptions(runId ?? "unknown", temporalScope),
    enabled: Boolean(runId) && enabled,
  });
}

export function useSuspenseRunTimeline(runId: string) {
  const temporalCursor = useMaybeTemporalCursor();
  return useSuspenseQuery(
    runTimelineQueryOptions(runId, temporalCursor?.committedScope ?? null),
  );
}
