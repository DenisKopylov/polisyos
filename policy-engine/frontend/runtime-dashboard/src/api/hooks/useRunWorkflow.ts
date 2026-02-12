import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { runWorkflowSchema } from "../validators";

async function fetchRunWorkflow(runId: string) {
  const { data, error, response } = await runtimeApiClient.GET("/api/v1/runs/{run_id}/workflow", {
    params: {
      path: {
        run_id: runId,
      },
    },
  });

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, `Failed to load workflow for ${runId}`);
  }

  const parsed = runWorkflowSchema.parse(data);
  return {
    ...parsed,
    workflow: {
      ...parsed.workflow,
      nodes: parsed.workflow.nodes ?? [],
      edges: parsed.workflow.edges ?? [],
      notes: parsed.workflow.notes ?? [],
    },
  };
}

export function useRunWorkflow(runId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.runWorkflow(runId ?? "unknown"),
    queryFn: () => fetchRunWorkflow(runId ?? ""),
    enabled: Boolean(runId) && enabled,
  });
}
