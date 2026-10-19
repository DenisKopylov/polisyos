import {
  lineageBatchResponseSchema,
  lineageGraphViewSchema,
} from "@/api/validators";
import type {
  ArtifactRefProvenance,
  LineageBatchResponsePayload,
  LineageGraphView,
  SelectedArtifactRef,
  TemporalRef,
} from "@/shared/ui/quantity/quantity.types";

/** Build one schema-validated lineage graph for consumer tests. */
export function lineageGraphFixture(options: {
  lineageId: string;
  status: LineageGraphView["status"];
  freshness: LineageGraphView["freshness"];
  hash?: string | null;
  compactSummary?: LineageGraphView["compact_summary"];
  nodes?: LineageGraphView["nodes"];
  edges?: LineageGraphView["edges"];
  metadata?: Record<string, unknown>;
  selectedArtifactRef?: SelectedArtifactRef | null;
  profileBindingStatus?: LineageGraphView["profile_binding_status"];
  artifactRefProvenance?: ArtifactRefProvenance | null;
  sourceRunId?: string | null;
  trustMetadata?: LineageGraphView["trust_metadata"];
}): LineageGraphView {
  const graph: Record<string, unknown> = {
    id: options.lineageId,
    status: options.status,
    freshness: options.freshness,
    exports: {
      openlineage: `/api/v1/lineage/${encodeURIComponent(options.lineageId)}/export/openlineage`,
      prov: `/api/v1/lineage/${encodeURIComponent(options.lineageId)}/export/prov`,
    },
    nodes: options.nodes ?? [],
    edges: options.edges ?? [],
  };

  if (Object.hasOwn(options, "hash")) graph.hash = options.hash;
  if (Object.hasOwn(options, "compactSummary")) {
    graph.compact_summary = options.compactSummary;
  }
  if (Object.hasOwn(options, "metadata")) graph.metadata = options.metadata;
  if (Object.hasOwn(options, "selectedArtifactRef")) {
    graph.selected_artifact_ref = options.selectedArtifactRef;
  }
  if (Object.hasOwn(options, "profileBindingStatus")) {
    graph.profile_binding_status = options.profileBindingStatus;
  }
  if (Object.hasOwn(options, "artifactRefProvenance")) {
    graph.artifact_ref_provenance = options.artifactRefProvenance;
  }
  if (Object.hasOwn(options, "sourceRunId")) {
    graph.source_run_id = options.sourceRunId;
  }
  if (Object.hasOwn(options, "trustMetadata")) {
    graph.trust_metadata = options.trustMetadata;
  }

  return lineageGraphViewSchema.parse(graph) as LineageGraphView;
}

/** Build a schema-validated batch reply with one explicit resolution per graph. */
export type CompleteLineageBatchFixture = LineageBatchResponsePayload & {
  lineages: LineageGraphView[];
  lineage_resolutions: NonNullable<
    LineageBatchResponsePayload["lineage_resolutions"]
  >;
};

export function lineageBatchFixture(options: {
  meta: LineageBatchResponsePayload["meta"];
  responseTemporalScope: TemporalRef | null | undefined;
  lineages: readonly LineageGraphView[];
  requestedLineageIds?: readonly string[];
}): CompleteLineageBatchFixture {
  const requestedLineageIds =
    options.requestedLineageIds ??
    options.lineages.map((lineage) => lineage.id);
  if (requestedLineageIds.length !== options.lineages.length) {
    throw new Error("Each lineage fixture needs one requested lineage ID");
  }
  const response = lineageBatchResponseSchema.parse({
    meta: options.meta,
    temporal_scope: options.responseTemporalScope,
    lineages: options.lineages,
    lineage_resolutions: options.lineages.map((lineage, index) => ({
      requested_lineage_id: requestedLineageIds[index],
      resolved_lineage_id: lineage.id,
    })),
  });
  return response as CompleteLineageBatchFixture;
}
