export type VerificationStatus =
  | "verified"
  | "pending"
  | "disputed"
  | "untraced";

export type LineageFreshness = "current" | "stale" | "unknown";
export type DisputeStatus = "none" | "disputed" | "under_review" | "resolved";

export type QuantityClass = "decision" | "telemetry" | "layout" | "debug";

export type UnitRef = {
  code: string;
  system: string;
  display?: string | null;
};

export type TemporalRef = {
  valid_at?: string | null;
  tx_at?: string | null;
  snapshot_id?: string | null;
  branch?: string | null;
  scenario_id?: string | null;
};

export type VerificationMetadata = {
  hash?: string | null;
  verification_status: VerificationStatus;
  verified_by?: string | null;
  verified_at?: string | null;
  verification_method?: string | null;
  freshness: LineageFreshness;
  dispute_status: DisputeStatus;
  temporal_scope?: TemporalRef | null;
};

export type TrustMetadataRef = {
  subject_id: string;
  subject_kind: "quantity" | "authored_text" | "artifact" | "lineage" | "chart";
  trust_metadata: VerificationMetadata;
};

export type LineageCompactSummaryItem = {
  kind:
    | "source"
    | "transform"
    | "model"
    | "agent"
    | "result"
    | "artifact"
    | "dataset"
    | "method"
    | "unknown";
  label: string;
  id?: string | null;
};

export type LineageRef = {
  id: string;
  hash?: string | null;
  status: VerificationStatus;
  freshness: LineageFreshness;
  summary?: Record<string, string>;
  compact_summary?: LineageCompactSummaryItem[];
  reason_code?: string | null;
  tracking_issue?: string | null;
  trust_metadata?: VerificationMetadata | null;
};

export type LineageGraphNode = {
  id: string;
  kind: string;
  label: string;
  timestamp?: string | null;
  metadata?: Record<string, unknown>;
};

export type LineageGraphEdge = {
  source_id: string;
  target_id: string;
  relation: string;
  metadata?: Record<string, unknown>;
};

export type LineageExportLinks = {
  openlineage: string;
  prov: string;
};

export type LineageGraphView = {
  id: string;
  status: VerificationStatus;
  hash?: string | null;
  freshness: LineageFreshness;
  compact_summary?: LineageCompactSummaryItem[];
  nodes?: LineageGraphNode[];
  edges?: LineageGraphEdge[];
  exports: LineageExportLinks;
  metadata?: Record<string, unknown>;
  trust_metadata?: VerificationMetadata | null;
};

export type LineageResponsePayload = {
  temporal_scope?: TemporalRef | null;
  lineage: LineageGraphView;
};

export type LineageBatchResponsePayload = {
  temporal_scope?: TemporalRef | null;
  lineages: LineageGraphView[];
};

export type LineageExportPayload = {
  temporal_scope?: TemporalRef | null;
  lineage_id: string;
  format: "openlineage" | "prov";
  payload: Record<string, unknown>;
};

export type QuantityUncertainty = {
  ci_80?: [number, number] | null;
  ci_95?: [number, number] | null;
  quantiles?: Record<string, number>;
  method?: string | null;
  identifiability?: "identified" | "estimated" | "assumed" | "unknown";
  disputed?: boolean;
};

export type QuantityValue = {
  point: number | null;
  unit: UnitRef;
  metric_id?: string | null;
  lineage: LineageRef;
  uncertainty?: QuantityUncertainty | null;
  time?: TemporalRef | null;
  quantity_class: QuantityClass;
  label?: string | null;
};

export type ScenarioStatus = "draft" | "computed" | "stale" | "failed";

export type ScenarioRef = {
  id: string;
  status: ScenarioStatus;
  baseline_run_id: string;
  temporal_scope?: TemporalRef | null;
  lineage: LineageRef;
  assumption_ids: string[];
  manifest_hash?: string | null;
};

export type CounterfactualMetric = {
  metric_id: string;
  label: string;
  actual: QuantityValue;
  counterfactual: QuantityValue;
  delta: QuantityValue;
  scenario_ref: ScenarioRef;
  assumption_ids: string[];
};
