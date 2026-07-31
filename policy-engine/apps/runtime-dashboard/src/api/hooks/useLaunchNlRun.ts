import { useQueryClient } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";
import { useControlPlaneMutation } from "../useControlPlaneMutation";

export type NaturalLanguageRunRequest =
  components["schemas"]["NaturalLanguageRunRequest"];
export type RunLaunchResponse = components["schemas"]["RunLaunchResponse"];

async function launchNlRun(
  body: NaturalLanguageRunRequest,
): Promise<RunLaunchResponse> {
  const { data, error, response } = await runtimeApiClient.POST(
    "/api/v1/control/runs/nl",
    {
      body,
    },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to launch natural-language run",
    );
  }
  return data as RunLaunchResponse;
}

export function useLaunchNlRun() {
  const queryClient = useQueryClient();
  return useControlPlaneMutation({
    blockWhenOffline: true,
    errorToast: {
      title: "Natural-language launch failed",
      description: "Existing run data remains unchanged.",
      tone: "error",
    },
    mutationId: "runs.launch.nl",
    mutationFn: launchNlRun,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.runsRoot() });
    },
    successToast: (data) => ({
      title:
        data.status === "accepted"
          ? "Scenario launch accepted"
          : "Scenario launch rejected",
      description: data.message,
      tone: data.status === "accepted" ? "success" : "warning",
    }),
  });
}
