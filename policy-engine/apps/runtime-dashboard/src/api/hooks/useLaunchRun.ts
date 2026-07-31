import { useQueryClient } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
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
      description: "Existing run data remains unchanged.",
      tone: "error",
    },
    mutationId: "runs.launch",
    mutationFn: launchRun,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.runsRoot() });
    },
    successToast: (data) => ({
      title:
        data.status === "accepted" ? "Run launch accepted" : "Run rejected",
      description: data.message,
      tone: data.status === "accepted" ? "success" : "warning",
    }),
  });
}
