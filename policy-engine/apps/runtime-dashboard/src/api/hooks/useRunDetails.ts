import { useQuery } from "@tanstack/react-query";

import {
  RUN_ACTIVE_REFETCH_MS,
  RUN_ACTIVE_STALE_MS,
  RUN_BOOTSTRAP_REFETCH_MS,
  RUN_TERMINAL_STALE_MS,
} from "@/shared/lib/constants";
import {
  toApiTemporalParams,
  type TemporalScope,
} from "@/shared/lib/domain/temporal";
import { useMaybeTemporalCursor } from "@/shared/ui/temporal/TemporalRuntimeBridge";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError, isRuntimeApiNotFound } from "../http";
import { queryKeys } from "../queryKeys";
import { runDetailsSchema } from "../validators";

async function fetchRunDetails(
  runId: string,
  temporalScope?: TemporalScope | null,
) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}",
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
    throw createRuntimeApiError(response, error, `Failed to load run ${runId}`);
  }
  return runDetailsSchema.parse(data);
}

export function runDetailsQueryOptions(
  runId: string,
  options?: { liveTransport?: boolean; resolveCurrentAlias?: boolean },
  temporalScope?: TemporalScope | null,
) {
  const liveTransport = options?.liveTransport ?? false;
  const resolveCurrentAlias = options?.resolveCurrentAlias ?? false;
  type QueryRun = {
    finished_at?: string | null | undefined;
    run_id?: string | null | undefined;
    source_kind?: string | null | undefined;
    status?: string | null | undefined;
  };
  const hasProducerFinishedAt = (run: QueryRun | undefined) =>
    typeof run?.finished_at === "string" && run.finished_at.trim().length > 0;
  type QuerySnapshot = {
    state: { data?: { run?: QueryRun }; error?: unknown };
  };
  const isResolvedDirectCoreRun = (run: QueryRun | undefined) =>
    run?.source_kind === "core_run" &&
    typeof run.run_id === "string" &&
    run.run_id.trim().length > 0 &&
    run.run_id === runId;
  const isResolvedCurrentAlias = (query: QuerySnapshot) =>
    resolveCurrentAlias &&
    (query.state.error === undefined || query.state.error === null) &&
    isResolvedDirectCoreRun(query.state.data?.run);
  const shouldRefreshCurrentAlias = (query: QuerySnapshot) =>
    resolveCurrentAlias && !isResolvedCurrentAlias(query)
      ? ("always" as const)
      : false;
  return {
    queryKey: queryKeys.run(runId, temporalScope),
    queryFn: () => fetchRunDetails(runId, temporalScope),
    // A stable route selector may resolve to a newer Core run after reissue.
    ...(resolveCurrentAlias
      ? {
          refetchOnMount: shouldRefreshCurrentAlias,
          refetchOnReconnect: shouldRefreshCurrentAlias,
          refetchOnWindowFocus: shouldRefreshCurrentAlias,
        }
      : {}),
    staleTime: (query: QuerySnapshot) => {
      const run = query.state.data?.run;
      if (resolveCurrentAlias && !isResolvedCurrentAlias(query)) {
        return RUN_ACTIVE_STALE_MS;
      }
      return hasProducerFinishedAt(run)
        ? RUN_TERMINAL_STALE_MS
        : RUN_ACTIVE_STALE_MS;
    },
    retry: (failureCount: number, error: unknown) =>
      isRuntimeApiNotFound(error) && failureCount < 6,
    retryDelay: (attempt: number) => Math.min(500 * 2 ** attempt, 2_500),
    refetchInterval: (query: QuerySnapshot) => {
      const run = query.state.data?.run;
      // The runs.byId stream requires a validated Core id matching the selector;
      // it cannot establish stable-selector identity or report alias remaps.
      if (resolveCurrentAlias && !isResolvedCurrentAlias(query)) {
        if (run === undefined && isRuntimeApiNotFound(query.state.error)) {
          return RUN_BOOTSTRAP_REFETCH_MS;
        }
        return RUN_ACTIVE_REFETCH_MS;
      }
      if (liveTransport) {
        return false;
      }
      const error = query.state.error;
      if (isRuntimeApiNotFound(error)) {
        return RUN_BOOTSTRAP_REFETCH_MS;
      }
      return hasProducerFinishedAt(run) ? false : RUN_ACTIVE_REFETCH_MS;
    },
  };
}

export function useRunDetails(
  runId: string | undefined,
  options?: { liveTransport?: boolean; resolveCurrentAlias?: boolean },
) {
  const temporalCursor = useMaybeTemporalCursor();
  const temporalScope = temporalCursor?.committedScope ?? null;
  return useQuery({
    ...runDetailsQueryOptions(runId ?? "unknown", options, temporalScope),
    enabled: Boolean(runId),
  });
}
