import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import type { components } from "../types";
import { useControlPlaneMutation } from "../useControlPlaneMutation";

export type DataPreviewRequest = components["schemas"]["DataPreviewRequest"];
export type DataPreviewResponse = components["schemas"]["DataPreviewResponse"];

async function previewFetchPlan(
  body: DataPreviewRequest,
): Promise<DataPreviewResponse> {
  const { data, error, response } = await runtimeApiClient.POST(
    "/api/v1/control/data/preview",
    {
      body,
    },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to preview fetch plan",
    );
  }
  return data as DataPreviewResponse;
}

export function usePreviewFetchPlan() {
  return useControlPlaneMutation({
    blockWhenOffline: true,
    mutationId: "data.preview",
    mutationFn: previewFetchPlan,
  });
}
