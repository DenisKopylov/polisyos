import { useQuery } from "@tanstack/react-query";

import {
  artifactRefForRequest,
  artifactRefMatchesResolvedView,
  type EvidenceArtifactRef,
} from "@/shared/lib/domain/evidence";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { artifactLineageSchema } from "../validators";

async function fetchArtifactLineage(expectedRef: EvidenceArtifactRef) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/artifacts/{artifact_id}/lineage",
    {
      params: {
        query: {
          manifest_profile_sha256:
            expectedRef.manifest_profile_sha256 ?? undefined,
        },
        path: {
          artifact_id: expectedRef.artifact_id,
        },
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to load artifact lineage ${expectedRef.artifact_id}`,
    );
  }

  const parsed = artifactLineageSchema.parse(data);
  const matchingRoot = (parsed.lineage.root_artifact_refs ?? []).some((ref) =>
    artifactRefMatchesResolvedView(expectedRef, ref),
  );
  if (!matchingRoot) {
    throw new Error(
      "Resolved artifact lineage does not match the selected ref",
    );
  }
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

export function useArtifactLineage(
  artifact: string | EvidenceArtifactRef | undefined,
  enabled = true,
  manifestProfileSha256?: string | null,
) {
  const expectedRef = artifactRefForRequest(artifact, manifestProfileSha256);
  const queryRef = expectedRef ?? { artifact_id: "unknown" };
  return useQuery({
    queryKey: queryKeys.artifactLineage(queryRef),
    queryFn: () => fetchArtifactLineage(expectedRef ?? { artifact_id: "" }),
    enabled: Boolean(expectedRef) && enabled,
  });
}
