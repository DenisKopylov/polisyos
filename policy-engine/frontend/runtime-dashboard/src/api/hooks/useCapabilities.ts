import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import { FALLBACK_CAPABILITY_MANIFEST } from "../../lib/capabilities";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";
import { capabilityManifestSchema } from "../validators";

export type CapabilityManifestResponse =
  components["schemas"]["CapabilityManifestResponse"];

export async function fetchCapabilities(): Promise<CapabilityManifestResponse> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/capabilities",
    {
      parseAs: "json",
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to load control capability manifest",
    );
  }

  return capabilityManifestSchema.parse(data);
}

export function capabilitiesQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.capabilities(),
    queryFn: fetchCapabilities,
    staleTime: Number.POSITIVE_INFINITY,
    retry: 1,
    placeholderData: FALLBACK_CAPABILITY_MANIFEST,
  });
}

export function useCapabilities() {
  return useQuery(capabilitiesQueryOptions());
}

export function useSuspenseCapabilities() {
  return useSuspenseQuery(capabilitiesQueryOptions());
}
