import { useQuery } from "@tanstack/react-query";

import {
  type ScenarioScope,
  toApiScenarioParams,
} from "@/app/providers/scenario-scope";
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
  scenarioCapabilitiesSchema,
  scenarioListSchema,
  type ScenarioCapabilitiesPayload,
  type ScenarioListPayload,
} from "../validators";

type ScenarioQueryOptions = {
  temporalScope?: TemporalScope | null;
  scenarioScope?: ScenarioScope | null;
  enabled?: boolean;
};

async function fetchRunScenarios(
  runId: string,
  temporalScope?: TemporalScope | null,
  scenarioScope?: ScenarioScope | null,
): Promise<ScenarioListPayload> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/scenarios",
    {
      params: {
        path: { run_id: runId },
        query: {
          ...toApiTemporalParams(temporalScope),
          ...toApiScenarioParams(scenarioScope),
        },
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to load scenarios for ${runId}`,
    );
  }
  return scenarioListSchema.parse(data);
}

async function fetchScenarioCapabilities(
  scenarioId: string,
  temporalScope?: TemporalScope | null,
): Promise<ScenarioCapabilitiesPayload> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/scenarios/{scenario_id}/capabilities",
    {
      params: {
        path: { scenario_id: scenarioId },
        query: toApiTemporalParams(temporalScope),
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to load scenario capabilities for ${scenarioId}`,
    );
  }
  return scenarioCapabilitiesSchema.parse(data);
}

export function useRunScenarios(
  runId: string | undefined,
  options?: ScenarioQueryOptions,
) {
  const temporalCursor = useMaybeTemporalCursor();
  const counterfactual = useMaybeCounterfactual();
  const temporalScope = withScenarioId(
    options?.temporalScope ?? temporalCursor?.committedScope ?? null,
    options?.scenarioScope?.scenarioId ?? counterfactual?.scenarioId ?? null,
  );
  const scenarioScope = options?.scenarioScope ?? counterfactual?.scope ?? null;
  return useQuery({
    queryKey: queryKeys.runScenarios(
      runId ?? "unknown",
      temporalScope,
      scenarioScope,
    ),
    queryFn: () =>
      fetchRunScenarios(runId ?? "unknown", temporalScope, scenarioScope),
    enabled: Boolean(runId) && (options?.enabled ?? true),
    staleTime: 30_000,
  });
}

export function useScenarioCapabilities(
  scenarioId: string | undefined,
  options?: ScenarioQueryOptions,
) {
  const temporalCursor = useMaybeTemporalCursor();
  const temporalScope = withScenarioId(
    options?.temporalScope ?? temporalCursor?.committedScope ?? null,
    scenarioId ?? null,
  );
  return useQuery({
    queryKey: queryKeys.scenarioCapabilities(
      scenarioId ?? "unknown",
      temporalScope,
    ),
    queryFn: () =>
      fetchScenarioCapabilities(scenarioId ?? "unknown", temporalScope),
    enabled: Boolean(scenarioId) && (options?.enabled ?? true),
    staleTime: 30_000,
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
