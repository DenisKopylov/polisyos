import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import type { components } from "../types";
import { useControlPlaneMutation } from "../useControlPlaneMutation";
import { lexSearchResponseSchema } from "../validators";

export type LexSearchRequest = components["schemas"]["LexSearchRequest"];
export type LexSearchResponse = components["schemas"]["LexSearchResponse"];

async function searchLexGraph(
  body: LexSearchRequest,
): Promise<LexSearchResponse> {
  const { data, error, response } = await runtimeApiClient.POST(
    "/api/v1/control/lex/search",
    {
      body,
    },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to search Lex graph");
  }
  return lexSearchResponseSchema.parse(data) as LexSearchResponse;
}

export function useLexSearch() {
  return useControlPlaneMutation({
    blockWhenOffline: true,
    mutationId: "lex.search",
    mutationFn: searchLexGraph,
  });
}
