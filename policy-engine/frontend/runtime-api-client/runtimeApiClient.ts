// GENERATED FILE. DO NOT EDIT.
// Source: schemas/runtime_api_v1.openapi.json

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | { [key: string]: JsonValue }
  | JsonValue[];

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
  decision_packet_ref?: ArtifactRef | null;
  evaluator?: EvaluatorReportView | null;
  execution_plan_ref?: ArtifactRef | null;
  iteration_lifecycle?: IterationLifecycleView | null;
  latest_verdict?: string | null;
  method_catalog_snapshot_ref?: ArtifactRef | null;
  notes?: Array<string>;
  preflight?: PreflightReportView | null;
  reflexion_terminal_ref?: ArtifactRef | null;
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

export type ArtifactRef = {
  artifact_id: ArtifactID;
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
  exec_plan_ref?: ExecPlanRef | null;
  feedback_jacobian_diagnostics_ref?: FeedbackJacobianDiagnosticsRef | null;
  feedback_result_ref?: FeedbackResultRef | null;
  initial_states?: Array<{
  [key: string]: number;
}>;
  largest_lyapunov_exponent?: number | null;
  max_period?: number;
  model_ref?: ArtifactRef | null;
  notes?: Array<string>;
  parameter_point?: AttractorParameterPoint;
  persist_artifact?: boolean;
  rtol?: number;
  schema_version?: string;
  seeds?: Array<number>;
  simulation_result_ref?: SimulationResultRef | null;
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
  exec_plan_ref?: ExecPlanRef | null;
  feedback_result_ref?: FeedbackResultRef | null;
  kind?: string;
  model_ref?: ArtifactRef | null;
  notes?: Array<string>;
  parameter_point?: AttractorParameterPoint;
  provenance?: AttractorAnalysisProvenance;
  schema_version?: string;
  simulation_result_ref?: SimulationResultRef | null;
  state_projection: AttractorStateProjection;
  uncertainty_summary?: AttractorUncertaintySummary;
};

export type AttractorAnalysisResultRef = {
  artifact_id: ArtifactID;
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
  proof_artifact_ref?: ArtifactRef | null;
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
  invariant_set_artifact_ref?: ArtifactRef | null;
  orbit_artifact_ref?: ArtifactRef | null;
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

export type AuthMeResponse = {
  cell_id?: string | null;
  display_name: string;
  feature_overrides?: {
  [key: string]: boolean;
};
  meta: ApiMeta;
  mfa_verified?: boolean;
  permissions?: Array<string>;
  principal_type?: "anonymous" | "service" | "user";
  roles?: Array<string>;
  tenant_id: string;
  user_id: string;
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
  artifact_id: ArtifactID;
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
  causal_diagnostics_ref?: ArtifactRef | null;
  dependence_ref?: ArtifactRef | null;
  governance_artifact_ref?: ArtifactRef | null;
  quality_certificate_ref?: ArtifactRef | null;
  sae_estimates_ref?: ArtifactRef | null;
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
  artifact_id: ArtifactID;
  kind?: string;
  media_type?: string;
};

export type ControlJobResponse = {
  capability_manifest_ref?: ArtifactRef | null;
  effective_execution_profile: "dev" | "research" | "governed" | "production";
  error_message?: string | null;
  finished_at?: string | null;
  job_id: string;
  kind: "workflow_run" | "natural_language_run" | "lex_pipeline";
  meta: ApiMeta;
  pipeline_id?: string | null;
  progress?: {
  [key: string]: unknown;
};
  requested_execution_profile?: "dev" | "research" | "governed" | "production" | null;
  run_id?: string | null;
  started_at?: string | null;
  state: "pending" | "running" | "completed" | "failed";
  submitted_at?: string | null;
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

export type CursorPage = {
  count?: number;
  cursor?: string | null;
  limit?: number;
  next_cursor?: string | null;
  total?: number | null;
};

export type DataCatalogSearchResponse = {
  matches?: Array<MetricCandidate>;
  meta: ApiMeta;
  query: string;
  total_matches?: number;
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

export type DecisionTriggerType = "law_change" | "dataset_superseded" | "historical_semantic_revision" | "contradicting_evidence" | "context_profile_drift" | "post_deployment_refutation" | "human_gate" | "expert_review" | "legacy_packet" | "superseded" | "revoked";

export type DecisionValidityEventRequest = {
  dedupe_key?: string | null;
  dependency_keys?: Array<string>;
  occurred_at?: string | null;
  payload?: {
  [key: string]: unknown;
};
  reason: string;
  source_ref?: string | null;
  status: DecisionValidityStatus;
  trigger_type: DecisionTriggerType;
};

export type DecisionValidityEventResponse = {
  affected_packets?: Array<string>;
  affected_statuses?: {
  [key: string]: number;
};
  dedupe_key: string;
  event_id: string;
  message: string;
  meta: ApiMeta;
};

export type DecisionValidityLifecycleSummary = {
  events?: Array<DecisionDependencyEvent>;
  latest_transition_at?: string | null;
  pending_reviews?: Array<DecisionValidityPendingReview>;
  reissue_candidates?: Array<ArtifactRef>;
  scheduled_jobs?: Array<DecisionLifecycleJob>;
  transitions?: Array<DecisionValidityTransition>;
};

export type DecisionValidityPendingReview = {
  event_id: string;
  occurred_at: string;
  reason: string;
  trigger_type: DecisionTriggerType;
};

export type DecisionValidityStatus = "active" | "warning" | "stale" | "superseded" | "revoked" | "requires_human_review";

export type DecisionValiditySummaryResponse = {
  checked_at: string;
  decision_lineage_key: string;
  decision_packet_ref: ArtifactRef;
  evaluation_ref?: ArtifactRef | null;
  lifecycle?: DecisionValidityLifecycleSummary;
  meta: ApiMeta;
  reasons?: Array<string>;
  recommended_action: string;
  review_required?: boolean;
  run_id?: string | null;
  status: DecisionValidityStatus;
  superseded_by_ref?: ArtifactRef | null;
  supersedes_decision_ref?: ArtifactRef | null;
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

export type DerivedArtifact = {
  ref: ArtifactRef;
  role: string;
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
  report_ref?: ArtifactRef | null;
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

export type ExecPlanRef = {
  artifact_id: ArtifactID;
  kind?: string;
  media_type?: string;
};

export type FeedbackActionResponse = {
  action: "evaluate_feedback" | "reissue";
  compare_report_ref?: ArtifactRef | null;
  message: string;
  meta: ApiMeta;
  monitoring_report_ref?: ArtifactRef | null;
  reissue_plan_ref?: ArtifactRef | null;
  reissued_run_id?: string | null;
  run_id: string;
  status?: "completed" | "accepted";
};

export type FeedbackJacobianDiagnosticsRef = {
  artifact_id: ArtifactID;
  kind?: string;
  media_type?: string;
};

export type FeedbackResultRef = {
  artifact_id: ArtifactID;
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
  [key: string]: ArtifactRef | null;
} | null;
  normative_arbitration_result_ref?: ArtifactRef | null;
  normative_summary?: {
  [key: string]: unknown;
} | null;
  notes?: Array<string>;
  report_kind?: string | null;
  report_ref?: ArtifactRef | null;
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

export type HTTPValidationError = {
  detail?: Array<ValidationError>;
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
  artifact_id: ArtifactID;
  role: string;
};

export type IterationLifecycleView = {
  iteration?: number;
  last_verdict?: "APPROVE" | "REPLAN_DATA" | "REPLAN_METHOD" | "REPLAN_PARAMS" | "STOP_BUDGET" | null;
  notes?: Array<string>;
  state?: "plan_created" | "preflight_running" | "preflight_failed" | "ready_to_run" | "executing" | "evaluating" | "replanning" | "approved" | "stopped_budget" | "stopped_no_delta" | "stopped_guardrail";
  state_ref?: ArtifactRef | null;
  stop_reason?: "approved" | "budget_exhausted" | "no_delta" | "guardrail_violation" | null;
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
  condition_text_uk?: string;
  confidence: number;
  doc_name: string;
  doc_reestr_code: string;
  exception_text_uk?: string;
  fact_id: string;
  fact_text: string;
  norm_type: string;
  norm_type_canon?: string;
  object_name: string;
  predicate: string;
  procedure_text_uk?: string;
  provision_citation: string;
  source_quote_uk?: string;
  subject_name: string;
  thresholds_json?: string;
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

export type LineageRefOutput = {
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
  bounds_bundle_ref?: ArtifactRef | null;
  cell_bounds?: {
  [key: string]: Array<number>;
};
  meta: ApiMeta;
  mobility_report_ref?: ArtifactRef | null;
  summary_bounds?: {
  [key: string]: Array<number>;
};
};

export type MobilityDiagnosticsResponse = {
  diagnostics: {
  [key: string]: unknown;
};
  meta: ApiMeta;
  mobility_report_ref: ArtifactRef;
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
  bounds_bundle_ref?: ArtifactRef | null;
  meta: ApiMeta;
  mobility_report_ref?: ArtifactRef | null;
  report: {
  [key: string]: unknown;
};
};

export type MobilityReportResponse = {
  meta: ApiMeta;
  mobility_report_ref: ArtifactRef;
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

export type PolicyFlags = {
  allow_mock_fallback?: boolean;
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
  report_ref?: ArtifactRef | null;
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
  time?: TemporalRef | null;
  uncertainty?: QuantityUncertainty | null;
  unit: UnitRef;
};

export type QuantityValueOutput = {
  label?: string | null;
  lineage: LineageRefOutput;
  metric_id?: string | null;
  point?: number | null;
  quantity_class?: "decision" | "telemetry" | "layout" | "debug";
  time?: TemporalRef | null;
  uncertainty?: QuantityUncertainty | null;
  unit: UnitRef;
};

export type ReproducibilityView = {
  data_snapshot_hash?: string | null;
  determinism_tier?: string | null;
  input_bindings_hash?: string | null;
  manifest_ref?: ArtifactRef | null;
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
  capability_manifest_ref?: ArtifactRef | null;
  cell_id?: string | null;
  control_job_id?: string | null;
  decision_review_required?: boolean;
  decision_superseded_by_ref?: ArtifactRef | null;
  decision_validity_checked_at?: string | null;
  decision_validity_status?: DecisionValidityStatus | null;
  duration_ms?: number | null;
  execution_profile?: string | null;
  finished_at?: string | null;
  has_trace?: boolean;
  has_workflow_report?: boolean;
  manifest_ref?: ArtifactRef | null;
  root_artifacts?: Array<ArtifactRef>;
  run_id: string;
  source_kind: string;
  started_at?: string | null;
  status: string;
  tenant_id?: string | null;
  trace_ref?: ArtifactRef | null;
  warnings?: Array<string>;
  workflow_report_ref?: ArtifactRef | null;
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
  report_ref?: ArtifactRef | null;
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
  data_snapshot_ref?: ArtifactRef | null;
  evidence_bundle_ref?: ArtifactRef | null;
  execution_plan_ref?: ArtifactRef | null;
  fetch_plans?: Array<RunEvidencePlanView>;
  input_bindings_ref?: ArtifactRef | null;
  promotion_candidates?: Array<RunEvidencePromotionView>;
  related_artifacts?: Array<ArtifactRef>;
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
  decision_packet_ref?: ArtifactRef | null;
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
  decision_superseded_by_ref?: ArtifactRef | null;
  decision_validity_checked_at?: string | null;
  decision_validity_status?: DecisionValidityStatus | null;
  duration_ms?: number | null;
  execution_profile?: string | null;
  finished_at?: string | null;
  has_trace?: boolean;
  has_workflow_report?: boolean;
  root_artifact_count?: number;
  run_id: string;
  source_kind: string;
  started_at?: string | null;
  status: string;
  tenant_id?: string | null;
  warnings?: Array<string>;
};

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
  workflow_report_ref?: ArtifactRef | null;
  workflow_spec_ref?: ArtifactRef | null;
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
  lineage: LineageRefOutput;
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
  baseline_lineage?: LineageRefOutput | null;
  baseline_run_id: string;
  computed_at?: string | null;
  constraints?: Array<ScenarioConstraintOutput>;
  id: string;
  interventions: Array<ScenarioInterventionOutput>;
  known_limitations?: Array<string>;
  lifecycle_status?: "generated" | "draft" | "saved" | "promoted";
  manifest_hash?: string;
  model_family: string;
  model_lineage: LineageRefOutput;
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
  lineage: LineageRefOutput;
  manifest_hash?: string | null;
  status: "draft" | "computed" | "stale" | "failed";
  temporal_scope?: TemporalScope | null;
};

export type SimulationResultRef = {
  artifact_id: ArtifactID;
  kind?: string;
  media_type?: string;
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

export type TemporalCapabilitiesResponse = {
  capabilities: TemporalCapabilitiesView;
  meta: ApiMeta;
};

export type TemporalCapabilitiesView = {
  default_scope?: TemporalScope | null;
  event_points?: Array<TemporalEventPoint>;
  resolution?: string;
  run_id?: string | null;
  surfaces?: Array<TemporalSurfaceCapability>;
  tx_range?: TemporalRange;
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

export type TemporalRange = {
  earliest?: string | null;
  latest?: string | null;
};

export type TemporalRef = {
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
  surface: "run_details" | "run_timeline" | "run_lineage" | "run_quantities" | "run_compare" | "run_agents" | "run_evidence_context" | "run_workflow" | "run_nodes" | "artifact_content";
  tx_range?: TemporalRange | null;
  valid_range?: TemporalRange | null;
};

export type UnitRef = {
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
  ): Promise<T> {
    const url = query && query.toString()
      ? `${this.baseUrl}${path}?${query.toString()}`
      : `${this.baseUrl}${path}`;
    const headers = body === undefined
      ? this.headers
      : { "Content-Type": "application/json", ...this.headers };
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
    return this.request<AttractorAnalysisResult>("GET", path, query);
  }

  async getAnalysisBasinMap(params: {
    analysis_id: string;
    basin_id: string;
  }): Promise<BasinMap> {
    const path = `/api/v1/analysis/${encodeURIComponent(String(params.analysis_id))}/basin/${encodeURIComponent(String(params.basin_id))}`;
    const query = undefined;
    return this.request<BasinMap>("GET", path, query);
  }

  async getAnalysisContinuationBranch(params: {
    analysis_id: string;
    branch_id: string;
  }): Promise<ContinuationBranchOutput> {
    const path = `/api/v1/analysis/${encodeURIComponent(String(params.analysis_id))}/branch/${encodeURIComponent(String(params.branch_id))}`;
    const query = undefined;
    return this.request<ContinuationBranchOutput>("GET", path, query);
  }

  async getArtifactBatch(params: {
    body: ArtifactBatchRequest;
  }): Promise<ArtifactBatchResponse> {
    const path = `/api/v1/artifacts/batch`;
    const query = undefined;
    return this.request<ArtifactBatchResponse>("POST", path, query, params.body);
  }

  async getArtifactManifest(params: {
    artifact_id: string;
  }): Promise<ArtifactManifestResponse> {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}`;
    const query = undefined;
    return this.request<ArtifactManifestResponse>("GET", path, query);
  }

  async getArtifactContent(params: {
    artifact_id: string;
    max_bytes?: number | null;
  }): Promise<ArtifactContentResponse> {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/content`;
    const query = this.buildQuery({
      max_bytes: params.max_bytes,
    });
    return this.request<ArtifactContentResponse>("GET", path, query);
  }

  async downloadArtifactContent(params: {
    artifact_id: string;
  }): Promise<unknown> {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/download`;
    const query = undefined;
    return this.request<unknown>("GET", path, query);
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
    return this.request<ArtifactLineageResponse>("GET", path, query);
  }

  async getArtifactSchema(params: {
    artifact_id: string;
  }): Promise<ArtifactSchemaResponse> {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/schema`;
    const query = undefined;
    return this.request<ArtifactSchemaResponse>("GET", path, query);
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
    });
    return this.request<BureaucraticExportResponse>("GET", path, query);
  }

  async getAuthMe(): Promise<AuthMeResponse> {
    const path = `/api/v1/auth/me`;
    const query = undefined;
    return this.request<AuthMeResponse>("GET", path, query);
  }

  async getControlCapabilities(): Promise<CapabilityManifestResponse> {
    const path = `/api/v1/control/capabilities`;
    const query = undefined;
    return this.request<CapabilityManifestResponse>("GET", path, query);
  }

  async listBindingProfiles(): Promise<BindingProfilesListResponse> {
    const path = `/api/v1/control/data/binding-profiles`;
    const query = undefined;
    return this.request<BindingProfilesListResponse>("GET", path, query);
  }

  async getCacheStatus(): Promise<CacheStatusResponse> {
    const path = `/api/v1/control/data/cache`;
    const query = undefined;
    return this.request<CacheStatusResponse>("GET", path, query);
  }

  async searchDataCatalog(params: {
    metric: string;
    geo?: string | null;
    limit?: number;
  }): Promise<DataCatalogSearchResponse> {
    const path = `/api/v1/control/data/catalog/search`;
    const query = this.buildQuery({
      metric: params.metric,
      geo: params.geo,
      limit: params.limit,
    });
    return this.request<DataCatalogSearchResponse>("GET", path, query);
  }

  async listConnectors(): Promise<ConnectorsListResponse> {
    const path = `/api/v1/control/data/connectors`;
    const query = undefined;
    return this.request<ConnectorsListResponse>("GET", path, query);
  }

  async getDataIndexStats(): Promise<IndexStatsResponse> {
    const path = `/api/v1/control/data/index/stats`;
    const query = undefined;
    return this.request<IndexStatsResponse>("GET", path, query);
  }

  async listSourceProfiles(): Promise<SourceProfilesListResponse> {
    const path = `/api/v1/control/data/profiles`;
    const query = undefined;
    return this.request<SourceProfilesListResponse>("GET", path, query);
  }

  async listDataPromotionCandidates(): Promise<PromotionCandidatesResponse> {
    const path = `/api/v1/control/data/promotion/candidates`;
    const query = undefined;
    return this.request<PromotionCandidatesResponse>("GET", path, query);
  }

  async getPacketDecisionValidity(params: {
    decision_packet_ref: string;
  }): Promise<DecisionValiditySummaryResponse> {
    const path = `/api/v1/control/decision-packets/${encodeURIComponent(String(params.decision_packet_ref))}/decision-validity`;
    const query = undefined;
    return this.request<DecisionValiditySummaryResponse>("GET", path, query);
  }

  async getControlJobStatus(params: {
    job_id: string;
  }): Promise<ControlJobResponse> {
    const path = `/api/v1/control/jobs/${encodeURIComponent(String(params.job_id))}`;
    const query = undefined;
    return this.request<ControlJobResponse>("GET", path, query);
  }

  async getLexGraphStats(params: {
    output_dir: string;
  }): Promise<LexGraphStatsResponse> {
    const path = `/api/v1/control/lex/graph/stats`;
    const query = this.buildQuery({
      output_dir: params.output_dir,
    });
    return this.request<LexGraphStatsResponse>("GET", path, query);
  }

  async getLexPipelineStatus(params: {
    pipeline_id: string;
  }): Promise<LexPipelineStatusResponse> {
    const path = `/api/v1/control/lex/status/${encodeURIComponent(String(params.pipeline_id))}`;
    const query = undefined;
    return this.request<LexPipelineStatusResponse>("GET", path, query);
  }

  async listLlmProfiles(): Promise<ModelProfilesListResponse> {
    const path = `/api/v1/control/llm/profiles`;
    const query = undefined;
    return this.request<ModelProfilesListResponse>("GET", path, query);
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
    return this.request<ControlOutboxEventsResponse>("GET", path, query);
  }

  async getRunDecisionValidity(params: {
    run_id: string;
  }): Promise<DecisionValiditySummaryResponse> {
    const path = `/api/v1/control/runs/${encodeURIComponent(String(params.run_id))}/decision-validity`;
    const query = undefined;
    return this.request<DecisionValiditySummaryResponse>("GET", path, query);
  }

  async listControlWorkers(params: {
    active_only?: boolean;
  }): Promise<ControlWorkersResponse> {
    const path = `/api/v1/control/workers`;
    const query = this.buildQuery({
      active_only: params.active_only,
    });
    return this.request<ControlWorkersResponse>("GET", path, query);
  }

  async getRunCompare(params: {
    left_run_id: string;
    right_run_id: string;
  }): Promise<RunCompareResponse> {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.left_run_id))}/compare/${encodeURIComponent(String(params.right_run_id))}`;
    const query = undefined;
    return this.request<RunCompareResponse>("GET", path, query);
  }

  async getRunEquilibria(params: {
    run_id: string;
  }): Promise<RunEquilibriaResponse> {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/equilibria`;
    const query = undefined;
    return this.request<RunEquilibriaResponse>("GET", path, query);
  }

  async getRunErrors(params: {
    run_id: string;
  }): Promise<RunErrorsResponse> {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/errors`;
    const query = undefined;
    return this.request<RunErrorsResponse>("GET", path, query);
  }

  async getRunFeedback(params: {
    run_id: string;
  }): Promise<RunFeedbackResponse> {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/feedback`;
    const query = undefined;
    return this.request<RunFeedbackResponse>("GET", path, query);
  }

  async getGovernanceDebug(params: {
    run_id: string;
  }): Promise<GovernanceDebugResponse> {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/governance`;
    const query = undefined;
    return this.request<GovernanceDebugResponse>("GET", path, query);
  }

  async getNodeDebug(params: {
    run_id: string;
    alias: string;
  }): Promise<NodeDebugResponse> {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/nodes/${encodeURIComponent(String(params.alias))}`;
    const query = undefined;
    return this.request<NodeDebugResponse>("GET", path, query);
  }

  async runtimeApiHealth(): Promise<{
  [key: string]: unknown;
}> {
    const path = `/api/v1/health`;
    const query = undefined;
    return this.request<{
  [key: string]: unknown;
}>("GET", path, query);
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
    return this.request<LineageResponse>("GET", path, query);
  }

  async exportLineageOpenlineage(params: {
    lineage_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
  }): Promise<LineageExportResponse> {
    const path = `/api/v1/lineage/${encodeURIComponent(String(params.lineage_id))}/export/openlineage`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<LineageExportResponse>("GET", path, query);
  }

  async exportLineageProv(params: {
    lineage_id: string;
    valid_at?: string | null;
    tx_at?: string | null;
    t?: string | null;
    branch?: string | null;
    snapshot_id?: string | null;
    scenario_id?: string | null;
  }): Promise<LineageExportResponse> {
    const path = `/api/v1/lineage/${encodeURIComponent(String(params.lineage_id))}/export/prov`;
    const query = this.buildQuery({
      valid_at: params.valid_at,
      tx_at: params.tx_at,
      t: params.t,
      branch: params.branch,
      snapshot_id: params.snapshot_id,
      scenario_id: params.scenario_id,
    });
    return this.request<LineageExportResponse>("GET", path, query);
  }

  async computeMobilityBounds(params: {
    body: MobilityBoundsRequest;
  }): Promise<MobilityBoundsResponse> {
    const path = `/api/v1/mobility/bounds`;
    const query = undefined;
    return this.request<MobilityBoundsResponse>("POST", path, query, params.body);
  }

  async estimateMobility(params: {
    body: MobilityEstimateRequest;
  }): Promise<MobilityEstimateResponse> {
    const path = `/api/v1/mobility/estimate`;
    const query = undefined;
    return this.request<MobilityEstimateResponse>("POST", path, query, params.body);
  }

  async getMobilityReport(params: {
    artifact_id: string;
  }): Promise<MobilityReportResponse> {
    const path = `/api/v1/mobility/reports/${encodeURIComponent(String(params.artifact_id))}`;
    const query = undefined;
    return this.request<MobilityReportResponse>("GET", path, query);
  }

  async getMobilityReportBounds(params: {
    artifact_id: string;
  }): Promise<MobilityBoundsResponse> {
    const path = `/api/v1/mobility/reports/${encodeURIComponent(String(params.artifact_id))}/bounds`;
    const query = undefined;
    return this.request<MobilityBoundsResponse>("GET", path, query);
  }

  async getMobilityReportDiagnostics(params: {
    artifact_id: string;
  }): Promise<MobilityDiagnosticsResponse> {
    const path = `/api/v1/mobility/reports/${encodeURIComponent(String(params.artifact_id))}/diagnostics`;
    const query = undefined;
    return this.request<MobilityDiagnosticsResponse>("GET", path, query);
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
    return this.request<RunsListResponse>("GET", path, query);
  }

  async getRunsBatch(params: {
    body: RunsBatchRequest;
  }): Promise<RunsBatchResponse> {
    const path = `/api/v1/runs/batch`;
    const query = undefined;
    return this.request<RunsBatchResponse>("POST", path, query, params.body);
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
    return this.request<CompareRunResponse>("GET", path, query);
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
    return this.request<RunDetailsResponse>("GET", path, query);
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
    return this.request<AgentPipelineResponse>("GET", path, query);
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
    return this.request<CompareCandidatesResponse>("GET", path, query);
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
    return this.request<RunEvidenceContextResponse>("GET", path, query);
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
    return this.request<RunLineageResponse>("GET", path, query);
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
    return this.request<CounterfactualMetricsResponse>("GET", path, query);
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
    return this.request<RunNodesResponse>("GET", path, query);
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
    return this.request<RunQuantitiesResponse>("GET", path, query);
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
    return this.request<ScenarioListResponse>("GET", path, query);
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
    return this.request<RunTimelineResponse>("GET", path, query);
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
    return this.request<RunWorkflowResponse>("GET", path, query);
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
    return this.request<ScenarioManifestResponse>("GET", path, query);
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
    return this.request<ScenarioCapabilitiesResponse>("GET", path, query);
  }

  async getTemporalCapabilities(params: {
    run_id?: string | null;
  }): Promise<TemporalCapabilitiesResponse> {
    const path = `/api/v1/temporal/capabilities`;
    const query = this.buildQuery({
      run_id: params.run_id,
    });
    return this.request<TemporalCapabilitiesResponse>("GET", path, query);
  }

  async health(): Promise<{
  [key: string]: unknown;
}> {
    const path = `/health`;
    const query = undefined;
    return this.request<{
  [key: string]: unknown;
}>("GET", path, query);
  }

  async ready(): Promise<{
  [key: string]: unknown;
}> {
    const path = `/ready`;
    const query = undefined;
    return this.request<{
  [key: string]: unknown;
}>("GET", path, query);
  }

}
