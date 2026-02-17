import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type LexPipelineStatusResponse = components["schemas"]["LexPipelineStatusResponse"];

async function fetchLexPipelineStatus(pipelineId: string): Promise<LexPipelineStatusResponse> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/lex/status/{pipeline_id}",
    { params: { path: { pipeline_id: pipelineId } } },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to fetch Lex pipeline status");
  }
  return data as LexPipelineStatusResponse;
}

export function useLexPipelineStatus(pipelineId: string | null) {
  return useQuery({
    queryKey: queryKeys.lexPipelineStatus(pipelineId ?? ""),
    queryFn: () => fetchLexPipelineStatus(pipelineId!),
    enabled: !!pipelineId,
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      if (state === "running" || state === "pending") {
        return 3000;
      }
      return false;
    },
  });
}
