// GENERATED FILE. DO NOT EDIT.
// Source: schemas/runtime_api_v1.openapi.json

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | { [key: string]: JsonValue }
  | JsonValue[];

export type AbsentFact = {
  availability: "not_established" | "artifact_missing" | "invalid_source";
  owner_route: string;
  reason: string;
};

export type AccessRef = {
  classification?: string;
  pii_tier?: string;
  policy_ref?: string | null;
  redaction?: "none" | "masked" | "redacted" | "aggregate_only" | "denied";
  tenant_scope?: string;
};

export type AcquisitionBacklogProjection = {
  authority_boundary: string;
  binding_confidence: number;
  classification_basis: "independently_reconciled" | "not_established";
  gap_class: GapClass;
  rank: number;
  ranking_method: string;
  ranking_score: number;
  route_demand: number;
  variable_id: string;
  voi_owner_fit: string;
  voi_owner_integration: string;
  voi_owner_ref: string;
};

export type AcquisitionDecisionRequestResponse = {
  authority_decision_ref: string;
  human_decision_request?: {
  [key: string]: unknown;
} | null;
  outcome: "decision_required" | "decision_available";
  route_id: string;
  run_id: string;
  world_growth?: string;
};

export type AcquisitionExecutionResponse = {
  authority_decision_ref: string;
  job_id: string;
  receipt_phase?: string;
  route_id: string;
  run_id: string;
  status?: string;
  world_growth?: string;
};

export type AcquisitionGrowthPayload = {
  backlog: Array<AcquisitionBacklogProjection>;
  carrier_liveness: {
  [key: string]: unknown;
};
  n13b_history: N13bHistoryProjection;
  schema_version?: string;
  structural_routes: Array<StructuralRouteProjection>;
  summary: AcquisitionGrowthSummary;
};

export type AcquisitionGrowthSummary = {
  actual_network_call_count: number;
  backlog_count: number;
  family_scorecard_count: number;
  metric_resolution_count: number;
  selected_record_count: number;
  structural_route_count: number;
};

export type AcquisitionRouteListResponse = {
  routes: Array<AcquisitionRouteProjection>;
  run_id: string;
};

export type AcquisitionRouteMutationRequest = {
  human_decision_record_ref?: string | null;
  idempotency_key: string;
  planner_report_hash: string;
  replay_pins: AcquisitionRouteReplayPins;
  route_projection_hash: string;
};

export type AcquisitionRouteProjection = {
  authority_badge?: string;
  authority_capability: "ready" | "producer_missing";
  cell_id: string;
  cost_basis: {
  [key: string]: unknown;
};
  execution_capability: "ready" | "producer_missing";
  external_nonclosures?: Array<string>;
  planner_record_id: string;
  planner_report_hash: string;
  qualification_predicate?: string;
  qualification_reason?: string;
  qualification_status?: string;
  recommended_strategy: string;
  replay_pins: AcquisitionRouteReplayPins;
  route_id: string;
  route_projection_hash: string;
  route_status?: string;
  run_id: string;
  schema_version?: string;
  tenant_id: string;
  world_growth?: string;
};

export type AcquisitionRouteReplayPins = {
  compiled_content_hash: string;
  compiled_ref: string;
  cost_basis_hash: string;
  design_problem_ref: string;
  source_job_id: string;
  terminal_event_id: string;
};

export type AcquisitionRoutingPayload = {
  compute_economics: {
  [key: string]: ProjectionJsonValue;
};
  denominators: {
  [key: string]: ProjectionJsonValue;
};
  fail_closed_probes: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  fail_closed_receipt: {
  [key: string]: ProjectionJsonValue;
};
  grounding_acquisition_request: {
  [key: string]: ProjectionJsonValue;
};
  known_residuals: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  no_result_receipt: {
  [key: string]: ProjectionJsonValue;
};
  positive_receipt: {
  [key: string]: ProjectionJsonValue;
};
  recorded_rederive_inputs: {
  [key: string]: ProjectionJsonValue;
};
};

export type AgentPipelineAttempt = {
  attempt: number;
  duration_ms?: number | null;
  finished_at?: string | null;
  notes?: Array<string>;
  started_at?: string | null;
  status?: string;
  steps?: Array<AgentPipelineStep>;
  verdict?: string | null;
};

export type AgentPipelineResponse = {
  meta: ApiMeta;
  pipeline: AgentPipelineView;
};

export type AgentPipelineStep = {
  action: string;
  agent: string;
  attempt?: number;
  cost_usd?: number | null;
  details?: {
  [key: string]: unknown;
};
  latency_ms?: number | null;
  model?: string | null;
  model_variant_id?: string | null;
  prompt?: string | null;
  provider?: string | null;
  response?: string | null;
  status?: "ok" | "warn" | "fail" | "info";
  summary?: string | null;
  timestamp?: string | null;
  token_usage?: {
  [key: string]: number;
};
};

export type AgentPipelineView = {
  attempts?: Array<AgentPipelineAttempt>;
  decision_packet_ref?: ArtifactRefOutput | null;
  evaluator?: EvaluatorReportView | null;
  execution_plan_ref?: ArtifactRefOutput | null;
  iteration_lifecycle?: IterationLifecycleView | null;
  latest_verdict?: string | null;
  method_catalog_snapshot_ref?: ArtifactRefOutput | null;
  notes?: Array<string>;
  performance_summary?: {
  [key: string]: unknown;
} | null;
  preflight?: PreflightReportView | null;
  reflexion_terminal_ref?: ArtifactRefOutput | null;
  reproducibility?: ReproducibilityView | null;
  retrieval?: RetrievalTelemetryView | null;
  run_id: string;
  source?: string | null;
  source_kind: string;
  total_attempts?: number;
};

export type ApiMeta = {
  generated_at?: string;
  request_id: string;
  source_kinds?: Array<string>;
};

export type AppointmentPosture = "institutional_authority_unappointed";

export type ArtifactBatchRequest = {
  artifact_ids?: Array<string>;
};

export type ArtifactBatchResponse = {
  artifacts?: Array<ArtifactManifestView>;
  meta: ApiMeta;
};

export type ArtifactContentPreview = {
  artifact_id: string;
  decision_packet_preview?: DecisionPacketPreview | null;
  kind: string;
  max_bytes: number;
  media_type: string;
  mode: "json" | "text" | "binary";
  preview?: unknown;
  size_bytes: number;
  truncated?: boolean;
};

export type ArtifactContentResponse = {
  artifact: ArtifactContentPreview;
  meta: ApiMeta;
};

export type ArtifactID = string;

export type ArtifactLineageEdge = {
  child_artifact_id: string;
  parent_artifact_id: string;
  role: string;
};

export type ArtifactLineageNode = {
  artifact_id: string;
  byte_size?: number;
  depth?: number;
  kind?: string | null;
  role?: string | null;
  status: string;
};

export type ArtifactLineageResponse = {
  lineage: ArtifactLineageView;
  meta: ApiMeta;
};

export type ArtifactLineageView = {
  corrupted_artifact_ids?: Array<string>;
  edges?: Array<ArtifactLineageEdge>;
  is_complete?: boolean;
  missing_artifact_ids?: Array<string>;
  nodes?: Array<ArtifactLineageNode>;
  root_artifact_ids?: Array<string>;
  total_edges?: number;
  total_nodes?: number;
  total_size_bytes?: number;
};

export type ArtifactManifestResponse = {
  artifact: ArtifactManifestView;
  meta: ApiMeta;
};

export type ArtifactManifestView = {
  artifact_id: string;
  byte_size: number;
  created_at: string;
  inputs?: Array<InputRef>;
  integrity_sha256: string;
  kind: string;
  media_type: string;
  producer_component?: string | null;
  producer_version?: string | null;
  schema_name?: string | null;
  schema_version?: string | null;
};

export type ArtifactMissingConfidenceLedgerRiskSpendPacket = {
  absence_reason: string;
  as_of: string;
  authoritative_for?: Array<"conditionality_disclosure" | "declared_set_accounting" | "source_validation_posture">;
  availability: string;
  export_replay_contract?: string;
  freshness: ProjectionFreshness;
  intended_audience?: string;
  intended_audiences?: Array<unknown>;
  may_not_use_for?: Array<"promotion_authority" | "publication_authority" | "public_audience" | "bounded_completeness">;
  packet_schema_version?: string;
  projection_hash?: null;
  projection_id?: string;
  projection_rule_version?: string;
  replay_address?: null;
  replay_pins?: null;
  source_artifact_content_hash?: null;
  source_blocked_reason?: null;
  source_dependency_hash?: null;
  source_rule_version?: null;
  source_schema_version?: null;
  stable_address?: string;
  worker_validation_receipt_hash?: null;
  worker_validation_receipt_ref?: null;
};

export type ArtifactMissingGovernedProjectionPacket = {
  absence_reason: string;
  as_of: string;
  authoritative_for: Array<string>;
  availability: string;
  export_replay_contract?: string;
  freshness: ProjectionFreshness;
  intended_audience: AudienceClass;
  may_not_use_for: Array<string>;
  packet_schema_version?: string;
  payload?: null;
  projection_hash?: null;
  projection_id: ProjectionId;
  projection_rule_version?: string;
  replay_address?: null;
  source?: null;
  source_dependency_hash?: null;
  source_rule_version?: null;
  source_schema_version?: null;
  stable_address: string;
};

export type ArtifactRefInput = {
  artifact_id: ArtifactID;
  kind: string;
  media_type: string;
};

export type ArtifactRefOutput = {
  artifact_id: string;
  kind: string;
  media_type: string;
};

export type ArtifactSchemaResponse = {
  meta: ApiMeta;
  schema: ArtifactSchemaView;
};

export type ArtifactSchemaView = {
  artifact_id: string;
  kind: string;
  media_type: string;
  schema_name?: string | null;
  schema_version?: string | null;
  top_level_keys?: Array<string>;
};

export type AttractorAnalysisProvenance = {
  derived_from?: Array<string>;
  notes?: Array<string>;
  toolchain?: Array<string>;
};

export type AttractorAnalysisRequest = {
  analysis_modes?: Array<"attractors" | "continuation" | "basin_map" | "lyapunov">;
  exec_plan_ref?: ExecPlanRefInput | null;
  feedback_jacobian_diagnostics_ref?: FeedbackJacobianDiagnosticsRef | null;
  feedback_result_ref?: FeedbackResultRefInput | null;
  initial_states?: Array<{
  [key: string]: number;
}>;
  largest_lyapunov_exponent?: number | null;
  max_period?: number;
  model_ref?: ArtifactRefInput | null;
  notes?: Array<string>;
  parameter_point?: AttractorParameterPoint;
  persist_artifact?: boolean;
  rtol?: number;
  schema_version?: string;
  seeds?: Array<number>;
  simulation_result_ref?: SimulationResultRefInput | null;
  state_projection?: AttractorStateProjection | null;
  stochastic_model?: boolean;
  tolerance?: number;
  trajectories?: Array<Array<Array<number>>>;
  trajectory?: Array<Array<number>> | null;
  variable_ids?: Array<string>;
  window?: number;
};

export type AttractorAnalysisResponse = {
  analysis_result?: AttractorAnalysisResult | null;
  analysis_result_ref?: AttractorAnalysisResultRef | null;
  derived_refs?: Array<DerivedArtifact>;
  notes?: Array<string>;
  ok: boolean;
  schema_version?: string;
};

export type AttractorAnalysisResult = {
  analysis_id: string;
  attractors?: Array<AttractorSummary>;
  bifurcations?: Array<BifurcationEvent>;
  exec_plan_ref?: ExecPlanRefOutput | null;
  feedback_result_ref?: FeedbackResultRefOutput | null;
  kind?: string;
  model_ref?: ArtifactRefOutput | null;
  notes?: Array<string>;
  parameter_point?: AttractorParameterPoint;
  provenance?: AttractorAnalysisProvenance;
  schema_version?: string;
  simulation_result_ref?: SimulationResultRefOutput | null;
  state_projection: AttractorStateProjection;
  uncertainty_summary?: AttractorUncertaintySummary;
};

export type AttractorAnalysisResultRef = {
  artifact_id: string;
  kind?: string;
  media_type?: string;
};

export type AttractorBasinEstimate = {
  basin_map_ref?: BasinMapRef | null;
  basin_measure_estimate?: number | null;
  boundary_complexity?: string | null;
  confidence_interval?: Array<unknown> | null;
  estimation_method?: string | null;
  notes?: Array<string>;
};

export type AttractorCertificate = {
  V_description?: string | null;
  evidence_strength?: number | null;
  notes?: Array<string>;
  proof_artifact_ref?: ArtifactRefOutput | null;
  status?: "not_attempted" | "not_applicable" | "numerically_supported" | "proved_local" | "proved_global" | "failed";
  type?: string;
};

export type AttractorObservableSummary = {
  max_amplitude?: number | null;
  period?: number | null;
  summary?: {
  [key: string]: unknown;
};
  terminal_residual_norm?: number | null;
};

export type AttractorParameterPoint = {
  names?: Array<string>;
  values?: Array<number>;
};

export type AttractorSpectralValue = {
  imag?: number;
  real: number;
};

export type AttractorStability = {
  diagnostics?: {
  [key: string]: unknown;
};
  floquet_multipliers?: Array<AttractorSpectralValue> | null;
  jacobian_eigenvalues?: Array<AttractorSpectralValue>;
  largest_lyapunov_exponent?: number | null;
  local_class?: "asymptotically_stable" | "orbitally_stable" | "neutral" | "unstable" | "mixed" | "unknown";
  lyapunov_spectrum?: Array<number> | null;
  notes?: Array<string>;
  spectral_radius?: number | null;
};

export type AttractorStateProjection = {
  quotient_notes?: Array<string>;
  reduced_dimension: number;
  variables?: Array<string>;
};

export type AttractorStateRepresentation = {
  equilibrium?: {
  [key: string]: number;
} | null;
  invariant_set_artifact_ref?: ArtifactRefOutput | null;
  orbit_artifact_ref?: ArtifactRefOutput | null;
  orbit_points?: Array<{
  [key: string]: number;
}>;
  section_definition?: string | null;
  summary?: {
  [key: string]: unknown;
};
};

export type AttractorSummary = {
  attractor_id: string;
  basin?: AttractorBasinEstimate;
  certificate?: AttractorCertificate;
  existence_status?: "candidate" | "numerically_confirmed" | "analytically_confirmed" | "rejected" | "unknown";
  kind: "fixed_point" | "limit_cycle" | "chaotic" | "torus" | "invariant_set" | "divergent";
  notes?: Array<string>;
  observables?: AttractorObservableSummary;
  stability?: AttractorStability;
  state_representation?: AttractorStateRepresentation;
  uncertainty?: AttractorUncertainty;
};

export type AttractorUncertainty = {
  continuation_step?: number | null;
  finite_time_horizon?: number | null;
  notes?: Array<string>;
  numerical_tolerance?: number | null;
  seeds_used?: number | null;
};

export type AttractorUncertaintySummary = {
  notes?: Array<string>;
  seed_ensemble_size?: number | null;
  stochastic_model?: boolean;
  unresolved_items?: Array<string>;
};

export type AudienceClass = "REVIEWER" | "EXPERT" | "MACHINE";

export type AuthMeResponse = {
  cell_id?: string | null;
  display_name: string;
  feature_overrides?: {
  [key: string]: boolean;
};
  meta: ApiMeta;
  mfa_verified?: boolean;
  permissions?: Array<RuntimePermission>;
  principal_type?: "anonymous" | "service" | "user";
  roles?: Array<string>;
  tenant_id: string;
  user_id: string;
};

export type AuthoredText = {
  format?: "plain" | "markdown" | "html" | "json";
  semantic_type?: string | null;
  text: string;
};

export type AuthorityAbstainingRunPaperCase = {
  admission_nonreceipt: RunPaperAuthorityNonReceipt;
  authority_projection?: string;
  availability?: string;
  case_id: string;
  design_record: DesignRecordV0;
  design_record_binding: RunBoundDesignRecordBinding;
  grounding_nonreceipt: RunPaperAuthorityNonReceipt;
  promotion_nonreceipt: RunPaperAuthorityNonReceipt;
};

export type AuthorityBoundary = {
  authoritative_for: Array<string>;
  boundary_id?: string | null;
  decision_grade?: DecisionGrade | null;
  evidence_basis?: EvidenceBasis | null;
  evidence_kind?: "measurement" | "derivation" | "proxy" | "transport" | "bounds" | "simulation" | "elicitation" | "incomparable_meet" | null;
  known_limits?: Array<string>;
  may_not_use_for: Array<string>;
  posture: "shadow" | "advisory" | "governed" | "production";
  rule_version_refs: Array<string>;
  source_authority: "deterministic_producer" | "governed_config" | "human_governance" | "llm_candidate" | "llm_critic" | "llm_drafter";
};

export type AuthorityProfile = {
  authority_refs?: Array<string>;
  mandate: string;
  requested_authority_level: "research" | "governed" | "production";
  requester_authority: string;
};

export type AuthoritySurface = "readiness" | "scientific";

export type AuthorityValueId = "readiness.composite_verdict" | "readiness.lens_projection" | "readiness.fairness_audit" | "readiness.harm_assessment" | "readiness.embargo_overlay" | "readiness.slow_review" | "readiness.revocation_ledger" | "scientific.identifiability_remedy" | "scientific.sensitivity_e_value" | "scientific.cohort_timeline" | "scientific.stress_ranking";

export type AvailableConfidenceLedgerRiskSpendPacket = {
  absence_reason?: null;
  as_of: string;
  authoritative_for?: Array<"conditionality_disclosure" | "declared_set_accounting" | "source_validation_posture">;
  availability: string;
  export_replay_contract?: string;
  freshness: ProjectionFreshness;
  frozen_semantic_projection_hash: string;
  intended_audience?: string;
  intended_audiences?: Array<unknown>;
  may_not_use_for?: Array<"promotion_authority" | "publication_authority" | "public_audience" | "bounded_completeness">;
  packet_schema_version?: string;
  payload: ConfidenceLedgerRiskSpendProjection;
  projection_hash: string;
  projection_id?: string;
  projection_rule_version?: string;
  registry_content_hash: string;
  registry_projection_hash: string;
  replay_address: string;
  replay_pins: ConfidenceLedgerRiskSpendReplayPins;
  source: ProjectionSourceIdentity;
  source_blocked_reason?: null;
  source_dependency_hash: string;
  source_rule_version: string | null;
  source_schema_version: string | null;
  stable_address?: string;
  worker_validation_receipt_hash: string;
  worker_validation_receipt_ref: string;
};

export type AvailableFact_CycleBoardAcquisitionEconomics_ = {
  availability?: string;
  source_as_of?: string | null;
  source_ref: string;
  value: CycleBoardAcquisitionEconomics;
};

export type AvailableFact_DepthNAcquisitionRouteReference_ = {
  availability?: string;
  source_as_of?: string | null;
  source_ref: string;
  value: DepthNAcquisitionRouteReference;
};

export type AvailableFact_DesignProblem_ = {
  availability?: string;
  source_as_of?: string | null;
  source_ref: string;
  value: DesignProblem;
};

export type AvailableFact_RunTerminality_ = {
  availability?: string;
  source_as_of?: string | null;
  source_ref: string;
  value: RunTerminality;
};

export type AvailableFact_SurfaceReadinessPayload_ = {
  availability?: string;
  source_as_of?: string | null;
  source_ref: string;
  value: SurfaceReadinessPayload;
};

export type AvailableFact_float_ = {
  availability?: string;
  source_as_of?: string | null;
  source_ref: string;
  value: number;
};

export type AvailableFact_int_ = {
  availability?: string;
  source_as_of?: string | null;
  source_ref: string;
  value: number;
};

export type AvailableFact_str_ = {
  availability?: string;
  source_as_of?: string | null;
  source_ref: string;
  value: string;
};

export type AvailableFact_tuple_str__________ = {
  availability?: string;
  source_as_of?: string | null;
  source_ref: string;
  value: Array<string>;
};

export type AvailableGovernedProjectionPacket = {
  absence_reason?: null;
  as_of: string;
  authoritative_for: Array<string>;
  availability: string;
  export_replay_contract?: string;
  freshness: ProjectionFreshness;
  intended_audience: AudienceClass;
  may_not_use_for: Array<string>;
  packet_schema_version?: string;
  payload: DepthNCycleBoardPayload | ValueGatePayload | GenerationCycleDispositionPayload | EngineCensusPayload | ForkBRelationCensusPayload | AcquisitionRoutingPayload | N13AAcquisitionCensusPayload | N13ALiveProbeJournalPayload | AcquisitionGrowthPayload | CapabilityRealityPayload | ClusterOwnershipPayload | Layer3HealthMetricsPayload | LegacyProvingGroundPayload | SurfaceReadinessPayload;
  projection_hash: string;
  projection_id: ProjectionId;
  projection_rule_version?: string;
  replay_address: string;
  source: ProjectionSourceIdentity;
  source_dependency_hash: string;
  source_rule_version?: string | null;
  source_schema_version?: string | null;
  stable_address: string;
};

export type AvailableRunPaperCase = {
  abstentions: Array<RunPaperAbstention>;
  admission_state: RunPaperAdmissionState;
  availability?: string;
  blockers: Array<RunPaperBlocker>;
  case_id: string;
  design_record: DesignRecordV0;
  design_record_binding: RunBoundDesignRecordBinding;
  grounding_state: RunPaperGroundingState;
  limitations: Array<RunPaperLimitation>;
  objections: Array<RunPaperObjection>;
  promotion_state: RunPaperPromotionState;
};

export type AvailableRunPaperStageTrace = {
  availability?: string;
  owner_route?: string;
  section_id?: string;
  trace_ref: ArtifactRefOutput;
};

export type AxisFirewallStatus = {
  cell_ref: string;
  maturity?: "fail_closed" | "predictive" | null;
  pattern_ids?: Array<string>;
  reason: string;
  rule_version_ref: string;
  status: "not_applicable" | "pass" | "warn" | "limit" | "block";
};

export type AxisPositionDeclaration = {
  authority_purpose: string;
  axis: string;
  cluster: string;
  evidence_refs?: Array<string>;
  position: string;
  rule_version_ref: string;
};

export type BasinEstimate = {
  ci_95?: EquilibriumBasinInterval | null;
  draws: number;
  equilibrium_id: string;
  hits: number;
  notes?: Array<string>;
  share_hat?: number | null;
};

export type BasinMap = {
  analysis_id?: string | null;
  basin_id: string;
  basin_measure_estimates?: {
  [key: string]: number;
};
  kind?: string;
  notes?: Array<string>;
  samples?: Array<BasinMapSample>;
  sampling_method: string;
  schema_version?: string;
  state_projection: AttractorStateProjection;
};

export type BasinMapRef = {
  artifact_id: string;
  kind?: string;
  media_type?: string;
};

export type BasinMapSample = {
  attractor_id?: string | null;
  confidence?: number | null;
  initial_state: {
  [key: string]: number;
};
  notes?: Array<string>;
  sample_id: string;
  seed?: number | null;
  terminal_residual_norm?: number | null;
};

export type BifurcationCandidate = {
  confidence?: "low" | "medium" | "high";
  diagnostics?: {
  [key: string]: unknown;
};
  equilibrium_id: string;
  kind: "fold" | "flip" | "loss_of_stability";
  lambda?: number | null;
  notes?: Array<string>;
};

export type BifurcationEvent = {
  bifurcation_id: string;
  branch_from?: string | null;
  branch_to?: string | null;
  confidence?: number | null;
  detection_method: string;
  kind: "saddle_node" | "hopf" | "period_doubling" | "neimark_sacker" | "torus" | "branch_point" | "homoclinic" | "regime_change" | "unknown";
  normal_form?: {
  [key: string]: unknown;
};
  notes?: Array<string>;
  parameter_values?: {
  [key: string]: number;
};
};

export type BindingProfileInfo = {
  description?: string;
  display_name: string;
  expected_columns?: Array<string>;
  profile_id: string;
  rule_count?: number;
  schema_family: string;
  strategy?: string;
  tags?: Array<string>;
};

export type BindingProfilesListResponse = {
  meta: ApiMeta;
  profiles?: Array<BindingProfileInfo>;
};

export type BureaucraticAuthorship = {
  agent_version?: string | null;
  author?: string;
  author_role?: string;
  reviewed_by_human?: boolean;
  timestamp?: string | null;
};

export type BureaucraticBlock = {
  authorship?: BureaucraticAuthorship;
  children?: Array<BureaucraticBlock>;
  epistemic_origin: "evidence_filled" | "model_generated" | "operator_filled" | "imported";
  id: string;
  items?: Array<string>;
  kind: "header" | "requisites" | "preamble" | "legal_basis" | "section" | "article" | "clause" | "subclause" | "paragraph" | "list" | "table" | "quantity" | "annex" | "signature" | "appendix";
  level?: number;
  metadata?: {
  [key: string]: unknown;
};
  number?: string | null;
  provenance?: Array<LineageCompactSummaryItem>;
  quantity?: QuantityValueOutput | null;
  raw_source_refs?: Array<string>;
  text?: string | null;
  title?: string | null;
};

export type BureaucraticDocument = {
  annexes?: Array<BureaucraticBlock>;
  blocks?: Array<BureaucraticBlock>;
  epistemic_summary?: BureaucraticEpistemicSummary;
  genre: "postanova_kmu" | "zakonoproekt" | "expert_vysnovok" | "analitichna_zapyska";
  id: string;
  jurisdiction?: string;
  language?: string;
  metadata?: {
  [key: string]: unknown;
};
  packet_hash: string;
  packet_id: string;
  render_timestamp?: string;
  status?: "draft" | "signed_external" | "archived";
  template: BureaucraticTemplateRef;
  temporal_scope?: TemporalScope | null;
  title: string;
  trust_view?: boolean;
  watermark: string;
};

export type BureaucraticEpistemicSummary = {
  evidence_filled?: number;
  imported?: number;
  model_generated?: number;
  operator_filled?: number;
};

export type BureaucraticExportResponse = {
  content: string;
  content_type: string;
  document_id: string;
  filename: string;
  format: "html" | "pdf" | "docx";
  meta: ApiMeta;
  metadata?: {
  [key: string]: unknown;
};
  packet_id: string;
};

export type BureaucraticRenderRequest = {
  genre: "postanova_kmu" | "zakonoproekt" | "expert_vysnovok" | "analitichna_zapyska";
  jurisdiction?: string;
  template_version?: string | null;
  temporal_scope?: TemporalScope | null;
  trust_view?: boolean;
};

export type BureaucraticRenderResponse = {
  document: BureaucraticDocument;
  meta: ApiMeta;
};

export type BureaucraticTemplateRef = {
  genre: "postanova_kmu" | "zakonoproekt" | "expert_vysnovok" | "analitichna_zapyska";
  id: string;
  jurisdiction?: string;
  legal_review_status?: "pending_external_review" | "approved" | "rejected";
  locale?: string;
  version: string;
};

export type CacheEntryInfo = {
  cache_key: string;
  connector_id: string;
  created_at: string;
  dataset_id: string;
  expires_at?: string | null;
  is_valid?: boolean;
  size_bytes?: number;
};

export type CacheStatusResponse = {
  entries?: Array<CacheEntryInfo>;
  meta: ApiMeta;
  total_entries?: number;
  total_size_bytes?: number;
};

export type CandidateLever = {
  instrument: string;
  lever_id: string;
  operator_kind: string;
  target_slot: string;
};

export type CandidateLeverSpace = {
  allowed_operator_kinds?: Array<string>;
  candidate_levers?: Array<CandidateLever>;
};

export type CapabilityAuthorityPostureResult = {
  authority_purpose: string;
  binding_ref?: string | null;
  currentness_ref?: string | null;
  producer_ref: string;
  provenance_refs: Array<string>;
  reason_codes?: Array<string>;
  state: "admitted_authority" | "candidate_only" | "producer_missing" | "bridge_missing" | "artifact_missing" | "invalid_source" | "revalidation_required" | "authority_blocked" | "not_established";
  time: CapabilityTimeSemantics;
};

export type CapabilityDiscoveryItem = {
  authoritative_for: Array<string>;
  authority_purpose: string;
  authority_result: CapabilityAuthorityPostureResult;
  capability_ref: string;
  content_digest: string;
  description: string;
  discovery_result: CapabilityDiscoveryPostureResult;
  execution_result: CapabilityExecutionPostureResult;
  label: string;
  may_not_use_for: Array<string>;
  provenance_refs: Array<string>;
  resource_kind: "method" | "dataset" | "source" | "legal_norm" | "case" | "agent";
  rule_version: string;
  schema_version?: string;
  time: CapabilityTimeSemantics;
};

export type CapabilityDiscoveryPostureResult = {
  freshness_ref?: string | null;
  producer_ref: string;
  provenance_refs: Array<string>;
  reason_codes?: Array<string>;
  snapshot_ref?: string | null;
  state: "discoverable" | "no_match" | "producer_missing" | "producer_unavailable" | "index_unavailable" | "index_stale" | "recall_unmeasured" | "budget_cutoff" | "incomplete";
  time: CapabilityTimeSemantics;
};

export type CapabilityDiscoveryRequest = {
  audience: "REVIEWER" | "EXPERT" | "MACHINE";
  resource_kinds: Array<"method" | "dataset" | "source" | "legal_norm" | "case" | "agent">;
  search: SearchRequest;
};

export type CapabilityDiscoveryResponse = {
  audience: "REVIEWER" | "EXPERT" | "MACHINE";
  authority_purpose: string;
  frontier: SearchFrontier;
  meta: ApiMeta;
  provenance_refs: Array<string>;
  request: CapabilityDiscoveryRequest;
  request_digest: string;
  results: Array<CapabilityDiscoveryItem>;
  rule_version: string;
  schema_version?: string;
  time: CapabilityTimeSemantics;
};

export type CapabilityExecutionPostureResult = {
  conformance_ref?: string | null;
  operation_ref?: string | null;
  policy_ref?: string | null;
  producer_ref: string;
  provenance_refs: Array<string>;
  reason_codes?: Array<string>;
  state: "executable" | "not_executable" | "operation_missing" | "conformance_failed" | "policy_disabled" | "producer_missing" | "execution_blocked" | "not_established";
  time: CapabilityTimeSemantics;
};

export type CapabilityFeatureInfo = {
  category: string;
  description: string;
  disabled_reason?: string | null;
  enabled?: boolean;
  key: string;
  label: string;
  stage?: "active" | "planned" | "deferred";
};

export type CapabilityManifestResponse = {
  constraints?: {
  [key: string]: unknown;
};
  default_execution_profile?: "dev" | "research" | "governed" | "production";
  default_locale?: "en" | "uk";
  fallback_rules?: {
  [key: string]: unknown;
};
  features?: Array<CapabilityFeatureInfo>;
  meta: ApiMeta;
  runtime_api_version?: string;
  security_posture?: {
  [key: string]: unknown;
};
  shell_flavor?: string;
  state_store_backend?: string;
  supported_execution_profiles?: Array<"dev" | "research" | "governed" | "production">;
  supported_locales?: Array<"en" | "uk">;
  worker_backend?: string;
  workspaces?: Array<string>;
};

export type CapabilityRealityPayload = {
  blockers: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  capability_claims: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  chain_clusters: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  debt_algebra: {
  [key: string]: ProjectionJsonValue;
};
  issues: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  ratchet_integrity_status: string;
  readiness: {
  [key: string]: ProjectionJsonValue;
};
  summary: {
  [key: string]: ProjectionJsonValue;
};
};

export type CapabilityTimeSemantics = {
  freshness: "current" | "stale" | "unknown";
  observed_at: string;
  valid_from: string;
  valid_until: string | null;
};

export type CausalFrontierAreaRecord = {
  area_id: string;
  covariates?: {
  [key: string]: number | null;
};
  direct_estimate: number;
  direct_variance: number;
  policy_indicator?: number | null;
  regime_id?: string | null;
  sample_size?: number | null;
};

export type CausalFrontierEdgeRecord = {
  adjacency_type?: "contiguity" | "distance" | "custom";
  dst_area_id: string;
  frontier_flag?: boolean;
  frontier_source?: string | null;
  frontier_type?: string | null;
  src_area_id: string;
  weight?: number;
};

export type CausalFrontierExposureRecord = {
  area_id: string;
  exposure_mapping_version?: string | null;
  spillover_exposure?: number | null;
  treatment?: number | null;
};

export type CausalFrontierOutputRefs = {
  causal_diagnostics_ref?: ArtifactRefOutput | null;
  dependence_ref?: ArtifactRefOutput | null;
  governance_artifact_ref?: ArtifactRefOutput | null;
  quality_certificate_ref?: ArtifactRefOutput | null;
  sae_estimates_ref?: ArtifactRefOutput | null;
};

export type CausalFrontierSAEEstimate = {
  area_id: string;
  borrow_strength_neighbors: number;
  component_id: number;
  mse: number;
  theta_mean: number;
  theta_sd: number;
};

export type CausalFrontierSAERequest = {
  add_intercept?: boolean;
  areas?: Array<CausalFrontierAreaRecord>;
  bundle_dir?: string | null;
  calibration_reps?: number;
  calibration_seed?: number;
  component_ridge?: number;
  contrast_eps?: number;
  covariate_columns?: Array<string> | null;
  edges?: Array<CausalFrontierEdgeRecord>;
  exposure?: Array<CausalFrontierExposureRecord>;
  governance_profile?: "fast" | "mvp" | "strict";
  green_threshold?: number;
  lambda_spatial?: number;
  metadata?: {
  [key: string]: unknown;
};
  output_dir?: string | null;
  persist_artifacts?: boolean;
  red_threshold?: number;
};

export type CausalFrontierSAEResponse = {
  artifact_refs?: CausalFrontierOutputRefs;
  diagnostics?: {
  [key: string]: unknown;
};
  estimates?: Array<CausalFrontierSAEEstimate>;
  governance_artifact?: {
  [key: string]: unknown;
};
  meta: ApiMeta;
  method_name: string;
  output_bundle?: {
  [key: string]: string;
};
};

export type CertificateClassRoute = {
  certificate_class: string;
  certificate_role: CertificateRole;
  claim_polarity: ClaimPolarity;
  instrument_id: string;
  obligation_class: PromotionObligationClass;
  owner_ref: string;
  verifier_kernel_id: string;
  verifier_ref: string;
};

export type CertificateRole = "promotion" | "promotion_conformance" | "refusal" | "acquisition" | "admission";

export type CertificateRouteRow = {
  anytime_valid: boolean;
  blocker: InstrumentBlocker | null;
  certificate_class: string;
  certificate_role: "promotion" | "promotion_conformance" | "refusal" | "acquisition" | "admission";
  claim_polarity: "false_accept" | "confident_wrong_refusal" | "confident_wrong_admission" | "conformance_only";
  deterministic: boolean;
  guarantee_kind: string;
  instrument_family: string;
  instrument_id: string;
  obligation_class: PromotionObligationClass;
  owner_ref: string;
  permits_obligation_satisfaction: boolean;
  proof_kernel_id: string;
  proof_profile_id: string;
  registry_content_hash: string;
  route_binding_hash: string;
  verifier_kernel_id: string;
  verifier_ref: string;
};

export type CertifiedOperationEnvelope = {
  actor_scopes: Array<string>;
  certified_for: Array<string>;
  cluster_authority_dimension_refs?: Array<string>;
  domains: Array<string>;
  envelope_id: string;
  epistemic_regime_scopes?: Array<"risk" | "uncertainty" | "ambiguity" | "ignorance" | "contested_model">;
  method_scopes: Array<string>;
  not_certified_for: Array<string>;
  posture_scopes: Array<"shadow" | "advisory" | "governed" | "production">;
  rule_version_ref: string;
};

export type ChannelRegistryEntry = {
  auth_class: string;
  capability_state?: string;
  channels?: Array<string>;
  consumers: Array<string>;
  include_in_schema?: boolean;
  message_contract: string;
  owner: string;
  path_template: string;
  producer_contract_ref: string;
  registry_id: string;
  status?: string;
  transport: "sse" | "websocket";
};

export type ChannelRegistryResponse = {
  channels: Array<ChannelRegistryEntry>;
  schema_version?: string;
};

export type ClaimPolarity = "false_accept" | "confident_wrong_refusal" | "confident_wrong_admission" | "conformance_only";

export type ClusterOwnershipPayload = {
  architecture_core: {
  [key: string]: ProjectionJsonValue;
};
  capability_chain_steps: Array<string>;
  clusters: {
  [key: string]: ProjectionJsonValue;
};
  handshake_graph: {
  [key: string]: ProjectionJsonValue;
};
  open_cell_closure: {
  [key: string]: ProjectionJsonValue;
};
  owner: string;
  purpose: string;
  ratchet_state_vocabulary: Array<string>;
  required_cell_fields: Array<string>;
  required_clusters: Array<string>;
  status: string;
  stop_rule: {
  [key: string]: ProjectionJsonValue;
};
};

export type ComparabilityReport = {
  blocked_reasons?: Array<string>;
  status: "compatible" | "warning" | "blocked";
  warnings?: Array<string>;
};

export type CompareCandidate = {
  comparability: ComparabilityReport;
  finished_at?: string | null;
  label?: string | null;
  relation?: "baseline" | "previous" | "selected" | "recommended";
  run_id: string;
  started_at?: string | null;
  status?: string | null;
};

export type CompareCandidatesResponse = {
  candidates?: Array<CompareCandidate>;
  meta: ApiMeta;
  run_id: string;
};

export type CompareDeltaSection = {
  changed?: boolean;
  details?: {
  [key: string]: unknown;
};
  refs?: {
  [key: string]: string | null;
};
  summary?: {
  [key: string]: unknown;
};
};

export type CompareRunResponse = {
  comparability: ComparabilityReport;
  comparison_frame: ComparisonFrame;
  deltas?: Array<DeltaQuantity>;
  meta: ApiMeta;
  status?: "computed" | "client_computable";
  temporal_scope?: TemporalScope | null;
};

export type ComparisonFrame = {
  assumption_set?: Array<string>;
  metric_set?: Array<string>;
  population?: string | null;
  run_a: string;
  run_b: string;
  scenario_scope?: {
  [key: string]: unknown;
};
  temporal_scope?: TemporalScope | null;
  unit_policy?: "canonical" | "source" | "mixed";
};

export type CompletionOutcome = "prepared" | "started" | "supported" | "not_supported" | "preflight_refusal" | "cancelled" | "owner_refused" | "owner_error" | "recovered_crash" | "refused";

export type ComponentId = string;

export type ConditionalDeltaAmount = {
  amount: RationalSpec;
  amount_hash: string;
  canonical_decimal: string;
  coverage_envelope_hash: string;
  coverage_envelope_ref: string;
  declared_obligation_classes_hash: string;
  declared_set_rider: string;
  locality_rider: string;
  maintained_assumptions: Array<"obligation_completeness" | "validator_soundness">;
  obligation_class: PromotionObligationClass | null;
  owner_scope_key: string;
  rational_display: string;
  rational_display_version: string;
  scope_id: string;
  semantic_role: string;
};

export type ConfidenceLedgerPolicy = {
  conditionality_clause: string;
  default_schedule_profile_id: string;
  delta: RationalSpec;
};

export type ConfidenceLedgerRegistry = {
  certificate_class_routes?: Array<CertificateClassRoute>;
  instruments: Array<InstrumentDefinition>;
  obligation_pools: Array<ObligationBudgetPool>;
  policy: ConfidenceLedgerPolicy;
  proof_profiles: Array<InstrumentProofProfile>;
  schedule_profiles: Array<PredictableScheduleProfile>;
  schema_version: string;
};

export type ConfidenceLedgerRiskSpendProjection = {
  acquisition_instance_refs: Array<string>;
  appointment_posture: AppointmentPosture;
  budget_posture: "within_budget" | "over_spend";
  certificate_route_denominator_count: number;
  certificate_route_denominator_hash: string;
  certificate_routes: Array<CertificateRouteRow>;
  conformance_instance_refs: Array<string>;
  coverage_assessment: CoverageAssessment;
  coverage_envelope: ObligationCoverageEnvelope;
  coverage_envelope_ref: string;
  fixed_scope_disclosure: string;
  good_event_posture: GoodEventPosture;
  grouped_spend: Array<InstrumentClassSpend>;
  instrument_blockers: Array<InstrumentBlocker>;
  instrument_definitions: Array<InstrumentDefinitionRow>;
  instrument_instances: Array<InstrumentInstanceRow>;
  obligation_class_risk_spend: Array<ObligationClassRiskSpend>;
  owner_scope_key: string;
  positive_register: PositiveCertificateRegister;
  projection_hash: string;
  refusal_instance_refs: Array<string>;
  registry_basis: ConfidenceLedgerRegistry;
  registry_content_hash: string;
  risk_scope: ConfidenceRiskBudgetScope;
  rule_version: string;
  schema_version: string;
  scope_id: string;
  scope_total_risk_spend: ScopeRiskSpend;
  semantic_ledger_basis: ConfidenceLedgerSemanticReceiptProjection;
  source_projection_hash: string;
  source_provenance: Array<CoverageSourceIdentity>;
  status: string;
  total_spend: ConditionalDeltaAmount;
};

export type ConfidenceLedgerRiskSpendReplayPins = {
  artifact_content_hash: string;
  projection_hash: string;
  projection_rule_version?: string;
  source_as_of: string;
  source_dependency_hash: string;
};

export type ConfidenceLedgerSemanticCheck = {
  anytime_valid: boolean;
  certificate_class?: string | null;
  certificate_ref: string;
  certificate_role: CertificateRole;
  certificate_route_hash?: string | null;
  check_projection_hash: string;
  claim_execution_projection_hash: string;
  claim_polarity: ClaimPolarity;
  claim_ref: string;
  claim_scope_ref: string;
  data_window_ref: string;
  deterministic_proof: boolean;
  eligible_for_promotion: boolean;
  execution_id?: string | null;
  execution_ordinal?: number | null;
  execution_status: ExecutionStatus;
  filtration_projection_hash: string;
  good_event_id?: string | null;
  instrument_definition_hash?: string | null;
  instrument_family: string;
  instrument_id: string;
  null_ref: string;
  obligation_class: PromotionObligationClass;
  outcome: CompletionOutcome;
  owner_binding: ConfidenceLedgerSemanticOwnerBinding | null;
  owner_invocation_claim_projection_hash?: string | null;
  proof_detail: string;
  proof_profile_hash?: string | null;
  proof_profile_id: string;
  refusal_code?: string | null;
  registry_content_hash: string;
  request_fingerprint: string;
  request_key: string;
  schedule_query_index?: number | null;
  schema_version: string;
  scope_id: string;
  spend: RationalSpec;
  spend_decimal: string;
  supports_obligation: boolean;
};

export type ConfidenceLedgerSemanticEvent = {
  check: ConfidenceLedgerSemanticCheck;
  event_projection_hash: string;
  event_type: "prepared" | "started" | "completed";
  parent_event_projection_hash: string;
  revision: number;
};

export type ConfidenceLedgerSemanticOwnerBinding = {
  binding_projection_hash: string;
  certificate_class: string;
  certificate_ref: string;
  certificate_route_hash: string;
  owner_projection_hash: string;
  owner_ref: string;
  verifier_kernel_id: string;
  verifier_ref: string;
};

export type ConfidenceLedgerSemanticReceiptProjection = {
  authority_provenance: SessionAuthorityProvenance;
  budget_delta: RationalSpec;
  budget_delta_decimal: string;
  checks: Array<ConfidenceLedgerSemanticCheck>;
  conditionality_clause: string;
  deployment_identity: string;
  events: Array<ConfidenceLedgerSemanticEvent>;
  good_event_clause: string;
  head_event_projection_hash: string;
  maintained_assumptions: Array<"obligation_completeness" | "validator_soundness">;
  projection_hash: string;
  projection_scope: "n11_real_accounting_append_lineage" | "n11_conformance_append_lineage";
  registry_content_hash: string;
  risk_scope: ConfidenceRiskBudgetScope;
  root_projection_hash: string;
  schedule_profile_hash: string;
  schedule_profile_id: string;
  schedule_projection_hash: string;
  schema_version: string;
  scope_anchor_ref: string;
  scope_id: string;
  total_spend: RationalSpec;
  total_spend_decimal: string;
  within_budget: boolean;
};

export type ConfidenceRiskBudgetScope = {
  authority_purpose: string;
  epoch_ref: string | null;
  model_ref: string | null;
  owner_projection_hash: string;
  owner_scope_key: string;
  rule_ref: string | null;
  schema_ref: string | null;
  scope_owner_ref: string;
};

export type ConnectorInfo = {
  available_profiles?: Array<string>;
  connector_id: string;
  known_datasets?: Array<string>;
  last_health_check?: string | null;
  loaded?: boolean;
  namespace: string;
  version: string;
};

export type ConnectorsListResponse = {
  connectors?: Array<ConnectorInfo>;
  meta: ApiMeta;
};

export type ContinuationBranchInput = {
  analysis_id?: string | null;
  bifurcations?: Array<BifurcationEvent>;
  branch_id: string;
  branch_kind: "equilibrium" | "periodic_orbit" | "bifurcation_curve" | "parameter_sweep";
  kind?: string;
  notes?: Array<string>;
  parameters?: Array<string>;
  points?: Array<ContinuationBranchPointInput>;
  schema_version?: string;
  toolchain?: Array<string>;
};

export type ContinuationBranchOutput = {
  analysis_id?: string | null;
  bifurcations?: Array<BifurcationEvent>;
  branch_id: string;
  branch_kind: "equilibrium" | "periodic_orbit" | "bifurcation_curve" | "parameter_sweep";
  kind?: string;
  notes?: Array<string>;
  parameters?: Array<string>;
  points?: Array<ContinuationBranchPointOutput>;
  schema_version?: string;
  toolchain?: Array<string>;
};

export type ContinuationBranchPointInput = {
  bifurcation_id?: string | null;
  notes?: Array<string>;
  parameter_values?: {
  [key: string]: number;
};
  period?: number | null;
  point_id: string;
  stability?: AttractorStability;
  state?: {
  [key: string]: number;
};
};

export type ContinuationBranchPointOutput = {
  bifurcation_id?: string | null;
  notes?: Array<string>;
  parameter_values?: {
  [key: string]: number;
};
  period?: number | null;
  point_id: string;
  stability?: AttractorStability;
  state?: {
  [key: string]: number;
};
};

export type ContinuationBranchRef = {
  artifact_id: string;
  kind?: string;
  media_type?: string;
};

export type ControlApprovalProjection = {
  authority_level: string;
  eligible?: boolean;
  reasons?: Array<string>;
  source_surface: string;
  state?: string | null;
};

export type ControlAuthorityGap = {
  code: string;
  evidence_ref?: string | null;
  layer: string;
  message: string;
  next_action?: string | null;
  next_diagnostic_command?: string | null;
  owner?: string | null;
  phase?: string | null;
};

export type ControlFailureEnvelope = {
  artifact_refs?: {
  [key: string]: unknown;
};
  code: string;
  job_id?: string | null;
  layer: string;
  message: string;
  model?: string | null;
  next_action?: string | null;
  operator_diagnostic?: OperatorDiagnostic | null;
  phase?: string | null;
  provider?: string | null;
  retryable?: boolean;
  run_id?: string | null;
  variant_failures?: Array<{
  [key: string]: unknown;
}>;
};

export type ControlJobResponse = {
  approval_projection?: ControlApprovalProjection;
  authoritative_scorecard_ref?: string | null;
  blocking_quality_failures?: Array<ControlQualityFailure>;
  capability_manifest_ref?: ArtifactRefOutput | null;
  effective_execution_profile: "dev" | "research" | "governed" | "production";
  error_message?: string | null;
  execution_status?: string | null;
  failure?: ControlFailureEnvelope | null;
  finished_at?: string | null;
  job_id: string;
  kind: "workflow_run" | "natural_language_run" | "lex_pipeline" | "acquisition";
  meta: ApiMeta;
  next_diagnostic_commands?: Array<string>;
  operator_diagnostic?: OperatorDiagnostic | null;
  pipeline_id?: string | null;
  policy_design_case_projection?: PolicyDesignCaseProjection | null;
  progress?: {
  [key: string]: unknown;
};
  projection_source?: ControlProjectionSource;
  quality_evidence_bundle_path?: string | null;
  quality_gates?: Array<ControlQualityGate>;
  quality_scorecard_ref?: string | null;
  quality_status?: string | null;
  requested_execution_profile?: "dev" | "research" | "governed" | "production" | null;
  run_id?: string | null;
  runtime_state?: string | null;
  started_at?: string | null;
  state: "pending" | "running" | "completed" | "failed";
  submitted_at?: string | null;
  unresolved_authority_gaps?: Array<ControlAuthorityGap>;
};

export type ControlOutboxEventInfo = {
  attempt?: number;
  created_at: string;
  error_message?: string | null;
  event_id: string;
  event_key?: string | null;
  job_id?: string | null;
  payload?: {
  [key: string]: unknown;
};
  published_at?: string | null;
  run_id?: string | null;
  state: string;
  topic: string;
};

export type ControlOutboxEventsResponse = {
  events?: Array<ControlOutboxEventInfo>;
  limit?: number;
  meta: ApiMeta;
  state?: string | null;
};

export type ControlProjectionSource = {
  authority_level: string;
  projection_policy: string;
  source_detail: string;
  source_surface: string;
};

export type ControlQualityFailure = {
  code?: string | null;
  evidence_ref?: string | null;
  gate: string;
  layer: string;
  message: string;
  next_action?: string | null;
  next_diagnostic_command?: string | null;
  operator_diagnostic?: OperatorDiagnostic | null;
  phase?: string | null;
};

export type ControlQualityGate = {
  blocking?: boolean;
  code?: string | null;
  evidence_ref?: string | null;
  layer: string;
  message: string;
  name: string;
  next_action?: string | null;
  next_diagnostic_command?: string | null;
  operator_diagnostic?: OperatorDiagnostic | null;
  phase?: string | null;
  status: string;
};

export type ControlWorkerLeaseInfo = {
  active_job_id?: string | null;
  backend?: string | null;
  created_at: string;
  heartbeat_at: string;
  lease_expires_at: string;
  metadata?: {
  [key: string]: unknown;
};
  state: string;
  updated_at: string;
  worker_id: string;
};

export type ControlWorkersResponse = {
  active_only?: boolean;
  meta: ApiMeta;
  workers?: Array<ControlWorkerLeaseInfo>;
};

export type CounterfactualMetric = {
  actual: QuantityValueOutput;
  assumption_ids: Array<string>;
  counterfactual: QuantityValueOutput;
  delta: QuantityValueOutput;
  label: string;
  metric_id: string;
  scenario_ref: ScenarioRef;
};

export type CounterfactualMetricsResponse = {
  meta: ApiMeta;
  metrics?: {
  [key: string]: CounterfactualMetric;
};
  run_id: string;
  scenario: ScenarioManifest;
  temporal_scope?: TemporalScope | null;
};

export type CoverageAssessment = "known_incomplete" | "open_world_unresolved";

export type CoverageReasonCode = "DS17-COVERAGE-OPEN-WORLD" | "DS17-COVERAGE-KNOWN-INCOMPLETE" | "DS17-COVERAGE-SEARCH-NOT-ESTABLISHED" | "DS17-COVERAGE-EXCLUSIONS-NOT-ESTABLISHED" | "DS17-COVERAGE-INDEPENDENCE-MISSING";

export type CoverageSourceIdentity = {
  admission_state: "canonical_registry_validated" | "worker_admission_not_established";
  availability_state: string;
  content_hash: string;
  source_ref: string;
  source_role: "canonical_registry" | "semantic_ledger";
  verifier_ref: string;
};

export type CoverageUnknownRemainder = {
  cardinality: string;
  kind: string;
  probability: string;
};

export type CursorPage = {
  count?: number;
  cursor?: string | null;
  limit?: number;
  next_cursor?: string | null;
  total?: number | null;
};

export type CycleBoardAcquisitionEconomics = {
  decision_owner_ref: string;
  execution_status: AvailableFact_str_ | AbsentFact;
  expected_cost: AvailableFact_float_ | AbsentFact;
  expected_voi: AvailableFact_float_ | AbsentFact;
  missing_requirement_fields: Array<string>;
  next_action: string;
  planner_report_content_hash: string;
  planner_status: string;
  producer_expected: string;
  recommended_strategy: string;
  voi_rank: AvailableFact_int_ | AbsentFact;
};

export type CycleBoardCompositionSource = {
  absence_reason?: string | null;
  artifact_content_hash?: string | null;
  as_of?: string | null;
  authoritative_for: Array<string>;
  availability: "available" | "artifact_missing" | "invalid_source" | "not_established";
  freshness?: ProjectionFreshness | null;
  may_not_use_for: Array<string>;
  source_dependency_hash?: string | null;
  source_id: string;
  source_kind: "governed_projection" | "control_plane_evidence" | "historical_owner_record" | "run_summary_lookup" | "run_paper_projection";
  source_ref?: string | null;
};

export type CycleBoardCoverageGap = {
  capability_state?: string;
  deficits?: Array<"artifact_missing" | "bridge_missing">;
  execution_status?: string;
  exhaustive?: boolean;
  known_row_count: number;
  known_scope?: string;
  missing_link?: string;
  owner_route?: string;
  unknown_scope?: string;
};

export type CycleBoardMovementGap = {
  capability_state?: string;
  chronology_route?: string;
  deficits?: Array<"artifact_missing" | "bridge_missing">;
  execution_status?: string;
  missing_link?: string;
  movement_records?: Array<{
  [key: string]: unknown;
}>;
  producer_route?: string;
};

export type CycleBoardProjectionPacket = {
  composition_manifest: Array<CycleBoardCompositionSource>;
  composition_manifest_hash: string;
  intended_audiences?: Array<unknown>;
  packet_schema_version?: string;
  payload: DepthNCycleBoardPayloadV2;
  projection_hash: string;
  projection_id?: string;
  projection_observed_at: string;
  projection_rule_version?: string;
  replay_address: string;
  source_dependency_hash: string;
  stable_address?: string;
};

export type CycleBoardRow = {
  acquisition_economics: AvailableFact_CycleBoardAcquisitionEconomics_ | AbsentFact;
  acquisition_route: AvailableFact_DepthNAcquisitionRouteReference_ | AbsentFact;
  cohort: "n10_capstone" | "legacy_fixture";
  design_problem: AvailableFact_DesignProblem_ | AbsentFact;
  domain_role: string;
  explanation_code: string;
  explanation_inputs: {
  [key: string]: string;
};
  generation_cycle_run_id: AvailableFact_str_ | AbsentFact;
  lifecycle_terminality: AvailableFact_RunTerminality_ | AbsentFact;
  missing_link: AvailableFact_str_ | AbsentFact;
  movement_records?: Array<{
  [key: string]: unknown;
}>;
  responsible_slices: Array<string>;
  row_id: string;
  search_terminal_kind: AvailableFact_str_ | AbsentFact;
  stage_trace_href: AvailableFact_str_ | AbsentFact;
  structural_evidence_class: AvailableFact_str_ | AbsentFact;
  surface_readiness: AvailableFact_SurfaceReadinessPayload_ | AbsentFact;
  weakest_links: AvailableFact_tuple_str__________ | AbsentFact;
};

export type DataDiscoverRequest = {
  cost_budget_usd?: number;
  data_needs: Array<DataNeed>;
  max_candidates_total?: number;
  max_discovery_calls_per_source?: number;
  max_sources_per_query?: number;
  time_budget_ms?: number;
};

export type DataDiscoverResponse = {
  candidates?: Array<DiscoveryCandidate>;
  docs_fetched_total?: number;
  index_stats?: IndexStats | null;
  meta: ApiMeta;
  warnings?: Array<string>;
};

export type DataNeed = {
  geography?: string | null;
  granularity?: string;
  metric: string;
  purpose?: string;
  quality_min?: number;
  time_end?: string | null;
  time_start?: string | null;
};

export type DataPreviewRequest = {
  allow_fallback?: boolean;
  fetch_plan: FetchPlan;
};

export type DataPreviewResponse = {
  meta: ApiMeta;
  preview: FetchPreview;
};

export type DataResolveRequest = {
  allow_explore_fallback?: boolean;
  data_needs: Array<DataNeed>;
  mode?: "fastlane" | "explorelane" | "hybrid";
};

export type DataResolveResponse = {
  candidates?: Array<MetricCandidate>;
  fetch_plans?: Array<FetchPlan>;
  meta: ApiMeta;
  mode: "fastlane" | "explorelane" | "hybrid";
  warnings?: Array<string>;
};

export type DataSourceBinding = {
  data_snapshot_ref?: string | null;
  data_view_request_ref?: string | null;
  input_bindings_ref?: string | null;
};

export type DatasetFetchSpecRequest = {
  connector_id: string;
  dataset_id: string;
  date_end?: string | null;
  date_start?: string | null;
  filters?: {
  [key: string]: Array<string>;
};
};

export type DecisionCompareReport = {
  deltas?: {
  [key: string]: CompareDeltaSection;
};
  left_decision_packet_ref?: string | null;
  left_run_id: string;
  notes?: Array<string>;
  right_decision_packet_ref?: string | null;
  right_run_id: string;
  root_cause?: Array<string>;
  schema_version?: string;
};

export type DecisionDependencyEvent = {
  dedupe_key: string;
  dependency_keys?: Array<string>;
  event_id: string;
  occurred_at?: string;
  payload?: {
  [key: string]: unknown;
};
  reason: string;
  recorded_at?: string;
  schema_version?: string;
  source_ref?: string | null;
  status: DecisionValidityStatus;
  trigger_type: DecisionTriggerType;
};

export type DecisionGrade = "unsupported" | "descriptive_only" | "advisory_admissible" | "decision_admissible";

export type DecisionLifecycleJob = {
  completed_at?: string | null;
  decision_lineage_key: string;
  job_id: string;
  job_kind: "evaluation" | "scheduled_monitoring";
  monitoring_contract_ref?: string | null;
  packet_ref: string;
  payload?: {
  [key: string]: unknown;
};
  reason: string;
  scheduled_for?: string;
  schema_version?: string;
  state?: "pending" | "completed" | "cancelled";
  trigger_event_id?: string | null;
};

export type DecisionMonitoringContract = {
  anchor_at: string;
  backtest_mode_effective?: string | null;
  backtest_trust_eligible?: boolean | null;
  decision_lineage_key?: string | null;
  metrics?: Array<MonitoredMetric>;
  notes?: Array<string>;
  run_id?: string | null;
  schema_version?: string;
};

export type DecisionMonitoringReport = {
  anchor_at?: string | null;
  decision_packet_ref?: string | null;
  degraded_reasons?: Array<string>;
  evaluated_at?: string;
  metrics?: Array<MonitoringMetricResult>;
  monitoring_contract_ref?: string | null;
  notes?: Array<string>;
  overall_verdict?: MonitoringVerdict;
  refuted_metric_ids?: Array<string>;
  run_id: string;
  schema_version?: string;
};

export type DecisionPacketAuthoredBlock = {
  author?: "citation" | "human" | "drafter" | "formalizer" | "critic" | null;
  author_agent_version?: string | null;
  confidence?: number | null;
  content: string;
  id?: string | null;
  reviewed_by_human?: boolean | null;
  sources?: Array<{
  [key: string]: string;
}>;
  timestamp?: string | null;
};

export type DecisionPacketEffectSize = {
  ci_80?: Array<unknown> | null;
  ci_95?: Array<unknown> | null;
  disputed?: boolean | null;
  identifiability?: "identified" | "estimated" | "assumed" | null;
  method?: string | null;
  point?: number | null;
  quantiles?: {
  [key: string]: number;
} | null;
};

export type DecisionPacketMetricComparisonRow = {
  alpha?: number | null;
  assumption_warnings?: Array<string>;
  baseline_model_id?: string | null;
  baseline_value?: number | null;
  calibration_warnings?: Array<string>;
  candidate_model_id?: string | null;
  candidate_value?: number | null;
  delta_value?: number | null;
  effect_size?: DecisionPacketEffectSize | null;
  family_id?: string | null;
  family_scope?: string | null;
  metric_direction?: string | null;
  metric_id: string;
  p_adj?: number | null;
  p_value?: number | null;
  resampling_method?: string | null;
  sample_size_effective?: number | null;
  significant?: boolean | null;
  statistic?: number | null;
  test_id?: string | null;
  test_label?: string | null;
};

export type DecisionPacketMetricSignificance = {
  alpha?: number | null;
  assumption_warnings?: Array<string>;
  baseline_model_id?: string | null;
  baseline_value?: number | null;
  calibration_warnings?: Array<string>;
  candidate_model_id?: string | null;
  candidate_value?: number | null;
  delta_value?: number | null;
  effect_size?: DecisionPacketEffectSize | null;
  metric_direction?: string | null;
  p_adj?: number | null;
  p_value?: number | null;
  significant?: boolean | null;
  test_id?: string | null;
  test_label?: string | null;
};

export type DecisionPacketOutlineEntry = {
  section_id: string;
  section_type?: string | null;
  title: string;
};

export type DecisionPacketPreview = {
  blocks?: Array<DecisionPacketAuthoredBlock>;
  document_outline?: Array<DecisionPacketOutlineEntry>;
  evidence_summary_blocks?: Array<DecisionPacketAuthoredBlock>;
  metric_significance_by_metric?: {
  [key: string]: DecisionPacketMetricSignificance;
};
  metric_validation_comparison_rows?: Array<DecisionPacketMetricComparisonRow>;
  narrative_blocks?: Array<DecisionPacketAuthoredBlock>;
  [key: string]: unknown;
};

export type DecisionReissuePlan = {
  calibration_config_ref?: string | null;
  compare_report_ref?: string | null;
  monitoring_report_ref?: string | null;
  notes?: Array<string>;
  parameter_override_bundle_ref?: string | null;
  publication_mode?: string;
  recommended_action?: string;
  refuted_metric_ids?: Array<string>;
  requires_operator_confirmation?: boolean;
  revised_metric_ids?: Array<string>;
  schema_version?: string;
  source_decision_packet_ref?: string | null;
  source_run_id: string;
};

export type DecisionTriggerRecord = {
  dependency_key?: string | null;
  details?: {
  [key: string]: unknown;
};
  reason: string;
  source_ref?: string | null;
  status: DecisionValidityStatus;
  trigger_type: DecisionTriggerType;
};

export type DecisionTriggerType = "norm_invalidation" | "data_invalidation" | "source_invalidation" | "metric_invalidation" | "model_invalidation" | "conflict_invalidation" | "law_change" | "dataset_superseded" | "historical_semantic_revision" | "contradicting_evidence" | "context_profile_drift" | "post_deployment_refutation" | "human_gate" | "expert_review" | "legacy_packet" | "superseded" | "revoked";

export type DecisionValidityEventRequest = {
  dedupe_key?: string | null;
  dependency_keys?: Array<string>;
  monitor_event_ref?: ArtifactRefInput | null;
  occurred_at?: string | null;
  payload?: {
  [key: string]: unknown;
};
  reason?: string | null;
  source_ref?: string | null;
  status?: DecisionValidityStatus | null;
  trigger_type?: DecisionTriggerType | null;
};

export type DecisionValidityEventResponse = {
  advisory_event_ref?: ArtifactRefOutput | null;
  affected_packets?: Array<string>;
  affected_statuses?: {
  [key: string]: number;
};
  dedupe_key: string;
  event_id: string;
  lifecycle_bridge_result_ref?: ArtifactRefOutput | null;
  message: string;
  meta: ApiMeta;
  monitor_event_ref?: ArtifactRefOutput | null;
};

export type DecisionValidityLifecycleSummary = {
  events?: Array<DecisionDependencyEvent>;
  latest_transition_at?: string | null;
  pending_reviews?: Array<DecisionValidityPendingReview>;
  reissue_candidates?: Array<ArtifactRefOutput>;
  scheduled_jobs?: Array<DecisionLifecycleJob>;
  status?: DecisionValidityStatus | null;
  transitions?: Array<DecisionValidityTransition>;
};

export type DecisionValidityPendingReview = {
  event_id: string;
  occurred_at: string;
  reason: string;
  trigger_type: DecisionTriggerType;
};

export type DecisionValidityStatus = "active" | "warning" | "stale" | "review_required" | "superseded" | "reissued" | "withdrawn" | "revoked" | "requires_human_review";

export type DecisionValiditySummaryResponse = {
  checked_at: string;
  decision_lineage_key: string;
  decision_packet_ref: ArtifactRefOutput;
  evaluation_ref?: ArtifactRefOutput | null;
  lifecycle?: DecisionValidityLifecycleSummary;
  lifecycle_status: DecisionValidityStatus;
  meta: ApiMeta;
  reasons?: Array<string>;
  recommended_action: string;
  review_required?: boolean;
  run_id?: string | null;
  status: DecisionValidityStatus;
  superseded_by_ref?: ArtifactRefOutput | null;
  supersedes_decision_ref?: ArtifactRefOutput | null;
  triggers?: Array<DecisionTriggerRecord>;
};

export type DecisionValidityTransition = {
  current_status: DecisionValidityStatus;
  decision_lineage_key: string;
  evaluation_ref?: string | null;
  occurred_at?: string;
  packet_ref: string;
  previous_status?: DecisionValidityStatus | null;
  reason: string;
  review_required?: boolean;
  schema_version?: string;
  transition_id: string;
  triggered_by_event_id?: string | null;
};

export type DeltaDistribution = {
  ci_overlap?: boolean | null;
  mean_shift?: number | null;
  median_shift?: number | null;
  quantiles?: {
  [key: string]: number;
};
};

export type DeltaQuantity = {
  a?: QuantityValueOutput | null;
  b?: QuantityValueOutput | null;
  decision_salience?: number;
  delta_absolute?: QuantityValueOutput | null;
  delta_distribution?: DeltaDistribution;
  delta_relative?: QuantityValueOutput | null;
  dominance?: "a" | "b" | "none" | "mixed" | "unknown";
  label: string;
  lineage_delta?: LineageDelta;
  metric_id: string;
  significance?: "improved" | "worsened" | "mixed" | "uncertain" | "not_comparable";
};

export type DependencyDigestProjection = {
  domain: string;
  value: string;
};

export type DependencyDiscriminantAuthorityBoundary = {
  authoritative_for: Array<string>;
  may_not_use_for: Array<"n8_admission" | "n10a_stage_gap_closure" | "chronology_acceptance" | "policy_publication" | "policy_promotion">;
};

export type DependencyDiscriminantOwnerBinding = {
  binding_name: string;
  dependency_environment: DependencyEnvironmentDiagnosticProjection;
  owner_semantic_hash: string | null;
  relation?: string;
  relative_path: string;
  resolved_artifact_content_hash: string | null;
  semantic_hash_rule_version: string;
};

export type DependencyDistributionProjection = {
  name: string;
  selected_artifact: DependencyDigestProjection;
  source_kind: string;
  version: string;
};

export type DependencyEnvironmentDiagnosticCaseProjection = {
  case_kind: "root_distribution_disagreement" | "missing_resolved_distribution" | "distribution_field_disagreement" | "unexpected_in_closure_identity";
  coordinate: string;
  expected: string;
  field?: "version" | "source_kind" | "selected_artifact" | null;
  observed: string;
  predicate_class: "independently_reconciled" | "recomputed";
};

export type DependencyEnvironmentDiagnosticProjection = {
  artifact_content_ref?: string | null;
  authority_boundary?: DependencyDiscriminantAuthorityBoundary | null;
  decision_role: string;
  first_case?: DependencyEnvironmentDiagnosticCaseProjection | null;
  predicate_class?: string | null;
  profile?: DependencyProfileDiscriminantProjection | null;
  receipt_state: "received" | "not_received";
  status: "pass" | "fail" | "not_established";
};

export type DependencyProfileDiscriminantProjection = {
  declaration_ref: DependencyRecordRefProjection;
  discriminant_ref: DependencyDigestProjection;
  distribution_set: DependencyDigestProjection;
  extras: Array<string>;
  lockfile_ref: DependencyDigestProjection;
  marker_environment: Array<Array<unknown>>;
  profile_id: string;
  pyproject_ref: DependencyDigestProjection;
  python_constraint: string;
  resolved_distributions: Array<DependencyDistributionProjection>;
  resolver_name: string;
  resolver_version: string;
  root_distribution: string;
  rule_version: string;
  schema_version: string;
};

export type DependencyRecordRefProjection = {
  artifact_id: string;
  schema_version: string;
  semantic_hash: DependencyDigestProjection;
};

export type DepthNAcquisitionEconomicsProjection = {
  decision_owner_ref: string;
  expected_cost: number | null;
  expected_voi: number | null;
  missing_requirement_fields: Array<string>;
  next_action: string;
  planner_report_content_hash: string;
  planner_status: string;
  producer_expected: string;
  recommended_strategy: string;
  voi_rank: number | null;
};

export type DepthNAcquisitionRouteReference = {
  owner_content_hash: string;
  owner_schema: string;
  planner_report_content_hash: string;
  requirement_gap_id: string;
};

export type DepthNCycleBoardPayload = {
  depth_evidence: {
  [key: string]: ProjectionJsonValue;
};
  domain_runs: {
  [key: string]: DepthNDomainRunProjection;
};
  terminal_distributions: {
  [key: string]: ProjectionJsonValue;
};
};

export type DepthNCycleBoardPayloadV2 = {
  coverage: CycleBoardCoverageGap;
  historical_producer_availability: HistoricalProducerAvailability;
  movement_gap: CycleBoardMovementGap;
  realized_ds4_disposition: HistoricalDS4Disposition;
  rows: Array<CycleBoardRow>;
};

export type DepthNDomainRunProjection = {
  acquisition_economics?: DepthNAcquisitionEconomicsProjection | null;
  acquisition_route?: DepthNAcquisitionRouteReference | null;
  design_problem: DesignProblem;
  design_problem_ref: string;
  domain_role: string;
  evidence_class: string;
  evidence_witness: {
  [key: string]: ProjectionJsonValue;
};
  generation_cycle_run_id: string;
  search_terminal_kind: string;
  terminal_distribution: {
  [key: string]: ProjectionJsonValue;
};
  weakest_links: Array<string>;
};

export type DerivedArtifact = {
  ref: ArtifactRefOutput;
  role: string;
};

export type DesignConstraint = {
  admissibility_basis: string;
  constraint_id: string;
  description: string;
  evidence_ref?: string | null;
  hard?: boolean;
  source_text?: string | null;
};

export type DesignObjective = {
  description: string;
  direction?: "maximize" | "minimize" | "maintain_range";
  metric_id: string;
  objective_id: string;
};

export type DesignProblem = {
  authority_profile: AuthorityProfile;
  candidate_lever_space: CandidateLeverSpace;
  constraints?: Array<DesignConstraint>;
  design_problem_id: string;
  domain: string;
  evidence_acquisition_needs: EvidenceAcquisitionNeeds;
  ir_problem_frame_ref?: string | null;
  jurisdiction_time: JurisdictionTimeSemantics;
  model_spec_ref?: string | null;
  nl_provenance: NLProvenance;
  objectives?: Array<DesignObjective>;
  outcome_of_interest: OutcomeOfInterest;
  policy_request_frame_ref?: string | null;
  problem_statement: string;
  runtime_hints?: {
  [key: string]: unknown;
};
  schema_version?: string;
  stakeholders?: Array<DesignStakeholder>;
};

export type DesignRecordV0 = {
  authority_boundary: AuthorityBoundary;
  axis_positions?: Array<AxisPositionDeclaration>;
  candidate_ref: string;
  candidate_source: "deterministic_producer" | "governed_config" | "human_governance" | "llm_candidate" | "llm_critic" | "llm_drafter";
  envelope: CertifiedOperationEnvelope;
  firewall_status?: Array<AxisFirewallStatus>;
  ledger_refs?: Array<string>;
  projection_audiences: Array<"PUBLIC" | "REVIEWER" | "EXPERT" | "MACHINE">;
  projection_status: "shadow" | "advisory" | "governed" | "production";
  record_id: string;
  schema_version?: string;
};

export type DesignStakeholder = {
  name: string;
  role?: string | null;
  stakeholder_id: string;
};

export type DiscoveryCandidate = {
  candidate_id: string;
  confidence?: number;
  connector_id: string;
  coverage_estimate?: number | null;
  dataset_id: string;
  dataset_name?: string | null;
  description?: string;
  discovered_at?: string | null;
  latency_estimate_ms?: number | null;
  metadata?: {
  [key: string]: unknown;
};
  metric_id: string;
  profile_id?: string | null;
  schema_excerpt?: {
  [key: string]: unknown;
};
  source_lane?: "fastlane" | "explorelane" | "catalog";
};

export type EngineCensusPayload = {
  critical_findings: Array<string>;
  discipline: string;
  evidence_reproducibility: {
  [key: string]: ProjectionJsonValue;
};
  execution_status_vocabulary: {
  [key: string]: ProjectionJsonValue;
};
  gap_taxonomy_extensions: {
  [key: string]: ProjectionJsonValue;
};
  row_count: number;
  scope: string;
  subcensus_summary: {
  [key: string]: ProjectionJsonValue;
};
  verb_gap_consistency: {
  [key: string]: ProjectionJsonValue;
};
};

export type EngineeringCapabilityAbsenceView = {
  absence_class?: string;
  candidate_owner_module?: string;
  candidate_owner_path?: string;
  capability?: string;
  closure_condition: string;
  consequence: string;
  institutional_dependency?: boolean;
  missing_labels?: Array<unknown>;
  missing_output: string;
  title?: string;
};

export type EnvInfo = {
  deps_lock_hash: string;
  platform: string;
  python: string;
};

export type EpochBoundaryLineageView = {
  current_epoch_ref: string;
  predecessor_packet_ref?: ArtifactRefOutput | null;
  previous_epoch_ref: string;
  successor_packet_ref?: ArtifactRefOutput | null;
  transition_ref?: ArtifactRefOutput | null;
  trigger_event_refs?: Array<ArtifactRefOutput>;
};

export type EpochCertificateStalenessView = {
  authority_purpose: string;
  bound_epoch_ref: string;
  certificate_ref: ArtifactRefOutput;
  current_epoch_ref?: string | null;
  input_certificate_refs?: Array<ArtifactRefOutput>;
  native_coordinate_refs?: Array<string>;
  recipe_ref: ArtifactRefOutput;
  revalidation_requirements?: Array<string>;
  rule_schema_profile_refs?: Array<string>;
  stale_reasons?: Array<string>;
  status: "current" | "stale" | "revalidation_required" | "contested" | "not_established";
  trigger_event_refs?: Array<ArtifactRefOutput>;
};

export type EpochDependencyStalenessView = {
  advisory_event_refs?: Array<ArtifactRefOutput>;
  authority_purpose: string;
  disposition: "unchanged" | "annotation_only" | "invalidate" | "reissue" | "supersede" | "withdraw" | "contested" | "review_required";
  owner_evidence_refs?: Array<ArtifactRefOutput>;
  recompute: EpochDerivedRecomputeView;
  relation: string;
  source_classes?: Array<"incident" | "appeal" | "correction" | "retraction" | "legal_change" | "discovered_bias">;
  source_ref: ArtifactRefOutput;
  target_ref: ArtifactRefOutput;
};

export type EpochDerivedRecomputeView = {
  evidence_content_hash?: string | null;
  evidence_ref?: ArtifactRefOutput | null;
  predicate_provenance: "recomputed" | "independently_reconciled" | "consumer_asserted" | "institutionally_supplied" | "not_established";
  status: "not_established" | "pending" | "running" | "completed" | "failed";
};

export type EpochOpenWorldRiskComponentView = {
  component_id: string;
  component_kind: "model" | "obligation" | "calibration" | "novel";
  evidence_ref?: ArtifactRefOutput | null;
  limitation_code: string;
  predicate_provenance: "independently_reconciled" | "not_established";
  status: "within_scope" | "outside_scope" | "not_established";
};

export type EpochOpenWorldRiskView = {
  components?: Array<EpochOpenWorldRiskComponentView>;
  limitation_code: string;
  promotion_frozen: boolean;
  status: "established" | "limited" | "not_established";
  vector_artifact_ref?: ArtifactRefOutput | null;
};

export type EpochPerturbationView = {
  adjudicated_disposition: "annotation_only" | "invalidate" | "reissue" | "supersede" | "withdraw" | "contested" | "review_required";
  advisory_posture: "annotation_only" | "review_required";
  event_ref: ArtifactRefOutput;
  observed_at: string;
  owner_evidence_refs?: Array<ArtifactRefOutput>;
  scope: "instance" | "dependency_descendants";
  source_class: "incident" | "appeal" | "correction" | "retraction" | "legal_change" | "discovered_bias";
  source_evidence_refs?: Array<ArtifactRefOutput>;
  target_ref: ArtifactRefOutput;
};

export type EpochProjectionDenominatorView = {
  denominator_ref?: string | null;
  predicate_provenance: "recomputed" | "independently_reconciled" | "consumer_asserted" | "institutionally_supplied" | "not_established";
  source_count?: number;
  target_count?: number;
};

export type EpochQualificationDisclosure = {
  appointment_state: string;
  appointment_would_establish: string;
  appointment_would_not_establish: Array<string>;
  authority_owner_ref?: null;
  authority_role: string;
  code: string;
  epoch_state: string;
  status: string;
};

export type EpochStalenessProjectionResponse = {
  meta: ApiMeta;
  projection: EpochStalenessProjectionView;
};

export type EpochStalenessProjectionView = {
  certificates?: Array<EpochCertificateStalenessView>;
  current_epoch_ref?: string | null;
  decision_packet_ref?: ArtifactRefOutput | null;
  decision_validity_status?: DecisionValidityStatus | null;
  denominator: EpochProjectionDenominatorView;
  dependencies?: Array<EpochDependencyStalenessView>;
  engineering_absences?: Array<EngineeringCapabilityAbsenceView>;
  fixture_only?: boolean;
  institutional_absences?: Array<InstitutionalAuthorityAbsenceView>;
  limitations?: Array<string>;
  lineage?: Array<EpochBoundaryLineageView>;
  observed_at: string;
  open_world_risk: EpochOpenWorldRiskView;
  owner_as_of?: string | null;
  owner_time_reason?: "owner_time_not_established" | "epoch_scope_unresolved" | null;
  perturbations?: Array<EpochPerturbationView>;
  predicate_provenance: "recomputed" | "independently_reconciled" | "consumer_asserted" | "institutionally_supplied" | "not_established";
  projection_semantic_hash: string;
  requested_query_context_ref: string;
  revalidation_required: boolean;
  run_id: string;
  schema_version?: string;
  scoped_epoch_refs?: Array<string>;
  status: "current" | "stale" | "revalidation_required" | "contested" | "not_established";
  temporal_scope: TemporalScope;
};

export type EpochValidityBatchReceipt = {
  adjudication_denominator_ref: string;
  affected_packet_refs: Array<string>;
  batch_id: string;
  claim_bridge_result_refs?: Array<ArtifactRefOutput>;
  completion_receipt_ref: ArtifactRefOutput;
  dependency_denominator_ref: string;
  requested_query_context_ref: string;
  schema_version?: string;
  state?: string;
  targets: Array<EpochValidityBatchTarget>;
  transition_artifact_ref: ArtifactRefOutput;
  transition_content_hash: string;
  verifier_provenance_ref: ArtifactRefOutput;
};

export type EpochValidityBatchRequest = {
  requested_query_context_ref: string;
  transition_artifact_ref: ArtifactRefInput;
};

export type EpochValidityBatchResponse = {
  affected_packet_refs?: Array<string>;
  batch_id: string;
  claim_bridge_result_refs?: Array<ArtifactRefOutput>;
  completion_receipt: EpochValidityBatchReceipt;
  meta: ApiMeta;
  state: string;
  transition: ArtifactRefOutput;
};

export type EpochValidityBatchTarget = {
  decision_lineage_key: string;
  dependency_key: string;
  packet_ref: string;
  reason: string;
  status: DecisionValidityStatus;
};

export type EquilibriumBasinInterval = {
  lower: number;
  upper: number;
};

export type EquilibriumBranch = {
  branch_id: string;
  notes?: Array<string>;
  points?: Array<EquilibriumBranchPoint>;
};

export type EquilibriumBranchPoint = {
  equilibrium_id: string;
  lambda: number;
};

export type EquilibriumCandidate = {
  basin_ci_95?: EquilibriumBasinInterval | null;
  basin_share_hat?: number | null;
  branch_id?: string | null;
  diagnostics?: {
  [key: string]: unknown;
};
  discovered_from_starts?: number;
  equilibrium_id: string;
  jacobian?: EquilibriumCandidateJacobian | null;
  local_stability?: "attractive" | "unstable" | "neutral_or_near_bifurcation" | "unknown";
  notes?: Array<string>;
  residual_norm?: number | null;
  state: FeedbackStateSnapshot;
  step_norm?: number | null;
};

export type EquilibriumCandidateJacobian = {
  condition_number?: number | null;
  near_bifurcation?: boolean;
  near_flip?: boolean;
  near_fold?: boolean;
  near_loss_of_stability?: boolean;
  operator_norm_inf?: number | null;
  smallest_singular_value_i_minus_j?: number | null;
  spectral_radius?: number | null;
};

export type EquilibriumMultiplicityDiagnostics = {
  branch_switch_events?: number;
  continuation_failures?: number;
  divergence_failures?: number;
  false_merge_risk?: number | null;
  max_pairwise_cluster_overlap?: number | null;
  notes?: Array<string>;
  num_attempts: number;
  num_converged: number;
  num_equilibria: number;
  num_unresolved?: number;
  stagnation_failures?: number;
  two_cycle_failures?: number;
  unresolved_starts_share?: number | null;
};

export type EquilibriumMultiplicityProvenance = {
  git_sha?: string;
  random_seed?: number | null;
  runtime_refs?: Array<string>;
  solver_version?: string;
};

export type EquilibriumMultiplicityReport = {
  basin_estimates?: Array<BasinEstimate>;
  bifurcation_candidates?: Array<BifurcationCandidate>;
  branches?: Array<EquilibriumBranch>;
  equilibria?: Array<EquilibriumCandidate>;
  global_diagnostics: EquilibriumMultiplicityDiagnostics;
  model_id: string;
  notes?: Array<string>;
  parameter_hash?: string | null;
  provenance?: EquilibriumMultiplicityProvenance;
  schema_version?: string;
  search_protocol: EquilibriumSearchProtocol;
  unresolved_starts?: Array<UnresolvedEquilibriumStart>;
};

export type EquilibriumSearchProtocol = {
  basin_draws?: number;
  continuation_grid?: Array<number>;
  continuation_parameter?: string | null;
  merge_tol?: number | null;
  mode?: "baseline" | "research" | "continuation";
  n_attempts: number;
  residual_tol?: number | null;
  start_domain?: {
  [key: string]: unknown;
};
};

export type EvaluatorReportView = {
  diagnostics?: Array<PreflightDiagnosticView>;
  notes?: Array<string>;
  reasons?: Array<string>;
  replanning_hints?: Array<string>;
  report_ref?: ArtifactRefOutput | null;
  scores?: EvaluatorScoresView;
  verdict?: "APPROVE" | "REPLAN_DATA" | "REPLAN_METHOD" | "REPLAN_PARAMS" | "STOP_BUDGET" | null;
};

export type EvaluatorScoresView = {
  budget_score?: number;
  constraints_score?: number;
  data_quality_score?: number;
  kpi_score?: number;
  total_score?: number;
  uncertainty_score?: number;
};

export type EvidenceAcquisitionNeeds = {
  needs?: Array<EvidenceNeed>;
};

export type EvidenceBasis = {
  calibration_refs?: Array<unknown>;
  counterexamples_closed?: Array<unknown>;
  method_refs?: Array<string>;
  producer_roots?: Array<unknown>;
};

export type EvidenceNeed = {
  artifact_ref?: string | null;
  need_id: string;
  question: string;
  required_for: string;
  source_hint?: string | null;
  status?: "required" | "satisfied" | "blocked";
};

export type ExecPlanRefInput = {
  artifact_id: ArtifactID;
  kind?: string;
  media_type?: string;
};

export type ExecPlanRefOutput = {
  artifact_id: string;
  kind?: string;
  media_type?: string;
};

export type ExecutionStatus = "prepared" | "started" | "executed" | "refused" | "unexecuted";

export type FabricDecisionData = {
  access: AccessRef;
  gaps?: Array<TypedGap>;
  id: string;
  kind?: "quantity" | "authored_text" | "fact" | "event" | "claim";
  lineage: polisyos__fabric__evidence__decision_data__LineageRef;
  metadata?: {
  [key: string]: unknown;
};
  quality: QualityRef;
  replay: ReplayRef;
  source_contract: SourceContractRef;
  time: polisyos__fabric__evidence__decision_data__TemporalRef;
  value: FabricQuantityValue | AuthoredText | {
  [key: string]: unknown;
};
};

export type FabricDecisionDataCoverage = {
  debug?: number;
  decision?: number;
  layout?: number;
  naked_decision_values?: number;
  telemetry?: number;
  total?: number;
  traced?: number;
  transitional_waivers?: number;
  untraced?: number;
};

export type FabricDecisionDataResponse = {
  coverage?: FabricDecisionDataCoverage;
  decision_data?: Array<FabricDecisionData>;
  meta: {
  [key: string]: unknown;
};
  run_id: string;
  source_kind: string;
  temporal_scope?: polisyos__fabric__evidence__decision_data__TemporalRef | null;
};

export type FabricImpactAnalysisRequest = {
  lineage_ids?: Array<string>;
  max_depth?: number;
  run_id?: string | null;
  source_contract_ids?: Array<string>;
  temporal_scope?: TemporalScope | null;
};

export type FabricImpactAnalysisResponse = {
  impacts?: Array<FabricImpactRecord>;
  meta: ApiMeta;
  summary?: {
  [key: string]: unknown;
};
  temporal_scope?: TemporalScope | null;
};

export type FabricImpactRecord = {
  affected_decision_data_ids?: Array<string>;
  downstream_refs?: Array<string>;
  evidence_refs?: Array<string>;
  lineage_status?: "verified" | "pending" | "disputed" | "untraced";
  notes?: Array<string>;
  quality_status?: string | null;
  replay_status?: string | null;
  source_contract_ids?: Array<string>;
  subject_id: string;
  subject_kind: "lineage" | "source_contract" | "run" | "decision_data";
  upstream_refs?: Array<string>;
};

export type FabricQualityBatchResponse = {
  coverage?: {
  [key: string]: unknown;
};
  meta: ApiMeta;
  quality_refs?: {
  [key: string]: {
  [key: string]: unknown;
};
};
  run_id: string;
  temporal_scope?: TemporalScope | null;
};

export type FabricQualityTrustBatchRequest = {
  decision_data_ids?: Array<string>;
  run_id: string;
  temporal_scope?: TemporalScope | null;
};

export type FabricQuantityValue = {
  label?: string | null;
  metric_id?: string | null;
  point?: number | null;
  semantic_type?: string | null;
  unit: polisyos__fabric__evidence__decision_data__UnitRef;
};

export type FabricReplayRunResponse = {
  coverage?: {
  [key: string]: unknown;
};
  meta: ApiMeta;
  replay_refs?: {
  [key: string]: {
  [key: string]: unknown;
};
};
  run_id: string;
  status_counts?: {
  [key: string]: number;
};
  temporal_scope?: TemporalScope | null;
};

export type FabricSourceScorecardsResponse = {
  count?: number;
  generated_at?: string | null;
  meta: ApiMeta;
  schema_version?: string;
  scorecards?: {
  [key: string]: {
  [key: string]: unknown;
};
};
};

export type FabricTrustBatchResponse = {
  coverage?: {
  [key: string]: unknown;
};
  meta: ApiMeta;
  run_id: string;
  temporal_scope?: TemporalScope | null;
  trust_refs?: {
  [key: string]: {
  [key: string]: unknown;
};
};
};

export type FeedbackActionResponse = {
  action: "evaluate_feedback" | "reissue";
  compare_report_ref?: ArtifactRefOutput | null;
  message: string;
  meta: ApiMeta;
  monitoring_report_ref?: ArtifactRefOutput | null;
  reissue_plan_ref?: ArtifactRefOutput | null;
  reissued_run_id?: string | null;
  run_id: string;
  status?: "completed" | "accepted";
};

export type FeedbackJacobianDiagnosticsRef = {
  artifact_id: ArtifactID;
  kind?: string;
  media_type?: string;
};

export type FeedbackResultRefInput = {
  artifact_id: ArtifactID;
  kind?: string;
  media_type?: string;
};

export type FeedbackResultRefOutput = {
  artifact_id: string;
  kind?: string;
  media_type?: string;
};

export type FeedbackStateSnapshot = {
  lower_bounds: Array<number | null>;
  notes?: Array<string>;
  scales: Array<number>;
  upper_bounds: Array<number | null>;
  values: Array<number>;
  variable_ids: Array<string>;
  weights: Array<number>;
};

export type FetchPlan = {
  connector_id: string;
  dataset_id: string;
  date_end?: string | null;
  date_start?: string | null;
  fallbacks?: Array<FetchPlanFallback>;
  filters?: {
  [key: string]: Array<string>;
};
  granularity?: string | null;
  max_preview_rows?: number;
  metadata?: {
  [key: string]: unknown;
};
  metric_id: string;
  persist_payload?: boolean;
  plan_id: string;
  profile_id?: string | null;
  quality_min?: number;
  source_lane?: "fastlane" | "explorelane" | "catalog";
};

export type FetchPlanFallback = {
  connector_id: string;
  dataset_id: string;
  filters?: {
  [key: string]: Array<string>;
};
  metadata?: {
  [key: string]: unknown;
};
  metric_id?: string | null;
  profile_id?: string | null;
};

export type FetchPreview = {
  completeness?: number;
  connector_id: string;
  coverage_ok?: boolean;
  dataset_id: string;
  latency_ms?: number | null;
  message?: string | null;
  quality_flags?: Array<string>;
  quality_min?: number;
  row_count?: number;
  sample_rows?: Array<{
  [key: string]: unknown;
}>;
  schema?: {
  [key: string]: unknown;
};
  status?: "ok" | "insufficient_coverage" | "error";
};

export type FiveRightsCheck = {
  right_decision: boolean;
  right_format_channel: boolean;
  right_information: boolean;
  right_person: boolean;
  right_time: boolean;
  schema_version?: string;
};

export type FiveRightsRequirement = {
  right_decision: string;
  right_format_channel: string;
  right_information: string;
  right_person: string;
  right_time: string;
  schema_version?: string;
};

export type ForkBRelationCensusPayload = {
  authority: string;
  certificate_summaries: {
  [key: string]: ProjectionJsonValue;
};
  coverage_manifest: {
  [key: string]: ProjectionJsonValue;
};
  known_bridge_limits: Array<string>;
  normalization: string;
  relation_counts: {
  [key: string]: number;
};
  relation_denominator_formula: string;
  transport_floor: number;
  transport_floor_rule: string;
};

export type GapClass = "data_gap" | "structural_gap" | "not_established";

export type GenerationCycleDispositionPayload = {
  bridge_artifacts: {
  [key: string]: ProjectionJsonValue;
};
  known_residuals: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  method_availability_gate: {
  [key: string]: ProjectionJsonValue;
};
  owners: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  parallel_world_reconciliation: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  task_owner_mapping: {
  [key: string]: ProjectionJsonValue;
};
  tasks: {
  [key: string]: ProjectionJsonValue;
};
};

export type GitInfo = {
  commit: string;
  dirty?: boolean;
};

export type GoodEventPosture = {
  composition_rule?: string;
  executed_probabilistic_good_event_refs: Array<string>;
  good_event_clause: string;
  independence_claim?: boolean;
};

export type GovernanceDebugResponse = {
  debug: GovernanceDebugView;
  meta: ApiMeta;
};

export type GovernanceDebugView = {
  contract_warnings?: Array<string>;
  decision_validity?: {
  [key: string]: unknown;
} | null;
  fallback_from_decision_packet?: boolean;
  issue_summary?: {
  [key: string]: number;
} | null;
  issues?: Array<{
  [key: string]: unknown;
}>;
  legal_executed?: boolean | null;
  links?: {
  [key: string]: ArtifactRefOutput | null;
} | null;
  normative_arbitration_result_ref?: ArtifactRefOutput | null;
  normative_summary?: {
  [key: string]: unknown;
} | null;
  notes?: Array<string>;
  report_kind?: string | null;
  report_ref?: ArtifactRefOutput | null;
  report_schema_version?: string | null;
  run_id: string;
  source_kind: string;
  transport_summary?: {
  [key: string]: unknown;
} | null;
  validation_trace?: {
  [key: string]: unknown;
} | null;
  verdict?: string | null;
};

export type GuardedProjectionId = "confidence-ledger-risk-spend";

export type HTTPValidationError = {
  detail?: Array<ValidationError>;
};

export type HistoricalDS4Disposition = {
  counts: {
  [key: string]: number;
};
  denominator: number;
  source_class?: string;
  source_content_hash: string;
  source_ref: string;
};

export type HistoricalProducerAvailability = {
  counts: {
  [key: string]: number;
};
  environment_absence?: string;
  measurement_scope?: string;
  source_content_hash: string;
  source_ref: string;
};

export type HumanDecisionAllowedDecision = {
  action: "request_evidence" | "approve" | "reject" | "revise_scope" | "escalate";
  decision_modes: Array<"ordinary" | "override" | "blocking">;
};

export type HumanDecisionCanonicalActor = {
  actor_ref: string;
  audience: string;
  issuer: string;
  signed_roles: Array<string>;
  signing_key_id: string;
  subject: string;
  tenant_id: string;
};

export type HumanDecisionContestabilitySurface = {
  case_id: string;
  href: string;
  source_ref: string;
};

export type HumanDecisionCreateResponse = {
  durable_event_id: string;
  record: HumanDecisionRecord;
  record_digest: string;
  record_ref: string;
  reservation_id: string;
  reservation_version: number;
  run_id: string;
};

export type HumanDecisionExposureSurface = {
  channel?: string | null;
  completed_artifact_digests: Array<string>;
  exposure_session_ref?: string | null;
  renderer_id?: string | null;
  renderer_version?: string | null;
  representation?: "full" | "redacted" | "truncated" | null;
  required_artifact_digests: Array<string>;
};

export type HumanDecisionFiveRightsBinding = {
  decision_class_id: string;
  decision_rights_matrix_ref: string;
  required_channel: "reviewer_console" | "governed_review";
  required_information_refs?: Array<string>;
  required_representation: string;
  required_role: "principal" | "mandate_owner" | "legal_approver" | "budget_owner" | "data_steward" | "affected_person_representative" | "domain_expert" | "governance_board" | "policy_design_governance_reviewer" | "technical_reviewer";
  schema_version?: string;
  time_rule: string;
};

export type HumanDecisionGateReason = {
  code: string;
  message: string;
  status: "invalid_source" | "artifact_missing" | "producer_missing" | "revalidation_required" | "blocked" | "available";
};

export type HumanDecisionGateResponse = {
  contestability?: HumanDecisionContestabilitySurface | null;
  continuation?: HumanDecisionPA2ReplaySelector | HumanDecisionProductionReplaySelector | null;
  decision_request?: HumanDecisionRequestSurface | null;
  decision_request_digest?: string | null;
  decision_request_ref: string | null;
  exposure: HumanDecisionExposureSurface;
  governed_action_key?: string | null;
  mandate?: HumanDecisionMandateSurface | null;
  operational_authority?: boolean;
  reason_codes: Array<string>;
  reasons: Array<HumanDecisionGateReason>;
  resolved_at: string;
  run_id: string;
  source_kind: "agent_action_authority" | "production_approval";
  source_ref?: string | null;
  status: "invalid_source" | "artifact_missing" | "producer_missing" | "revalidation_required" | "blocked" | "available";
  submission?: HumanDecisionSubmissionSurface | null;
  tenant_id: string;
  verifier_epoch: string;
};

export type HumanDecisionMandateSurface = {
  action_kind: string;
  mandate_owner_ref: string;
  mandate_record_ref: string;
  operation_id: string;
  valid_from: string;
  valid_until: string;
};

export type HumanDecisionMutationRequest = {
  accountability_statement: string;
  action: "request_evidence" | "approve" | "reject" | "revise_scope" | "escalate";
  action_kind?: string | null;
  basis_digest?: string | null;
  basis_ref?: string | null;
  blocking_reason?: string | null;
  decision_mode: "ordinary" | "override" | "blocking";
  decision_request_digest?: string | null;
  decision_request_ref?: string | null;
  dissent_statement: string;
  override_reason?: string | null;
  presentation_contract_ref?: string | null;
  principal_binding_ref?: string | null;
  production_packet_ref?: string | null;
  reviewer_separation_ref?: string | null;
  source_kind: "agent_action_authority" | "production_approval";
  source_ref?: string | null;
};

export type HumanDecisionPA2ReplaySelector = {
  action_kind: string;
  basis_digest: string;
  basis_ref: string;
  decision_request_digest: string;
  decision_request_ref: string;
  exposure_session_ref: string;
  operational_authority?: boolean;
  presentation_contract_ref: string;
  principal_binding_ref: string;
  reviewer_separation_ref: string;
  source_kind: string;
  source_ref: string;
};

export type HumanDecisionPredicateReceipt = {
  evidence_refs: Array<string>;
  predicate: "identity_permission" | "role_mandate_or_basis" | "operation_accountability" | "currentness" | "right_decision_time" | "reviewer_independence_change" | "evidence_exposure" | "presentation_format_channel" | "source_producer_trust";
  provenance: "recomputed" | "independently_reconciled";
  reason: string;
  reason_code: string;
  rule_version_ref: string;
  satisfied: boolean;
};

export type HumanDecisionProductionReplaySelector = {
  basis_digest: string;
  basis_ref: string;
  decision_request_digest: string;
  decision_request_ref: string;
  exposure_session_ref: string;
  operational_authority?: boolean;
  presentation_contract_ref: string;
  principal_binding_ref: string;
  reviewer_separation_ref: string;
  source_kind: string;
  source_ref: string;
};

export type HumanDecisionRecord = {
  accountability_statement: string;
  active_choice: boolean;
  actor_ref: string;
  actor_role: "principal" | "mandate_owner" | "legal_approver" | "budget_owner" | "data_steward" | "affected_person_representative" | "domain_expert" | "governance_board" | "policy_design_governance_reviewer" | "technical_reviewer";
  authority_boundary: AuthorityBoundary;
  basis_digest?: string | null;
  basis_ref?: string | null;
  binding_sha256?: string | null;
  blocking_reason?: string | null;
  canonical_actor?: HumanDecisionCanonicalActor | null;
  case_id: string;
  created_at?: string;
  custody_boundary?: AuthorityBoundary | null;
  custody_key_id?: string | null;
  custody_signer_identity?: string | null;
  decided_at: string;
  decision_action_exercised: "request_evidence" | "approve" | "reject" | "revise_scope" | "escalate";
  decision_attempt_id?: string | null;
  decision_mode?: "ordinary" | "override" | "blocking" | null;
  decision_request_digest?: string | null;
  disconfirming_evidence_refs: Array<string>;
  dissent_statement?: string | null;
  evidence_summary_ref: string;
  exposure_artifact_digests?: Array<string> | null;
  exposure_event_refs?: Array<string> | null;
  exposure_session_digest?: string | null;
  exposure_session_ref?: string | null;
  five_rights_check: FiveRightsCheck;
  governed_action_key?: string | null;
  human_decision_request_ref: string;
  mandate_record_ref: string;
  mandate_source_refs?: Array<string>;
  observed_at?: string | null;
  override_reason?: string | null;
  predicate_receipts?: Array<HumanDecisionPredicateReceipt> | null;
  presentation_contract_digest?: string | null;
  presentation_contract_ref?: string | null;
  principal_binding_digest?: string | null;
  principal_binding_ref?: string | null;
  provenance_refs?: Array<string>;
  record_id: string;
  record_ref: string;
  recorded_at?: string | null;
  requested_at?: string | null;
  reservation_id?: string | null;
  reservation_version?: number | null;
  responsibility_integrity: ResponsibilityIntegrityCheck;
  reviewer_separation_digest?: string | null;
  reviewer_separation_ref?: string | null;
  rule_version_ref: string;
  run_id?: string | null;
  schema_version: "policyos.policy_design_case.layer2_s7_delegation.v1" | "policyos.runtime.human_decision_record.v2";
  source_digest?: string | null;
  source_kind?: "agent_action_authority" | "production_approval" | null;
  source_ref?: string | null;
  tenant_id?: string | null;
  valid_from?: string | null;
  valid_until?: string | null;
  verifier_epoch?: string | null;
};

export type HumanDecisionRequestSurface = {
  available_actions: Array<"request_evidence" | "approve" | "reject" | "revise_scope" | "escalate">;
  case_id: string;
  decidable_until?: string | null;
  decision_due_at?: string | null;
  decision_rights_matrix_ref: string;
  delegation_contract_ref: string;
  five_rights_binding: HumanDecisionFiveRightsBinding;
  five_rights_requirements: FiveRightsRequirement;
  requested_at: string;
  required_role: "principal" | "mandate_owner" | "legal_approver" | "budget_owner" | "data_steward" | "affected_person_representative" | "domain_expert" | "governance_board" | "policy_design_governance_reviewer" | "technical_reviewer";
};

export type HumanDecisionReviewEffectivenessResponse = {
  advisory_signal_codes: Array<string>;
  approval_count: number;
  audit_predicate_provenance?: string;
  audit_read_error_count: number;
  authoritative_for?: Array<"review_effectiveness_measurement" | "future_policy_calibration" | "reviewer_load_observability">;
  authorization_allow_count: number;
  blocking_count: number;
  blocking_permitted?: boolean;
  candidate_human_decision_count: number;
  completed_human_decision_count: number;
  coverage_claim_scope?: string;
  coverage_status: "complete" | "incomplete";
  dissent_count: number;
  duplicate_authorization_request_count: number;
  duplicate_record_event_count: number;
  duplicate_record_request_count: number;
  exact_join_count: number;
  invalid_authorization_event_count: number;
  invalid_record_event_count: number;
  malformed_json_line_count: number;
  may_not_use_for?: Array<"current_run_closeout_block" | "publication_block" | "claim_support_downgrade" | "authorization_writer_provenance" | "forensic_tamper_detection">;
  measurement_status?: string;
  nonblank_line_count: number;
  nonobject_line_count: number;
  override_count: number;
  parsed_object_count: number;
  report_status_effect?: string;
  retained_or_missing_record_count: number;
  review_count: number;
  review_posture?: string;
  review_time_established_count?: number;
  review_time_not_established_count: number;
  review_time_status?: string;
  reviewer_independence_rate?: number | null;
  run_id: string;
  schema_version?: string;
  separation_of_duty_attestation_rate?: number | null;
  tenant_scope_unknown_record_event_count: number;
  threshold_scope?: string;
  threshold_status: "pass" | "warn" | "fail";
  trail_path_exists: boolean;
  unmatched_authorization_count: number;
  unmatched_record_event_count: number;
};

export type HumanDecisionSubmissionSurface = {
  allowed_decisions: Array<HumanDecisionAllowedDecision>;
  operational_authority?: boolean;
  selector: HumanDecisionPA2ReplaySelector | HumanDecisionProductionReplaySelector;
};

export type IndexStats = {
  docs_added_last_run?: number;
  index_docs_total?: number;
  index_size_bytes?: number;
  indexed_sources?: number;
  last_updated?: string | null;
  source_coverage?: {
  [key: string]: number;
};
};

export type IndexStatsResponse = {
  meta: ApiMeta;
  stats: IndexStats;
};

export type IngestRequest = {
  binding_profile_id?: string | null;
  cache_policy?: string;
  connection_profile?: string | null;
  datasets?: Array<DatasetFetchSpecRequest>;
  execution_mode?: "batch_full" | "batch_incremental" | "streaming_windowed";
  fetch_plans?: Array<FetchPlan>;
  license_name?: string;
  produce_data_snapshot?: boolean;
  produce_input_bindings?: boolean;
  record_mode?: boolean;
  replay_ref?: string | null;
  source?: string;
};

export type IngestResponse = {
  cursor_ref?: string | null;
  data_snapshot_ref?: string | null;
  datasets_fetched?: number;
  evidence_bundle_ref?: string | null;
  input_bindings_ref?: string | null;
  message: string;
  meta: ApiMeta;
  mode_effective?: string | null;
  record_ref?: string | null;
  status: "completed" | "partial" | "failed";
  warnings?: Array<string>;
};

export type InputRef = {
  artifact_id: string;
  role: string;
};

export type InstitutionalAuthorityAbsenceView = {
  absence_class?: string;
  appointment_is_closure_precondition?: boolean;
  authority_purpose: string;
  capability_state?: string;
  closure_condition: string;
  consequence: string;
  inspectable_capabilities?: Array<string>;
  observed_result?: string;
  predicate_provenance?: string;
  refusal_code: "policy_admission_missing" | "epoch_transition_signer_not_established";
  role: "epoch_predicate_policy_signer" | "epoch_transition_signer";
  source_refs?: Array<ArtifactRefOutput>;
  title?: string;
};

export type InstrumentBlocker = "coverage_argument_missing" | "non_anytime_valid" | "owner_theorem_unavailable" | "other_runtime_refusal";

export type InstrumentClassSpend = {
  instrument_id: string;
  obligation_class: PromotionObligationClass;
  spend: ConditionalDeltaAmount;
};

export type InstrumentDefinition = {
  certificate_roles: Array<CertificateRole>;
  instrument_family: string;
  instrument_id: string;
  proof_profile_id: string;
};

export type InstrumentDefinitionRow = {
  anytime_valid: boolean;
  blocker: InstrumentBlocker | null;
  certificate_roles: Array<"promotion" | "promotion_conformance" | "refusal" | "acquisition" | "admission">;
  deterministic: boolean;
  guarantee_kind: string;
  instrument_family: string;
  instrument_id: string;
  permits_obligation_satisfaction: boolean;
  proof_kernel_id: string;
  proof_profile_id: string;
};

export type InstrumentInstanceRow = {
  anytime_valid: boolean;
  blocker: InstrumentBlocker | null;
  certificate_class: string | null;
  certificate_ref: string;
  certificate_role: "promotion" | "promotion_conformance" | "refusal" | "acquisition" | "admission";
  certificate_route_ref: string | null;
  eligible_for_promotion: boolean;
  execution_status: "prepared" | "started" | "executed" | "refused" | "unexecuted";
  instance_ref: string;
  instrument_family: string;
  instrument_id: string;
  obligation_class: PromotionObligationClass;
  outcome: "prepared" | "started" | "supported" | "not_supported" | "preflight_refusal" | "cancelled" | "owner_refused" | "owner_error" | "recovered_crash" | "refused";
  proof_profile_id: string;
  raw_runtime_refusal_source: string | null;
  spend: ConditionalDeltaAmount;
  supports_obligation: boolean;
};

export type InstrumentProofProfile = {
  anytime_valid: boolean;
  deterministic: boolean;
  guarantee_kind: string;
  permits_obligation_satisfaction: boolean;
  profile_id: string;
  proof_kernel_id: string;
  refusal_code?: string | null;
};

export type InvalidConfidenceLedgerRiskSpendPacket = {
  absence_reason: string;
  as_of: string;
  authoritative_for?: Array<"conditionality_disclosure" | "declared_set_accounting" | "source_validation_posture">;
  availability: string;
  export_replay_contract?: string;
  freshness: ProjectionFreshness;
  intended_audience?: string;
  intended_audiences?: Array<unknown>;
  may_not_use_for?: Array<"promotion_authority" | "publication_authority" | "public_audience" | "bounded_completeness">;
  packet_schema_version?: string;
  projection_hash?: null;
  projection_id?: string;
  projection_rule_version?: string;
  replay_address?: null;
  replay_pins?: null;
  source_artifact_content_hash?: string | null;
  source_blocked_reason?: null;
  source_dependency_hash?: null;
  source_rule_version: string | null;
  source_schema_version: string | null;
  stable_address?: string;
  worker_validation_receipt_hash?: string | null;
  worker_validation_receipt_ref?: string | null;
};

export type InvalidGovernedProjectionPacket = {
  absence_reason: string;
  as_of: string;
  authoritative_for: Array<string>;
  availability: string;
  export_replay_contract?: string;
  freshness: ProjectionFreshness;
  intended_audience: AudienceClass;
  may_not_use_for: Array<string>;
  packet_schema_version?: string;
  payload?: null;
  projection_hash?: null;
  projection_id: ProjectionId;
  projection_rule_version?: string;
  replay_address?: null;
  source: ProjectionSourceIdentity;
  source_dependency_hash?: null;
  source_rule_version?: string | null;
  source_schema_version?: string | null;
  stable_address: string;
};

export type IterationLifecycleView = {
  iteration?: number;
  last_verdict?: "APPROVE" | "REPLAN_DATA" | "REPLAN_METHOD" | "REPLAN_PARAMS" | "STOP_BUDGET" | null;
  notes?: Array<string>;
  state?: "plan_created" | "preflight_running" | "preflight_failed" | "ready_to_run" | "executing" | "evaluating" | "replanning" | "approved" | "stopped_budget" | "stopped_no_delta" | "stopped_guardrail";
  state_ref?: ArtifactRefOutput | null;
  stop_reason?: "approved" | "budget_exhausted" | "no_delta" | "guardrail_violation" | null;
};

export type JurisdictionTimeSemantics = {
  as_of: string;
  data_time: string;
  policy_time: string;
  region: string;
  time_semantics?: TimeSemantics | null;
  valid_time: string;
};

export type Layer3HealthMetricsPayload = {
  health_metric_ledgers: Array<{
  [key: string]: ProjectionJsonValue;
}>;
};

export type LegacyProvingGroundPayload = {
  fixture_authority?: string;
  fixture_identities: Array<ProvingGroundFixtureIdentity>;
  fixture_records: Array<ProvingGroundFixtureRecord>;
  runtime_outcomes: ProvingGroundRuntimeOutcomes;
};

export type LexGraphStatsResponse = {
  db_exists?: boolean;
  meta: ApiMeta;
  top_entity_types?: Array<{
  [key: string]: unknown;
}>;
  top_predicates?: Array<{
  [key: string]: unknown;
}>;
  total_entities?: number;
  total_facts?: number;
  total_provisions?: number;
};

export type LexPipelineStageConfig = {
  embed?: boolean;
  graph?: boolean;
  parse?: boolean;
  spo?: boolean;
  structure?: boolean;
};

export type LexPipelineStatusResponse = {
  error_message?: string | null;
  meta: ApiMeta;
  pipeline_id: string;
  progress_summary?: {
  [key: string]: number;
};
  state: "pending" | "running" | "completed" | "failed";
};

export type LexSearchRequest = {
  output_dir: string;
  query: string;
  top_k?: number;
};

export type LexSearchResponse = {
  meta: ApiMeta;
  query: string;
  results?: Array<LexSearchResultItem>;
  total?: number;
};

export type LexSearchResultItem = {
  action_canon?: string;
  audit_miss_prone?: boolean;
  canonical_status?: "canonicalized" | "partially_canonicalized" | "raw";
  condition_text_uk?: string;
  confidence: number;
  confidence_breakdown_json?: string;
  consistency_score?: number | null;
  constraint_type_canon?: string;
  doc_family_id?: string;
  doc_id?: string;
  doc_name: string;
  doc_reestr_code: string;
  effective_from?: string;
  effective_to?: string;
  empty_spo_retry_eligible?: boolean;
  exception_text_uk?: string;
  fact_id: string;
  fact_text: string;
  fused_confidence?: number | null;
  grounding_status?: "exact_quote" | "quote_without_offsets" | "offsets_without_quote" | "missing_quote";
  hallucination_flags_json?: string;
  jurisdiction?: string;
  legal_unit_subtype?: string;
  norm_type: string;
  norm_type_canon?: string;
  object_name: string;
  predicate: string;
  procedure_text_uk?: string;
  provision_anchor?: string;
  provision_citation: string;
  quality_band?: string;
  reference_bearing?: boolean;
  reference_resolution_status?: "resolved" | "partial" | "unresolved" | "not_applicable";
  route_class?: string;
  similarity: number;
  source_quote_uk?: string;
  structure_quality?: string;
  subject_name: string;
  temporal_confidence?: number | null;
  temporal_provenance_json?: string;
  temporal_resolution_status?: string;
  temporal_source_kind?: string;
  temporal_source_scope?: string;
  temporal_state?: string;
  threshold_bearing?: boolean;
  thresholds_json?: string;
  top_domain?: string;
  trust_tier?: "search_candidate" | "grounded_fact" | "normative_fact";
  version_id?: string;
};

export type LexTriggerRequest = {
  cards_path: string;
  execution_profile?: "dev" | "research" | "governed" | "production" | null;
  llm_model?: string;
  output_dir: string;
  policy_flags?: PolicyFlags;
  resume?: boolean;
  stages?: LexPipelineStageConfig;
  status_filter?: Array<string> | null;
  texts_path: string;
};

export type LexTriggerResponse = {
  effective_execution_profile: "dev" | "research" | "governed" | "production";
  job_id: string;
  message: string;
  meta: ApiMeta;
  pipeline_id: string;
  status: "accepted" | "rejected";
};

export type LineageBatchRequest = {
  lineage_ids?: Array<string>;
};

export type LineageBatchResponse = {
  lineages?: Array<LineageGraphView>;
  meta: ApiMeta;
  temporal_scope?: TemporalScope | null;
};

export type LineageCompactSummaryItem = {
  id?: string | null;
  kind?: "source" | "transform" | "model" | "agent" | "result" | "artifact" | "dataset" | "method" | "unknown";
  label: string;
};

export type LineageDelta = {
  freshness_changed?: boolean;
  hash_changed?: boolean;
  model_changed?: boolean;
  notes?: Array<string>;
  source_changed?: boolean;
  verification_changed?: string | null;
};

export type LineageExportLinks = {
  openlineage: string;
  prov: string;
};

export type LineageExportResponse = {
  format: "openlineage" | "prov";
  lineage_id: string;
  meta: ApiMeta;
  payload: {
  [key: string]: unknown;
};
  temporal_scope?: TemporalScope | null;
};

export type LineageGraphEdge = {
  metadata?: {
  [key: string]: unknown;
};
  relation: string;
  source_id: string;
  target_id: string;
};

export type LineageGraphNode = {
  id: string;
  kind?: string;
  label: string;
  metadata?: {
  [key: string]: unknown;
};
  timestamp?: string | null;
};

export type LineageGraphView = {
  compact_summary?: Array<LineageCompactSummaryItem>;
  edges?: Array<LineageGraphEdge>;
  exports: LineageExportLinks;
  freshness?: "current" | "stale" | "unknown";
  hash?: string | null;
  id: string;
  metadata?: {
  [key: string]: unknown;
};
  nodes?: Array<LineageGraphNode>;
  status?: "verified" | "pending" | "disputed" | "untraced";
  trust_metadata?: VerificationMetadata | null;
};

export type LineageRefInput = {
  compact_summary?: Array<LineageCompactSummaryItem>;
  freshness?: "current" | "stale" | "unknown";
  hash?: string | null;
  id: string;
  reason_code?: string | null;
  status?: "verified" | "pending" | "disputed" | "untraced";
  summary?: {
  [key: string]: string;
};
  tracking_issue?: string | null;
  trust_metadata?: VerificationMetadata | null;
};

export type LineageResponse = {
  lineage: LineageGraphView;
  meta: ApiMeta;
  temporal_scope?: TemporalScope | null;
};

export type MetricCandidate = {
  candidate_id: string;
  confidence?: number;
  connector_id: string;
  coverage_estimate?: number | null;
  dataset_id: string;
  filters_template?: {
  [key: string]: Array<string>;
};
  freshness_score?: number;
  latency_estimate_ms?: number | null;
  match_reason?: string;
  metadata?: {
  [key: string]: unknown;
};
  metric_id: string;
  profile_id?: string | null;
  rank?: number;
  source_lane?: "fastlane" | "explorelane" | "catalog";
  trust_score?: number;
};

export type MobilityBoundsRequest = {
  column_marginals?: Array<number> | null;
  headline_metric?: string;
  metadata?: {
  [key: string]: unknown;
};
  observed_joint_matrix: Array<Array<number>>;
  persist_artifact?: boolean;
  row_marginals: Array<number>;
};

export type MobilityBoundsResponse = {
  bounds: {
  [key: string]: unknown;
};
  bounds_bundle_ref?: ArtifactRefOutput | null;
  cell_bounds?: {
  [key: string]: Array<number>;
};
  meta: ApiMeta;
  mobility_report_ref?: ArtifactRefOutput | null;
  summary_bounds?: {
  [key: string]: Array<number>;
};
};

export type MobilityDiagnosticsResponse = {
  diagnostics: {
  [key: string]: unknown;
};
  meta: ApiMeta;
  mobility_report_ref: ArtifactRefOutput;
};

export type MobilityEstimateRequest = {
  attrition_features?: Array<Array<number>> | null;
  attrition_features_by_wave?: Array<Array<Array<number>>> | null;
  compute_bounds?: boolean;
  destination_classes?: Array<number | null>;
  destination_marginals?: Array<number> | null;
  estimator?: "ipcw" | "aipw";
  feature_names?: Array<string>;
  metadata?: {
  [key: string]: unknown;
};
  mode?: "complete_case" | "attrition_adjusted" | "sequential_attrition_adjusted" | "refreshment_anchored";
  monotone?: boolean;
  n_classes?: number;
  origin_classes?: Array<number>;
  panel_length?: number | null;
  persist_artifact?: boolean;
  positivity_floor?: number;
  refreshment_destination_classes?: Array<number> | null;
  refreshment_weights?: Array<number> | null;
  retention_indicators?: Array<number> | null;
  retention_indicators_by_wave?: Array<Array<number>> | null;
  retention_probabilities?: Array<number> | null;
  retention_probabilities_by_wave?: Array<Array<number>> | null;
  sample_weights?: Array<number> | null;
  waves_used?: Array<number>;
};

export type MobilityEstimateResponse = {
  bounds_bundle_ref?: ArtifactRefOutput | null;
  meta: ApiMeta;
  mobility_report_ref?: ArtifactRefOutput | null;
  report: {
  [key: string]: unknown;
};
};

export type MobilityReportResponse = {
  meta: ApiMeta;
  mobility_report_ref: ArtifactRefOutput;
  report: {
  [key: string]: unknown;
};
};

export type ModelProfileInfo = {
  base_url: string;
  capabilities?: Array<string>;
  description?: string;
  display_name: string;
  enabled?: boolean;
  input_cost_per_mtoken_usd?: number | null;
  model_id: string;
  output_cost_per_mtoken_usd?: number | null;
  profile_id: string;
  provider: string;
  tags?: Array<string>;
};

export type ModelProfilesListResponse = {
  meta: ApiMeta;
  profiles?: Array<ModelProfileInfo>;
};

export type MonitoredMetric = {
  baseline_value: number;
  confirm_range: MonitoringRange;
  metadata?: {
  [key: string]: unknown;
};
  metric_id: string;
  min_observations?: number;
  recalibration_target?: boolean;
  refute_range: MonitoringRange;
  source_metric_id: string;
  weight?: number;
  window?: MonitoringWindow;
};

export type MonitoringMetricResult = {
  actual_value?: number | null;
  baseline_value: number;
  delta?: number | null;
  metadata?: {
  [key: string]: unknown;
};
  metric_id: string;
  observed_count?: number;
  reason?: string | null;
  recalibration_target?: boolean;
  source_metric_id: string;
  verdict?: MonitoringVerdict;
};

export type MonitoringRange = {
  lower?: number | null;
  upper?: number | null;
};

export type MonitoringVerdict = "pending" | "confirmed" | "refuted" | "inconclusive" | "insufficient_data" | "degraded";

export type MonitoringWindow = {
  end_offset_days?: number;
  grace_days?: number;
  start_offset_days?: number;
};

export type N13AAcquisitionCensusPayload = {
  catalog_identity: {
  [key: string]: ProjectionJsonValue;
};
  family_scorecards: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  fetch_plan_generation: {
  [key: string]: ProjectionJsonValue;
};
  growth_backlog: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  metric_resolutions: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  projection_bindings: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  reverse_demand_residuals: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  route_evidence: Array<{
  [key: string]: ProjectionJsonValue;
}>;
};

export type N13ALiveProbeJournalPayload = {
  family_receipts: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  records: Array<{
  [key: string]: ProjectionJsonValue;
}>;
  selection_plan: {
  [key: string]: ProjectionJsonValue;
};
};

export type N13bHistoryProjection = {
  admission: "not_reached" | "not_established";
  attempt_count: number;
  epoch_qualification: EpochQualificationDisclosure;
  execution_phase: "executing" | "terminal";
  overlay_epoch_count: number;
  quarantine: "none" | "raw_terminal";
  quarantine_count: number;
  raw_response_count: number;
  reentry: "not_established" | "deeper_terminal";
  response_admitted_count: number;
  terminal_count: number;
  world_growth: "not_established" | "no_growth";
};

export type NLProvenance = {
  raw_request: string;
  source_context?: {
  [key: string]: unknown;
};
  source_surface: string;
};

export type NaturalLanguageRunRequest = {
  checkpoint_policy?: "strict" | "lenient" | "disabled";
  context?: {
  [key: string]: unknown;
};
  data_source?: DataSourceBinding | null;
  domain_hint?: string | null;
  execution_plan?: {
  [key: string]: unknown;
} | null;
  execution_plan_ref?: string | null;
  execution_profile?: "dev" | "research" | "governed" | "production" | null;
  expected_outputs?: Array<{
  [key: string]: unknown;
}>;
  governance_constraints?: Array<{
  [key: string]: unknown;
}>;
  llm_model?: string | null;
  llm_models?: Array<string> | null;
  max_iterations?: number;
  max_parallel_models?: number;
  per_model_budget_usd?: number | null;
  policy_flags?: PolicyFlags;
  request: string;
  run_budget_usd?: number | null;
  stop_criteria?: {
  [key: string]: unknown;
};
};

export type NodeDebugResponse = {
  debug: NodeDebugView;
  meta: ApiMeta;
};

export type NodeDebugView = {
  alias: string;
  cache_bypasses?: number;
  cache_hits?: number;
  cache_stores?: number;
  notes?: Array<string>;
  record: RunNodeRecord;
  run_id: string;
  source_kind: string;
  timeline_events?: Array<RunTimelineEvent>;
};

export type ObligationBudgetPool = {
  obligation_classes: Array<PromotionObligationClass>;
  pool_id: string;
  weight: RationalSpec;
};

export type ObligationClassRiskSpend = {
  allocation: ConditionalDeltaAmount;
  check_refs: Array<string>;
  good_event_refs: Array<string>;
  instrument_refs: Array<string>;
  obligation_class: PromotionObligationClass;
  overspend_amount: ConditionalDeltaAmount;
  remaining: ConditionalDeltaAmount;
  spent: ConditionalDeltaAmount;
};

export type ObligationCoverageEnvelope = {
  assessment: CoverageAssessment;
  assessment_key: string;
  authoritative_for: Array<"conditionality_disclosure" | "declared_set_accounting">;
  authority_purpose: string;
  authorized_audiences: Array<"reviewer" | "expert" | "machine">;
  challenge_route_state: string;
  declared_obligation_classes: Array<PromotionObligationClass>;
  declared_scope: ConfidenceRiskBudgetScope;
  declared_set_rider: string;
  delta: RationalSpec;
  envelope_hash: string;
  envelope_ref: string;
  exclusion_basis_state?: string;
  exclusions?: Array<unknown>;
  expiry_state: string;
  locality_rider: string;
  maintained_assumptions: Array<"obligation_completeness" | "validator_soundness">;
  may_not_use_for: Array<"promotion_authority" | "publication_authority" | "bounded_completeness" | "world_completeness">;
  obligation_language_version: string;
  obligation_rule_ref: string;
  obligation_schema_ref: string;
  owner_scope_key: string;
  protected_action_id: string;
  reason_codes: Array<CoverageReasonCode>;
  review_state: string;
  rule_version: string;
  schema_version: string;
  scope_id: string;
  search_basis_state?: string;
  searched_sources?: Array<unknown>;
  source_cutoff_state: string;
  source_identities: Array<unknown>;
  ttl_state: "not_issued_known_incomplete" | "not_issued_open_world_unresolved";
  unknown_remainder: CoverageUnknownRemainder;
  witness_refs: Array<string>;
};

export type OperatorDiagnostic = {
  authoritative_runtime_state: string;
  authority_refs?: {
  [key: string]: string;
};
  blocker_overridable?: boolean;
  downstream_impact: string;
  evidence_refs?: Array<string>;
  first_blocking_cause: string;
  next_diagnostic_command: string;
  owner: string;
  phase: string;
  projection_labels?: Array<OperatorProjectionStateLabel>;
  projection_source: string;
  upstream_missing_input?: string | null;
};

export type OperatorProjectionStateLabel = {
  authority: "runtime_authority" | "projection_only";
  label: string;
  state: "draft" | "projection_only" | "redacted" | "stale" | "contested" | "projected" | "blocked" | "readiness_closed" | "approved" | "rejected" | "published_blocked" | "publishable";
};

export type OutcomeOfInterest = {
  direction?: "maximize" | "minimize" | "maintain_range";
  estimand: string;
  metric_id: string;
  target_variable: string;
};

export type PolicyDesignCaseAudience = "public" | "reviewer" | "expert" | "machine";

export type PolicyDesignCaseCloseoutTruth = {
  blocker_codes?: Array<string>;
  blockers?: Array<PolicyDesignCaseProjectionBlocker>;
  can_closeout: boolean;
  contested_state?: string;
  limitation_codes?: Array<string>;
  omission_codes?: Array<string>;
  status: string;
  verdict: string;
};

export type PolicyDesignCaseContestedRecord = {
  audience_visibility?: Array<PolicyDesignCaseAudience>;
  authority_profile: string;
  case_ref: string;
  claim_refs?: Array<string>;
  contestability_status: string;
  contested_record_id: string;
  counterevidence_refs?: Array<string>;
  grounds?: Array<string>;
  ingestion_event_refs?: Array<string>;
  lifecycle_event_refs?: Array<string>;
  public_projection_effect: string;
  publication_effect: string;
  recourse_outcome_refs?: Array<string>;
  recourse_pointer?: PolicyDesignCaseRecoursePointer | null;
  reopening_trigger_refs?: Array<string>;
  source_truth_conflict_refs?: Array<string>;
  standing_or_actor_ref?: string | null;
};

export type PolicyDesignCaseDeficitProjection = {
  audience_scope: string;
  authority_level: string;
  claim_ids?: Array<string>;
  deficit_code: string;
  deficit_family: string;
  deficit_id: string;
  disposition: string;
  evidence_ref: string;
  max_audience?: string | null;
  owner: string;
  public_limitation_note?: string | null;
  readiness_cap?: string | null;
  review_refs?: Array<string>;
  runtime_event_ref: string;
  support_cap?: string | null;
  ttl_expires_at?: string | null;
};

export type PolicyDesignCaseInvariantSummary = {
  blocker_codes?: Array<string>;
  details?: {
  [key: string]: unknown;
};
  evidence_refs?: Array<string>;
  failing_count?: number;
  passing_count?: number;
  status?: string;
};

export type PolicyDesignCaseParticipationRequirementProjection = {
  audience_visibility?: Array<PolicyDesignCaseAudience>;
  blocker_code?: string | null;
  claim_id: string;
  claim_use_allowed: string;
  claim_use_requested: string;
  consultation_mode?: string | null;
  downgrade_reason?: string | null;
  evidence_ref?: string | null;
  limitations?: Array<string>;
  participation_ref?: string | null;
  privacy_constraints?: Array<string>;
  provenance_class: string;
  public_projection_effect: string;
  raw_materials_redacted?: boolean;
  representativeness_class: string;
  requirement_id: string;
  source_kind: string;
};

export type PolicyDesignCaseProjection = {
  audience: PolicyDesignCaseAudience;
  audit_refs?: Array<string>;
  authoritative_for?: Array<string>;
  authority_role?: string;
  capability_reality_state?: string;
  closeout_truth: PolicyDesignCaseCloseoutTruth;
  contested_records?: Array<PolicyDesignCaseContestedRecord>;
  contract_verification_refs?: Array<string>;
  contract_verification_status?: string;
  deficit_register?: Array<PolicyDesignCaseDeficitProjection>;
  evidence_class: string;
  generated_at: string;
  invariant_summary?: PolicyDesignCaseInvariantSummary;
  labels?: Array<PolicyDesignCaseProjectionLabel>;
  may_be_used_for?: Array<string>;
  may_not_be_used_for?: Array<string>;
  omission_manifest?: Array<PolicyDesignCaseProjectionOmission>;
  participation_requirements?: Array<PolicyDesignCaseParticipationRequirementProjection>;
  policy_design_case_id?: string | null;
  primary_state: string;
  projection_gaps?: Array<PolicyDesignCaseProjectionGap>;
  projection_policy?: "reads_policy_design_case_only" | "reads_runtime_policy_design_case_graph";
  provenance_kind?: string;
  recourse_pointer?: PolicyDesignCaseRecoursePointer | null;
  redacted?: boolean;
  redaction_summary?: {
  [key: string]: unknown;
};
  run_id?: string | null;
  schema_version?: string;
  source_authority_refs?: {
  [key: string]: string;
};
  source_ref?: string | null;
  source_ref_fingerprint?: string | null;
  source_state?: {
  [key: string]: unknown;
};
  states?: Array<string>;
  surface: string;
};

export type PolicyDesignCaseProjectionBlocker = {
  code: string;
  evidence_ref?: string | null;
  message: string;
  module_id?: string | null;
  next_action?: string | null;
  owner?: string | null;
  severity?: string;
};

export type PolicyDesignCaseProjectionGap = {
  audience_visibility?: Array<PolicyDesignCaseAudience>;
  claim_ids?: Array<string>;
  closeout_effect?: string;
  evidence_ref?: string | null;
  gap_code: string;
  gap_family: string;
  gap_id: string;
  message: string;
  next_action?: string | null;
  owner?: string | null;
  publication_effect?: string;
  severity: string;
  source?: string | null;
};

export type PolicyDesignCaseProjectionLabel = {
  authority_role?: string;
  label: string;
  source_authority?: string;
  state: string;
};

export type PolicyDesignCaseProjectionOmission = {
  audience_visibility?: Array<PolicyDesignCaseAudience>;
  claim_ids?: Array<string>;
  closeout_effect?: string;
  evidence_ref?: string | null;
  manifest_ref?: string | null;
  omission_code: string;
  omission_family?: string;
  omission_id: string;
  owner?: string | null;
  publication_effect?: string;
  reason: string;
  source?: string | null;
};

export type PolicyDesignCaseRecoursePointer = {
  authority_boundary?: string;
  owner?: string | null;
  schema_version?: string;
  uri: string;
  verification_ref: string;
  verification_status?: string;
  verified_at: string;
};

export type PolicyFlags = {
  allow_mock_fallback?: boolean;
};

export type PositiveCertificateRegister = {
  appointment_denominator_state?: string;
  appointment_sufficiency_state?: string;
  authority_posture?: AppointmentPosture;
  blockers: Array<ReasonAlgebraRow>;
  entries?: Array<unknown>;
  population_count?: number;
  population_state?: string;
  verified_appointment_refs?: Array<unknown>;
  would_populate_when: Array<PositiveRegisterPredicate>;
};

export type PositiveRegisterPredicate = "owner_validated_promotion_row" | "execution_completed_supported" | "registry_profile_anytime_valid" | "obligation_supported_and_eligible" | "total_and_class_spend_within_budget" | "coverage_supports_protected_use" | "institutional_authority_appointed";

export type PredictableScheduleProfile = {
  mass: RationalSpec;
  profile_id: string;
  proof_kernel_id: string;
};

export type PreflightDiagnosticView = {
  code: string;
  data?: {
  [key: string]: unknown;
};
  message: string;
  path?: Array<string>;
  replanning_hints?: Array<string>;
  severity?: string;
};

export type PreflightReportView = {
  diagnostics?: Array<PreflightDiagnosticView>;
  notes?: Array<string>;
  ready_to_run?: boolean;
  report_ref?: ArtifactRefOutput | null;
};

export type ProducerInfo = {
  component: ComponentId | string;
  git?: GitInfo | null;
  version: string;
};

export type ProductionApprovalEligibility = {
  blocking_failure_count: number;
  conflict_blocking?: boolean;
  conflict_status?: string | null;
  eligible: boolean;
  execution_completed: boolean;
  performance_blocking?: boolean;
  performance_status?: string | null;
  quality_passed: boolean;
  reasons?: Array<string>;
};

export type ProductionApprovalOverridePacket = {
  evidence_refs?: Array<string>;
  expires_at: string;
  metadata?: {
  [key: string]: unknown;
};
  reason: string;
  reviewer_identity: string;
  scope: string;
  signature: string;
  signed_at: string;
};

export type ProductionApprovalOverrideRequest = {
  evidence_refs: Array<string>;
  expires_at: string;
  metadata?: {
  [key: string]: unknown;
};
  reason: string;
  reviewer_identity: string;
  scope: string;
  signature?: string | null;
};

export type ProductionApprovalPacket = {
  canary_kind?: string | null;
  decision: "approved" | "approved_with_override" | "blocked";
  decision_request_digest?: string | null;
  decision_request_ref?: string | null;
  eligibility: ProductionApprovalEligibility;
  evidence_refs?: {
  [key: string]: string;
};
  expected_audience?: string | null;
  expected_consumer?: string | null;
  generated_at: string;
  governed_action_key?: string | null;
  historical_only?: boolean;
  human_decision_record_digest?: string | null;
  human_decision_record_ref?: string | null;
  job_id?: string | null;
  limitations?: Array<string> | null;
  operational_authority?: boolean;
  override?: ProductionApprovalOverridePacket | null;
  production_basis_digest?: string | null;
  production_basis_producer_identity?: string | null;
  production_basis_ref?: string | null;
  rule_version_ref?: string | null;
  run_id?: string | null;
  schema_version?: "policyos.production_approval_packet.v1" | "policyos.production_approval_packet.v2";
  scorecard_digest: string;
  scorecard_generated_at?: string | null;
  scorecard_producer_identity?: string | null;
  scorecard_ref?: string | null;
  tenant_id?: string | null;
  valid_from?: string | null;
  valid_until?: string | null;
  verifier_epoch?: string | null;
};

export type ProductionApprovalRequest = {
  human_decision_record_digest?: string | null;
  human_decision_record_ref?: string | null;
  override?: ProductionApprovalOverrideRequest | null;
  production_basis_digest?: string | null;
  production_basis_ref?: string | null;
  quality_scorecard?: {
  [key: string]: unknown;
} | null;
  quality_scorecard_ref?: string | null;
};

export type ProductionApprovalResponse = {
  approval_packet_ref: ArtifactRefOutput;
  decision: "approved" | "approved_with_override" | "blocked";
  evidence_bundle_packet_path?: string | null;
  meta: ApiMeta;
  packet: ProductionApprovalPacket;
  run_id: string;
};

export type ProjectionCatalogEntry = {
  authoritative_for: Array<string>;
  expected_source_path: string;
  expected_source_rule_version: string | null;
  expected_source_schema_version: string | null;
  intended_audience: AudienceClass;
  may_not_use_for: Array<string>;
  owner_validator_id: string;
  owner_validator_version: string;
  projection_id: ProjectionId | GuardedProjectionId;
  source_policy: "required" | "presence_gated" | "fixture_identity_only";
  stable_address: string;
};

export type ProjectionCatalogResponse = {
  projections: Array<ProjectionCatalogEntry>;
  schema_version?: string;
};

export type ProjectionFreshness = {
  basis: "source_timestamp" | "filesystem_mtime" | "request_observation";
  observed_at: string;
  source_as_of?: string | null;
  state: "observed" | "artifact_missing" | "invalid_source";
};

export type ProjectionId = "depth-n-cycle-board" | "value-gate" | "generation-cycle-disposition" | "engine-census" | "fork-b-relation-census" | "acquisition-routing-contract" | "n13a-acquisition-census" | "n13a-live-probe-journal" | "acquisition-growth" | "capability-reality" | "cluster-ownership" | "layer3-health-metrics" | "legacy-proving-ground" | "surface-readiness";

export type ProjectionJsonValue = string | number | boolean | Array<unknown> | {
  [key: string]: unknown;
} | null;

export type ProjectionOwnerBinding = {
  binding_name: string;
  owner_semantic_hash: string;
  relation?: string;
  relative_path: string;
  resolved_artifact_content_hash: string;
  semantic_hash_rule_version: string;
};

export type ProjectionSourceIdentity = {
  artifact_content_hash: string;
  declared_content_hash?: string | null;
  related_artifact_bindings?: Array<RelatedArtifactBinding>;
  relative_path: string;
  validation: ProjectionSourceValidation;
};

export type ProjectionSourceValidation = {
  bound_artifact_content_hash: string;
  bound_dependency_aggregate_identity: string;
  bound_dependency_count: number;
  frozen_semantic_projection_hash?: string | null;
  issue_codes?: Array<string>;
  recomputed_total_spend_denominator?: number | null;
  recomputed_total_spend_numerator?: number | null;
  registry_content_hash?: string | null;
  registry_delta_denominator?: number | null;
  registry_delta_numerator?: number | null;
  registry_projection_hash?: string | null;
  semantic_projection_hash?: string | null;
  semantic_projection_hash_rule_version?: string | null;
  source_payload_equal?: boolean | null;
  status: "passed" | "failed" | "not_run";
  validator_id: string;
  validator_version: string;
  worker_validation_receipt_hash?: string | null;
};

export type PromotionCandidate = {
  confidence?: number;
  connector_id: string;
  created_at?: string | null;
  dataset_id: string;
  metadata?: {
  [key: string]: unknown;
};
  metric_id: string;
  profile_id?: string | null;
  promotion_id: string;
  signals?: Array<string>;
  source_lane?: "fastlane" | "explorelane" | "catalog";
  status?: "pending" | "approved" | "rejected";
};

export type PromotionCandidatesResponse = {
  candidates?: Array<PromotionCandidate>;
  meta: ApiMeta;
};

export type PromotionDecisionRequest = {
  reason?: string | null;
};

export type PromotionDecisionResponse = {
  binding_updated?: boolean;
  message: string;
  meta: ApiMeta;
  promotion_id: string;
  status: "approved" | "rejected";
};

export type PromotionObligationClass = "syntax" | "type" | "slot" | "param" | "coupling" | "effect" | "identification" | "calibration" | "measurement" | "data" | "implementation" | "equilibrium" | "normative" | "eval_safety" | "value";

export type ProvingGroundFixtureIdentity = {
  authority_levels: Array<string>;
  case_id: string;
  domain: string;
  split: string;
};

export type ProvingGroundFixtureRecord = {
  case_id: string;
  claim_evidence_annotations: {
  [key: string]: ProjectionJsonValue;
};
  compilation_intent_text: string;
  concept_spine_refs: {
  [key: string]: ProjectionJsonValue;
};
  domain: string;
  expected_adapter_bindings: {
  [key: string]: ProjectionJsonValue;
};
  expected_claim_families: {
  [key: string]: ProjectionJsonValue;
};
  expected_closeout_states: {
  [key: string]: ProjectionJsonValue;
};
  expected_facets: {
  [key: string]: ProjectionJsonValue;
};
  expected_obligation_graph: {
  [key: string]: ProjectionJsonValue;
};
  expected_projection_truthfulness: {
  [key: string]: ProjectionJsonValue;
};
  expected_requirement_specs: {
  [key: string]: ProjectionJsonValue;
};
  expert_adjudication: {
  [key: string]: ProjectionJsonValue;
};
  input_intent_ref: string;
  intent: {
  [key: string]: ProjectionJsonValue;
};
  schema_version: string;
  split: string;
  title: string;
};

export type ProvingGroundRuntimeOutcomes = {
  availability?: string;
  reason: string;
};

export type QualityRef = {
  quality_surface?: string | null;
  reason_code?: string | null;
  remediation_link?: string | null;
  report_ref?: string | null;
  score?: number | null;
  status?: "passed" | "warning" | "failed" | "unknown_quality";
};

export type QuantityCoverageEntry = {
  lineage_id?: string | null;
  metric_id?: string | null;
  path: string;
  quantity_class: "decision" | "telemetry" | "layout" | "debug";
  reason_code?: string | null;
  status: "verified" | "pending" | "disputed" | "untraced";
  tracking_issue?: string | null;
};

export type QuantityCoverageSummary = {
  debug?: number;
  decision?: number;
  layout?: number;
  telemetry?: number;
  total?: number;
  traced?: number;
  untraced?: number;
};

export type QuantityUncertainty = {
  ci_80?: Array<unknown> | null;
  ci_95?: Array<unknown> | null;
  disputed?: boolean;
  identifiability?: "identified" | "estimated" | "assumed" | "unknown";
  method?: "bootstrap" | "bayesian" | "analytic" | "simulation" | "none" | string | null;
  quantiles?: {
  [key: string]: number;
};
};

export type QuantityValueInput = {
  label?: string | null;
  lineage: LineageRefInput;
  metric_id?: string | null;
  point?: number | null;
  quantity_class?: "decision" | "telemetry" | "layout" | "debug";
  time?: TemporalRefInput | null;
  uncertainty?: QuantityUncertainty | null;
  unit: UnitRefInput;
};

export type QuantityValueOutput = {
  label?: string | null;
  lineage: PolisyosCoreContractsRuntimeLineageRefOutput;
  metric_id?: string | null;
  point?: number | null;
  quantity_class?: "decision" | "telemetry" | "layout" | "debug";
  time?: polisyos__core__contracts__runtime__TemporalRef | null;
  uncertainty?: QuantityUncertainty | null;
  unit: polisyos__core__contracts__runtime__UnitRef;
};

export type RationalSpec = {
  denominator: number;
  numerator: number;
};

export type ReasonAlgebraRow = {
  slot: "coverage_assessment" | "instrument_blocker" | "appointment_posture";
  value: string;
};

export type RefusedAuthorityValue = {
  owner_surface?: string | null;
  reason: string;
  refusal_code: ValueRefusalCode;
  retired_from: string;
  state?: string;
  surface: AuthoritySurface;
  value_id: AuthorityValueId;
};

export type RelatedArtifactBinding = ProjectionOwnerBinding | DependencyDiscriminantOwnerBinding;

export type ReplayRef = {
  manifest_ref?: string | null;
  reason_code?: string | null;
  retention_alternative?: string | null;
  source_reason?: string | null;
  status?: "replayable" | "non_replayable" | "unknown";
};

export type ReproducibilityView = {
  data_snapshot_hash?: string | null;
  determinism_tier?: string | null;
  input_bindings_hash?: string | null;
  manifest_ref?: ArtifactRefOutput | null;
  method_catalog_hash?: string | null;
  missing_refs?: Array<string>;
  notes?: Array<string>;
  plan_hash?: string | null;
  readiness?: string | null;
  registry_hash?: string | null;
  seed?: number;
  seed_source?: string | null;
  suggested_next_step?: string | null;
  why_partial?: Array<string>;
};

export type ResponsibilityIntegrityCheck = {
  missing_requirements?: Array<string>;
  pattern_ids?: Array<string>;
  reason: string;
  rule_version_ref: string;
  schema_version?: string;
  status: "pass" | "limit" | "block";
};

export type RetrievalPhaseTelemetry = {
  candidates_selected?: number;
  candidates_total?: number;
  docs_fetched?: number;
  duration_ms?: number;
  lane?: string | null;
  phase: string;
};

export type RetrievalTelemetryView = {
  candidates_filtered?: number;
  candidates_promoted?: number;
  lane_used?: string;
  local_index_docs_total?: number;
  local_index_size_bytes?: number;
  metadata_docs_fetched?: number;
  mode?: string;
  notes?: Array<string>;
  phases?: Array<RetrievalPhaseTelemetry>;
};

export type RunAuthorityProjection = {
  inventory_version: string;
  retirement_commit: string;
  run_id: string;
  values: Array<RefusedAuthorityValue | SuppliedAuthorityValue>;
};

export type RunBoundDesignRecordBinding = {
  binding_id: string;
  case_id: string;
  cell_id: string | null;
  design_record_content_digest: string;
  design_record_record_id: string;
  design_record_ref: ArtifactRefOutput;
  design_record_schema_name?: string;
  design_record_schema_version: string;
  producer: ProducerInfo;
  run_id: string;
  schema_version?: string;
  search_ledger_content_digest: string;
  search_ledger_id: string;
  search_ledger_ref: ArtifactRefOutput;
  tenant_id: string;
};

export type RunCompareResponse = {
  compare: RunCompareView;
  meta: ApiMeta;
};

export type RunCompareView = {
  left_run_id: string;
  report: DecisionCompareReport;
  right_run_id: string;
};

export type RunDetails = {
  capability_manifest_ref?: ArtifactRefOutput | null;
  cell_id?: string | null;
  control_job_id?: string | null;
  decision_review_required?: boolean;
  decision_superseded_by_ref?: ArtifactRefOutput | null;
  decision_validity_checked_at?: string | null;
  decision_validity_status?: DecisionValidityStatus | null;
  duration_ms?: number | null;
  execution_profile?: string | null;
  finished_at?: string | null;
  has_trace?: boolean;
  has_workflow_report?: boolean;
  manifest_ref?: ArtifactRefOutput | null;
  operator_diagnostic?: RunOperatorDiagnostic | null;
  policy_design_case_projection?: PolicyDesignCaseProjection | null;
  root_artifacts?: Array<ArtifactRefOutput>;
  run_id: string;
  source_kind: string;
  started_at?: string | null;
  status: string;
  tenant_id?: string | null;
  trace_ref?: ArtifactRefOutput | null;
  warnings?: Array<string>;
  workflow_report_ref?: ArtifactRefOutput | null;
};

export type RunDetailsResponse = {
  meta: ApiMeta;
  run: RunDetails;
  temporal_scope?: TemporalScope | null;
};

export type RunEquilibriaResponse = {
  equilibria: RunEquilibriaView;
  meta: ApiMeta;
};

export type RunEquilibriaView = {
  notes?: Array<string>;
  report?: EquilibriumMultiplicityReport | null;
  report_ref?: ArtifactRefOutput | null;
  run_id: string;
  source_kind: string;
};

export type RunErrorView = {
  code: string;
  details?: {
  [key: string]: unknown;
};
  message: string;
  node_alias?: string | null;
  source: "manifest" | "workflow_report" | "trace" | "runtime";
  timestamp?: string | null;
};

export type RunErrorsResponse = {
  errors?: Array<RunErrorView>;
  meta: ApiMeta;
  run_id: string;
};

export type RunEvidenceContextResponse = {
  context: RunEvidenceContextView;
  meta: ApiMeta;
};

export type RunEvidenceContextView = {
  data_needs?: Array<RunEvidenceNeedView>;
  data_snapshot_ref?: ArtifactRefOutput | null;
  evidence_bundle_ref?: ArtifactRefOutput | null;
  execution_plan_ref?: ArtifactRefOutput | null;
  fabric_retrieval_trace_ref?: ArtifactRefOutput | null;
  fetch_plans?: Array<RunEvidencePlanView>;
  input_bindings_ref?: ArtifactRefOutput | null;
  materialization_refs?: {
  [key: string]: ArtifactRefOutput;
};
  production_data_evidence_context?: {
  [key: string]: unknown;
};
  promotion_candidates?: Array<RunEvidencePromotionView>;
  related_artifacts?: Array<ArtifactRefOutput>;
  run_id: string;
  source_kind: string;
  warnings?: Array<string>;
};

export type RunEvidenceNeedView = {
  geography?: string | null;
  granularity?: string;
  matched_plan_ids?: Array<string>;
  metric: string;
  need_id: string;
  notes?: Array<string>;
  purpose?: string;
  quality_min?: number;
  time_end?: string | null;
  time_start?: string | null;
};

export type RunEvidencePlanView = {
  connector_id: string;
  dataset_id: string;
  date_end?: string | null;
  date_start?: string | null;
  fallback_count?: number;
  filters?: {
  [key: string]: Array<string>;
};
  granularity?: string | null;
  matched_need_ids?: Array<string>;
  metric_id: string;
  notes?: Array<string>;
  plan_id: string;
  profile_id?: string | null;
  quality_min?: number;
  source_lane?: string;
};

export type RunEvidencePromotionView = {
  confidence?: number;
  connector_id: string;
  created_at?: string | null;
  dataset_id: string;
  matched_plan_id?: string | null;
  metadata?: {
  [key: string]: unknown;
};
  metric_id: string;
  profile_id?: string | null;
  promotion_id: string;
  signals?: Array<string>;
  source_lane?: string;
  status?: string;
};

export type RunFeedbackResponse = {
  feedback: RunFeedbackView;
  meta: ApiMeta;
};

export type RunFeedbackView = {
  compare_report?: DecisionCompareReport | null;
  decision_packet_ref?: ArtifactRefOutput | null;
  decision_validity?: {
  [key: string]: unknown;
} | null;
  feedback_loop?: {
  [key: string]: unknown;
} | null;
  monitoring_contract?: DecisionMonitoringContract | null;
  monitoring_report?: DecisionMonitoringReport | null;
  notes?: Array<string>;
  reissue_plan?: DecisionReissuePlan | null;
  run_id: string;
  source_kind: string;
};

export type RunLaunchResponse = {
  effective_execution_profile: "dev" | "research" | "governed" | "production";
  job_id: string;
  message: string;
  meta: ApiMeta;
  run_id: string;
  status: "accepted" | "rejected";
};

export type RunLineageResponse = {
  lineage: ArtifactLineageView;
  meta: ApiMeta;
  run_id: string;
  temporal_scope?: TemporalScope | null;
};

export type RunNodeRecord = {
  alias: string;
  artifact_ids?: Array<string>;
  duration_ms?: number;
  error_code?: string | null;
  error_details?: {
  [key: string]: unknown;
};
  error_message?: string | null;
  input_artifact_ids?: Array<string>;
  node_id?: string | null;
  output_artifact_ids?: Array<string>;
  skip_reason?: string | null;
  status?: "ok" | "skip" | "fail" | "unknown";
};

export type RunNodesResponse = {
  meta: ApiMeta;
  nodes?: Array<RunNodeRecord>;
  run_id: string;
  source_kind: string;
};

export type RunOperatorDiagnostic = {
  authoritative_runtime_state: string;
  authority_refs?: {
  [key: string]: string;
};
  blocker_overridable?: boolean;
  downstream_impact: string;
  evidence_refs?: Array<string>;
  first_blocking_cause: string;
  next_diagnostic_command: string;
  owner: string;
  phase: string;
  projection_labels?: Array<RunOperatorProjectionStateLabel>;
  projection_source: string;
  upstream_missing_input?: string | null;
};

export type RunOperatorProjectionStateLabel = {
  authority: "runtime_authority" | "projection_only";
  label: string;
  state: "draft" | "projection_only" | "redacted" | "stale" | "contested" | "projected" | "blocked" | "readiness_closed" | "approved" | "rejected" | "published_blocked" | "publishable";
};

export type RunPaperAbstention = {
  code: string;
  issue_id: string;
  kind?: string;
  owner_route: string;
  source_bindings: Array<RunPaperVerifiedCaseSource>;
  statement: string;
  status: "open" | "resolved" | "escalated" | "accepted_as_limit";
  status_vocabulary_ref?: string;
};

export type RunPaperAdmissionState = {
  source_binding: RunPaperVerifiedCaseSource;
  state: "candidate_unverified" | "rejected_speculation" | "typed_blocker" | "limitation" | "admitted_to_obligation" | "admitted_to_claim";
  vocabulary_ref?: string;
};

export type RunPaperArtifactLink = {
  artifact_ref: ArtifactRefOutput;
  href: string;
  relation?: string;
};

export type RunPaperAuthorityNonReceipt = {
  authority_state?: string;
  denied_uses: Array<string>;
  kind?: string;
  missing_authority: "generation_cycle_grounding_authority" | "hypothesis_ledger_admission_authority" | "layer3_g4_promotion_authority";
  owner_route: string;
  status?: string;
};

export type RunPaperBlocker = {
  code: string;
  issue_id: string;
  kind?: string;
  owner_route: string;
  source_bindings: Array<RunPaperVerifiedCaseSource>;
  statement: string;
  status: "open" | "resolved" | "escalated" | "accepted_as_limit";
  status_vocabulary_ref?: string;
};

export type RunPaperCaseSourceVerification = {
  bound_artifact_content_hash: string;
  bound_case_id: string;
  bound_cell_id: string | null;
  bound_design_record_record_id: string;
  bound_run_id: string;
  bound_tenant_id: string;
  status?: string;
  validator_id: string;
  validator_version: string;
};

export type RunPaperDesignRecordBinding = RunBoundDesignRecordBinding;

export type RunPaperGroundingState = {
  source_binding: RunPaperVerifiedCaseSource;
  state: "current_valid" | "grounded_shadow" | "grounding_gap" | "grounding_failed" | "grounding_unavailable";
  vocabulary_ref?: string;
};

export type RunPaperLimitation = {
  code: string;
  issue_id: string;
  kind?: string;
  owner_route: string;
  source_bindings: Array<RunPaperVerifiedCaseSource>;
  statement: string;
  status: "open" | "resolved" | "escalated" | "accepted_as_limit";
  status_vocabulary_ref?: string;
};

export type RunPaperObjection = {
  code: string;
  issue_id: string;
  kind?: string;
  owner_route: string;
  source_bindings: Array<RunPaperVerifiedCaseSource>;
  statement: string;
  status: "open" | "resolved" | "escalated" | "accepted_as_limit";
  status_vocabulary_ref?: string;
};

export type RunPaperPacket = {
  artifact_links: Array<RunPaperArtifactLink>;
  case_record: AvailableRunPaperCase | AuthorityAbstainingRunPaperCase | UnavailableRunPaperCase;
  intended_audiences?: Array<unknown>;
  packet_schema_version?: string;
  projection_hash: string;
  projection_rule_version?: string;
  replay_address: string;
  replay_pins: RunPaperReplayPins;
  report_href: string;
  run: RunPaperRun;
  source: RunPaperSourceBinding;
  stable_address: string;
  stage_trace: AvailableRunPaperStageTrace | UnavailableRunPaperStageTrace;
};

export type RunPaperPromotionState = {
  source_binding: RunPaperVerifiedCaseSource;
  state: "governed_promoted" | "promotion_blocked";
  vocabulary_ref?: string;
};

export type RunPaperReplayPins = {
  manifest_artifact_id: string;
  manifest_schema_version?: string;
  paper_projection_hash: string;
  paper_projection_rule_version?: string;
};

export type RunPaperRun = {
  cell_id?: string | null;
  duration_ms?: number | null;
  finished_at?: string | null;
  run_id: string;
  run_terminality: "terminal" | "non_terminal" | "not_established";
  source_kind?: string;
  started_at?: string | null;
  status: string;
  tenant_id: string;
};

export type RunPaperSourceBinding = {
  environment: EnvInfo | null;
  manifest_ref: ArtifactRefOutput;
  manifest_schema_name?: string;
  manifest_schema_version?: string;
  producer: ProducerInfo | null;
  registry_bundle: ArtifactRefOutput;
};

export type RunPaperVerifiedCaseSource = {
  as_of?: string | null;
  authority_purpose: "grounding_state" | "admission_state" | "promotion_state" | "blocker" | "limitation" | "objection" | "abstention";
  producer: ProducerInfo;
  source_digest: string;
  source_ref: ArtifactRefOutput;
  source_schema_name: string;
  source_schema_version: string;
  verification: RunPaperCaseSourceVerification;
};

export type RunQuantitiesResponse = {
  coverage?: QuantityCoverageSummary;
  entries?: Array<QuantityCoverageEntry>;
  meta: ApiMeta;
  quantities?: Array<QuantityValueOutput>;
  run_id: string;
  source_kind: string;
  temporal_scope?: TemporalScope | null;
};

export type RunSummary = {
  cell_id?: string | null;
  control_job_id?: string | null;
  decision_review_required?: boolean;
  decision_superseded_by_ref?: ArtifactRefOutput | null;
  decision_validity_checked_at?: string | null;
  decision_validity_status?: DecisionValidityStatus | null;
  duration_ms?: number | null;
  execution_profile?: string | null;
  finished_at?: string | null;
  has_trace?: boolean;
  has_workflow_report?: boolean;
  root_artifact_count?: number;
  run_id: string;
  run_terminality: RunTerminality;
  source_kind: string;
  started_at?: string | null;
  status: string;
  tenant_id?: string | null;
  warnings?: Array<string>;
};

export type RunTerminality = "terminal" | "non_terminal" | "not_established";

export type RunTimelineEvent = {
  error_count?: number;
  event: string;
  index: number;
  input_artifact_ids?: Array<string>;
  metrics?: {
  [key: string]: number;
};
  output_artifact_ids?: Array<string>;
  parent_span_id?: string | null;
  phase: string;
  span_id?: string | null;
  timestamp: string;
  warning_count?: number;
};

export type RunTimelineResponse = {
  meta: ApiMeta;
  temporal_scope?: TemporalScope | null;
  timeline: RunTimelineView;
};

export type RunTimelineSummary = {
  cache_bypasses?: number;
  cache_hits?: number;
  cache_stores?: number;
  duration_ms?: number | null;
  node_status_counts?: {
  [key: string]: number;
};
  phase_counts?: {
  [key: string]: number;
};
  run_id: string;
  total_events?: number;
};

export type RunTimelineView = {
  events?: Array<RunTimelineEvent>;
  notes?: Array<string>;
  run_id: string;
  source_kind: string;
  summary: RunTimelineSummary;
};

export type RunWorkflowEdgeView = {
  from_alias: string;
  to_alias: string;
};

export type RunWorkflowNodeView = {
  alias: string;
  artifact_ids?: Array<string>;
  depends_on?: Array<string>;
  depth?: number;
  duration_ms?: number;
  error_code?: string | null;
  error_message?: string | null;
  heat?: number;
  input_artifact_ids?: Array<string>;
  node_id?: string | null;
  output_artifact_ids?: Array<string>;
  status?: "ok" | "skip" | "fail" | "unknown";
};

export type RunWorkflowResponse = {
  meta: ApiMeta;
  workflow: RunWorkflowView;
};

export type RunWorkflowSummary = {
  critical_path_duration_ms?: number | null;
  edge_count?: number;
  error_policy?: string | null;
  fail_count?: number;
  max_depth?: number;
  node_count?: number;
  ok_count?: number;
  skip_count?: number;
  status?: string | null;
  workflow_id?: string | null;
};

export type RunWorkflowView = {
  edges?: Array<RunWorkflowEdgeView>;
  nodes?: Array<RunWorkflowNodeView>;
  notes?: Array<string>;
  run_id: string;
  source_kind: string;
  summary: RunWorkflowSummary;
  workflow_report_ref?: ArtifactRefOutput | null;
  workflow_spec_ref?: ArtifactRefOutput | null;
};

export type RunsBatchRequest = {
  run_ids?: Array<string>;
};

export type RunsBatchResponse = {
  meta: ApiMeta;
  runs?: Array<RunDetails>;
};

export type RunsListResponse = {
  meta: ApiMeta;
  page: CursorPage;
  runs?: Array<RunSummary>;
};

export type RuntimeApiProblem = {
  code: string;
  detail: string;
  error?: string | null;
  instance?: string | null;
  request_id?: string | null;
  status?: number;
  status_code?: number;
  title: string;
  type?: string;
};

export type RuntimePermission = "analysis.execute" | "artifacts.batch.read" | "artifacts.render" | "dashboard.view" | "decisions.validity.publish" | "evidence.acquire" | "evidence.discover" | "evidence.preview" | "evidence.promotions.approve" | "evidence.promotions.reject" | "evidence.resolve" | "evidence.review" | "evidence.sae.analyze" | "evidence.view" | "fabric.impact.analyze" | "fabric.quality.read" | "fabric.trust.read" | "knowledge.search" | "knowledge.trigger" | "knowledge.view" | "lineage.batch.read" | "mobility.analyze" | "mode.analyst" | "platform.admin" | "platform.view" | "runs.batch.read" | "runs.feedback.evaluate" | "runs.human_decisions.create" | "runs.launch" | "runs.production_approval.create" | "runs.reissue" | "runs.review" | "runs.view" | "scenarios.create";

export type ScenarioAssumptionInput = {
  description?: string | null;
  id: string;
  label: string;
  lineage: LineageRefInput;
  status: "operator_assumption" | "model_assumption" | "observed_evidence" | "disputed";
};

export type ScenarioAssumptionOutput = {
  description?: string | null;
  id: string;
  label: string;
  lineage: PolisyosCoreContractsRuntimeLineageRefOutput;
  status: "operator_assumption" | "model_assumption" | "observed_evidence" | "disputed";
};

export type ScenarioCapabilitiesResponse = {
  capabilities?: Array<ScenarioCapability>;
  meta: ApiMeta;
  run_id?: string | null;
  scenario_id?: string | null;
  temporal_scope?: TemporalScope | null;
};

export type ScenarioCapability = {
  limitations?: Array<string>;
  metric_id?: string | null;
  reason_code?: string | null;
  supported: boolean;
  supported_modes?: Array<"actual" | "actual_vs_scenario" | "scenario_only">;
  surface: "run_metrics" | "quantities" | "lineage" | "charts" | "whatif";
};

export type ScenarioConstraintInput = {
  field?: string | null;
  id: string;
  label: string;
  message?: string | null;
  operator?: string | null;
  severity?: "error" | "warning";
  value?: QuantityValueInput | null;
};

export type ScenarioConstraintOutput = {
  field?: string | null;
  id: string;
  label: string;
  message?: string | null;
  operator?: string | null;
  severity?: "error" | "warning";
  value?: QuantityValueOutput | null;
};

export type ScenarioCreateRequest = {
  affected_population?: string | null;
  assumptions: Array<ScenarioAssumptionInput>;
  author?: string;
  constraints?: Array<ScenarioConstraintInput>;
  id?: string | null;
  interventions: Array<ScenarioInterventionInput>;
  known_limitations?: Array<string>;
  model_family?: string;
  model_version?: string | null;
  policy_question: string;
  regime_shift_forecast_bundle_ref?: string | null;
};

export type ScenarioInterventionInput = {
  baseline_value?: QuantityValueInput | null;
  constraint_ids?: Array<string>;
  field: string;
  operator: "set" | "add" | "multiply" | "remove";
  value: QuantityValueInput;
};

export type ScenarioInterventionOutput = {
  baseline_value?: QuantityValueOutput | null;
  constraint_ids?: Array<string>;
  field: string;
  operator: "set" | "add" | "multiply" | "remove";
  value: QuantityValueOutput;
};

export type ScenarioListResponse = {
  meta: ApiMeta;
  run_id: string;
  scenarios?: Array<ScenarioManifest>;
  temporal_scope?: TemporalScope | null;
};

export type ScenarioManifest = {
  affected_population?: string | null;
  assumptions: Array<ScenarioAssumptionOutput>;
  author: string;
  baseline_hash?: string | null;
  baseline_lineage?: PolisyosCoreContractsRuntimeLineageRefOutput | null;
  baseline_run_id: string;
  computed_at?: string | null;
  constraints?: Array<ScenarioConstraintOutput>;
  id: string;
  interventions: Array<ScenarioInterventionOutput>;
  known_limitations?: Array<string>;
  lifecycle_status?: "generated" | "draft" | "saved" | "promoted";
  manifest_hash?: string;
  model_family: string;
  model_lineage: PolisyosCoreContractsRuntimeLineageRefOutput;
  model_version?: string | null;
  phase4_gate_verdict?: {
  [key: string]: unknown;
} | null;
  policy_question: string;
  promoted_at?: string | null;
  revision?: number;
  saved_at?: string | null;
  stale_reasons?: Array<string>;
  status: "draft" | "computed" | "stale" | "failed";
  temporal_scope?: TemporalScope | null;
  temporal_window?: TemporalRange | null;
  validity_window?: TemporalRange | null;
};

export type ScenarioManifestResponse = {
  meta: ApiMeta;
  scenario: ScenarioManifest;
  temporal_scope?: TemporalScope | null;
};

export type ScenarioRef = {
  assumption_ids: Array<string>;
  baseline_run_id: string;
  id: string;
  lineage: PolisyosCoreContractsRuntimeLineageRefOutput;
  manifest_hash?: string | null;
  status: "draft" | "computed" | "stale" | "failed";
  temporal_scope?: TemporalScope | null;
};

export type ScopeRiskSpend = {
  allocation: ConditionalDeltaAmount;
  overspend_amount: ConditionalDeltaAmount;
  remaining: ConditionalDeltaAmount;
  spent: ConditionalDeltaAmount;
};

export type SearchCandidate = {
  authority_boundary?: {
  [key: string]: unknown;
};
  candidate_ref: string;
  evidence_refs?: Array<string>;
  limitation_refs?: Array<string>;
  match_mode: "exact" | "alias" | "lexical" | "semantic" | "relational" | "derived";
  may_not_use_for?: Array<string>;
  score: number;
  source_layer: string;
};

export type SearchFrontier = {
  actual_cutoff?: number | null;
  candidates?: Array<SearchCandidate>;
  completeness_status: "complete" | "complete_no_match" | "recall_unmeasured" | "budget_cutoff" | "index_stale" | "producer_unavailable" | "producer_missing";
  configured_store_path?: string | null;
  corpus_kind: "canonical" | "bounded_surrogate" | "temp_store" | "fixture";
  corpus_path: string;
  corpus_ref: string;
  corpus_snapshot_hash: string;
  evaluated_count: number;
  incompleteness?: {
  [key: string]: unknown;
};
  incompleteness_reasons: Array<string>;
  index_freshness?: {
  [key: string]: unknown;
};
  index_version_refs?: Array<string>;
  indexes_used: Array<string>;
  no_hit_frontier?: Array<string>;
  query_expansion_traces?: Array<{
  [key: string]: unknown;
}>;
  query_plan?: {
  [key: string]: unknown;
};
  rejected_candidates?: Array<SearchCandidate>;
  replay_command: string;
  replay_expected_output_hash: string;
  replay_key: string;
  request_ref: string;
  requested_count: number;
  returned_count: number;
  schema_version?: string;
};

export type SearchRequest = {
  allowed_modes: Array<"exact" | "alias" | "lexical" | "semantic" | "relational" | "derived">;
  authority_purpose: string;
  budget?: {
  [key: string]: unknown;
};
  construct_refs: Array<string>;
  intent: string;
  query_text: string;
  request_id: string;
  required_layers: Array<string>;
  rule_version: string;
  schema_version?: string;
};

export type SessionAuthorityProvenance = "canonical_repo" | "verification";

export type SimulationResultRefInput = {
  artifact_id: ArtifactID;
  kind?: string;
  media_type?: string;
};

export type SimulationResultRefOutput = {
  artifact_id: string;
  kind?: string;
  media_type?: string;
};

export type SourceBlockedConfidenceLedgerRiskSpendPacket = {
  absence_reason?: null;
  as_of: string;
  authoritative_for?: Array<"conditionality_disclosure" | "declared_set_accounting" | "source_validation_posture">;
  availability: string;
  export_replay_contract?: string;
  freshness: ProjectionFreshness;
  intended_audience?: string;
  intended_audiences?: Array<unknown>;
  may_not_use_for?: Array<"promotion_authority" | "publication_authority" | "public_audience" | "bounded_completeness">;
  packet_schema_version?: string;
  projection_hash: string;
  projection_id?: string;
  projection_rule_version?: string;
  replay_address: string;
  replay_pins: ConfidenceLedgerRiskSpendReplayPins;
  source_artifact_content_hash: string;
  source_blocked_reason: string;
  source_dependency_hash: string;
  source_rule_version: string | null;
  source_schema_version: string | null;
  stable_address?: string;
  worker_validation_receipt_hash: string;
  worker_validation_receipt_ref: string;
};

export type SourceContractRef = {
  id: string;
  version: string;
};

export type SourceProfileInfo = {
  auth_policy?: string;
  base_url: string;
  connector_available?: boolean;
  connector_family: string;
  description?: string;
  display_name: string;
  estimated_datasets?: number | null;
  profile_id: string;
  source_organization?: string;
  tags?: Array<string>;
};

export type SourceProfilesListResponse = {
  meta: ApiMeta;
  profiles?: Array<SourceProfileInfo>;
};

export type StructuralRouteProjection = {
  action_eligibility: "not_applicable" | "blocked";
  gap_class: GapClass;
  missing_link: string;
  route_class: string;
  route_id: string;
  witness_kind: string;
};

export type SuppliedAuthorityValue = {
  metric_id: string;
  point?: number | null;
  state?: string;
  surface: AuthoritySurface;
  value_id: AuthorityValueId;
};

export type SurfaceReadinessPayload = {
  authority: {
  [key: string]: ProjectionJsonValue;
};
  controlled_vocabulary_source: string;
  entries: Array<ProjectionJsonValue>;
  ledger_id: string;
};

export type TemporalCapabilitiesResponse = {
  capabilities: TemporalCapabilitiesView;
  meta: ApiMeta;
};

export type TemporalCapabilitiesView = {
  branch_support?: boolean;
  default_scope?: TemporalScope | null;
  event_points?: Array<TemporalEventPoint>;
  graph_temporal_scope?: "full" | "partial" | "unsupported";
  nearest_event_points?: Array<TemporalEventPoint>;
  resolution?: string;
  run_id?: string | null;
  scenario_branch_support?: "explicit_only" | "unsupported";
  slow_query_evidence?: Array<TemporalIndexEvidence>;
  snapshot_support?: boolean;
  supported_tables?: Array<string>;
  surfaces?: Array<TemporalSurfaceCapability>;
  tx_range?: TemporalRange;
  unsupported_surfaces?: Array<"run_details" | "run_timeline" | "run_lineage" | "run_quantities" | "run_fabric_decision_data" | "run_compare" | "run_agents" | "run_evidence_context" | "run_workflow" | "run_nodes" | "artifact_content" | "epoch_staleness">;
  valid_range?: TemporalRange;
};

export type TemporalEventPoint = {
  id: string;
  kind?: "run_start" | "run_finish" | "trace_event" | "policy_change" | "late_evidence" | "correction" | "snapshot" | "now";
  label: string;
  observed?: boolean;
  timestamp: string;
  tx_at?: string | null;
  valid_at?: string | null;
};

export type TemporalGapRange = {
  end?: string | null;
  label?: string | null;
  reason_code: string;
  start?: string | null;
};

export type TemporalIndexEvidence = {
  adapter?: string;
  columns?: Array<string>;
  evidence_ref?: string | null;
  index_name: string;
  slow_query_gate_ms?: number;
  status?: "implemented" | "recommended" | "missing" | "not_applicable";
  table: string;
};

export type TemporalRange = {
  earliest?: string | null;
  latest?: string | null;
};

export type TemporalRefInput = {
  branch?: string | null;
  scenario_id?: string | null;
  snapshot_id?: string | null;
  tx_at?: string | null;
  valid_at?: string | null;
};

export type TemporalScope = {
  branch?: string | null;
  scenario_id?: string | null;
  snapshot_id?: string | null;
  tx_at?: string | null;
  valid_at?: string | null;
};

export type TemporalSurfaceCapability = {
  gaps?: Array<TemporalGapRange>;
  nearest_event_points?: Array<TemporalEventPoint>;
  reason_code?: string | null;
  resolution?: string;
  supported: boolean;
  surface: "run_details" | "run_timeline" | "run_lineage" | "run_quantities" | "run_fabric_decision_data" | "run_compare" | "run_agents" | "run_evidence_context" | "run_workflow" | "run_nodes" | "artifact_content" | "epoch_staleness";
  tx_range?: TemporalRange | null;
  valid_range?: TemporalRange | null;
};

export type TimeFrequency = "M" | "Q" | "Y";

export type TimeSemantics = {
  end_date?: string | null;
  frequency: TimeFrequency;
  notes?: Array<string>;
  start_date: string;
  step_count?: number | null;
};

export type TypedGap = {
  access_policy?: string | null;
  capability_endpoint?: string | null;
  owner?: string | null;
  quality_surface?: string | null;
  reason_code?: string | null;
  redaction_behavior?: string | null;
  remediation_link?: string | null;
  retention_alternative?: string | null;
  source_reason?: string | null;
  status: "untraced" | "unknown_quality" | "restricted" | "non_replayable" | "unsupported_temporal_scope";
};

export type UnavailableRunPaperCase = {
  availability?: string;
  capability_state?: string;
  closure_signal?: string;
  may_not_use_for?: Array<string>;
  owner_route?: string;
  reason_code?: string;
};

export type UnavailableRunPaperStageTrace = {
  availability?: "not_established" | "invalid_source";
  owner_route?: string;
  reason?: string;
};

export type UnitRefInput = {
  code: string;
  display?: string | null;
  system?: string;
};

export type UnresolvedEquilibriumStart = {
  diagnostics?: {
  [key: string]: unknown;
};
  failure_reason?: string | null;
  notes?: Array<string>;
  residual_norm?: number | null;
  start_state: FeedbackStateSnapshot;
  status: string;
};

export type ValidationError = {
  ctx?: {
  [key: string]: unknown;
};
  input?: unknown;
  loc: Array<string | number>;
  msg: string;
  type: string;
};

export type ValueGatePayload = {
  acquisition_routing: {
  [key: string]: ProjectionJsonValue;
};
  advisor_receipts: {
  [key: string]: ProjectionJsonValue;
};
  denominators: {
  [key: string]: ProjectionJsonValue;
};
  disposition: {
  [key: string]: ProjectionJsonValue;
};
  education_refusal: {
  [key: string]: ProjectionJsonValue;
};
  mode_gates: {
  [key: string]: ProjectionJsonValue;
};
  production_refusal: {
  [key: string]: ProjectionJsonValue;
};
  value_outer_set_contract: Array<{
  [key: string]: ProjectionJsonValue;
}>;
};

export type ValueRefusalCode = "no_runtime_composition_rule" | "no_runtime_estimator" | "analysis_not_runtime_resident" | "no_runtime_producer" | "owned_by_another_surface";

export type VerificationMetadata = {
  dispute_status?: "none" | "disputed" | "under_review" | "resolved";
  freshness?: "current" | "stale" | "unknown";
  hash?: string | null;
  temporal_scope?: TemporalScope | null;
  verification_method?: string | null;
  verification_status?: "verified" | "pending" | "disputed" | "untraced";
  verified_at?: string | null;
  verified_by?: string | null;
};

export type WorkflowRunRequest = {
  calibration_report_ref?: string | null;
  checkpoint_policy?: "strict" | "lenient" | "disabled";
  data_source: DataSourceBinding;
  execution_profile?: "dev" | "research" | "governed" | "production" | null;
  knowledge_bundle_ref?: string | null;
  mode?: "workflow" | "agent_circuit";
  model_spec_ref?: string | null;
  norm_pack_ref?: string | null;
  params?: {
  [key: string]: unknown;
};
  policy_flags?: PolicyFlags;
  policy_spec_ref?: string | null;
  research_intent_ref?: string | null;
  trinity_bundle_ref?: string | null;
};

export type PolisyosCoreContractsRuntimeLineageRefOutput = {
  compact_summary?: Array<LineageCompactSummaryItem>;
  freshness?: "current" | "stale" | "unknown";
  hash?: string | null;
  id: string;
  reason_code?: string | null;
  status?: "verified" | "pending" | "disputed" | "untraced";
  summary?: {
  [key: string]: string;
};
  tracking_issue?: string | null;
  trust_metadata?: VerificationMetadata | null;
};

export type polisyos__core__contracts__runtime__TemporalRef = {
  branch?: string | null;
  scenario_id?: string | null;
  snapshot_id?: string | null;
  tx_at?: string | null;
  valid_at?: string | null;
};

export type polisyos__core__contracts__runtime__UnitRef = {
  code: string;
  display?: string | null;
  system?: string;
};

export type polisyos__fabric__evidence__decision_data__LineageRef = {
  compact_summary_ref?: string | null;
  export_links?: {
  [key: string]: string;
};
  full_graph_ref?: string | null;
  hash?: string | null;
  id: string;
  owner?: string | null;
  raw_evidence_refs?: Array<string>;
  reason_code?: string | null;
  status?: "verified" | "pending" | "disputed" | "untraced";
  tracking_issue?: string | null;
};

export type polisyos__fabric__evidence__decision_data__TemporalRef = {
  branch?: string | null;
  scenario_id?: string | null;
  snapshot_id?: string | null;
  tx_at?: string | null;
  valid_at?: string | null;
};

export type polisyos__fabric__evidence__decision_data__UnitRef = {
  code: string;
  display?: string | null;
  system?: string;
};

export interface RuntimeApiClientOptions {
  baseUrl: string;
  headers?: HeadersInit;
  fetchImpl?: typeof fetch;
}

export class RuntimeApiClient {
  private readonly baseUrl: string;
  private readonly headers: HeadersInit;
  private readonly fetchImpl: typeof fetch;

  constructor(options: RuntimeApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.headers = options.headers ?? {};
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  private async request<T>(
    method: string,
    path: string,
    query?: URLSearchParams,
    body?: unknown,
    requestHeaders?: HeadersInit,
    responseMode: "json" | "arrayBuffer" = "json",
  ): Promise<T> {
    const url = query && query.toString()
      ? `${this.baseUrl}${path}?${query.toString()}`
      : `${this.baseUrl}${path}`;
    const headers = new Headers(this.headers);
    if (body !== undefined && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (requestHeaders !== undefined) {
      new Headers(requestHeaders).forEach((value, key) => {
        headers.set(key, value);
      });
    }
    const response = await this.fetchImpl(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(
        `Runtime API request failed: ${response.status} ${response.statusText} ${body}`
      );
    }
    if (responseMode === "arrayBuffer") {
      return (await response.arrayBuffer()) as T;
    }
    return (await response.json()) as T;
  }

  private buildQuery(params: Record<string, unknown>): URLSearchParams {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null) {
        continue;
      }
      if (Array.isArray(value)) {
        for (const item of value) {
          query.append(key, String(item));
        }
        continue;
      }
      if (value instanceof Date) {
        query.append(key, value.toISOString());
        continue;
      }
      query.append(key, String(value));
    }
    return query;
  }

  async getAttractorAnalysis(params: {
    analysis_id: string;
  }): Promise<AttractorAnalysisResult> {
    const path = `/api/v1/analysis/${encodeURIComponent(String(params.analysis_id))}`;
    const query = undefined;
    return this.request<AttractorAnalysisResult>("GET", path, query, undefined, undefined);
  }

  async getAnalysisBasinMap(params: {
    analysis_id: string;
    basin_id: string;
  }): Promise<BasinMap> {
    const path = `/api/v1/analysis/${encodeURIComponent(String(params.analysis_id))}/basin/${encodeURIComponent(String(params.basin_id))}`;
    const query = undefined;
    return this.request<BasinMap>("GET", path, query, undefined, undefined);
  }

  async getAnalysisContinuationBranch(params: {
    analysis_id: string;
    branch_id: string;
  }): Promise<ContinuationBranchOutput> {
    const path = `/api/v1/analysis/${encodeURIComponent(String(params.analysis_id))}/branch/${encodeURIComponent(String(params.branch_id))}`;
    const query = undefined;
    return this.request<ContinuationBranchOutput>("GET", path, query, undefined, undefined);
  }

  async getArtifactBatch(params: {
    body: ArtifactBatchRequest;
  }): Promise<ArtifactBatchResponse> {
    const path = `/api/v1/artifacts/batch`;
    const query = undefined;
    return this.request<ArtifactBatchResponse>("POST", path, query, params.body, undefined);
  }

  async getArtifactManifest(params: {
    artifact_id: string;
  }): Promise<ArtifactManifestResponse> {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}`;
    const query = undefined;
    return this.request<ArtifactManifestResponse>("GET", path, query, undefined, undefined);
  }

  async getArtifactContent(params: {
    artifact_id: string;
    max_bytes?: number | null;
  }): Promise<ArtifactContentResponse> {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/content`;
    const query = this.buildQuery({
      max_bytes: params.max_bytes,
    });
    return this.request<ArtifactContentResponse>("GET", path, query, undefined, undefined);
  }

  async downloadArtifactContent(params: {
    artifact_id: string;
  }): Promise<unknown> {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/download`;
    const query = undefined;
    return this.request<unknown>("GET", path, query, undefined, undefined);
  }

  async getArtifactLineage(params: {
    artifact_id: string;
    max_depth?: number | null;
    max_nodes?: number | null;
  }): Promise<ArtifactLineageResponse> {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/lineage`;
    const query = this.buildQuery({
      max_depth: params.max_depth,
      max_nodes: params.max_nodes,
    });
    return this.request<ArtifactLineageResponse>("GET", path, query, undefined, undefined);
  }

  async getArtifactSchema(params: {
    artifact_id: string;
  }): Promise<ArtifactSchemaResponse> {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/schema`;
    const query = undefined;
    return this.request<ArtifactSchemaResponse>("GET", path, query, undefined, undefined);
  }

  async exportBureaucraticArtifact(params: {
    packet_id: string;
    format?: "html" | "pdf" | "docx";
    genre?: "postanova_kmu" | "zakonoproekt" | "expert_vysnovok" | "analitichna_zapyska";
    jurisdiction?: string;
    template_version?: string | null;
    trust_view?: boolean;
    valid_at?: string | null;
    tx_at?: string | null;
    export_projection_hash?: string | null;
  }): Promise<BureaucraticExportResponse> {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.packet_id))}/export`;
    const query = this.buildQuery({
      format: params.format,
      genre: params.genre,
      jurisdiction: params.jurisdiction,
      template_version: params.template_version,
      trust_view: params.trust_view,
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      export_projection_hash: params.export_projection_hash,
    });
    return this.request<BureaucraticExportResponse>("GET", path, query, undefined, undefined);
  }

  async getAuthMe(): Promise<AuthMeResponse> {
    const path = `/api/v1/auth/me`;
    const query = undefined;
    return this.request<AuthMeResponse>("GET", path, query, undefined, undefined);
  }

  async getControlCapabilities(): Promise<CapabilityManifestResponse> {
    const path = `/api/v1/control/capabilities`;
    const query = undefined;
    return this.request<CapabilityManifestResponse>("GET", path, query, undefined, undefined);
  }

  async searchCapabilities(params: {
    body: CapabilityDiscoveryRequest;
  }): Promise<CapabilityDiscoveryResponse> {
    const path = `/api/v1/control/capabilities/search`;
    const query = undefined;
    return this.request<CapabilityDiscoveryResponse>("POST", path, query, params.body, undefined);
  }

  async listBindingProfiles(): Promise<BindingProfilesListResponse> {
    const path = `/api/v1/control/data/binding-profiles`;
    const query = undefined;
    return this.request<BindingProfilesListResponse>("GET", path, query, undefined, undefined);
  }

  async getCacheStatus(): Promise<CacheStatusResponse> {
    const path = `/api/v1/control/data/cache`;
    const query = undefined;
    return this.request<CacheStatusResponse>("GET", path, query, undefined, undefined);
  }

  async searchDataCatalog(params: {
    metric: string;
    geo?: string | null;
    limit?: number;
  }): Promise<CapabilityDiscoveryResponse> {
    const path = `/api/v1/control/data/catalog/search`;
    const query = this.buildQuery({
      metric: params.metric,
      geo: params.geo,
      limit: params.limit,
    });
    return this.request<CapabilityDiscoveryResponse>("GET", path, query, undefined, undefined);
  }

  async listConnectors(): Promise<ConnectorsListResponse> {
    const path = `/api/v1/control/data/connectors`;
    const query = undefined;
    return this.request<ConnectorsListResponse>("GET", path, query, undefined, undefined);
  }

  async getDataIndexStats(): Promise<IndexStatsResponse> {
    const path = `/api/v1/control/data/index/stats`;
    const query = undefined;
    return this.request<IndexStatsResponse>("GET", path, query, undefined, undefined);
  }

  async listSourceProfiles(): Promise<SourceProfilesListResponse> {
    const path = `/api/v1/control/data/profiles`;
    const query = undefined;
    return this.request<SourceProfilesListResponse>("GET", path, query, undefined, undefined);
  }

  async listDataPromotionCandidates(): Promise<PromotionCandidatesResponse> {
    const path = `/api/v1/control/data/promotion/candidates`;
    const query = undefined;
    return this.request<PromotionCandidatesResponse>("GET", path, query, undefined, undefined);
  }

  async getPacketDecisionValidity(params: {
    decision_packet_ref: string;
    export_projection_hash?: string | null;
  }): Promise<DecisionValiditySummaryResponse> {
    const path = `/api/v1/control/decision-packets/${encodeURIComponent(String(params.decision_packet_ref))}/decision-validity`;
    const query = this.buildQuery({
      export_projection_hash: params.export_projection_hash,
    });
    return this.request<DecisionValiditySummaryResponse>("GET", path, query, undefined, undefined);
  }

  async admitEpochValidityBatch(params: {
    body: EpochValidityBatchRequest;
  }): Promise<EpochValidityBatchResponse> {
    const path = `/api/v1/control/decision-validity/epoch-batches`;
    const query = undefined;
    return this.request<EpochValidityBatchResponse>("POST", path, query, params.body, undefined);
  }

  async getControlJobStatus(params: {
    job_id: string;
  }): Promise<ControlJobResponse> {
    const path = `/api/v1/control/jobs/${encodeURIComponent(String(params.job_id))}`;
    const query = undefined;
    return this.request<ControlJobResponse>("GET", path, query, undefined, undefined);
  }

  async getLexGraphStats(params: {
    output_dir: string;
  }): Promise<LexGraphStatsResponse> {
    const path = `/api/v1/control/lex/graph/stats`;
    const query = this.buildQuery({
      output_dir: params.output_dir,
    });
    return this.request<LexGraphStatsResponse>("GET", path, query, undefined, undefined);
  }

  async getLexPipelineStatus(params: {
    pipeline_id: string;
  }): Promise<LexPipelineStatusResponse> {
    const path = `/api/v1/control/lex/status/${encodeURIComponent(String(params.pipeline_id))}`;
    const query = undefined;
    return this.request<LexPipelineStatusResponse>("GET", path, query, undefined, undefined);
  }

  async listLlmProfiles(): Promise<ModelProfilesListResponse> {
    const path = `/api/v1/control/llm/profiles`;
    const query = undefined;
    return this.request<ModelProfilesListResponse>("GET", path, query, undefined, undefined);
  }

  async listControlOutbox(params: {
    state?: string | null;
    limit?: number;
  }): Promise<ControlOutboxEventsResponse> {
    const path = `/api/v1/control/outbox`;
    const query = this.buildQuery({
      state: params.state,
      limit: params.limit,
    });
    return this.request<ControlOutboxEventsResponse>("GET", path, query, undefined, undefined);
  }

  async getRunDecisionValidity(params: {
    run_id: string;
    export_projection_hash?: string | null;
  }): Promise<DecisionValiditySummaryResponse> {
    const path = `/api/v1/control/runs/${encodeURIComponent(String(params.run_id))}/decision-validity`;
    const query = this.buildQuery({
      export_projection_hash: params.export_projection_hash,
    });
    return this.request<DecisionValiditySummaryResponse>("GET", path, query, undefined, undefined);
  }

  async listControlWorkers(params: {
    active_only?: boolean;
  }): Promise<ControlWorkersResponse> {
    const path = `/api/v1/control/workers`;
    const query = this.buildQuery({
      active_only: params.active_only,
    });
    return this.request<ControlWorkersResponse>("GET", path, query, undefined, undefined);
  }

  async getRunCompare(params: {
    left_run_id: string;
    right_run_id: string;
  }): Promise<RunCompareResponse> {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.left_run_id))}/compare/${encodeURIComponent(String(params.right_run_id))}`;
    const query = undefined;
    return this.request<RunCompareResponse>("GET", path, query, undefined, undefined);
  }

  async getRunEquilibria(params: {
    run_id: string;
  }): Promise<RunEquilibriaResponse> {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/equilibria`;
    const query = undefined;
    return this.request<RunEquilibriaResponse>("GET", path, query, undefined, undefined);
  }

  async getRunErrors(params: {
    run_id: string;
  }): Promise<RunErrorsResponse> {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/errors`;
    const query = undefined;
    return this.request<RunErrorsResponse>("GET", path, query, undefined, undefined);
  }

  async getRunFeedback(params: {
    run_id: string;
  }): Promise<RunFeedbackResponse> {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/feedback`;
    const query = undefined;
    return this.request<RunFeedbackResponse>("GET", path, query, undefined, undefined);
  }

  async getGovernanceDebug(params: {
    run_id: string;
  }): Promise<GovernanceDebugResponse> {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/governance`;
    const query = undefined;
    return this.request<GovernanceDebugResponse>("GET", path, query, undefined, undefined);
  }

  async getNodeDebug(params: {
    run_id: string;
    alias: string;
  }): Promise<NodeDebugResponse> {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/nodes/${encodeURIComponent(String(params.alias))}`;
    const query = undefined;
    return this.request<NodeDebugResponse>("GET", path, query, undefined, undefined);
  }

  async getRuntimeChannelRegistry(): Promise<ChannelRegistryResponse> {
    const path = `/api/v1/exports/channel-registry`;
    const query = undefined;
    return this.request<ChannelRegistryResponse>("GET", path, query, undefined, undefined);
  }

  async listGovernedProjections(): Promise<ProjectionCatalogResponse> {
    const path = `/api/v1/exports/governed-projections`;
    const query = undefined;
    return this.request<ProjectionCatalogResponse>("GET", path, query, undefined, undefined);
  }

  async getConfidenceLedgerRiskSpendProjection(params: {
    artifact_content_hash?: string | null;
    projection_hash?: string | null;
    source_dependency_hash?: string | null;
    source_as_of?: string | null;
    projection_rule_version?: string | null;
  }): Promise<AvailableConfidenceLedgerRiskSpendPacket | SourceBlockedConfidenceLedgerRiskSpendPacket | ArtifactMissingConfidenceLedgerRiskSpendPacket | InvalidConfidenceLedgerRiskSpendPacket> {
    const path = `/api/v1/exports/governed-projections/confidence-ledger-risk-spend`;
    const query = this.buildQuery({
      artifact_content_hash: params.artifact_content_hash,
      projection_hash: params.projection_hash,
      source_dependency_hash: params.source_dependency_hash,
      source_as_of: params.source_as_of,
      projection_rule_version: params.projection_rule_version,
    });
    return this.request<AvailableConfidenceLedgerRiskSpendPacket | SourceBlockedConfidenceLedgerRiskSpendPacket | ArtifactMissingConfidenceLedgerRiskSpendPacket | InvalidConfidenceLedgerRiskSpendPacket>("GET", path, query, undefined, undefined);
  }

  async getDepthNCycleBoardProjection(params: {
    replay_target?: "raw_v1" | "composed_v2" | null;
    artifact_content_hash?: string | null;
    projection_hash?: string | null;
    source_dependency_hash?: string | null;
    source_as_of?: string | null;
    projection_rule_version?: string | null;
    composition_manifest_hash?: string | null;
  }): Promise<AvailableGovernedProjectionPacket | ArtifactMissingGovernedProjectionPacket | InvalidGovernedProjectionPacket | CycleBoardProjectionPacket> {
    const path = `/api/v1/exports/governed-projections/depth-n-cycle-board`;
    const query = this.buildQuery({
      replay_target: params.replay_target,
      artifact_content_hash: params.artifact_content_hash,
      projection_hash: params.projection_hash,
      source_dependency_hash: params.source_dependency_hash,
      source_as_of: params.source_as_of,
      projection_rule_version: params.projection_rule_version,
      composition_manifest_hash: params.composition_manifest_hash,
    });
    return this.request<AvailableGovernedProjectionPacket | ArtifactMissingGovernedProjectionPacket | InvalidGovernedProjectionPacket | CycleBoardProjectionPacket>("GET", path, query, undefined, undefined);
  }

  async getGovernedProjection(params: {
    projection_id: ProjectionId;
    artifact_content_hash?: string | null;
    projection_hash?: string | null;
    source_dependency_hash?: string | null;
    source_as_of?: string | null;
  }): Promise<AvailableGovernedProjectionPacket | ArtifactMissingGovernedProjectionPacket | InvalidGovernedProjectionPacket> {
    const path = `/api/v1/exports/governed-projections/${encodeURIComponent(String(params.projection_id))}`;
    const query = this.buildQuery({
      artifact_content_hash: params.artifact_content_hash,
      projection_hash: params.projection_hash,
      source_dependency_hash: params.source_dependency_hash,
      source_as_of: params.source_as_of,
    });
    return this.request<AvailableGovernedProjectionPacket | ArtifactMissingGovernedProjectionPacket | InvalidGovernedProjectionPacket>("GET", path, query, undefined, undefined);
  }

  async analyzeFabricImpact(params: {
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
    body: FabricImpactAnalysisRequest;
  }): Promise<FabricImpactAnalysisResponse> {
    const path = `/api/v1/fabric/impact`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<FabricImpactAnalysisResponse>("POST", path, query, params.body, undefined);
  }

  async getFabricQualityBatch(params: {
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
    body: FabricQualityTrustBatchRequest;
  }): Promise<FabricQualityBatchResponse> {
    const path = `/api/v1/fabric/quality/batch`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<FabricQualityBatchResponse>("POST", path, query, params.body, undefined);
  }

  async getFabricRunReplay(params: {
    run_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
  }): Promise<FabricReplayRunResponse> {
    const path = `/api/v1/fabric/runs/${encodeURIComponent(String(params.run_id))}/replay`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<FabricReplayRunResponse>("GET", path, query, undefined, undefined);
  }

  async getFabricSourceScorecards(): Promise<FabricSourceScorecardsResponse> {
    const path = `/api/v1/fabric/source-scorecards`;
    const query = undefined;
    return this.request<FabricSourceScorecardsResponse>("GET", path, query, undefined, undefined);
  }

  async getFabricTrustBatch(params: {
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
    body: FabricQualityTrustBatchRequest;
  }): Promise<FabricTrustBatchResponse> {
    const path = `/api/v1/fabric/trust/batch`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<FabricTrustBatchResponse>("POST", path, query, params.body, undefined);
  }

  async runtimeApiHealth(): Promise<{
  [key: string]: unknown;
}> {
    const path = `/api/v1/health`;
    const query = undefined;
    return this.request<{
  [key: string]: unknown;
}>("GET", path, query, undefined, undefined);
  }

  async getLineageBatch(params: {
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
    body: LineageBatchRequest;
  }): Promise<LineageBatchResponse> {
    const path = `/api/v1/lineage/batch`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<LineageBatchResponse>("POST", path, query, params.body, undefined);
  }

  async getLineage(params: {
    lineage_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
  }): Promise<LineageResponse> {
    const path = `/api/v1/lineage/${encodeURIComponent(String(params.lineage_id))}`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<LineageResponse>("GET", path, query, undefined, undefined);
  }

  async exportLineageOpenlineage(params: {
    lineage_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
    export_projection_hash?: string | null;
  }): Promise<LineageExportResponse> {
    const path = `/api/v1/lineage/${encodeURIComponent(String(params.lineage_id))}/export/openlineage`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
      export_projection_hash: params.export_projection_hash,
    });
    return this.request<LineageExportResponse>("GET", path, query, undefined, undefined);
  }

  async exportLineageProv(params: {
    lineage_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
    export_projection_hash?: string | null;
  }): Promise<LineageExportResponse> {
    const path = `/api/v1/lineage/${encodeURIComponent(String(params.lineage_id))}/export/prov`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
      export_projection_hash: params.export_projection_hash,
    });
    return this.request<LineageExportResponse>("GET", path, query, undefined, undefined);
  }

  async computeMobilityBounds(params: {
    body: MobilityBoundsRequest;
  }): Promise<MobilityBoundsResponse> {
    const path = `/api/v1/mobility/bounds`;
    const query = undefined;
    return this.request<MobilityBoundsResponse>("POST", path, query, params.body, undefined);
  }

  async estimateMobility(params: {
    body: MobilityEstimateRequest;
  }): Promise<MobilityEstimateResponse> {
    const path = `/api/v1/mobility/estimate`;
    const query = undefined;
    return this.request<MobilityEstimateResponse>("POST", path, query, params.body, undefined);
  }

  async getMobilityReport(params: {
    artifact_id: string;
  }): Promise<MobilityReportResponse> {
    const path = `/api/v1/mobility/reports/${encodeURIComponent(String(params.artifact_id))}`;
    const query = undefined;
    return this.request<MobilityReportResponse>("GET", path, query, undefined, undefined);
  }

  async getMobilityReportBounds(params: {
    artifact_id: string;
  }): Promise<MobilityBoundsResponse> {
    const path = `/api/v1/mobility/reports/${encodeURIComponent(String(params.artifact_id))}/bounds`;
    const query = undefined;
    return this.request<MobilityBoundsResponse>("GET", path, query, undefined, undefined);
  }

  async getMobilityReportDiagnostics(params: {
    artifact_id: string;
  }): Promise<MobilityDiagnosticsResponse> {
    const path = `/api/v1/mobility/reports/${encodeURIComponent(String(params.artifact_id))}/diagnostics`;
    const query = undefined;
    return this.request<MobilityDiagnosticsResponse>("GET", path, query, undefined, undefined);
  }

  async listRuns(params: {
    limit?: number;
    cursor?: string | null;
    q?: string | null;
    status?: string | null;
    from_ts?: string | null;
    to_ts?: string | null;
  }): Promise<RunsListResponse> {
    const path = `/api/v1/runs`;
    const query = this.buildQuery({
      limit: params.limit,
      cursor: params.cursor,
      q: params.q,
      status: params.status,
      from_ts: params.from_ts,
      to_ts: params.to_ts,
    });
    return this.request<RunsListResponse>("GET", path, query, undefined, undefined);
  }

  async getRunsBatch(params: {
    body: RunsBatchRequest;
  }): Promise<RunsBatchResponse> {
    const path = `/api/v1/runs/batch`;
    const query = undefined;
    return this.request<RunsBatchResponse>("POST", path, query, params.body, undefined);
  }

  async compareRuns(params: {
    a: string;
    b: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
  }): Promise<CompareRunResponse> {
    const path = `/api/v1/runs/compare`;
    const query = this.buildQuery({
      a: params.a,
      b: params.b,
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<CompareRunResponse>("GET", path, query, undefined, undefined);
  }

  async getRunDetails(params: {
    run_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
  }): Promise<RunDetailsResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<RunDetailsResponse>("GET", path, query, undefined, undefined);
  }

  async listRunAcquisitionRoutes(params: {
    run_id: string;
  }): Promise<AcquisitionRouteListResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/acquisition-routes`;
    const query = undefined;
    return this.request<AcquisitionRouteListResponse>("GET", path, query, undefined, undefined);
  }

  async getRunAcquisitionRoute(params: {
    run_id: string;
    route_id: string;
  }): Promise<AcquisitionRouteProjection> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/acquisition-routes/${encodeURIComponent(String(params.route_id))}`;
    const query = undefined;
    return this.request<AcquisitionRouteProjection>("GET", path, query, undefined, undefined);
  }

  async requestRunAcquisitionDecision(params: {
    run_id: string;
    route_id: string;
    body: AcquisitionRouteMutationRequest;
  }): Promise<AcquisitionDecisionRequestResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/acquisition-routes/${encodeURIComponent(String(params.route_id))}/decision-request`;
    const query = undefined;
    return this.request<AcquisitionDecisionRequestResponse>("POST", path, query, params.body, undefined);
  }

  async executeRunAcquisitionRoute(params: {
    run_id: string;
    route_id: string;
    body: AcquisitionRouteMutationRequest;
  }): Promise<AcquisitionExecutionResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/acquisition-routes/${encodeURIComponent(String(params.route_id))}/execute`;
    const query = undefined;
    return this.request<AcquisitionExecutionResponse>("POST", path, query, params.body, undefined);
  }

  async getRunAgents(params: {
    run_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
  }): Promise<AgentPipelineResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/agents`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<AgentPipelineResponse>("GET", path, query, undefined, undefined);
  }

  async getRunAuthorityValues(params: {
    run_id: string;
  }): Promise<RunAuthorityProjection> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/authority-values`;
    const query = undefined;
    return this.request<RunAuthorityProjection>("GET", path, query, undefined, undefined);
  }

  async getCaseInspection(params: {
    run_id: string;
    manifest_artifact_id?: string | null;
    manifest_schema_version?: string | null;
    paper_projection_rule_version?: string | null;
    paper_projection_hash?: string | null;
  }): Promise<RunPaperPacket> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/case-inspection`;
    const query = this.buildQuery({
      manifest_artifact_id: params.manifest_artifact_id,
      manifest_schema_version: params.manifest_schema_version,
      paper_projection_rule_version: params.paper_projection_rule_version,
      paper_projection_hash: params.paper_projection_hash,
    });
    return this.request<RunPaperPacket>("GET", path, query, undefined, undefined);
  }

  async getRunCompareCandidates(params: {
    run_id: string;
    limit?: number;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
  }): Promise<CompareCandidatesResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/compare-candidates`;
    const query = this.buildQuery({
      limit: params.limit,
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<CompareCandidatesResponse>("GET", path, query, undefined, undefined);
  }

  async getRunEvidenceContext(params: {
    run_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
  }): Promise<RunEvidenceContextResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/evidence-context`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<RunEvidenceContextResponse>("GET", path, query, undefined, undefined);
  }

  async getRunFabricDecisionData(params: {
    run_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
  }): Promise<FabricDecisionDataResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/fabric-decision-data`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<FabricDecisionDataResponse>("GET", path, query, undefined, undefined);
  }

  async getRunHumanDecisionEvidenceContent(params: {
    run_id: string;
    artifact_id: string;
    "X-PolicyOS-Human-Decision-Exposure": string;
  }): Promise<ArrayBuffer> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/human-decision-evidence/${encodeURIComponent(String(params.artifact_id))}/content`;
    const query = undefined;
    const requestHeaders = new Headers();
    requestHeaders.set("X-PolicyOS-Human-Decision-Exposure", String(params["X-PolicyOS-Human-Decision-Exposure"]));
    return this.request<ArrayBuffer>("GET", path, query, undefined, requestHeaders, "arrayBuffer");
  }

  async getRunHumanDecisionGate(params: {
    run_id: string;
    source_kind: "agent_action_authority" | "production_approval";
    source_ref?: string | null;
    production_packet_ref?: string | null;
    decision_request_ref?: string | null;
    principal_binding_ref?: string | null;
    reviewer_separation_ref?: string | null;
    presentation_contract_ref?: string | null;
    exposure_session_ref?: string | null;
    basis_digest?: string | null;
    action_kind?: string | null;
  }): Promise<HumanDecisionGateResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/human-decision-gate`;
    const query = this.buildQuery({
      source_kind: params.source_kind,
      source_ref: params.source_ref,
      production_packet_ref: params.production_packet_ref,
      decision_request_ref: params.decision_request_ref,
      principal_binding_ref: params.principal_binding_ref,
      reviewer_separation_ref: params.reviewer_separation_ref,
      presentation_contract_ref: params.presentation_contract_ref,
      exposure_session_ref: params.exposure_session_ref,
      basis_digest: params.basis_digest,
      action_kind: params.action_kind,
    });
    return this.request<HumanDecisionGateResponse>("GET", path, query, undefined, undefined);
  }

  async getRunHumanDecisionRecord(params: {
    run_id: string;
    record_ref: string;
  }): Promise<HumanDecisionRecord> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/human-decisions`;
    const query = this.buildQuery({
      record_ref: params.record_ref,
    });
    return this.request<HumanDecisionRecord>("GET", path, query, undefined, undefined);
  }

  async createRunHumanDecision(params: {
    run_id: string;
    "X-PolicyOS-Human-Decision-Exposure": string;
    body: HumanDecisionMutationRequest;
  }): Promise<HumanDecisionCreateResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/human-decisions`;
    const query = undefined;
    const requestHeaders = new Headers();
    requestHeaders.set("X-PolicyOS-Human-Decision-Exposure", String(params["X-PolicyOS-Human-Decision-Exposure"]));
    return this.request<HumanDecisionCreateResponse>("POST", path, query, params.body, requestHeaders);
  }

  async getRunHumanDecisionReviewEffectiveness(params: {
    run_id: string;
  }): Promise<HumanDecisionReviewEffectivenessResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/human-decisions/review-effectiveness`;
    const query = undefined;
    return this.request<HumanDecisionReviewEffectivenessResponse>("GET", path, query, undefined, undefined);
  }

  async getRunLineage(params: {
    run_id: string;
    root_artifact_id?: Array<string> | null;
    max_depth?: number | null;
    max_nodes?: number | null;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
  }): Promise<RunLineageResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/lineage`;
    const query = this.buildQuery({
      root_artifact_id: params.root_artifact_id,
      max_depth: params.max_depth,
      max_nodes: params.max_nodes,
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<RunLineageResponse>("GET", path, query, undefined, undefined);
  }

  async getRunCounterfactualMetrics(params: {
    run_id: string;
    scenario_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    regime_shift_forecast_bundle_ref?: string | null;
  }): Promise<CounterfactualMetricsResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/metrics`;
    const query = this.buildQuery({
      scenario_id: params.scenario_id,
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      regime_shift_forecast_bundle_ref: params.regime_shift_forecast_bundle_ref,
    });
    return this.request<CounterfactualMetricsResponse>("GET", path, query, undefined, undefined);
  }

  async getRunNodes(params: {
    run_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
  }): Promise<RunNodesResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/nodes`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<RunNodesResponse>("GET", path, query, undefined, undefined);
  }

  async getRunPaper(params: {
    run_id: string;
    manifest_artifact_id?: string | null;
    manifest_schema_version?: string | null;
    paper_projection_rule_version?: string | null;
    paper_projection_hash?: string | null;
  }): Promise<RunPaperPacket> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/paper`;
    const query = this.buildQuery({
      manifest_artifact_id: params.manifest_artifact_id,
      manifest_schema_version: params.manifest_schema_version,
      paper_projection_rule_version: params.paper_projection_rule_version,
      paper_projection_hash: params.paper_projection_hash,
    });
    return this.request<RunPaperPacket>("GET", path, query, undefined, undefined);
  }

  async getRunQuantities(params: {
    run_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
  }): Promise<RunQuantitiesResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/quantities`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<RunQuantitiesResponse>("GET", path, query, undefined, undefined);
  }

  async listRunScenarios(params: {
    run_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
    regime_shift_forecast_bundle_ref?: string | null;
  }): Promise<ScenarioListResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/scenarios`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
      regime_shift_forecast_bundle_ref: params.regime_shift_forecast_bundle_ref,
    });
    return this.request<ScenarioListResponse>("GET", path, query, undefined, undefined);
  }

  async getRunTimeline(params: {
    run_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
  }): Promise<RunTimelineResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/timeline`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<RunTimelineResponse>("GET", path, query, undefined, undefined);
  }

  async getRunWorkflow(params: {
    run_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
  }): Promise<RunWorkflowResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/workflow`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<RunWorkflowResponse>("GET", path, query, undefined, undefined);
  }

  async getScenarioManifest(params: {
    scenario_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
  }): Promise<ScenarioManifestResponse> {
    const path = `/api/v1/scenarios/${encodeURIComponent(String(params.scenario_id))}`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
    });
    return this.request<ScenarioManifestResponse>("GET", path, query, undefined, undefined);
  }

  async getScenarioCapabilities(params: {
    scenario_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    regime_shift_forecast_bundle_ref?: string | null;
  }): Promise<ScenarioCapabilitiesResponse> {
    const path = `/api/v1/scenarios/${encodeURIComponent(String(params.scenario_id))}/capabilities`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      regime_shift_forecast_bundle_ref: params.regime_shift_forecast_bundle_ref,
    });
    return this.request<ScenarioCapabilitiesResponse>("GET", path, query, undefined, undefined);
  }

  async getTemporalCapabilities(params: {
    run_id?: string | null;
  }): Promise<TemporalCapabilitiesResponse> {
    const path = `/api/v1/temporal/capabilities`;
    const query = this.buildQuery({
      run_id: params.run_id,
    });
    return this.request<TemporalCapabilitiesResponse>("GET", path, query, undefined, undefined);
  }

  async getRunEpochStaleness(params: {
    run_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
    export_projection_hash?: string | null;
  }): Promise<EpochStalenessProjectionResponse> {
    const path = `/api/v1/temporal/runs/${encodeURIComponent(String(params.run_id))}/epoch-staleness`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
      export_projection_hash: params.export_projection_hash,
    });
    return this.request<EpochStalenessProjectionResponse>("GET", path, query, undefined, undefined);
  }

  async health(): Promise<{
  [key: string]: unknown;
}> {
    const path = `/health`;
    const query = undefined;
    return this.request<{
  [key: string]: unknown;
}>("GET", path, query, undefined, undefined);
  }

  async ready(): Promise<{
  [key: string]: unknown;
}> {
    const path = `/ready`;
    const query = undefined;
    return this.request<{
  [key: string]: unknown;
}>("GET", path, query, undefined, undefined);
  }

}
