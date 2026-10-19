import type {
  ArtifactRefOutput as RuntimeArtifactRef,
  CounterfactualMetric as RuntimeCounterfactualMetric,
  FabricDecisionData as RuntimeFabricDecisionData,
  FabricDecisionDataResponse as RuntimeFabricDecisionDataResponse,
  LineageBatchResponse as RuntimeLineageBatchResponse,
  LineageCompactSummaryItem as RuntimeLineageCompactSummaryItem,
  LineageExportLinks as RuntimeLineageExportLinks,
  LineageExportResponse as RuntimeLineageExportResponse,
  LineageGraphEdge as RuntimeLineageGraphEdge,
  LineageGraphNode as RuntimeLineageGraphNode,
  LineageGraphView as RuntimeLineageGraphView,
  LineageResponse as RuntimeLineageResponse,
  PolisyosCoreContractsRuntimeLineageRefOutput as RuntimeLineageRef,
  QuantityUncertainty as RuntimeQuantityUncertainty,
  QuantityValueOutput as RuntimeQuantityValue,
  ScenarioRef as RuntimeScenarioRef,
  polisyos__core__contracts__runtime__TemporalRef as RuntimeTemporalRef,
  polisyos__core__contracts__runtime__UnitRef as RuntimeUnitRef,
} from "@polisyos/runtime-api-client";

export type CounterfactualMetric = RuntimeCounterfactualMetric;
export type FabricDecisionData = RuntimeFabricDecisionData;
export type FabricDecisionDataResponse = RuntimeFabricDecisionDataResponse;
export type LineageBatchResponsePayload = RuntimeLineageBatchResponse;
export type LineageCompactSummaryItem = RuntimeLineageCompactSummaryItem;
export type LineageExportLinks = RuntimeLineageExportLinks;
export type LineageExportPayload = RuntimeLineageExportResponse;
export type LineageGraphEdge = RuntimeLineageGraphEdge;
export type LineageGraphNode = RuntimeLineageGraphNode;
export type LineageGraphView = Omit<
  RuntimeLineageGraphView,
  "selected_artifact_ref"
> & {
  selected_artifact_ref?: RuntimeArtifactRef | null;
  profile_binding_status?: ProfileBindingStatus | null;
  artifact_ref_provenance?: ArtifactRefProvenance | null;
  source_run_id?: string | null;
};
export type LineageRef = RuntimeLineageRef;
export type LineageResponsePayload = RuntimeLineageResponse;
export type QuantityUncertainty = RuntimeQuantityUncertainty;
export type QuantityValue = Omit<RuntimeQuantityValue, "lineage"> & {
  lineage: RuntimeLineageRef & {
    artifact_ref?: SelectedArtifactRef | null;
    artifact_ref_provenance?: ArtifactRefProvenance | null;
    source_run_id?: string | null;
  };
  /** Consumer-side status for the selected profile/run/time join. */
  profile_binding_status?: ProfileBindingStatus;
  /** Requested time scope, preserving explicit null and missing scope. */
  profile_binding_temporal_scope?: TemporalRef | null;
  /** Exact tuple used to admit this quantity's profile trust metadata. */
  profile_binding_context?: ProfileBindingContext;
};
export type ScenarioRef = RuntimeScenarioRef;
export type TemporalRef = RuntimeTemporalRef;
export type UnitRef = RuntimeUnitRef;

export type LineageFreshness = LineageRef["freshness"];
export type QuantityClass = QuantityValue["quantity_class"];
export type VerificationStatus = LineageRef["status"];

export type SelectedArtifactRef = {
  artifact_id: string;
  kind: string;
  media_type: string;
  manifest_profile_sha256: string;
};

export type ArtifactRefProvenance = "run_output_ref" | "reader_materialized";
export type ProfileBindingStatus = "verified" | "not_established";

export type ProfileBindingContext = {
  status: "verified";
  lineageId: string;
  selectedArtifactRef: SelectedArtifactRef;
  sourceRunId: string;
  origin: ArtifactRefProvenance;
  temporalScope: TemporalRef | null;
  /** Admission epoch that produced the graph used for this consumer join. */
  admissionGeneration?: number;
};

export type LineageBatchSelector = {
  lineageId: string;
  selectedArtifactRef?: SelectedArtifactRef | null;
  artifactRefProvenance?: ArtifactRefProvenance | null;
  sourceRunId?: string | null;
};
