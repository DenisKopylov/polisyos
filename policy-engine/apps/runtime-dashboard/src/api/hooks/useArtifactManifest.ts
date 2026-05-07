import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { artifactManifestSchema } from "../validators";

async function fetchArtifactManifest(artifactId: string) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/artifacts/{artifact_id}",
    {
      params: {
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
      `Failed to load artifact ${artifactId}`,
    );
  }

  return artifactManifestSchema.parse(data);
}

export function useArtifactManifest(artifactId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.artifactManifest(artifactId ?? "unknown"),
    queryFn: () => fetchArtifactManifest(artifactId ?? ""),
    enabled: Boolean(artifactId),
  });
}
