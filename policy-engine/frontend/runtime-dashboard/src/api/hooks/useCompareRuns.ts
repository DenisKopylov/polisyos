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
  compareCandidatesSchema,
  compareRunsSchema,
  type CompareCandidatesPayload,
  type CompareRunsPayload,
} from "../validators";

type CompareRunsQueryOptions = {
  temporalScope?: TemporalScope | null;
  enabled?: boolean;
};

async function fetchCompareRuns(
  runAId: string,
  runBId: string,
  temporalScope?: TemporalScope | null,
): Promise<CompareRunsPayload> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/compare",
    {
      params: {
        query: {
          a: runAId,
          b: runBId,
          ...toApiTemporalParams(temporalScope),
        },
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to compare runs ${runAId} and ${runBId}`,
    );
  }
  return compareRunsSchema.parse(data);
}

async function fetchCompareCandidates(
  runId: string,
  temporalScope?: TemporalScope | null,
): Promise<CompareCandidatesPayload> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/compare-candidates",
    {
      params: {
        path: { run_id: runId },
        query: toApiTemporalParams(temporalScope),
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to load compare candidates for ${runId}`,
    );
  }
  return compareCandidatesSchema.parse(data);
}

export function compareRunsQueryOptions(
  runAId: string,
  runBId: string,
  temporalScope?: TemporalScope | null,
) {
  return {
    queryKey: queryKeys.runCompare(runAId, runBId, temporalScope),
    queryFn: () => fetchCompareRuns(runAId, runBId, temporalScope),
    staleTime: 30_000,
  };
}

export function useCompareRuns(
  runAId: string | undefined,
  runBId: string | undefined,
  options?: CompareRunsQueryOptions,
) {
  const cursor = useMaybeTemporalCursor();
  const temporalScope =
    options?.temporalScope ?? cursor?.committedScope ?? null;
  return useQuery({
    ...compareRunsQueryOptions(
      runAId ?? "unknown-a",
      runBId ?? "unknown-b",
      temporalScope,
    ),
    enabled: Boolean(runAId && runBId) && (options?.enabled ?? true),
  });
}

export function useCompareCandidates(
  runId: string | undefined,
  options?: CompareRunsQueryOptions,
) {
  const cursor = useMaybeTemporalCursor();
  const temporalScope =
    options?.temporalScope ?? cursor?.committedScope ?? null;
  return useQuery({
    queryKey: queryKeys.runCompareCandidates(runId ?? "unknown", temporalScope),
    queryFn: () => fetchCompareCandidates(runId ?? "unknown", temporalScope),
    enabled: Boolean(runId) && (options?.enabled ?? true),
    staleTime: 30_000,
  });
}
