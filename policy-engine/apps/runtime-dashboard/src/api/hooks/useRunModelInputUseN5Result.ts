import { queryOptions, useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import {
  runModelInputUseN5SuccessorResponseSchema,
  type RunModelInputUseActionsProjection,
  type RunModelInputUseN5SuccessorProjection,
} from "../validators";

async function fetchRunModelInputUseN5Result(
  runId: string,
  actionJobId: string,
  signal: AbortSignal,
): Promise<RunModelInputUseN5SuccessorProjection> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/model-input-use/{job_id}/n5-result",
    {
      params: {
        path: {
          run_id: runId,
          job_id: actionJobId,
        },
      },
      signal,
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to load model-input use result for ${actionJobId}`,
    );
  }

  const parsed = runModelInputUseN5SuccessorResponseSchema.parse(data);
  if (
    parsed.result.run_id !== runId ||
    parsed.result.action_job_id !== actionJobId
  ) {
    throw new Error("Model-input use result does not match its run/job path");
  }
  return parsed.result;
}

function runModelInputUseN5ResultQueryOptions(
  runId: string,
  actionJobId: string,
) {
  return queryOptions({
    queryKey: queryKeys.runModelInputUseN5Result(runId, actionJobId),
    queryFn: ({ signal }) =>
      fetchRunModelInputUseN5Result(runId, actionJobId, signal),
    retry: false,
    staleTime: 15_000,
  });
}

export function useRunModelInputUseN5Result(
  inventory: RunModelInputUseActionsProjection | undefined,
  selectedActionJobId: string | null,
) {
  const selectedAction = inventory?.actions.find(
    (action) => action.action_job_id === selectedActionJobId,
  );
  const runId = inventory?.run_id ?? "unselected-run";
  const actionJobId = selectedAction?.action_job_id ?? "unselected-action";

  return useQuery({
    ...runModelInputUseN5ResultQueryOptions(runId, actionJobId),
    enabled: Boolean(inventory && selectedAction),
  });
}
