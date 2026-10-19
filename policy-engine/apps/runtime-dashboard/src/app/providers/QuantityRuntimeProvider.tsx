import { useCallback, useMemo, type PropsWithChildren } from "react";

import { runtimeApiClient } from "@/api/client";
import { createRuntimeApiError } from "@/api/http";
import {
  lineageBatchResponseSchema,
  lineageExportResponseSchema,
  lineageResponseSchema,
} from "@/api/validators";
import {
  alignLineageBatchResponses,
  quantityHasExactProfileTrust,
  QuantityRuntimeBridgeProvider,
  type LineageBatchResponsePayload,
  type LineageBatchSelector,
  type LineageExportPayload,
  type LineageResponsePayload,
  type QuantityValue,
  type TemporalRef,
} from "@/shared/ui/quantity";
import { TrustMetadata, useMaybeTrustView } from "@/shared/ui/trust-view";
import {
  sameProfileBindingIdentity,
  useAdmittedBoundLineage,
} from "@/shared/ui/quantity/useLineageBatch";

import { useMaybeTemporalCursor } from "@/shared/ui/temporal/TemporalRuntimeBridge";

export function QuantityRuntimeProvider({ children }: PropsWithChildren) {
  const cursor = useMaybeTemporalCursor();
  const trustView = useMaybeTrustView();
  const temporalScope = temporalRef(cursor?.committedScope ?? null);

  const fetchLineage = useCallback(
    async (lineageId: string, scope: TemporalRef | null | undefined) => {
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
      if (parsed.lineage.id !== lineageId) {
        throw new Error(
          "Lineage response does not match the requested lineage ID",
        );
      }
      return {
        ...parsed,
        lineage: normalizeLineage(parsed.lineage),
      } as LineageResponsePayload;
    },
    [],
  );

  const fetchLineageBatch = useCallback(
    async (
      selectors: readonly LineageBatchSelector[],
      runId: string | undefined,
      scope: TemporalRef | null | undefined,
    ) => {
      const includeSelectedArtifactRefs =
        Boolean(runId) ||
        selectors.some((selector) => selector.selectedArtifactRef != null);
      const body = {
        lineage_ids: selectors.map((selector) => selector.lineageId),
        ...(includeSelectedArtifactRefs
          ? {
              selected_artifact_refs: selectors.map(
                (selector) => selector.selectedArtifactRef ?? null,
              ),
            }
          : {}),
        ...(runId ? { run_id: runId } : {}),
      };
      const { data, error, response } = await runtimeApiClient.POST(
        "/api/v1/lineage/batch",
        {
          params: { query: temporalQuery(scope) },
          body,
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
      alignLineageBatchResponses(
        selectors,
        parsed as LineageBatchResponsePayload,
        {
          runId,
          temporalScope: scope,
        },
      );
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
      scope: TemporalRef | null | undefined,
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
      const parsed = lineageExportResponseSchema.parse(data);
      if (parsed.lineage_id !== lineageId || parsed.format !== format) {
        throw new Error(
          "Lineage export does not match the requested subject and format",
        );
      }
      return parsed as LineageExportPayload;
    },
    [],
  );

  const renderTrustMetadata = useCallback(
    (quantity: QuantityValue, mode: "compact" | "expanded") => {
      if (!quantityHasExactProfileTrust(quantity)) {
        return null;
      }
      return <AdmittedQuantityTrustMetadata quantity={quantity} mode={mode} />;
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

function AdmittedQuantityTrustMetadata({
  quantity,
  mode,
}: {
  quantity: QuantityValue;
  mode: "compact" | "expanded";
}) {
  const selectedProfileContext = quantity.profile_binding_context;
  const selector = {
    lineageId: quantity.lineage.id,
    selectedArtifactRef: quantity.lineage.artifact_ref ?? null,
    artifactRefProvenance: quantity.lineage.artifact_ref_provenance ?? null,
    sourceRunId: quantity.lineage.source_run_id ?? null,
  };
  const query = useAdmittedBoundLineage(selector, {
    runId: selectedProfileContext?.sourceRunId,
    temporalScope: selectedProfileContext?.temporalScope,
  });
  const currentProfileContext = query.profileBindingContext;
  const metadata = query.data?.lineage.trust_metadata;
  if (
    query.isError ||
    query.isFetching ||
    !selectedProfileContext ||
    !currentProfileContext ||
    !sameProfileBindingIdentity(
      currentProfileContext,
      selectedProfileContext,
    ) ||
    !metadata
  ) {
    return null;
  }
  return (
    <TrustMetadata
      hash={query.data?.lineage.hash ?? quantity.lineage.hash}
      label={quantity.label ?? quantity.metric_id}
      metadata={metadata}
      selectedProfileContext={currentProfileContext}
      mode={mode}
      subjectId={quantity.lineage.id}
      subjectKind="quantity"
    />
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
    ...(scope.branch !== undefined ? { branch: scope.branch } : {}),
    ...(scope.scenarioId !== undefined
      ? { scenario_id: scope.scenarioId }
      : {}),
    ...(scope.snapshotId !== undefined
      ? { snapshot_id: scope.snapshotId }
      : {}),
    ...(scope.txAt !== undefined ? { tx_at: scope.txAt } : {}),
    ...(scope.validAt !== undefined ? { valid_at: scope.validAt } : {}),
  };
}

function temporalQuery(scope: TemporalRef | null | undefined) {
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
