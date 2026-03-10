import { useQuery } from "@tanstack/react-query";

import {
  RUN_ACTIVE_REFETCH_MS,
  RUN_ACTIVE_STALE_MS,
  RUN_BOOTSTRAP_REFETCH_MS,
  RUN_TERMINAL_STALE_MS,
} from "../../lib/constants";
import { isRunTerminal } from "../../features/runs/domain/status";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError, isRuntimeApiNotFound } from "../http";
import { queryKeys } from "../queryKeys";
import { runDetailsSchema } from "../validators";

async function fetchRunDetails(runId: string) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}",
    {
      params: {
        path: {
          run_id: runId,
        },
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
  options?: { liveTransport?: boolean },
) {
  const liveTransport = options?.liveTransport ?? false;
  return {
    queryKey: queryKeys.run(runId),
    queryFn: () => fetchRunDetails(runId),
    staleTime: (query: {
      state: { data?: { run?: { status?: string | null | undefined } } };
    }) => {
      const run = query.state.data?.run;
      return isRunTerminal(run?.status)
        ? RUN_TERMINAL_STALE_MS
        : RUN_ACTIVE_STALE_MS;
    },
    retry: (failureCount: number, error: unknown) =>
      isRuntimeApiNotFound(error) && failureCount < 6,
    retryDelay: (attempt: number) => Math.min(500 * 2 ** attempt, 2_500),
    refetchInterval: (query: {
      state: {
        data?: { run?: { status?: string | null | undefined } };
        error?: unknown;
      };
    }) => {
      if (liveTransport) {
        return false;
      }
      const error = query.state.error;
      if (isRuntimeApiNotFound(error)) {
        return RUN_BOOTSTRAP_REFETCH_MS;
      }
      const run = query.state.data?.run;
      return isRunTerminal(run?.status) ? false : RUN_ACTIVE_REFETCH_MS;
    },
  };
}

export function useRunDetails(
  runId: string | undefined,
  options?: { liveTransport?: boolean },
) {
  return useQuery({
    ...runDetailsQueryOptions(runId ?? "unknown", options),
    enabled: Boolean(runId),
  });
}
