import { queryOptions, useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { lexSearchProfileResponseSchema } from "../validators";

export type LexSearchProfileResponse = ReturnType<
  typeof lexSearchProfileResponseSchema.parse
>;

async function fetchLexSearchProfile(
  outputDir: string,
): Promise<LexSearchProfileResponse> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/lex/search-profile",
    { params: { query: { output_dir: outputDir } } },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to read the selected Legal search profile",
    );
  }
  return lexSearchProfileResponseSchema.parse(data);
}

export function lexSearchProfileQueryOptions(outputDir: string) {
  return queryOptions({
    queryKey: queryKeys.lexSearchProfile(outputDir),
    queryFn: () => fetchLexSearchProfile(outputDir),
    staleTime: 0,
  });
}

export function useLexSearchProfile(outputDir: string) {
  return useQuery({
    ...lexSearchProfileQueryOptions(outputDir),
    enabled: outputDir.trim().length > 0,
  });
}
