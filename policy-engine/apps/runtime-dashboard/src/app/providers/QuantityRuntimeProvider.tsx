import { useCallback, useMemo, type PropsWithChildren } from "react";

import { runtimeApiClient } from "@/api/client";
import { createRuntimeApiError } from "@/api/http";
import {
  lineageBatchResponseSchema,
  lineageExportResponseSchema,
  lineageResponseSchema,
} from "@/api/validators";
import {
  QuantityRuntimeBridgeProvider,
  type LineageBatchResponsePayload,
  type LineageExportPayload,
  type LineageResponsePayload,
  type QuantityValue,
  type TemporalRef,
} from "@/shared/ui/quantity";
import { TrustMetadata } from "@/shared/ui/trust-view";

import { useMaybeTemporalCursor } from "@/shared/ui/temporal/TemporalRuntimeBridge";
import { useMaybeTrustView } from "./useTrustView";

export function QuantityRuntimeProvider({ children }: PropsWithChildren) {
  const cursor = useMaybeTemporalCursor();
  const trustView = useMaybeTrustView();
  const temporalScope = temporalRef(cursor?.committedScope ?? null);

  const fetchLineage = useCallback(
    async (lineageId: string, scope: TemporalRef | null) => {
      const { data, error, response } = await runtimeApiClient.GET(
        "/api/v1/lineage/{lineage_id}",
        {
          params: {
            path: { lineage_id: lineageId },
            query: temporalQuery(scope),
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
        lineage: normalizeLineage(parsed.lineage),
      } as LineageResponsePayload;
    },
    [],
  );

  const fetchLineageBatch = useCallback(
    async (lineageIds: readonly string[], scope: TemporalRef | null) => {
      const { data, error, response } = await runtimeApiClient.POST(
        "/api/v1/lineage/batch",
        {
          params: { query: temporalQuery(scope) },
          body: { lineage_ids: [...lineageIds] },
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
        lineages: (parsed.lineages ?? []).map(normalizeLineage),
      } as LineageBatchResponsePayload;
    },
    [],
  );

  const fetchLineageExport = useCallback(
    async (
      lineageId: string,
      format: LineageExportPayload["format"],
      scope: TemporalRef | null,
    ) => {
      const path =
        format === "openlineage"
          ? "/api/v1/lineage/{lineage_id}/export/openlineage"
          : "/api/v1/lineage/{lineage_id}/export/prov";
      const { data, error, response } = await runtimeApiClient.GET(path, {
        params: {
          path: { lineage_id: lineageId },
          query: temporalQuery(scope),
        },
      });
      if (error || !response.ok || !data) {
        throw createRuntimeApiError(
          response,
          error,
          `Failed to export lineage ${lineageId}`,
        );
      }
      return lineageExportResponseSchema.parse(data) as LineageExportPayload;
    },
    [],
  );

  const renderTrustMetadata = useCallback(
    (quantity: QuantityValue, mode: "compact" | "expanded") => {
      const metadata = quantity.lineage.trust_metadata;
      if (!metadata) {
        return null;
      }
      return (
        <TrustMetadata
          hash={quantity.lineage.hash}
          label={quantity.label ?? quantity.metric_id}
          metadata={metadata}
          mode={mode}
          subjectId={quantity.lineage.id}
          subjectKind="quantity"
        />
      );
    },
    [],
  );

  const value = useMemo(
    () => ({
      fetchLineage,
      fetchLineageBatch,
      fetchLineageExport,
      renderTrustMetadata,
      temporalScope,
      trustMode:
        trustView?.mode === "off" || !trustView
          ? ("off" as const)
          : trustView.density === "condensed"
            ? ("compact" as const)
            : trustView.mode,
    }),
    [
      fetchLineage,
      fetchLineageBatch,
      fetchLineageExport,
      renderTrustMetadata,
      temporalScope,
      trustView,
    ],
  );

  return (
    <QuantityRuntimeBridgeProvider value={value}>
      {children}
    </QuantityRuntimeBridgeProvider>
  );
}

function temporalRef(
  scope: {
    branch?: string | null;
    scenarioId?: string | null;
    snapshotId?: string | null;
    txAt?: string | null;
    validAt?: string | null;
  } | null,
): TemporalRef | null {
  if (!scope) {
    return null;
  }
  return {
    branch: scope.branch ?? null,
    scenario_id: scope.scenarioId ?? null,
    snapshot_id: scope.snapshotId ?? null,
    tx_at: scope.txAt ?? null,
    valid_at: scope.validAt ?? null,
  };
}

function temporalQuery(scope: TemporalRef | null) {
  return {
    branch: scope?.branch ?? undefined,
    scenario_id: scope?.scenario_id ?? undefined,
    snapshot_id: scope?.snapshot_id ?? undefined,
    tx_at: scope?.tx_at ?? undefined,
    valid_at: scope?.valid_at ?? undefined,
  };
}

function normalizeLineage<T extends Record<string, unknown>>(lineage: T) {
  return {
    ...lineage,
    compact_summary: lineage.compact_summary ?? [],
    edges: lineage.edges ?? [],
    metadata: lineage.metadata ?? {},
    nodes: lineage.nodes ?? [],
  };
}
