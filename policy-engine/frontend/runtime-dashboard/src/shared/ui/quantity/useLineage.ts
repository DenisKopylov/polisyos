import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "@/api/client";
import { createRuntimeApiError } from "@/api/http";
import { queryKeys } from "@/api/queryKeys";
import {
  lineageExportResponseSchema,
  lineageResponseSchema,
} from "@/api/validators";
import {
  toApiTemporalParams,
  type TemporalScope,
} from "@/app/providers/temporal-scope";
import { useMaybeTemporalCursor } from "@/app/providers/useTemporalCursor";

export async function fetchLineage(
  lineageId: string,
  temporalScope?: TemporalScope | null,
) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/lineage/{lineage_id}",
    {
      params: {
        path: { lineage_id: lineageId },
        query: toApiTemporalParams(temporalScope),
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to load lineage ${lineageId}`,
    );
  }

  const parsed = lineageResponseSchema.parse(data);
  return {
    ...parsed,
    lineage: {
      ...parsed.lineage,
      compact_summary: parsed.lineage.compact_summary ?? [],
      nodes: parsed.lineage.nodes ?? [],
      edges: parsed.lineage.edges ?? [],
      metadata: parsed.lineage.metadata ?? {},
    },
  };
}

export async function fetchLineageExport(
  lineageId: string,
  format: "openlineage" | "prov",
  temporalScope?: TemporalScope | null,
) {
  const path =
    format === "openlineage"
      ? "/api/v1/lineage/{lineage_id}/export/openlineage"
      : "/api/v1/lineage/{lineage_id}/export/prov";
  const { data, error, response } = await runtimeApiClient.GET(path, {
    params: {
      path: { lineage_id: lineageId },
      query: toApiTemporalParams(temporalScope),
    },
  });

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to export lineage ${lineageId}`,
    );
  }

  return lineageExportResponseSchema.parse(data);
}

export function useLineage(
  lineageId: string | null | undefined,
  options: {
    enabled?: boolean;
    temporalScope?: TemporalScope | null;
  } = {},
) {
  const cursor = useMaybeTemporalCursor();
  const temporalScope = options.temporalScope ?? cursor?.committedScope ?? null;
  return useQuery({
    queryKey: queryKeys.lineage(lineageId ?? "unknown", temporalScope),
    queryFn: () => fetchLineage(lineageId ?? "", temporalScope),
    enabled: Boolean(lineageId) && (options.enabled ?? true),
  });
}

export function useLineageExport(
  lineageId: string | null | undefined,
  format: "openlineage" | "prov",
  options: {
    enabled?: boolean;
    temporalScope?: TemporalScope | null;
  } = {},
) {
  const cursor = useMaybeTemporalCursor();
  const temporalScope = options.temporalScope ?? cursor?.committedScope ?? null;
  return useQuery({
    queryKey: queryKeys.lineageExport(
      lineageId ?? "unknown",
      format,
      temporalScope,
    ),
    queryFn: () => fetchLineageExport(lineageId ?? "", format, temporalScope),
    enabled: Boolean(lineageId) && (options.enabled ?? false),
  });
}
