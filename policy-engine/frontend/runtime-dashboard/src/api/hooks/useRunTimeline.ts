import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { runTimelineSchema } from "../validators";

async function fetchRunTimeline(runId: string) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/timeline",
    {
      params: {
        path: {
          run_id: runId,
        },
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

export function runTimelineQueryOptions(runId: string) {
  return queryOptions({
    queryKey: queryKeys.runTimeline(runId),
    queryFn: () => fetchRunTimeline(runId),
  });
}

export function useRunTimeline(runId: string | undefined, enabled = true) {
  return useQuery({
    ...runTimelineQueryOptions(runId ?? "unknown"),
    enabled: Boolean(runId) && enabled,
  });
}

export function useSuspenseRunTimeline(runId: string) {
  return useSuspenseQuery(runTimelineQueryOptions(runId));
}
