import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type LexGraphStatsResponse =
  components["schemas"]["LexGraphStatsResponse"];

async function fetchLexGraphStats(
  outputDir: string,
): Promise<LexGraphStatsResponse> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/lex/graph/stats",
    { params: { query: { output_dir: outputDir } } },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to fetch Lex graph stats",
    );
  }
  return data as LexGraphStatsResponse;
}

export function lexGraphStatsQueryOptions(outputDir: string) {
  return queryOptions({
    queryKey: queryKeys.lexGraphStats(outputDir),
    queryFn: () => fetchLexGraphStats(outputDir),
  });
}

export function useLexGraphStats(outputDir: string, enabled = true) {
  return useQuery({
    ...lexGraphStatsQueryOptions(outputDir),
    enabled: enabled && outputDir.trim().length > 0,
  });
}

export function useSuspenseLexGraphStats(outputDir: string) {
  return useSuspenseQuery(lexGraphStatsQueryOptions(outputDir));
}
