import { useQuery } from "@tanstack/react-query";

import {
  toApiTemporalParams,
  type TemporalScope,
} from "@/app/providers/temporal-scope";
import { useMaybeTemporalCursor } from "@/app/providers/useTemporalCursor";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import {
  scenarioManifestResponseSchema,
  type ScenarioManifestPayload,
} from "../validators";

type ScenarioManifestQueryOptions = {
  temporalScope?: TemporalScope | null;
  enabled?: boolean;
};

async function fetchScenarioManifest(
  scenarioId: string,
  temporalScope?: TemporalScope | null,
): Promise<ScenarioManifestPayload> {
  const query = { ...toApiTemporalParams(temporalScope) };
  delete query.scenario_id;
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/scenarios/{scenario_id}",
    {
      params: {
        path: { scenario_id: scenarioId },
        query,
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to load scenario ${scenarioId}`,
    );
  }
  return scenarioManifestResponseSchema.parse(data);
}

export function useScenarioManifest(
  scenarioId: string | undefined,
  options?: ScenarioManifestQueryOptions,
) {
  const temporalCursor = useMaybeTemporalCursor();
  const temporalScope =
    options?.temporalScope ?? temporalCursor?.committedScope ?? null;
  return useQuery({
    queryKey: queryKeys.scenarioManifest(
      scenarioId ?? "unknown",
      temporalScope,
    ),
    queryFn: () => fetchScenarioManifest(scenarioId ?? "unknown", temporalScope),
    enabled: Boolean(scenarioId) && (options?.enabled ?? true),
    staleTime: 60_000,
  });
}
