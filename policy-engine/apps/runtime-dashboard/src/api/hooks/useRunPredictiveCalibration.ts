import { queryOptions, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "../types";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { useControlPlaneMutation } from "../useControlPlaneMutation";
import { predictiveCalibrationResponseSchema } from "../validators";

type GeneratedPredictiveCalibrationRequest =
  components["schemas"]["PredictiveCalibrationRequest"];
type SelectedArtifactRef = components["schemas"]["ArtifactRef-Input"] & {
  media_type: "application/json";
  manifest_profile_sha256: string;
};

/** Exact local wire type until the canonical OpenAPI types are regenerated. */
export type PredictiveCalibrationRequest = Omit<
  GeneratedPredictiveCalibrationRequest,
  "value_data_profile_ref" | "value_data_unit_id"
> & {
  value_data_profile_ref?: SelectedArtifactRef | null;
  value_data_unit_id?: string | null;
};

async function fetchRunPredictiveCalibration(runId: string) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/predictive-calibration",
    { params: { path: { run_id: runId } } },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to load predictive calibration for ${runId}`,
    );
  }
  return predictiveCalibrationResponseSchema.parse(data);
}

async function createRunPredictiveCalibration(
  runId: string,
  body: PredictiveCalibrationRequest,
) {
  const { data, error, response } = await runtimeApiClient.POST(
    "/api/v1/runs/{run_id}/predictive-calibration",
    {
      params: { path: { run_id: runId } },
      // API5 regenerates the generated type from the already-typed server DTO.
      body: body as GeneratedPredictiveCalibrationRequest,
    },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to create predictive calibration for ${runId}`,
    );
  }
  return predictiveCalibrationResponseSchema.parse(data);
}

export function runPredictiveCalibrationQueryOptions(runId: string) {
  return queryOptions({
    queryKey: queryKeys.runPredictiveCalibration(runId),
    queryFn: () => fetchRunPredictiveCalibration(runId),
    retry: false,
    staleTime: 30_000,
  });
}

export function useRunPredictiveCalibration(
  runId: string | undefined,
  enabled = true,
) {
  return useQuery({
    ...runPredictiveCalibrationQueryOptions(runId ?? "unknown"),
    enabled: Boolean(runId) && enabled,
  });
}

export function useCreateRunPredictiveCalibration(runId: string) {
  const queryClient = useQueryClient();
  return useControlPlaneMutation({
    blockWhenOffline: true,
    mutationId: "runs.feedback.evaluate",
    mutationKey: ["runs", "predictive-calibration", runId],
    mutationFn: (body: PredictiveCalibrationRequest) =>
      createRunPredictiveCalibration(runId, body),
    errorToast: {
      title: "Predictive diagnostic failed",
      description:
        "The diagnostic could not be verified; the run remains unchanged.",
      tone: "error",
    },
    onSettled: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.runPredictiveCalibration(runId),
      });
    },
  });
}
