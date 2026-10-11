import { useQuery } from "@tanstack/react-query";

import {
  artifactRefForRequest,
  artifactRefMatchesResolvedView,
  type EvidenceArtifactRef,
} from "@/shared/lib/domain/evidence";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { artifactSchemaSchema } from "../validators";

async function fetchArtifactSchema(expectedRef: EvidenceArtifactRef) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/artifacts/{artifact_id}/schema",
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
      `Failed to load artifact schema ${expectedRef.artifact_id}`,
    );
  }

  const parsed = artifactSchemaSchema.parse(data);
  if (!artifactRefMatchesResolvedView(expectedRef, parsed.schema)) {
    throw new Error("Resolved artifact schema does not match the selected ref");
  }
  return parsed;
}

export function useArtifactSchema(
  artifact: string | EvidenceArtifactRef | undefined,
  enabled = true,
  manifestProfileSha256?: string | null,
) {
  const expectedRef = artifactRefForRequest(artifact, manifestProfileSha256);
  const queryRef = expectedRef ?? { artifact_id: "unknown" };
  return useQuery({
    queryKey: queryKeys.artifactSchema(queryRef),
    queryFn: () => fetchArtifactSchema(expectedRef ?? { artifact_id: "" }),
    enabled: Boolean(expectedRef) && enabled,
  });
}
