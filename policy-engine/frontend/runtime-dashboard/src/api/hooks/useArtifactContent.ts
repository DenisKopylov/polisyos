import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { artifactContentSchema } from "../validators";

async function fetchArtifactContent(artifactId: string, maxBytes: number | null) {
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
    throw createRuntimeApiError(response, error, `Failed to load artifact content ${artifactId}`);
  }

  return artifactContentSchema.parse(data);
}

type UseArtifactContentOptions = {
  enabled?: boolean;
  maxBytes?: number | null;
};

export function useArtifactContent(
  artifactId: string | undefined,
  { enabled = true, maxBytes = null }: UseArtifactContentOptions = {},
) {
  return useQuery({
    queryKey: queryKeys.artifactContent(artifactId ?? "unknown", maxBytes),
    queryFn: () => fetchArtifactContent(artifactId ?? "", maxBytes),
    enabled: Boolean(artifactId) && enabled,
  });
}
