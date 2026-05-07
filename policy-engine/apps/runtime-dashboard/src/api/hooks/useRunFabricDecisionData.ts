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
import { fabricDecisionDataPayloadToQuantities } from "@/shared/ui/quantity";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { runFabricDecisionDataSchema } from "../validators";

async function fetchRunFabricDecisionData(
  runId: string,
  temporalScope?: TemporalScope | null,
) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/fabric-decision-data",
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
      `Failed to load Fabric decision data for ${runId}`,
    );
  }

  const parsed = runFabricDecisionDataSchema.parse(data);
  return {
    ...parsed,
    decision_data: parsed.decision_data ?? [],
    quantities: fabricDecisionDataPayloadToQuantities(parsed),
  };
}

export function runFabricDecisionDataQueryOptions(
  runId: string,
  temporalScope?: TemporalScope | null,
) {
  return queryOptions({
    queryKey: queryKeys.runFabricDecisionData(runId, temporalScope),
    queryFn: () => fetchRunFabricDecisionData(runId, temporalScope),
  });
}

export function useRunFabricDecisionData(
  runId: string | undefined,
  enabled = true,
) {
  const temporalCursor = useMaybeTemporalCursor();
  const temporalScope = temporalCursor?.committedScope ?? null;
  return useQuery({
    ...runFabricDecisionDataQueryOptions(runId ?? "unknown", temporalScope),
    enabled: Boolean(runId) && enabled,
  });
}

export function useSuspenseRunFabricDecisionData(runId: string) {
  const temporalCursor = useMaybeTemporalCursor();
  return useSuspenseQuery(
    runFabricDecisionDataQueryOptions(
      runId,
      temporalCursor?.committedScope ?? null,
    ),
  );
}
