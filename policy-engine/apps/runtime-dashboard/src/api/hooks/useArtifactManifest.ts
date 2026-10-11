import { useQuery } from "@tanstack/react-query";

import {
  artifactRefForRequest,
  artifactRefMatchesResolvedView,
  type EvidenceArtifactRef,
} from "@/shared/lib/domain/evidence";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { artifactManifestSchema } from "../validators";

async function fetchArtifactManifest(expectedRef: EvidenceArtifactRef) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/artifacts/{artifact_id}",
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
      `Failed to load artifact ${expectedRef.artifact_id}`,
    );
  }

  const parsed = artifactManifestSchema.parse(data);
  if (!artifactRefMatchesResolvedView(expectedRef, parsed.artifact)) {
    throw new Error(
      "Resolved artifact manifest does not match the selected ref",
    );
  }
  return parsed;
}

export function useArtifactManifest(
  artifact: string | EvidenceArtifactRef | undefined,
  { manifestProfileSha256 }: { manifestProfileSha256?: string | null } = {},
) {
  const expectedRef = artifactRefForRequest(artifact, manifestProfileSha256);
  const queryRef = expectedRef ?? { artifact_id: "unknown" };
  return useQuery({
    queryKey: queryKeys.artifactManifest(queryRef),
    queryFn: () => fetchArtifactManifest(expectedRef ?? { artifact_id: "" }),
    enabled: Boolean(expectedRef),
  });
}
