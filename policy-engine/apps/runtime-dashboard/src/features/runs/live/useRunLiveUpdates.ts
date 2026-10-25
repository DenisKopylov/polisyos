import { useEffect, useState } from "react";
import { useQueryClient, type QueryKey } from "@tanstack/react-query";

import { runDetailsSchema } from "@/api/validators";
import { getSseRealtimeTransport } from "@/app/realtime/sseTransport";
import { invalidateRunQueries } from "@/app/realtime/runInvalidation";
import { parseRunsLiveEvent } from "@/app/providers/runsLiveMachine";
import {
  readRunsLiveDisabledPreference,
  useRunsLivePreferenceStore,
} from "@/app/state/useRunsLivePreferenceStore";

function isRunDetailsQueryKey(queryKey: QueryKey, routeRunId: string): boolean {
  const temporalKey = queryKey[3];
  return (
    queryKey.length === 4 &&
    queryKey[0] === "runtime" &&
    queryKey[1] === "run" &&
    queryKey[2] === routeRunId &&
    typeof temporalKey === "object" &&
    temporalKey !== null &&
    !Array.isArray(temporalKey) &&
    "temporal" in temporalKey
  );
}

function cachedCoreRunIds(
  queryClient: ReturnType<typeof useQueryClient>,
  routeRunId: string,
) {
  const coreRunIds = new Set<string>();
  const cachedQueries = queryClient.getQueriesData({
    queryKey: ["runtime", "run", routeRunId],
  });
  for (const [queryKey, cachedData] of cachedQueries) {
    if (!isRunDetailsQueryKey(queryKey, routeRunId)) {
      continue;
    }
    const parsed = runDetailsSchema.safeParse(cachedData);
    if (
      parsed.success &&
      parsed.data.run.source_kind === "core_run" &&
      parsed.data.run.run_id.length > 0
    ) {
      coreRunIds.add(parsed.data.run.run_id);
    }
  }
  return [...coreRunIds];
}

export function useRunLiveUpdates(runId: string | undefined) {
  const queryClient = useQueryClient();
  const disableLivePreference = useRunsLivePreferenceStore(
    (state) => state.disableLive,
  );
  const [isLiveConnected, setIsLiveConnected] = useState(false);

  useEffect(() => {
    const liveDisabled =
      import.meta.env.VITE_DISABLE_RUNS_LIVE?.trim() === "true" ||
      disableLivePreference ||
      readRunsLiveDisabledPreference();
    if (!runId || liveDisabled || typeof window === "undefined") {
      setIsLiveConnected(false);
      return;
    }
    if (typeof EventSource === "undefined") {
      setIsLiveConnected(false);
      return;
    }

    const transport = getSseRealtimeTransport();
    const subscription = transport.subscribe(
      {
        channel: "runs.byId",
        runId,
      },
      {
        onOpen: () => setIsLiveConnected(true),
        onMessage: (event) => {
          const parsed = parseRunsLiveEvent({
            data: event.data,
            lastEventId: event.lastEventId,
          });
          if (parsed.kind === "run.snapshot" && parsed.runId === runId) {
            const invalidations: Promise<unknown>[] = [
              invalidateRunQueries(queryClient, runId),
            ];
            for (const coreRunId of cachedCoreRunIds(queryClient, runId)) {
              invalidations.push(
                queryClient.invalidateQueries({
                  queryKey: ["runtime", "run", coreRunId],
                }),
              );
            }
            void Promise.all(invalidations);
          }
        },
        onError: () => {
          setIsLiveConnected(false);
        },
      },
    );

    return () => {
      setIsLiveConnected(false);
      subscription.close();
    };
  }, [disableLivePreference, queryClient, runId]);

  return { isLiveConnected };
}
