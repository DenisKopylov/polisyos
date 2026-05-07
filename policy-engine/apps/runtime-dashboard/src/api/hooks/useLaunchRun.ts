import { useQueryClient } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import {
  applyOptimisticRunToCache,
  buildLaunchedRunSummary,
  createOptimisticRun,
  replaceOptimisticRunInCache,
  restoreRunsQueries,
  snapshotRunsQueries,
} from "../optimistic";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";
import { useControlPlaneMutation } from "../useControlPlaneMutation";

export type WorkflowRunRequest = components["schemas"]["WorkflowRunRequest"];
export type RunLaunchResponse = components["schemas"]["RunLaunchResponse"];

async function launchRun(body: WorkflowRunRequest): Promise<RunLaunchResponse> {
  const { data, error, response } = await runtimeApiClient.POST(
    "/api/v1/control/runs",
    {
      body,
    },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to launch workflow run",
    );
  }
  return data as RunLaunchResponse;
}

export function useLaunchRun() {
  const queryClient = useQueryClient();
  return useControlPlaneMutation({
    blockWhenOffline: true,
    errorToast: {
      title: "Run launch failed",
      description:
        "Atlas restored the optimistic run and kept existing data intact.",
      tone: "error",
    },
    mutationId: "runs.launch",
    mutationFn: launchRun,
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: queryKeys.runsRoot() });
      const runsSnapshot = snapshotRunsQueries(queryClient);
      const optimisticRun = createOptimisticRun(`launch-pending-${Date.now()}`);
      applyOptimisticRunToCache(queryClient, optimisticRun);
      return {
        optimisticRun,
        runsSnapshot,
      };
    },
    onError: (_error, _variables, context) => {
      if (!context) {
        return;
      }
      restoreRunsQueries(queryClient, context.runsSnapshot);
      queryClient.removeQueries({
        queryKey: queryKeys.run(context.optimisticRun.run_id),
        exact: true,
      });
    },
    onSuccess: (data, _variables, context) => {
      if (context) {
        replaceOptimisticRunInCache(
          queryClient,
          context.optimisticRun.run_id,
          buildLaunchedRunSummary(
            data,
            context.optimisticRun.started_at ?? new Date().toISOString(),
          ),
        );
      }
      queryClient.invalidateQueries({ queryKey: queryKeys.runsRoot() });
    },
    onSettled: (_data, _error, _variables, context) => {
      if (context?.optimisticRun) {
        queryClient.removeQueries({
          queryKey: queryKeys.run(context.optimisticRun.run_id),
          exact: true,
        });
      }
    },
    successToast: (data) => ({
      title:
        data.status === "accepted" ? "Run launch accepted" : "Run rejected",
      description: data.message,
      tone: data.status === "accepted" ? "success" : "warning",
    }),
  });
}
