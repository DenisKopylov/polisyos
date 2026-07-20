import { queryOptions, useQuery } from "@tanstack/react-query";

import {
  toApiTemporalParams,
  type TemporalScope,
} from "@/shared/lib/domain/temporal";
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
  artifactId: string,
  request: BureaucraticRenderRequest,
) {
  const { data, error, response } = await runtimeApiClient.POST(
    "/api/v1/artifacts/{packet_id}/render",
    {
      body: {
        genre: request.genre,
        jurisdiction: request.jurisdiction ?? "ua",
        template_version: request.templateVersion ?? undefined,
        temporal_scope: Object.keys(toApiTemporalParams(request.temporalScope))
          .length
          ? toApiTemporalParams(request.temporalScope)
          : undefined,
        trust_view: request.trustView ?? false,
      },
      params: {
        path: {
          packet_id: artifactId,
        },
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to render bureaucratic document ${artifactId}`,
    );
  }

  return bureaucraticRenderSchema.parse(data);
}

export function bureaucraticRenderQueryOptions(
  artifactId: string,
  request: BureaucraticRenderRequest,
) {
  return queryOptions({
    queryKey: queryKeys.bureaucraticRender(artifactId, request),
    queryFn: () => fetchBureaucraticRender(artifactId, request),
  });
}

export function useBureaucraticRender(
  artifactId: string | undefined,
  request: BureaucraticRenderRequest,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    ...bureaucraticRenderQueryOptions(artifactId ?? "unknown", request),
    enabled: Boolean(artifactId) && (options.enabled ?? true),
  });
}
