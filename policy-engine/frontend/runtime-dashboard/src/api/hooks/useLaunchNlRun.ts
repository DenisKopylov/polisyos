import { useMutation, useQueryClient } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type NaturalLanguageRunRequest = components["schemas"]["NaturalLanguageRunRequest"];
export type RunLaunchResponse = components["schemas"]["RunLaunchResponse"];

async function launchNlRun(body: NaturalLanguageRunRequest): Promise<RunLaunchResponse> {
  const { data, error, response } = await runtimeApiClient.POST("/api/v1/control/runs/nl", {
    body,
  });
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to launch natural-language run");
  }
  return data as RunLaunchResponse;
}

export function useLaunchNlRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: launchNlRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runs({}) });
    },
  });
}
