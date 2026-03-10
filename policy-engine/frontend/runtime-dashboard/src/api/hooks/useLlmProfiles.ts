import { queryOptions, useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type ModelProfilesListResponse =
  components["schemas"]["ModelProfilesListResponse"];
export type ModelProfileInfo = components["schemas"]["ModelProfileInfo"];

export async function fetchLlmProfiles(): Promise<ModelProfilesListResponse> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/llm/profiles",
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to load LLM profiles");
  }
  return data as ModelProfilesListResponse;
}

export function llmProfilesQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.llmProfiles(),
    queryFn: fetchLlmProfiles,
  });
}

export function useLlmProfiles() {
  return useQuery(llmProfilesQueryOptions());
}
