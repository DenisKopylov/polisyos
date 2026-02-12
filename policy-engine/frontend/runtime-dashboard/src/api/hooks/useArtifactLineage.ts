import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { artifactLineageSchema } from "../validators";

async function fetchArtifactLineage(artifactId: string) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/artifacts/{artifact_id}/lineage",
    {
      params: {
        path: {
          artifact_id: artifactId,
        },
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, `Failed to load artifact lineage ${artifactId}`);
  }

  const parsed = artifactLineageSchema.parse(data);
  return {
    ...parsed,
    lineage: {
      ...parsed.lineage,
      nodes: parsed.lineage.nodes ?? [],
      edges: parsed.lineage.edges ?? [],
      root_artifact_ids: parsed.lineage.root_artifact_ids ?? [],
      missing_artifact_ids: parsed.lineage.missing_artifact_ids ?? [],
      corrupted_artifact_ids: parsed.lineage.corrupted_artifact_ids ?? [],
    },
  };
}

export function useArtifactLineage(artifactId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.artifactLineage(artifactId ?? "unknown"),
    queryFn: () => fetchArtifactLineage(artifactId ?? ""),
    enabled: Boolean(artifactId) && enabled,
  });
}
