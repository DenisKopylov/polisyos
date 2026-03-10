import { queryOptions, useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type SourceProfilesListResponse =
  components["schemas"]["SourceProfilesListResponse"];
export type SourceProfileInfo = components["schemas"]["SourceProfileInfo"];

export async function fetchProfiles(): Promise<SourceProfilesListResponse> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/data/profiles",
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to load source profiles",
    );
  }
  return data as SourceProfilesListResponse;
}

export function sourceProfilesQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.sourceProfiles(),
    queryFn: fetchProfiles,
  });
}

export function useSourceProfiles() {
  return useQuery(sourceProfilesQueryOptions());
}
