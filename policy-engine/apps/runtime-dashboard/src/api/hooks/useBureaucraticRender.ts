import { queryOptions, useQuery } from "@tanstack/react-query";

import {
  toApiTemporalParams,
  type TemporalScope,
} from "@/shared/lib/domain/temporal";
import {
  artifactRefForRequest,
  artifactRefMatchesResolvedView,
  type EvidenceArtifactRef,
} from "@/shared/lib/domain/evidence";
import type { BureaucraticGenre } from "@/features/artifacts/bureaucratic/ast/bureaucratic-document-ast";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { bureaucraticRenderSchema } from "../validators";

export type BureaucraticRenderRequest = {
  genre: BureaucraticGenre;
  jurisdiction?: string;
  templateVersion?: string | null;
  temporalScope?: TemporalScope | null;
  trustView?: boolean;
};

async function fetchBureaucraticRender(
  expectedRef: EvidenceArtifactRef,
  request: BureaucraticRenderRequest,
) {
  const { data, error, response } = await runtimeApiClient.POST(
    "/api/v1/artifacts/{packet_id}/render",
    {
      body: {
        genre: request.genre,
        jurisdiction: request.jurisdiction ?? "ua",
        manifest_profile_sha256:
          expectedRef.manifest_profile_sha256 ?? undefined,
        template_version: request.templateVersion ?? undefined,
        temporal_scope: Object.keys(toApiTemporalParams(request.temporalScope))
          .length
          ? toApiTemporalParams(request.temporalScope)
          : undefined,
        trust_view: request.trustView ?? false,
      },
      params: {
        path: {
          packet_id: expectedRef.artifact_id,
        },
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to render bureaucratic document ${expectedRef.artifact_id}`,
    );
  }

  const parsed = bureaucraticRenderSchema.parse(data);
  const metadata = parsed.document.metadata ?? {};
  const sourceKind = metadata.source_artifact_kind;
  const sourceMediaType = metadata.source_media_type;
  const sourceProfile = metadata.source_manifest_profile_sha256;
  if (
    (sourceKind !== undefined &&
      sourceKind !== null &&
      typeof sourceKind !== "string") ||
    (sourceMediaType !== undefined &&
      sourceMediaType !== null &&
      typeof sourceMediaType !== "string") ||
    (sourceProfile !== undefined &&
      sourceProfile !== null &&
      (typeof sourceProfile !== "string" ||
        !/^sha256:[0-9a-f]{64}$/u.test(sourceProfile)))
  ) {
    throw new Error("Bureaucratic render returned malformed source identity");
  }
  if (
    !artifactRefMatchesResolvedView(expectedRef, {
      artifact_id: parsed.document.packet_id,
      kind: typeof sourceKind === "string" ? sourceKind : null,
      media_type: typeof sourceMediaType === "string" ? sourceMediaType : null,
      manifest_profile_sha256:
        typeof sourceProfile === "string" ? sourceProfile : null,
    })
  ) {
    throw new Error(
      "Bureaucratic render does not match the selected artifact ref",
    );
  }
  return parsed;
}

export function bureaucraticRenderQueryOptions(
  artifact: string | EvidenceArtifactRef,
  request: BureaucraticRenderRequest,
) {
  const expectedRef = artifactRefForRequest(artifact);
  if (!expectedRef) {
    throw new Error("Bureaucratic rendering requires an artifact reference");
  }
  return queryOptions({
    queryKey: queryKeys.bureaucraticRender(expectedRef, request),
    queryFn: () => fetchBureaucraticRender(expectedRef, request),
  });
}

export function useBureaucraticRender(
  artifact: string | EvidenceArtifactRef | undefined,
  request: BureaucraticRenderRequest,
  options: { enabled?: boolean } = {},
) {
  const expectedRef = artifactRefForRequest(artifact);
  return useQuery({
    ...bureaucraticRenderQueryOptions(
      expectedRef ?? { artifact_id: "unknown" },
      request,
    ),
    enabled: Boolean(expectedRef) && (options.enabled ?? true),
  });
}
