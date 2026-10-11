import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import {
  artifactRefForRequest,
  artifactRefMatchesResolvedView,
  type EvidenceArtifactRef,
} from "@/shared/lib/domain/evidence";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { artifactContentSchema } from "../validators";

async function fetchArtifactContent(
  expectedRef: EvidenceArtifactRef,
  maxBytes: number | null,
) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/artifacts/{artifact_id}/content",
    {
      params: {
        query: {
          max_bytes: maxBytes ?? undefined,
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
      `Failed to load artifact content ${expectedRef.artifact_id}`,
    );
  }

  const parsed = artifactContentSchema.parse(data);
  if (!artifactRefMatchesResolvedView(expectedRef, parsed.artifact)) {
    throw new Error(
      "Resolved artifact content does not match the selected ref",
    );
  }
  return parsed;
}

type UseArtifactContentOptions = {
  enabled?: boolean;
  maxBytes?: number | null;
  manifestProfileSha256?: string | null;
};

export function artifactContentQueryOptions(
  artifact: string | EvidenceArtifactRef,
  maxBytes: number | null = null,
  manifestProfileSha256?: string | null,
) {
  const expectedRef = artifactRefForRequest(artifact, manifestProfileSha256);
  if (!expectedRef) {
    throw new Error("Artifact content query requires an artifact reference");
  }
  return queryOptions({
    queryKey: queryKeys.artifactContent(expectedRef, maxBytes),
    queryFn: () => fetchArtifactContent(expectedRef, maxBytes),
  });
}

export function useArtifactContent(
  artifact: string | EvidenceArtifactRef | undefined,
  {
    enabled = true,
    maxBytes = null,
    manifestProfileSha256,
  }: UseArtifactContentOptions = {},
) {
  const expectedRef = artifactRefForRequest(artifact, manifestProfileSha256);
  const queryRef = expectedRef ?? { artifact_id: "unknown" };
  return useQuery({
    ...artifactContentQueryOptions(queryRef, maxBytes),
    enabled: Boolean(expectedRef) && enabled,
  });
}

export function useSuspenseArtifactContent(
  artifact: string | EvidenceArtifactRef,
  {
    maxBytes = null,
    manifestProfileSha256,
  }: Omit<UseArtifactContentOptions, "enabled"> = {},
) {
  return useSuspenseQuery(
    artifactContentQueryOptions(artifact, maxBytes, manifestProfileSha256),
  );
}
