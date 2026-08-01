import { z } from "zod";

import type {
  DecisionValidityStatus,
  QuantityUncertainty,
  QuantityValueOutput,
} from "@polisyos/runtime-api-client";

import type { components } from "./types";
import {
  isGeneratedProjectionAuthority,
  normalizeApiProjectionFailClosed,
  normalizeOperatorProjectionLabelFailClosed,
  type GeneratedProjectionAuthority,
} from "@/shared/lib/domain/projectionFailClosed";

const apiMetaSchema = z.object({
  request_id: z.string(),
  generated_at: z.string(),
  source_kinds: z.array(z.literal("core_run")).default([]),
});

const cursorPageSchema = z.object({
  limit: z.number(),
  cursor: z.string().nullable().optional(),
  next_cursor: z.string().nullable().optional(),
  count: z.number(),
  total: z.number().nullable().optional(),
});

const temporalRefSchema = z.object({
  valid_at: z.string().nullable().optional(),
  tx_at: z.string().nullable().optional(),
  branch: z.string().nullable().optional(),
  snapshot_id: z.string().nullable().optional(),
  scenario_id: z.string().nullable().optional(),
});

const temporalScopeSchema = temporalRefSchema.nullable().optional();

const decisionValidityStatusMembers = {
  active: true,
  requires_human_review: true,
  reissued: true,
  review_required: true,
  revoked: true,
  stale: true,
  superseded: true,
  warning: true,
  withdrawn: true,
} as const satisfies Record<DecisionValidityStatus, true>;

const decisionValidityStatusSchema = z
  .string()
  .refine(
    (value): value is DecisionValidityStatus =>
      Object.hasOwn(decisionValidityStatusMembers, value),
    "unknown generated decision validity status",
  );

const temporalRangeSchema = z.object({
  earliest: z.string().nullable().optional(),
  latest: z.string().nullable().optional(),
});

const temporalEventPointSchema = z.object({
  id: z.string(),
  timestamp: z.string(),
  kind: z.enum([
    "run_start",
    "run_finish",
    "trace_event",
    "policy_change",
    "late_evidence",
    "correction",
    "snapshot",
    "now",
  ]),
  label: z.string(),
  valid_at: z.string().nullable().optional(),
  tx_at: z.string().nullable().optional(),
  observed: z.boolean().optional(),
});

const temporalSurfaceCapabilitySchema = z.object({
  surface: z.string(),
  supported: z.boolean(),
  resolution: z.string(),
  reason_code: z.string().nullable().optional(),
  valid_range: temporalRangeSchema.nullable().optional(),
  tx_range: temporalRangeSchema.nullable().optional(),
  nearest_event_points: z.array(temporalEventPointSchema).optional(),
  gaps: z
    .array(
      z.object({
        start: z.string().nullable().optional(),
        end: z.string().nullable().optional(),
        reason_code: z.string(),
        label: z.string().nullable().optional(),
      }),
    )
    .optional(),
});

const temporalCapabilitiesViewSchema = z.object({
  run_id: z.string().nullable().optional(),
  default_scope: temporalScopeSchema,
  valid_range: temporalRangeSchema,
  tx_range: temporalRangeSchema,
  resolution: z.string(),
  surfaces: z.array(temporalSurfaceCapabilitySchema).optional(),
  event_points: z.array(temporalEventPointSchema).optional(),
});

const artifactRefSchema = z.object({
  artifact_id: z.string(),
  kind: z.string().optional(),
  media_type: z.string().optional(),
});

const operatorProjectionStateLabelSchema = z
  .object({
    authority: z.enum(["runtime_authority", "projection_only"]),
    label: z.string(),
    state: z.enum([
      "draft",
      "projection_only",
      "redacted",
      "stale",
      "contested",
      "projected",
      "blocked",
      "readiness_closed",
      "approved",
      "rejected",
      "published_blocked",
      "publishable",
    ]),
  })
  .transform(normalizeOperatorProjectionLabelFailClosed);

const policyDesignCaseProjectionSchema = z
  .custom<GeneratedProjectionAuthority>(isGeneratedProjectionAuthority, {
    message: "Policy Design Case projection lacks generated authority fields",
  })
  .transform(normalizeApiProjectionFailClosed);

const operatorDiagnosticSchema = z.object({
  authoritative_runtime_state: z.string(),
  projection_source: z.string(),
  owner: z.string(),
  phase: z.string(),
  first_blocking_cause: z.string(),
  upstream_missing_input: z.string().nullable().optional(),
  downstream_impact: z.string(),
  authority_refs: z.record(z.string(), z.string()).optional(),
  blocker_overridable: z.boolean().default(false),
  evidence_refs: z.array(z.string()).optional(),
  next_diagnostic_command: z.string(),
  projection_labels: z.array(operatorProjectionStateLabelSchema).optional(),
});

const runSummarySchema = z.object({
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  status: z.string(),
  decision_review_required: z.boolean().optional(),
  started_at: z.string().nullable().optional(),
  finished_at: z.string().nullable().optional(),
  duration_ms: z.number().nullable().optional(),
  tenant_id: z.string().nullable().optional(),
  has_trace: z.boolean().optional(),
  root_artifact_count: z.number().optional(),
  has_workflow_report: z.boolean().optional(),
  warnings: z.array(z.string()).optional(),
});

const runDetailsSchemaInner = z.object({
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  status: z.string(),
  started_at: z.string().nullable().optional(),
  finished_at: z.string().nullable().optional(),
  duration_ms: z.number().nullable().optional(),
  tenant_id: z.string().nullable().optional(),
  cell_id: z.string().nullable().optional(),
  decision_validity_status: decisionValidityStatusSchema.nullable().optional(),
  has_trace: z.boolean().optional(),
  has_workflow_report: z.boolean().optional(),
  manifest_ref: artifactRefSchema.nullable().optional(),
  operator_diagnostic: operatorDiagnosticSchema.nullable().optional(),
  policy_design_case_projection: policyDesignCaseProjectionSchema
    .nullable()
    .optional(),
  trace_ref: artifactRefSchema.nullable().optional(),
  workflow_report_ref: artifactRefSchema.nullable().optional(),
  root_artifacts: z.array(artifactRefSchema).optional(),
  warnings: z.array(z.string()).optional(),
});

const runTimelineEventSchema = z.object({
  index: z.number(),
  timestamp: z.string(),
  phase: z.string(),
  event: z.string(),
  span_id: z.string().nullable().optional(),
  parent_span_id: z.string().nullable().optional(),
  input_artifact_ids: z.array(z.string()).optional(),
  output_artifact_ids: z.array(z.string()).optional(),
  metrics: z.record(z.string(), z.number()).optional(),
  warning_count: z.number().optional(),
  error_count: z.number().optional(),
});

const runTimelineSummarySchema = z.object({
  run_id: z.string(),
  total_events: z.number(),
  duration_ms: z.number().nullable().optional(),
  node_status_counts: z.record(z.string(), z.number()).optional(),
  phase_counts: z.record(z.string(), z.number()).optional(),
  cache_hits: z.number().optional(),
  cache_stores: z.number().optional(),
  cache_bypasses: z.number().optional(),
});

const runTimelineViewSchema = z.object({
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  summary: runTimelineSummarySchema,
  events: z.array(runTimelineEventSchema).optional(),
  notes: z.array(z.string()).optional(),
});

const runNodeRecordSchema = z.object({
  alias: z.string(),
  node_id: z.string().nullable().optional(),
  status: z.enum(["ok", "skip", "fail", "unknown"]),
  duration_ms: z.number(),
  error_code: z.string().nullable().optional(),
  error_message: z.string().nullable().optional(),
  error_details: z.record(z.string(), z.unknown()).optional(),
  skip_reason: z.string().nullable().optional(),
  artifact_ids: z.array(z.string()).optional(),
  input_artifact_ids: z.array(z.string()).optional(),
  output_artifact_ids: z.array(z.string()).optional(),
});

const runErrorViewSchema = z.object({
  source: z.enum(["manifest", "workflow_report", "trace", "runtime"]),
  code: z.string(),
  message: z.string(),
  node_alias: z.string().nullable().optional(),
  timestamp: z.string().nullable().optional(),
  details: z.record(z.string(), z.unknown()).optional(),
});

const governanceIssueSchema = z.record(z.string(), z.unknown()).and(
  z.object({
    code: z.string().optional(),
    severity: z.string().optional(),
    message: z.string().optional(),
    pass_id: z.string().optional(),
  }),
);

const governanceDebugViewSchema = z.object({
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  verdict: z.string().nullable().optional(),
  issues: z.array(governanceIssueSchema).optional(),
  issue_summary: z.record(z.string(), z.number()).nullable().optional(),
  notes: z.array(z.string()).optional(),
  report_ref: artifactRefSchema.nullable().optional(),
  report_kind: z.string().nullable().optional(),
  report_schema_version: z.string().nullable().optional(),
  links: z
    .record(z.string(), artifactRefSchema.nullable())
    .nullable()
    .optional(),
  legal_executed: z.boolean().nullable().optional(),
  transport_summary: z.record(z.string(), z.unknown()).nullable().optional(),
  validation_trace: z.record(z.string(), z.unknown()).nullable().optional(),
  contract_warnings: z.array(z.string()).optional(),
  decision_validity: z.record(z.string(), z.unknown()).nullable().optional(),
  normative_summary: z.record(z.string(), z.unknown()).nullable().optional(),
  normative_arbitration_result_ref: artifactRefSchema.nullable().optional(),
  fallback_from_decision_packet: z.boolean().optional(),
});

const nodeDebugViewSchema = z.object({
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  alias: z.string(),
  record: runNodeRecordSchema,
  timeline_events: z.array(runTimelineEventSchema).optional(),
  cache_hits: z.number().optional(),
  cache_stores: z.number().optional(),
  cache_bypasses: z.number().optional(),
  notes: z.array(z.string()).optional(),
});

const agentPipelineStepSchema = z.object({
  attempt: z.number(),
  agent: z.string(),
  action: z.string(),
  status: z.enum(["ok", "warn", "fail", "info"]).default("info"),
  timestamp: z.string().nullable().optional(),
  summary: z.string().nullable().optional(),
  details: z.record(z.string(), z.unknown()).optional(),
  prompt: z.string().nullable().optional(),
  response: z.string().nullable().optional(),
  model: z.string().nullable().optional(),
  provider: z.string().nullable().optional(),
  model_variant_id: z.string().nullable().optional(),
  latency_ms: z.number().nullable().optional(),
  cost_usd: z.number().nullable().optional(),
  token_usage: z.record(z.string(), z.number()).optional(),
});

const agentPipelineAttemptSchema = z.object({
  attempt: z.number(),
  status: z.string(),
  verdict: z.string().nullable().optional(),
  started_at: z.string().nullable().optional(),
  finished_at: z.string().nullable().optional(),
  duration_ms: z.number().nullable().optional(),
  steps: z.array(agentPipelineStepSchema).optional(),
  notes: z.array(z.string()).optional(),
});

const retrievalPhaseTelemetrySchema = z.object({
  phase: z.string(),
  lane: z.string().nullable().optional(),
  duration_ms: z.number().optional(),
  candidates_total: z.number().optional(),
  candidates_selected: z.number().optional(),
  docs_fetched: z.number().optional(),
});

const retrievalTelemetryViewSchema = z.object({
  mode: z.string().optional(),
  lane_used: z.string().optional(),
  metadata_docs_fetched: z.number().optional(),
  local_index_size_bytes: z.number().optional(),
  local_index_docs_total: z.number().optional(),
  candidates_filtered: z.number().optional(),
  candidates_promoted: z.number().optional(),
  phases: z.array(retrievalPhaseTelemetrySchema).optional(),
  notes: z.array(z.string()).optional(),
});

const preflightDiagnosticViewSchema = z.object({
  code: z.string(),
  severity: z.string().optional(),
  message: z.string(),
  path: z.array(z.string()).optional(),
  replanning_hints: z.array(z.string()).optional(),
  data: z.record(z.string(), z.unknown()).optional(),
});

const preflightReportViewSchema = z.object({
  ready_to_run: z.boolean().optional(),
  diagnostics: z.array(preflightDiagnosticViewSchema).optional(),
  notes: z.array(z.string()).optional(),
  report_ref: artifactRefSchema.nullable().optional(),
});

const evaluatorScoresViewSchema = z.object({
  kpi_score: z.number().optional(),
  uncertainty_score: z.number().optional(),
  constraints_score: z.number().optional(),
  data_quality_score: z.number().optional(),
  budget_score: z.number().optional(),
  total_score: z.number().optional(),
});

const evaluatorReportViewSchema = z.object({
  verdict: z.string().nullable().optional(),
  scores: evaluatorScoresViewSchema.optional(),
  reasons: z.array(z.string()).optional(),
  replanning_hints: z.array(z.string()).optional(),
  diagnostics: z.array(preflightDiagnosticViewSchema).optional(),
  notes: z.array(z.string()).optional(),
  report_ref: artifactRefSchema.nullable().optional(),
});

const iterationLifecycleViewSchema = z.object({
  iteration: z.number().optional(),
  state: z.string().optional(),
  stop_reason: z.string().nullable().optional(),
  last_verdict: z.string().nullable().optional(),
  state_ref: artifactRefSchema.nullable().optional(),
  notes: z.array(z.string()).optional(),
});

const reproducibilityViewSchema = z.object({
  seed: z.number().optional(),
  seed_source: z.string().nullable().optional(),
  determinism_tier: z.string().nullable().optional(),
  plan_hash: z.string().nullable().optional(),
  registry_hash: z.string().nullable().optional(),
  method_catalog_hash: z.string().nullable().optional(),
  data_snapshot_hash: z.string().nullable().optional(),
  input_bindings_hash: z.string().nullable().optional(),
  readiness: z.string().nullable().optional(),
  why_partial: z.array(z.string()).optional(),
  missing_refs: z.array(z.string()).optional(),
  suggested_next_step: z.string().nullable().optional(),
  manifest_ref: artifactRefSchema.nullable().optional(),
  notes: z.array(z.string()).optional(),
});

const performancePhaseBudgetSchema = z.object({
  budget_ms: z.number().nullable().optional(),
  category: z.string().optional(),
  duration_ms: z.number().optional(),
  over_by_ms: z.number().optional(),
  phase: z.string(),
  status: z.string().optional(),
});

const runPerformanceSummarySchema = z
  .object({
    budget_summary: z.record(z.string(), z.unknown()).optional(),
    llm: z.record(z.string(), z.unknown()).optional(),
    phase_budgets: z.array(performancePhaseBudgetSchema).optional(),
    retrieval_phase_durations: z.record(z.string(), z.unknown()).optional(),
    schema_version: z.string().optional(),
    steps_by_action: z.record(z.string(), z.unknown()).optional(),
    variant_rows: z.array(z.record(z.string(), z.unknown())).optional(),
    variants: z.record(z.string(), z.unknown()).optional(),
  })
  .loose();

const agentPipelineViewSchema = z.object({
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  total_attempts: z.number(),
  latest_verdict: z.string().nullable().optional(),
  attempts: z.array(agentPipelineAttemptSchema).optional(),
  decision_packet_ref: artifactRefSchema.nullable().optional(),
  reflexion_terminal_ref: artifactRefSchema.nullable().optional(),
  retrieval: retrievalTelemetryViewSchema.nullable().optional(),
  execution_plan_ref: artifactRefSchema.nullable().optional(),
  method_catalog_snapshot_ref: artifactRefSchema.nullable().optional(),
  preflight: preflightReportViewSchema.nullable().optional(),
  evaluator: evaluatorReportViewSchema.nullable().optional(),
  iteration_lifecycle: iterationLifecycleViewSchema.nullable().optional(),
  reproducibility: reproducibilityViewSchema.nullable().optional(),
  performance_summary: runPerformanceSummarySchema.nullable().optional(),
  source: z.string().nullable().optional(),
  notes: z.array(z.string()).optional(),
});

const runWorkflowEdgeViewSchema = z.object({
  from_alias: z.string(),
  to_alias: z.string(),
});

const runWorkflowNodeViewSchema = z.object({
  alias: z.string(),
  node_id: z.string().nullable().optional(),
  depends_on: z.array(z.string()).optional(),
  depth: z.number(),
  status: z.enum(["ok", "skip", "fail", "unknown"]),
  duration_ms: z.number(),
  error_code: z.string().nullable().optional(),
  error_message: z.string().nullable().optional(),
  artifact_ids: z.array(z.string()).optional(),
  input_artifact_ids: z.array(z.string()).optional(),
  output_artifact_ids: z.array(z.string()).optional(),
  heat: z.number().optional(),
});

const runWorkflowSummarySchema = z.object({
  workflow_id: z.string().nullable().optional(),
  error_policy: z.string().nullable().optional(),
  status: z.string().nullable().optional(),
  node_count: z.number(),
  edge_count: z.number(),
  ok_count: z.number(),
  skip_count: z.number(),
  fail_count: z.number(),
  max_depth: z.number(),
  critical_path_duration_ms: z.number().nullable().optional(),
});

const runWorkflowViewSchema = z.object({
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  summary: runWorkflowSummarySchema,
  nodes: z.array(runWorkflowNodeViewSchema).optional(),
  edges: z.array(runWorkflowEdgeViewSchema).optional(),
  workflow_spec_ref: artifactRefSchema.nullable().optional(),
  workflow_report_ref: artifactRefSchema.nullable().optional(),
  notes: z.array(z.string()).optional(),
});

const artifactLineageNodeSchema = z.object({
  artifact_id: z.string(),
  role: z.string().nullable().optional(),
  kind: z.string().nullable().optional(),
  status: z.string(),
  byte_size: z.number(),
  depth: z.number(),
});

const artifactLineageEdgeSchema = z.object({
  parent_artifact_id: z.string(),
  child_artifact_id: z.string(),
  role: z.string(),
});

const artifactLineageViewSchema = z.object({
  root_artifact_ids: z.array(z.string()).optional(),
  total_nodes: z.number(),
  total_edges: z.number(),
  total_size_bytes: z.number(),
  is_complete: z.boolean(),
  missing_artifact_ids: z.array(z.string()).optional(),
  corrupted_artifact_ids: z.array(z.string()).optional(),
  nodes: z.array(artifactLineageNodeSchema).optional(),
  edges: z.array(artifactLineageEdgeSchema).optional(),
});

const lineageCompactSummaryItemSchema = z.object({
  kind: z.enum([
    "source",
    "transform",
    "model",
    "agent",
    "result",
    "artifact",
    "dataset",
    "method",
    "unknown",
  ]),
  label: z.string(),
  id: z.string().nullable().optional(),
});

const lineageGraphNodeSchema = z.object({
  id: z.string(),
  kind: z.string(),
  label: z.string(),
  timestamp: z.string().nullable().optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

const lineageGraphEdgeSchema = z.object({
  source_id: z.string(),
  target_id: z.string(),
  relation: z.string(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

const lineageExportLinksSchema = z.object({
  openlineage: z.string(),
  prov: z.string(),
});

const verificationMetadataSchema = z.object({
  hash: z.string().nullable().optional(),
  verification_status: z.enum(["verified", "pending", "disputed", "untraced"]),
  verified_by: z.string().nullable().optional(),
  verified_at: z.string().nullable().optional(),
  verification_method: z.string().nullable().optional(),
  freshness: z.enum(["current", "stale", "unknown"]),
  dispute_status: z.enum(["none", "disputed", "under_review", "resolved"]),
  temporal_scope: temporalScopeSchema,
});

export const lineageGraphViewSchema = z.object({
  id: z.string(),
  status: z.enum(["verified", "pending", "disputed", "untraced"]),
  hash: z.string().nullable().optional(),
  freshness: z.enum(["current", "stale", "unknown"]),
  compact_summary: z.array(lineageCompactSummaryItemSchema).optional(),
  nodes: z.array(lineageGraphNodeSchema).optional(),
  edges: z.array(lineageGraphEdgeSchema).optional(),
  exports: lineageExportLinksSchema,
  metadata: z.record(z.string(), z.unknown()).optional(),
  trust_metadata: verificationMetadataSchema.nullable().optional(),
});

const unitRefSchema = z.object({
  code: z.string(),
  system: z.string(),
  display: z.string().nullable().optional(),
});

const lineageRefSchema = z.object({
  id: z.string(),
  hash: z.string().nullable().optional(),
  status: z.enum(["verified", "pending", "disputed", "untraced"]),
  freshness: z.enum(["current", "stale", "unknown"]),
  summary: z.record(z.string(), z.string()).optional(),
  compact_summary: z.array(lineageCompactSummaryItemSchema).optional(),
  reason_code: z.string().nullable().optional(),
  tracking_issue: z.string().nullable().optional(),
  trust_metadata: verificationMetadataSchema.nullable().optional(),
});

const quantityUncertaintySchema = z.object({
  ci_80: z.tuple([z.number(), z.number()]).nullable().optional(),
  ci_95: z.tuple([z.number(), z.number()]).nullable().optional(),
  quantiles: z.record(z.string(), z.number()).optional(),
  method: z.string().nullable().optional(),
  identifiability: z.enum(["identified", "estimated", "assumed", "unknown"]),
  disputed: z.boolean(),
}) satisfies z.ZodType<QuantityUncertainty>;

export const quantityValueSchema = z.object({
  point: z.number().nullable().optional(),
  unit: unitRefSchema,
  metric_id: z.string().nullable().optional(),
  lineage: lineageRefSchema,
  uncertainty: quantityUncertaintySchema.nullable().optional(),
  time: temporalScopeSchema,
  quantity_class: z.enum(["decision", "telemetry", "layout", "debug"]),
  label: z.string().nullable().optional(),
}) satisfies z.ZodType<QuantityValueOutput>;

const comparabilityReportSchema = z.object({
  status: z.enum(["compatible", "warning", "blocked"]),
  warnings: z.array(z.string()).optional(),
  blocked_reasons: z.array(z.string()).optional(),
});

const lineageDeltaSchema = z.object({
  source_changed: z.boolean(),
  model_changed: z.boolean(),
  hash_changed: z.boolean(),
  freshness_changed: z.boolean(),
  verification_changed: z.string().nullable().optional(),
  notes: z.array(z.string()).optional(),
});

const deltaDistributionSchema = z.object({
  quantiles: z.record(z.string(), z.number()).optional(),
  mean_shift: z.number().nullable().optional(),
  median_shift: z.number().nullable().optional(),
  ci_overlap: z.boolean().nullable().optional(),
});

const deltaQuantitySchema = z.object({
  metric_id: z.string(),
  label: z.string(),
  a: quantityValueSchema.nullable().optional(),
  b: quantityValueSchema.nullable().optional(),
  delta_absolute: quantityValueSchema.nullable().optional(),
  delta_relative: quantityValueSchema.nullable().optional(),
  delta_distribution: deltaDistributionSchema.optional(),
  significance: z.enum([
    "improved",
    "worsened",
    "mixed",
    "uncertain",
    "not_comparable",
  ]),
  dominance: z.enum(["a", "b", "none", "mixed", "unknown"]),
  decision_salience: z.number(),
  lineage_delta: lineageDeltaSchema,
});

const comparisonFrameSchema = z.object({
  run_a: z.string(),
  run_b: z.string(),
  metric_set: z.array(z.string()).optional(),
  population: z.string().nullable().optional(),
  unit_policy: z.enum(["canonical", "source", "mixed"]),
  temporal_scope: temporalScopeSchema,
  scenario_scope: z.record(z.string(), z.unknown()).optional(),
  assumption_set: z.array(z.string()).optional(),
});

const compareCandidateSchema = z.object({
  run_id: z.string(),
  label: z.string().nullable().optional(),
  relation: z
    .enum(["baseline", "previous", "selected", "recommended"])
    .default("recommended"),
  status: z.string().nullable().optional(),
  started_at: z.string().nullable().optional(),
  finished_at: z.string().nullable().optional(),
  comparability: comparabilityReportSchema,
});

const scenarioStatusSchema = z.enum(["draft", "computed", "stale", "failed"]);
const scenarioLifecycleStatusSchema = z.enum([
  "generated",
  "draft",
  "saved",
  "promoted",
]);

export const scenarioConstraintSchema = z.object({
  id: z.string(),
  label: z.string(),
  field: z.string().nullable().optional(),
  severity: z.enum(["error", "warning"]),
  operator: z.string().nullable().optional(),
  value: quantityValueSchema.nullable().optional(),
  message: z.string().nullable().optional(),
});

export const scenarioAssumptionSchema = z.object({
  id: z.string(),
  label: z.string(),
  status: z.enum([
    "operator_assumption",
    "model_assumption",
    "observed_evidence",
    "disputed",
  ]),
  lineage: lineageRefSchema,
  description: z.string().nullable().optional(),
});

export const scenarioInterventionSchema = z.object({
  field: z.string(),
  operator: z.enum(["set", "add", "multiply", "remove"]),
  value: quantityValueSchema,
  baseline_value: quantityValueSchema.nullable().optional(),
  constraint_ids: z.array(z.string()).optional(),
});

export const scenarioRefSchema = z.object({
  id: z.string(),
  status: scenarioStatusSchema,
  baseline_run_id: z.string(),
  temporal_scope: temporalScopeSchema,
  lineage: lineageRefSchema,
  assumption_ids: z.array(z.string()),
  manifest_hash: z.string().nullable().optional(),
});

export const scenarioManifestSchema = z.object({
  id: z.string(),
  baseline_run_id: z.string(),
  status: scenarioStatusSchema,
  lifecycle_status: scenarioLifecycleStatusSchema.optional(),
  revision: z.number().optional(),
  manifest_hash: z.string().optional(),
  temporal_scope: temporalScopeSchema,
  policy_question: z.string(),
  author: z.string(),
  affected_population: z.string().nullable().optional(),
  temporal_window: temporalRangeSchema.nullable().optional(),
  model_family: z.string(),
  model_version: z.string().nullable().optional(),
  model_lineage: lineageRefSchema,
  baseline_lineage: lineageRefSchema.nullable().optional(),
  baseline_hash: z.string().nullable().optional(),
  computed_at: z.string().nullable().optional(),
  saved_at: z.string().nullable().optional(),
  promoted_at: z.string().nullable().optional(),
  validity_window: temporalRangeSchema.nullable().optional(),
  known_limitations: z.array(z.string()).optional(),
  stale_reasons: z.array(z.string()).optional(),
  interventions: z.array(scenarioInterventionSchema),
  assumptions: z.array(scenarioAssumptionSchema),
  constraints: z.array(scenarioConstraintSchema).optional(),
});

export const scenarioCapabilitySchema = z.object({
  surface: z.string(),
  supported: z.boolean(),
  reason_code: z.string().nullable().optional(),
  metric_id: z.string().nullable().optional(),
  supported_modes: z
    .array(z.enum(["actual", "actual_vs_scenario", "scenario_only"]))
    .optional(),
  limitations: z.array(z.string()).optional(),
});

export const counterfactualMetricSchema = z.object({
  metric_id: z.string(),
  label: z.string(),
  actual: quantityValueSchema,
  counterfactual: quantityValueSchema,
  delta: quantityValueSchema,
  scenario_ref: scenarioRefSchema,
  assumption_ids: z.array(z.string()),
});

const runEvidenceNeedSchema = z.object({
  need_id: z.string(),
  metric: z.string(),
  geography: z.string().nullable().optional(),
  time_start: z.string().nullable().optional(),
  time_end: z.string().nullable().optional(),
  granularity: z.string().optional(),
  quality_min: z.number().optional(),
  purpose: z.string().optional(),
  matched_plan_ids: z.array(z.string()).optional(),
  notes: z.array(z.string()).optional(),
});

const runEvidencePlanSchema = z.object({
  plan_id: z.string(),
  metric_id: z.string(),
  connector_id: z.string(),
  dataset_id: z.string(),
  profile_id: z.string().nullable().optional(),
  source_lane: z.string().optional(),
  quality_min: z.number().optional(),
  filters: z.record(z.string(), z.array(z.string())).optional(),
  date_start: z.string().nullable().optional(),
  date_end: z.string().nullable().optional(),
  granularity: z.string().nullable().optional(),
  fallback_count: z.number().optional(),
  matched_need_ids: z.array(z.string()).optional(),
  notes: z.array(z.string()).optional(),
});

const runEvidencePromotionSchema = z.object({
  promotion_id: z.string(),
  metric_id: z.string(),
  connector_id: z.string(),
  dataset_id: z.string(),
  profile_id: z.string().nullable().optional(),
  source_lane: z.string().optional(),
  confidence: z.number().optional(),
  status: z.string().optional(),
  created_at: z.string().nullable().optional(),
  signals: z.array(z.string()).optional(),
  matched_plan_id: z.string().nullable().optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

const runEvidenceContextViewSchema = z.object({
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  execution_plan_ref: artifactRefSchema.nullable().optional(),
  evidence_bundle_ref: artifactRefSchema.nullable().optional(),
  data_snapshot_ref: artifactRefSchema.nullable().optional(),
  input_bindings_ref: artifactRefSchema.nullable().optional(),
  related_artifacts: z.array(artifactRefSchema).optional(),
  data_needs: z.array(runEvidenceNeedSchema).optional(),
  fetch_plans: z.array(runEvidencePlanSchema).optional(),
  promotion_candidates: z.array(runEvidencePromotionSchema).optional(),
  warnings: z.array(z.string()).optional(),
});

const lexSearchResultItemSchema = z.object({
  fact_id: z.string(),
  subject_name: z.string(),
  predicate: z.string(),
  object_name: z.string(),
  fact_text: z.string(),
  confidence: z.number(),
  norm_type: z.string(),
  action_canon: z.string().default(""),
  norm_type_canon: z.string().default(""),
  condition_text_uk: z.string().default(""),
  exception_text_uk: z.string().default(""),
  procedure_text_uk: z.string().default(""),
  thresholds_json: z.string().default(""),
  source_quote_uk: z.string().default(""),
  doc_name: z.string(),
  doc_reestr_code: z.string().default(""),
  provision_citation: z.string().default(""),
});

const artifactManifestViewSchema = z.object({
  artifact_id: z.string(),
  kind: z.string(),
  media_type: z.string(),
  byte_size: z.number(),
  created_at: z.string(),
  schema_name: z.string().nullable().optional(),
  schema_version: z.string().nullable().optional(),
  producer_component: z.string().nullable().optional(),
  producer_version: z.string().nullable().optional(),
  inputs: z
    .array(z.object({ artifact_id: z.string(), role: z.string() }))
    .optional(),
  integrity_sha256: z.string(),
});

const decisionPacketOutlineEntrySchema = z.object({
  section_id: z.string(),
  title: z.string(),
  section_type: z.string().nullable().optional(),
});

const decisionPacketEffectSizeSchema = z.object({
  point: z.number().nullable().optional(),
  ci_80: z.tuple([z.number(), z.number()]).nullable().optional(),
  ci_95: z.tuple([z.number(), z.number()]).nullable().optional(),
  quantiles: z.record(z.string(), z.number()).nullable().optional(),
  identifiability: z
    .enum(["identified", "estimated", "assumed"])
    .nullable()
    .optional(),
  disputed: z.boolean().nullable().optional(),
  method: z.string().nullable().optional(),
});

const decisionPacketMetricSignificanceSchema = z.object({
  baseline_model_id: z.string().nullable().optional(),
  candidate_model_id: z.string().nullable().optional(),
  metric_direction: z.string().nullable().optional(),
  baseline_value: z.number().nullable().optional(),
  candidate_value: z.number().nullable().optional(),
  delta_value: z.number().nullable().optional(),
  test_id: z.string().nullable().optional(),
  test_label: z.string().nullable().optional(),
  p_value: z.number().nullable().optional(),
  p_adj: z.number().nullable().optional(),
  alpha: z.number().nullable().optional(),
  significant: z.boolean().nullable().optional(),
  effect_size: decisionPacketEffectSizeSchema.nullable().optional(),
  assumption_warnings: z.array(z.string()).optional(),
  calibration_warnings: z.array(z.string()).optional(),
});

const decisionPacketMetricComparisonRowSchema = z.object({
  metric_id: z.string(),
  metric_direction: z.string().nullable().optional(),
  baseline_model_id: z.string().nullable().optional(),
  candidate_model_id: z.string().nullable().optional(),
  baseline_value: z.number().nullable().optional(),
  candidate_value: z.number().nullable().optional(),
  delta_value: z.number().nullable().optional(),
  family_id: z.string().nullable().optional(),
  family_scope: z.string().nullable().optional(),
  sample_size_effective: z.number().int().nullable().optional(),
  resampling_method: z.string().nullable().optional(),
  test_id: z.string().nullable().optional(),
  test_label: z.string().nullable().optional(),
  statistic: z.number().nullable().optional(),
  effect_size: decisionPacketEffectSizeSchema.nullable().optional(),
  p_value: z.number().nullable().optional(),
  p_adj: z.number().nullable().optional(),
  alpha: z.number().nullable().optional(),
  significant: z.boolean().nullable().optional(),
  assumption_warnings: z.array(z.string()).optional(),
  calibration_warnings: z.array(z.string()).optional(),
});

const decisionPacketAuthoredBlockSchema = z.object({
  id: z.string().nullable().optional(),
  content: z.string(),
  author: z
    .enum(["citation", "human", "drafter", "formalizer", "critic"])
    .nullable()
    .optional(),
  author_agent_version: z.string().nullable().optional(),
  sources: z.array(z.object({ kind: z.string(), ref: z.string() })).optional(),
  timestamp: z.string().nullable().optional(),
  confidence: z.number().nullable().optional(),
  reviewed_by_human: z.boolean().nullable().optional(),
});

const decisionPacketPreviewSchema = z
  .object({
    document_outline: z.array(decisionPacketOutlineEntrySchema).optional(),
    metric_significance_by_metric: z
      .record(z.string(), decisionPacketMetricSignificanceSchema)
      .optional(),
    metric_validation_comparison_rows: z
      .array(decisionPacketMetricComparisonRowSchema)
      .optional(),
    blocks: z.array(decisionPacketAuthoredBlockSchema).optional(),
    narrative_blocks: z.array(decisionPacketAuthoredBlockSchema).optional(),
    evidence_summary_blocks: z
      .array(decisionPacketAuthoredBlockSchema)
      .optional(),
  })
  .loose();

const artifactContentPreviewSchema = z.object({
  artifact_id: z.string(),
  kind: z.string(),
  media_type: z.string(),
  mode: z.enum(["json", "text", "binary"]),
  size_bytes: z.number(),
  max_bytes: z.number(),
  truncated: z.boolean(),
  preview: z.unknown().optional(),
  decision_packet_preview: decisionPacketPreviewSchema.nullable().optional(),
});

const artifactSchemaViewSchema = z.object({
  artifact_id: z.string(),
  kind: z.string(),
  media_type: z.string(),
  schema_name: z.string().nullable().optional(),
  schema_version: z.string().nullable().optional(),
  top_level_keys: z.array(z.string()).optional(),
});

const bureaucraticGenreSchema = z.enum([
  "postanova_kmu",
  "zakonoproekt",
  "expert_vysnovok",
  "analitichna_zapyska",
]);

const bureaucraticTemplateRefSchema = z.object({
  id: z.string(),
  version: z.string(),
  genre: bureaucraticGenreSchema,
  jurisdiction: z.string(),
  locale: z.string(),
  legal_review_status: z.enum([
    "pending_external_review",
    "approved",
    "rejected",
  ]),
});

const bureaucraticAuthorshipSchema = z.object({
  author: z.string(),
  author_role: z.string(),
  agent_version: z.string().nullable().optional(),
  timestamp: z.string().nullable().optional(),
  reviewed_by_human: z.boolean(),
});

const bureaucraticBlockSchema: z.ZodType = z.lazy(() =>
  z.object({
    id: z.string(),
    kind: z.enum([
      "header",
      "requisites",
      "preamble",
      "legal_basis",
      "section",
      "article",
      "clause",
      "subclause",
      "paragraph",
      "list",
      "table",
      "quantity",
      "annex",
      "signature",
      "appendix",
    ]),
    title: z.string().nullable().optional(),
    text: z.string().nullable().optional(),
    level: z.number(),
    number: z.string().nullable().optional(),
    items: z.array(z.string()).optional(),
    quantity: quantityValueSchema.nullable().optional(),
    epistemic_origin: z.enum([
      "evidence_filled",
      "model_generated",
      "operator_filled",
      "imported",
    ]),
    authorship: bureaucraticAuthorshipSchema,
    provenance: z.array(lineageCompactSummaryItemSchema).optional(),
    raw_source_refs: z.array(z.string()).optional(),
    children: z.array(bureaucraticBlockSchema).optional(),
    metadata: z.record(z.string(), z.unknown()).optional(),
  }),
);

export const bureaucraticDocumentSchema = z.object({
  id: z.string(),
  packet_id: z.string(),
  genre: bureaucraticGenreSchema,
  jurisdiction: z.string(),
  template: bureaucraticTemplateRefSchema,
  status: z.enum(["draft", "signed_external", "archived"]),
  title: z.string(),
  language: z.string(),
  watermark: z.string(),
  render_timestamp: z.string(),
  packet_hash: z.string(),
  temporal_scope: temporalScopeSchema,
  trust_view: z.boolean(),
  blocks: z.array(bureaucraticBlockSchema),
  annexes: z.array(bureaucraticBlockSchema),
  epistemic_summary: z.object({
    evidence_filled: z.number(),
    model_generated: z.number(),
    operator_filled: z.number(),
    imported: z.number(),
  }),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

type CapabilityFeaturePayload = components["schemas"]["CapabilityFeatureInfo"];
export type CapabilityManifestPayload =
  components["schemas"]["CapabilityManifestResponse"];

const capabilityFeatureSchema = z.object({
  key: z.string(),
  label: z.string(),
  description: z.string(),
  category: z.string(),
  enabled: z.boolean().default(true),
  stage: z.enum(["active", "planned", "deferred"]).default("active"),
});

const authMeSchemaInternal = z.object({
  meta: apiMetaSchema,
  user_id: z.string(),
  display_name: z.string(),
  tenant_id: z.string(),
  principal_type: z.enum(["anonymous", "service", "user"]).default("user"),
  cell_id: z.string().nullable().optional(),
  roles: z.array(z.string()).default([]),
  permissions: z.array(z.string()).default([]),
  mfa_verified: z.boolean().default(false),
  feature_overrides: z.record(z.string(), z.boolean()).default({}),
});

export const capabilityManifestSchema = z.object({
  meta: apiMetaSchema,
  runtime_api_version: z.string().default("1.0.0"),
  shell_flavor: z.string().default("atlas"),
  default_execution_profile: z
    .enum(["dev", "research", "governed", "production"])
    .default("dev"),
  default_locale: z.enum(["en", "uk"]).default("en"),
  supported_execution_profiles: z
    .array(z.enum(["dev", "research", "governed", "production"]))
    .default(["dev", "research", "governed", "production"]),
  supported_locales: z.array(z.enum(["en", "uk"])).default(["en", "uk"]),
  state_store_backend: z.string().default("sqlite"),
  worker_backend: z.string().default("embedded"),
  workspaces: z.array(z.string()).default([]),
  features: z.array(capabilityFeatureSchema).default([]),
  constraints: z.record(z.string(), z.unknown()).default({}),
});

export const authMeSchema = authMeSchemaInternal;

export const healthSchema = z
  .object({
    meta: apiMetaSchema.nullish(),
    status: z.string().optional(),
    service: z.string().optional(),
    ts: z.string().optional(),
  })
  .catchall(
    z.union([
      z.string(),
      z.number(),
      z.boolean(),
      z.null(),
      z.array(z.unknown()),
      z.record(z.string(), z.unknown()),
    ]),
  );

export const runsListSchema = z.object({
  meta: apiMetaSchema,
  page: cursorPageSchema,
  runs: z.array(runSummarySchema).optional(),
});

export const runDetailsSchema = z.object({
  meta: apiMetaSchema,
  temporal_scope: temporalScopeSchema,
  run: runDetailsSchemaInner,
});

export const runTimelineSchema = z.object({
  meta: apiMetaSchema,
  temporal_scope: temporalScopeSchema,
  timeline: runTimelineViewSchema,
});

export const runNodesSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  nodes: z.array(runNodeRecordSchema).optional(),
});

export const runLineageSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  temporal_scope: temporalScopeSchema,
  lineage: artifactLineageViewSchema,
});

export const runQuantitiesSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  temporal_scope: temporalScopeSchema,
  quantities: z.array(quantityValueSchema).optional(),
  coverage: z
    .object({
      total: z.number(),
      decision: z.number(),
      telemetry: z.number(),
      layout: z.number(),
      debug: z.number(),
      traced: z.number(),
      untraced: z.number(),
    })
    .optional(),
  entries: z.array(z.record(z.string(), z.unknown())).optional(),
});

const fabricQualityRefSchema = z.object({
  status: z.enum(["passed", "warning", "failed", "unknown_quality"]),
  score: z.number().nullable().optional(),
  report_ref: z.string().nullable().optional(),
  reason_code: z.string().nullable().optional(),
  quality_surface: z.string().nullable().optional(),
  remediation_link: z.string().nullable().optional(),
});

const fabricAccessRefSchema = z.object({
  classification: z.string(),
  pii_tier: z.string(),
  tenant_scope: z.string(),
  redaction: z.enum(["none", "masked", "redacted", "aggregate_only", "denied"]),
  policy_ref: z.string().nullable().optional(),
});

const fabricLineageRefSchema = z.object({
  id: z.string(),
  status: z.enum(["verified", "pending", "disputed", "untraced"]),
  hash: z.string().nullable().optional(),
  compact_summary_ref: z.string().nullable().optional(),
  full_graph_ref: z.string().nullable().optional(),
  raw_evidence_refs: z.array(z.string()).optional(),
  export_links: z.record(z.string(), z.string()).optional(),
  reason_code: z.string().nullable().optional(),
  owner: z.string().nullable().optional(),
  tracking_issue: z.string().nullable().optional(),
});

const fabricReplayRefSchema = z.object({
  status: z.enum(["replayable", "non_replayable", "unknown"]),
  manifest_ref: z.string().nullable().optional(),
  reason_code: z.string().nullable().optional(),
  source_reason: z.string().nullable().optional(),
  retention_alternative: z.string().nullable().optional(),
});

const fabricTypedGapSchema = z.object({
  status: z.enum([
    "untraced",
    "unknown_quality",
    "restricted",
    "non_replayable",
    "unsupported_temporal_scope",
  ]),
  reason_code: z.string().nullable().optional(),
  owner: z.string().nullable().optional(),
  quality_surface: z.string().nullable().optional(),
  remediation_link: z.string().nullable().optional(),
  access_policy: z.string().nullable().optional(),
  redaction_behavior: z.string().nullable().optional(),
  source_reason: z.string().nullable().optional(),
  retention_alternative: z.string().nullable().optional(),
  capability_endpoint: z.string().nullable().optional(),
});

const fabricDecisionDataSchema = z.object({
  id: z.string(),
  kind: z.enum(["quantity", "authored_text", "fact", "event", "claim"]),
  value: z.record(z.string(), z.unknown()),
  source_contract: z.object({
    id: z.string(),
    version: z.string(),
  }),
  quality: fabricQualityRefSchema,
  lineage: fabricLineageRefSchema,
  access: fabricAccessRefSchema,
  time: temporalRefSchema,
  replay: fabricReplayRefSchema,
  gaps: z.array(fabricTypedGapSchema).optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

export const runFabricDecisionDataSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  temporal_scope: temporalScopeSchema,
  decision_data: z.array(fabricDecisionDataSchema).optional(),
  coverage: z
    .object({
      total: z.number(),
      decision: z.number(),
      telemetry: z.number(),
      layout: z.number(),
      debug: z.number(),
      traced: z.number(),
      untraced: z.number(),
      naked_decision_values: z.number(),
      transitional_waivers: z.number(),
    })
    .optional(),
});

export const fabricSourceScorecardsSchema = z.object({
  meta: apiMetaSchema,
  schema_version: z.string(),
  generated_at: z.string().nullable().optional(),
  count: z.number(),
  scorecards: z.record(z.string(), z.record(z.string(), z.unknown())),
});

export const fabricQualityBatchSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  temporal_scope: temporalScopeSchema,
  quality_refs: z.record(z.string(), fabricQualityRefSchema),
  coverage: z.record(z.string(), z.unknown()).optional(),
});

export const fabricTrustBatchSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  temporal_scope: temporalScopeSchema,
  trust_refs: z.record(
    z.string(),
    z.object({
      quality: fabricQualityRefSchema,
      access: fabricAccessRefSchema,
      lineage: fabricLineageRefSchema,
      replay: fabricReplayRefSchema,
      time: temporalScopeSchema,
      gaps: z.array(fabricTypedGapSchema).optional(),
    }),
  ),
  coverage: z.record(z.string(), z.unknown()).optional(),
});

export const fabricReplaySchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  temporal_scope: temporalScopeSchema,
  replay_refs: z.record(z.string(), fabricReplayRefSchema),
  status_counts: z.record(z.string(), z.number()),
  coverage: z.record(z.string(), z.unknown()).optional(),
});

const fabricImpactRecordSchema = z.object({
  subject_id: z.string(),
  subject_kind: z.enum(["lineage", "source_contract", "run", "decision_data"]),
  lineage_status: z.enum(["verified", "pending", "disputed", "untraced"]),
  quality_status: z.string().nullable().optional(),
  replay_status: z.string().nullable().optional(),
  downstream_refs: z.array(z.string()).optional(),
  upstream_refs: z.array(z.string()).optional(),
  affected_decision_data_ids: z.array(z.string()).optional(),
  source_contract_ids: z.array(z.string()).optional(),
  evidence_refs: z.array(z.string()).optional(),
  notes: z.array(z.string()).optional(),
});

export const fabricImpactAnalysisSchema = z.object({
  meta: apiMetaSchema,
  temporal_scope: temporalScopeSchema,
  impacts: z.array(fabricImpactRecordSchema).optional(),
  summary: z.record(z.string(), z.unknown()).optional(),
});

export const compareRunsSchema = z.object({
  meta: apiMetaSchema,
  status: z.enum(["computed", "client_computable"]),
  temporal_scope: temporalScopeSchema,
  comparison_frame: comparisonFrameSchema,
  comparability: comparabilityReportSchema,
  deltas: z.array(deltaQuantitySchema).optional(),
});

export const compareCandidatesSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  candidates: z.array(compareCandidateSchema).optional(),
});

export const temporalCapabilitiesSchema = z.object({
  meta: apiMetaSchema,
  capabilities: temporalCapabilitiesViewSchema,
});

export const scenarioListSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  temporal_scope: temporalScopeSchema,
  scenarios: z.array(scenarioManifestSchema).optional(),
});

export const scenarioManifestResponseSchema = z.object({
  meta: apiMetaSchema,
  temporal_scope: temporalScopeSchema,
  scenario: scenarioManifestSchema,
});

export const scenarioCapabilitiesSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string().nullable().optional(),
  scenario_id: z.string().nullable().optional(),
  temporal_scope: temporalScopeSchema,
  capabilities: z.array(scenarioCapabilitySchema).optional(),
});

export const counterfactualMetricsSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  temporal_scope: temporalScopeSchema,
  scenario: scenarioManifestSchema,
  metrics: z.record(z.string(), counterfactualMetricSchema).optional(),
});

export const runEvidenceContextSchema = z.object({
  meta: apiMetaSchema,
  context: runEvidenceContextViewSchema,
});

export const governanceDebugSchema = z.object({
  meta: apiMetaSchema,
  debug: governanceDebugViewSchema,
});

export const promotionCandidatesSchema = z.object({
  meta: apiMetaSchema,
  candidates: z.array(runEvidencePromotionSchema).default([]),
});

export const promotionDecisionResponseSchema = z.object({
  meta: apiMetaSchema,
  promotion_id: z.string(),
  status: z.enum(["approved", "rejected"]),
  message: z.string(),
  binding_updated: z.boolean().default(false),
});

export const lexSearchResponseSchema = z.object({
  meta: apiMetaSchema,
  query: z.string(),
  results: z.array(lexSearchResultItemSchema).default([]),
  total: z.number().default(0),
});

export const nodeDebugSchema = z.object({
  meta: apiMetaSchema,
  debug: nodeDebugViewSchema,
});

export const runErrorsSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  errors: z.array(runErrorViewSchema).optional(),
});

export const runAgentsSchema = z.object({
  meta: apiMetaSchema,
  pipeline: agentPipelineViewSchema,
});

export const runWorkflowSchema = z.object({
  meta: apiMetaSchema,
  workflow: runWorkflowViewSchema,
});

export const artifactManifestSchema = z.object({
  meta: apiMetaSchema,
  artifact: artifactManifestViewSchema,
});

export const artifactContentSchema = z.object({
  meta: apiMetaSchema,
  artifact: artifactContentPreviewSchema,
});

export const artifactSchemaSchema = z.object({
  meta: apiMetaSchema,
  schema: artifactSchemaViewSchema,
});

export const artifactLineageSchema = z.object({
  meta: apiMetaSchema,
  lineage: artifactLineageViewSchema,
});

export const bureaucraticRenderSchema = z.object({
  meta: apiMetaSchema,
  document: bureaucraticDocumentSchema,
});

export const bureaucraticExportSchema = z.object({
  meta: apiMetaSchema,
  document_id: z.string(),
  packet_id: z.string(),
  format: z.enum(["html", "pdf", "docx"]),
  content_type: z.string(),
  filename: z.string(),
  content: z.string(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

export const lineageResponseSchema = z.object({
  meta: apiMetaSchema,
  temporal_scope: temporalScopeSchema,
  lineage: lineageGraphViewSchema,
});

export const lineageBatchResponseSchema = z.object({
  meta: apiMetaSchema,
  temporal_scope: temporalScopeSchema,
  lineages: z.array(lineageGraphViewSchema).optional(),
});

export const lineageExportResponseSchema = z.object({
  meta: apiMetaSchema,
  temporal_scope: temporalScopeSchema,
  lineage_id: z.string(),
  format: z.enum(["openlineage", "prov"]),
  payload: z.record(z.string(), z.unknown()),
});

export type HealthPayload = z.infer<typeof healthSchema>;
export type AuthMePayload = z.infer<typeof authMeSchema>;
export type RunsListPayload = z.infer<typeof runsListSchema>;
export type RunDetailsPayload = z.infer<typeof runDetailsSchema>;
export type RunTimelinePayload = z.infer<typeof runTimelineSchema>;
export type RunNodesPayload = z.infer<typeof runNodesSchema>;
export type RunLineagePayload = z.infer<typeof runLineageSchema>;
export type RunQuantitiesPayload = z.infer<typeof runQuantitiesSchema>;
export type RunFabricDecisionDataPayload = z.infer<
  typeof runFabricDecisionDataSchema
>;
export type FabricSourceScorecardsPayload = z.infer<
  typeof fabricSourceScorecardsSchema
>;
export type FabricQualityBatchPayload = z.infer<
  typeof fabricQualityBatchSchema
>;
export type FabricTrustBatchPayload = z.infer<typeof fabricTrustBatchSchema>;
export type FabricReplayPayload = z.infer<typeof fabricReplaySchema>;
export type FabricImpactAnalysisPayload = z.infer<
  typeof fabricImpactAnalysisSchema
>;
export type CompareRunsPayload = z.infer<typeof compareRunsSchema>;
export type CompareCandidatesPayload = z.infer<typeof compareCandidatesSchema>;
export type TemporalCapabilitiesPayload = z.infer<
  typeof temporalCapabilitiesSchema
>;
export type ScenarioListPayload = z.infer<typeof scenarioListSchema>;
export type ScenarioManifestPayload = z.infer<
  typeof scenarioManifestResponseSchema
>;
export type ScenarioCapabilitiesPayload = z.infer<
  typeof scenarioCapabilitiesSchema
>;
export type CounterfactualMetricsPayload = z.infer<
  typeof counterfactualMetricsSchema
>;
export type RunEvidenceContextPayload = z.infer<
  typeof runEvidenceContextSchema
>;
export type GovernanceDebugPayload = z.infer<typeof governanceDebugSchema>;
export type PromotionCandidatesPayload = z.infer<
  typeof promotionCandidatesSchema
>;
export type PromotionDecisionResponsePayload = z.infer<
  typeof promotionDecisionResponseSchema
>;
export type LexSearchResponsePayload = z.infer<typeof lexSearchResponseSchema>;
export type NodeDebugPayload = z.infer<typeof nodeDebugSchema>;
export type RunErrorsPayload = z.infer<typeof runErrorsSchema>;
export type RunAgentsPayload = z.infer<typeof runAgentsSchema>;
export type RunWorkflowPayload = z.infer<typeof runWorkflowSchema>;
export type ArtifactManifestPayload = z.infer<typeof artifactManifestSchema>;
export type ArtifactContentPayload = z.infer<typeof artifactContentSchema>;
export type ArtifactSchemaPayload = z.infer<typeof artifactSchemaSchema>;
export type ArtifactLineagePayload = z.infer<typeof artifactLineageSchema>;
export type BureaucraticRenderPayload = z.infer<
  typeof bureaucraticRenderSchema
>;
export type BureaucraticExportPayload = z.infer<
  typeof bureaucraticExportSchema
>;
export type LineagePayload = z.infer<typeof lineageResponseSchema>;
export type LineageBatchPayload = z.infer<typeof lineageBatchResponseSchema>;
export type LineageExportPayload = z.infer<typeof lineageExportResponseSchema>;
