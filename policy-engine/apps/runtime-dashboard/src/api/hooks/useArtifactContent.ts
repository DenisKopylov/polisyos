import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { artifactContentSchema } from "../validators";

async function fetchArtifactContent(
  artifactId: string,
  maxBytes: number | null,
) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/artifacts/{artifact_id}/content",
    {
      params: {
        query: {
          max_bytes: maxBytes ?? undefined,
        },
        path: {
          artifact_id: artifactId,
        },
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to load artifact content ${artifactId}`,
    );
  }

  return artifactContentSchema.parse(data);
}

type UseArtifactContentOptions = {
  enabled?: boolean;
  maxBytes?: number | null;
};

export function artifactContentQueryOptions(
  artifactId: string,
  maxBytes: number | null = null,
) {
  return queryOptions({
    queryKey: queryKeys.artifactContent(artifactId, maxBytes),
    queryFn: () => fetchArtifactContent(artifactId, maxBytes),
  });
}

export function useArtifactContent(
  artifactId: string | undefined,
  { enabled = true, maxBytes = null }: UseArtifactContentOptions = {},
) {
  return useQuery({
    ...artifactContentQueryOptions(artifactId ?? "unknown", maxBytes),
    enabled: Boolean(artifactId) && enabled,
  });
}

export function useSuspenseArtifactContent(
  artifactId: string,
  { maxBytes = null }: Omit<UseArtifactContentOptions, "enabled"> = {},
) {
  return useSuspenseQuery(artifactContentQueryOptions(artifactId, maxBytes));
}
