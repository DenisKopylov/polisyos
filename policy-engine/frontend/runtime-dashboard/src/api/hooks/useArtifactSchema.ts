import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { artifactSchemaSchema } from "../validators";

async function fetchArtifactSchema(artifactId: string) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/artifacts/{artifact_id}/schema",
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
      `Failed to load artifact schema ${artifactId}`,
    );
  }

  return artifactSchemaSchema.parse(data);
}

export function useArtifactSchema(
  artifactId: string | undefined,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.artifactSchema(artifactId ?? "unknown"),
    queryFn: () => fetchArtifactSchema(artifactId ?? ""),
    enabled: Boolean(artifactId) && enabled,
  });
}
