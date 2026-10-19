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

/** Build one schema-validated selected-profile reader response for consumer tests. */
export function profileLineageGraphFixture(options: {
  lineageId?: string;
  selectedArtifactRef: SelectedArtifactRef;
  artifactRefProvenance: ArtifactRefProvenance;
  sourceRunId: string;
  trustTemporalScope: TemporalRef | null | undefined;
  includeTrustMetadata?: boolean;
}): LineageGraphView {
  const lineageId =
    options.lineageId ?? `artifact:${options.selectedArtifactRef.artifact_id}`;
  const graph = lineageGraphViewSchema.parse({
    id: lineageId,
    status: "verified",
    hash: "sha256:selected-profile-lineage-fixture",
    freshness: "current",
    selected_artifact_ref: options.selectedArtifactRef,
    profile_binding_status: "verified",
    artifact_ref_provenance: options.artifactRefProvenance,
    source_run_id: options.sourceRunId,
    exports: {
      openlineage: `/api/v1/lineage/${encodeURIComponent(lineageId)}/export/openlineage`,
      prov: `/api/v1/lineage/${encodeURIComponent(lineageId)}/export/prov`,
    },
    nodes: [],
    edges: [],
    trust_metadata:
      options.includeTrustMetadata === false
        ? null
        : {
            hash: "sha256:selected-profile-lineage-fixture",
            verification_status: "verified",
            freshness: "current",
            dispute_status: "none",
            verified_by: "selected-profile-reader-fixture",
            verified_at: "2026-04-15T12:00:00Z",
            verification_method: "selected-profile-reader",
            temporal_scope: options.trustTemporalScope,
          },
  });
  return graph as LineageGraphView;
}

/** Build a schema-validated batch reply with one explicit resolution per graph. */
export function lineageBatchFixture(options: {
  meta: LineageBatchResponsePayload["meta"];
  responseTemporalScope: TemporalRef | null | undefined;
  lineages: readonly LineageGraphView[];
  requestedLineageIds?: readonly string[];
}): LineageBatchResponsePayload {
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
  return response as LineageBatchResponsePayload;
}
