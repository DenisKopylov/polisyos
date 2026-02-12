import { useMutation, useQueryClient } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type WorkflowRunRequest = components["schemas"]["WorkflowRunRequest"];
export type RunLaunchResponse = components["schemas"]["RunLaunchResponse"];

async function launchRun(body: WorkflowRunRequest): Promise<RunLaunchResponse> {
  const { data, error, response } = await runtimeApiClient.POST("/api/v1/control/runs", {
    body,
  });
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to launch workflow run");
  }
  return data as RunLaunchResponse;
}

export function useLaunchRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: launchRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runs({}) });
    },
  });
}
