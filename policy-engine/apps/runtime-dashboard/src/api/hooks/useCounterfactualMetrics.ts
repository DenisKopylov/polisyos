import { useQuery } from "@tanstack/react-query";

import { type ScenarioScope } from "@/app/providers/scenario-scope";
import {
  toApiTemporalParams,
  type TemporalScope,
} from "@/app/providers/temporal-scope";
import { useMaybeCounterfactual } from "@/app/providers/useCounterfactual";
import { useMaybeTemporalCursor } from "@/app/providers/useTemporalCursor";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import {
  counterfactualMetricsSchema,
  type CounterfactualMetricsPayload,
} from "../validators";

type CounterfactualMetricsQueryOptions = {
  temporalScope?: TemporalScope | null;
  scenarioScope?: ScenarioScope | null;
  enabled?: boolean;
};

async function fetchCounterfactualMetrics(
  runId: string,
  scenarioId: string,
  temporalScope?: TemporalScope | null,
): Promise<CounterfactualMetricsPayload> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/metrics",
    {
      params: {
        path: { run_id: runId },
        query: {
          ...toApiTemporalParams(temporalScope),
          scenario_id: scenarioId,
        },
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to load counterfactual metrics for ${runId}`,
    );
  }
  return counterfactualMetricsSchema.parse(data);
}

export function counterfactualMetricsQueryOptions(
  runId: string,
  scenarioId: string,
  temporalScope?: TemporalScope | null,
  scenarioScope?: ScenarioScope | null,
) {
  return {
    queryKey: queryKeys.counterfactualMetrics(
      runId,
      scenarioId,
      temporalScope,
      scenarioScope,
    ),
    queryFn: () => fetchCounterfactualMetrics(runId, scenarioId, temporalScope),
    staleTime: 30_000,
  };
}

export function useCounterfactualMetrics(
  runId: string | undefined,
  options?: CounterfactualMetricsQueryOptions,
) {
  const temporalCursor = useMaybeTemporalCursor();
  const counterfactual = useMaybeCounterfactual();
  const scenarioScope = options?.scenarioScope ?? counterfactual?.scope ?? null;
  const scenarioId =
    scenarioScope?.scenarioId ?? counterfactual?.scenarioId ?? null;
  const temporalScope = withScenarioId(
    options?.temporalScope ?? temporalCursor?.committedScope ?? null,
    scenarioId,
  );

  return useQuery({
    ...counterfactualMetricsQueryOptions(
      runId ?? "unknown",
      scenarioId ?? "unknown",
      temporalScope,
      scenarioScope,
    ),
    enabled: Boolean(runId && scenarioId) && (options?.enabled ?? true),
  });
}

function withScenarioId(
  temporalScope: TemporalScope | null | undefined,
  scenarioId: string | null,
): TemporalScope | null {
  if (!scenarioId) {
    return temporalScope ?? null;
  }
  return { ...(temporalScope ?? {}), scenarioId };
}
