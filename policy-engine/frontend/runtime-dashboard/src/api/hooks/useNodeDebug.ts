import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { nodeDebugSchema } from "../validators";

async function fetchNodeDebug(runId: string, alias: string) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/debug/runs/{run_id}/nodes/{alias}",
    {
      params: {
        path: {
          run_id: runId,
          alias,
        },
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, `Failed to load node debug for ${runId}/${alias}`);
  }

  const parsed = nodeDebugSchema.parse(data);
  return {
    ...parsed,
    debug: {
      ...parsed.debug,
      timeline_events: parsed.debug.timeline_events ?? [],
      notes: parsed.debug.notes ?? [],
      cache_hits: parsed.debug.cache_hits ?? 0,
      cache_stores: parsed.debug.cache_stores ?? 0,
      cache_bypasses: parsed.debug.cache_bypasses ?? 0,
    },
  };
}

export function useNodeDebug(runId: string | undefined, alias: string | null, enabled = true) {
  return useQuery({
    queryKey: queryKeys.runNodeDebug(runId ?? "unknown", alias ?? "unknown"),
    queryFn: () => fetchNodeDebug(runId ?? "", alias ?? ""),
    enabled: Boolean(runId) && Boolean(alias) && enabled,
  });
}
