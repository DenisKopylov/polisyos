import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { getSseRealtimeTransport } from "@/app/realtime/sseTransport";
import { invalidateRunQueries } from "@/app/realtime/runInvalidation";
import { parseRunsLiveEvent } from "@/app/providers/runsLiveMachine";
import {
  readRunsLiveDisabledPreference,
  useRunsLivePreferenceStore,
} from "@/app/state/useRunsLivePreferenceStore";

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
            void invalidateRunQueries(queryClient, runId);
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
