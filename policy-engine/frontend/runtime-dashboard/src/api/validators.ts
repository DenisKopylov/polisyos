import { z } from "zod";

const apiMetaSchema = z.object({
  request_id: z.string(),
  generated_at: z.string(),
  source_kinds: z.array(z.literal("core_run")).or(z.array(z.string())).default([]),
});

const cursorPageSchema = z.object({
  limit: z.number(),
  cursor: z.string().nullable().optional(),
  next_cursor: z.string().nullable().optional(),
  count: z.number(),
  total: z.number().nullable().optional(),
});

const artifactRefSchema = z.object({
  artifact_id: z.string(),
  kind: z.string().optional(),
  media_type: z.string().optional(),
});

const runSummarySchema = z.object({
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  status: z.string(),
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
  has_trace: z.boolean().optional(),
  has_workflow_report: z.boolean().optional(),
  manifest_ref: artifactRefSchema.nullable().optional(),
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
  metrics: z.record(z.number()).optional(),
  warning_count: z.number().optional(),
  error_count: z.number().optional(),
});

const runTimelineSummarySchema = z.object({
  run_id: z.string(),
  total_events: z.number(),
  duration_ms: z.number().nullable().optional(),
  node_status_counts: z.record(z.number()).optional(),
  phase_counts: z.record(z.number()).optional(),
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
  error_details: z.record(z.unknown()).optional(),
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
  details: z.record(z.unknown()).optional(),
});

const governanceIssueSchema = z.record(z.unknown()).and(
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
  notes: z.array(z.string()).optional(),
  report_ref: artifactRefSchema.nullable().optional(),
  validation_trace: z.record(z.unknown()).nullable().optional(),
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
  details: z.record(z.unknown()).optional(),
  prompt: z.string().nullable().optional(),
  response: z.string().nullable().optional(),
  model: z.string().nullable().optional(),
  provider: z.string().nullable().optional(),
  model_variant_id: z.string().nullable().optional(),
  latency_ms: z.number().nullable().optional(),
  cost_usd: z.number().nullable().optional(),
  token_usage: z.record(z.number()).optional(),
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
  data: z.record(z.unknown()).optional(),
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
  plan_hash: z.string().nullable().optional(),
  registry_hash: z.string().nullable().optional(),
  method_catalog_hash: z.string().nullable().optional(),
  data_snapshot_hash: z.string().nullable().optional(),
  input_bindings_hash: z.string().nullable().optional(),
  manifest_ref: artifactRefSchema.nullable().optional(),
  notes: z.array(z.string()).optional(),
});

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
  inputs: z.array(z.object({ artifact_id: z.string(), role: z.string() })).optional(),
  integrity_sha256: z.string(),
});

const artifactContentPreviewSchema = z.object({
  artifact_id: z.string(),
  kind: z.string(),
  media_type: z.string(),
  mode: z.enum(["json", "text", "binary"]),
  size_bytes: z.number(),
  max_bytes: z.number(),
  truncated: z.boolean(),
  preview: z.unknown().optional(),
});

const artifactSchemaViewSchema = z.object({
  artifact_id: z.string(),
  kind: z.string(),
  media_type: z.string(),
  schema_name: z.string().nullable().optional(),
  schema_version: z.string().nullable().optional(),
  top_level_keys: z.array(z.string()).optional(),
});

export const healthSchema = z.record(z.string());

export const runsListSchema = z.object({
  meta: apiMetaSchema,
  page: cursorPageSchema,
  runs: z.array(runSummarySchema).optional(),
});

export const runDetailsSchema = z.object({
  meta: apiMetaSchema,
  run: runDetailsSchemaInner,
});

export const runTimelineSchema = z.object({
  meta: apiMetaSchema,
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
  lineage: artifactLineageViewSchema,
});

export const governanceDebugSchema = z.object({
  meta: apiMetaSchema,
  debug: governanceDebugViewSchema,
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

export type HealthPayload = z.infer<typeof healthSchema>;
export type RunsListPayload = z.infer<typeof runsListSchema>;
export type RunDetailsPayload = z.infer<typeof runDetailsSchema>;
export type RunTimelinePayload = z.infer<typeof runTimelineSchema>;
export type RunNodesPayload = z.infer<typeof runNodesSchema>;
export type RunLineagePayload = z.infer<typeof runLineageSchema>;
export type GovernanceDebugPayload = z.infer<typeof governanceDebugSchema>;
export type NodeDebugPayload = z.infer<typeof nodeDebugSchema>;
export type RunErrorsPayload = z.infer<typeof runErrorsSchema>;
export type RunAgentsPayload = z.infer<typeof runAgentsSchema>;
export type RunWorkflowPayload = z.infer<typeof runWorkflowSchema>;
export type ArtifactManifestPayload = z.infer<typeof artifactManifestSchema>;
export type ArtifactContentPayload = z.infer<typeof artifactContentSchema>;
export type ArtifactSchemaPayload = z.infer<typeof artifactSchemaSchema>;
export type ArtifactLineagePayload = z.infer<typeof artifactLineageSchema>;
