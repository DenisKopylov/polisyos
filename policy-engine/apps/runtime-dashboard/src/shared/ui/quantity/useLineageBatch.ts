import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "@/api/client";
import { createRuntimeApiError } from "@/api/http";
import { queryKeys } from "@/api/queryKeys";
import { lineageBatchResponseSchema } from "@/api/validators";
import {
  toApiTemporalParams,
  type TemporalScope,
} from "@/app/providers/temporal-scope";
import { useMaybeTemporalCursor } from "@/app/providers/useTemporalCursor";

import type { QuantityValue } from "./quantity.types";

export function lineageIdsFromQuantities(quantities: readonly QuantityValue[]) {
  return Array.from(
    new Set(
      quantities
        .map((quantity) => quantity.lineage.id)
        .filter((lineageId) => lineageId && lineageId !== "untraced"),
    ),
  );
}

export async function fetchLineageBatch(
  lineageIds: readonly string[],
  temporalScope?: TemporalScope | null,
) {
  const { data, error, response } = await runtimeApiClient.POST(
    "/api/v1/lineage/batch",
    {
      params: {
        query: toApiTemporalParams(temporalScope),
      },
      body: {
        lineage_ids: [...lineageIds],
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to load lineage batch",
    );
  }

  const parsed = lineageBatchResponseSchema.parse(data);
  return {
    ...parsed,
    lineages: (parsed.lineages ?? []).map((lineage) => ({
      ...lineage,
      compact_summary: lineage.compact_summary ?? [],
      nodes: lineage.nodes ?? [],
      edges: lineage.edges ?? [],
      metadata: lineage.metadata ?? {},
    })),
  };
}

export function useLineageBatch(
  lineageIds: readonly string[],
  options: {
    enabled?: boolean;
    temporalScope?: TemporalScope | null;
  } = {},
) {
  const cursor = useMaybeTemporalCursor();
  const temporalScope = options.temporalScope ?? cursor?.committedScope ?? null;
  const uniqueLineageIds = Array.from(new Set(lineageIds)).filter(Boolean);
  return useQuery({
    queryKey: queryKeys.lineageBatch(uniqueLineageIds, temporalScope),
    queryFn: () => fetchLineageBatch(uniqueLineageIds, temporalScope),
    enabled: uniqueLineageIds.length > 0 && (options.enabled ?? true),
  });
}
