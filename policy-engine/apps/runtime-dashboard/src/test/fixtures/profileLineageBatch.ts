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

export type LineageGraphFixture = LineageGraphView;
export type LineageBatchMetaFixture = ReturnType<
  typeof lineageBatchResponseSchema.parse
>["meta"];
export type LineageTrustMetadataFixture = NonNullable<
  LineageGraphFixture["trust_metadata"]
>;

type ParsedLineageBatch = ReturnType<typeof lineageBatchResponseSchema.parse>;

type LineageGraphFixtureOptions = {
  lineageId: string;
  status: LineageGraphFixture["status"];
  freshness: LineageGraphFixture["freshness"];
  hash?: LineageGraphFixture["hash"];
  compactSummary?: LineageGraphFixture["compact_summary"];
  nodes?: LineageGraphFixture["nodes"];
  edges?: LineageGraphFixture["edges"];
  metadata?: Record<string, unknown>;
  selectedArtifactRef?: SelectedArtifactRef | null;
  profileBindingStatus?: LineageGraphFixture["profile_binding_status"];
  artifactRefProvenance?: ArtifactRefProvenance | null;
  sourceRunId?: string | null;
  trustMetadata?: LineageGraphFixture["trust_metadata"];
};

type ProfileBoundLineageGraphFixtureOptions = Omit<
  LineageGraphFixtureOptions,
  | "selectedArtifactRef"
  | "profileBindingStatus"
  | "artifactRefProvenance"
  | "sourceRunId"
> & {
  selectedArtifactRef: SelectedArtifactRef;
  artifactRefProvenance: ArtifactRefProvenance;
  sourceRunId: string;
};

/** Build one schema-validated lineage graph for consumer tests. */
export function lineageGraphFixture(
  options: LineageGraphFixtureOptions,
): LineageGraphFixture {
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

  return lineageGraphViewSchema.parse(graph);
}

/**
 * Build a profile-bound graph from the exact selector fields tested by consumers.
 * The constructor checks binding metadata without deriving it from the graph's
 * own ID or adding trust metadata.
 */
export function profileBoundLineageGraphFixture(
  options: ProfileBoundLineageGraphFixtureOptions,
): LineageGraphFixture {
  if (!options.sourceRunId.trim()) {
    throw new Error("Profile graph fixtures require an explicit source run");
  }
  const graph = lineageGraphFixture({
    ...options,
    profileBindingStatus: "verified",
  });
  if (
    graph.profile_binding_status !== "verified" ||
    !graph.selected_artifact_ref ||
    graph.artifact_ref_provenance !== options.artifactRefProvenance ||
    graph.source_run_id !== options.sourceRunId
  ) {
    throw new Error("The profile graph fixture failed its selected tuple");
  }
  return graph;
}

/** Build declared fixture metadata while keeping its temporal scope explicit. */
export function profileTrustMetadataFixture(options: {
  temporalScope: TemporalRef | null | undefined;
  hash?: string;
  verifiedBy?: string;
  verifiedAt?: string;
  verificationMethod?: string;
}): LineageTrustMetadataFixture {
  return {
    hash: options.hash ?? "sha256:selected-profile-lineage-fixture",
    verification_status: "verified",
    freshness: "current",
    dispute_status: "none",
    verified_by: options.verifiedBy ?? "selected-profile-reader-fixture",
    verified_at: options.verifiedAt ?? "2026-04-15T12:00:00Z",
    verification_method:
      options.verificationMethod ?? "selected-profile-reader",
    temporal_scope: options.temporalScope,
  };
}

/** Build a schema-validated batch reply from the caller's explicit request tuple. */
export type CompleteLineageBatchFixture = Omit<
  LineageBatchResponsePayload,
  "lineages" | "lineage_resolutions"
> & {
  lineages: LineageGraphFixture[];
  lineage_resolutions: NonNullable<ParsedLineageBatch["lineage_resolutions"]>;
};

export function lineageBatchFixture(options: {
  meta: LineageBatchMetaFixture;
  responseTemporalScope: TemporalRef | null | undefined;
  lineages: readonly LineageGraphFixture[];
  requestedLineageIds: readonly string[];
}): CompleteLineageBatchFixture {
  if (options.requestedLineageIds.length !== options.lineages.length) {
    throw new Error(
      "Each response graph needs one explicit requested lineage ID",
    );
  }
  const lineageResolutions = options.lineages.map((lineage, index) => {
    const requestedLineageId = options.requestedLineageIds[index];
    if (requestedLineageId === undefined) {
      throw new Error("A batch resolution is missing its requested lineage ID");
    }
    return {
      requested_lineage_id: requestedLineageId,
      resolved_lineage_id: lineage.id,
    };
  });
  const response = lineageBatchResponseSchema.parse({
    meta: options.meta,
    temporal_scope: options.responseTemporalScope,
    lineages: options.lineages,
    lineage_resolutions: lineageResolutions,
  });
  if (!response.lineages || !response.lineage_resolutions) {
    throw new Error(
      "The parsed batch fixture must retain every response member",
    );
  }
  return {
    ...response,
    lineages: response.lineages,
    lineage_resolutions: response.lineage_resolutions,
  };
}
