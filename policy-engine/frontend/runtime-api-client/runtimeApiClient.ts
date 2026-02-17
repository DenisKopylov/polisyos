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
  latest_verdict?: string | null;
  notes?: Array<string>;
  reflexion_terminal_ref?: ArtifactRef | null;
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

export type ArtifactContentPreview = {
  artifact_id: string;
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
  source_lane?: "fastlane" | "explorelane";
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
  source_lane?: "fastlane" | "explorelane";
};

export type FetchPlanFallback = {
  connector_id: string;
  dataset_id: string;
  filters?: {
  [key: string]: Array<string>;
};
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
  fallback_from_decision_packet?: boolean;
  issues?: Array<{
  [key: string]: unknown;
}>;
  notes?: Array<string>;
  report_ref?: ArtifactRef | null;
  run_id: string;
  source_kind: string;
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
  source_lane?: "fastlane" | "explorelane";
  trust_score?: number;
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

export type NaturalLanguageRunRequest = {
  checkpoint_policy?: "strict" | "lenient" | "disabled";
  context?: {
  [key: string]: unknown;
};
  data_source?: DataSourceBinding | null;
  domain_hint?: string | null;
  llm_model?: string | null;
  llm_models?: Array<string> | null;
  max_iterations?: number;
  max_parallel_models?: number;
  per_model_budget_usd?: number | null;
  request: string;
  run_budget_usd?: number | null;
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
  source_lane?: "fastlane" | "explorelane";
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

export type RunDetails = {
  cell_id?: string | null;
  duration_ms?: number | null;
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

export type RunLaunchResponse = {
  message: string;
  meta: ApiMeta;
  run_id: string;
  status: "accepted" | "rejected";
};

export type RunLineageResponse = {
  lineage: ArtifactLineageView;
  meta: ApiMeta;
  run_id: string;
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

export type RunSummary = {
  cell_id?: string | null;
  duration_ms?: number | null;
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

export type ValidationError = {
  ctx?: {
  [key: string]: unknown;
};
  input?: unknown;
  loc: Array<string | number>;
  msg: string;
  type: string;
};

export type WorkflowRunRequest = {
  calibration_report_ref?: string | null;
  checkpoint_policy?: "strict" | "lenient" | "disabled";
  data_source: DataSourceBinding;
  knowledge_bundle_ref?: string | null;
  mode?: "workflow" | "agent_circuit";
  model_spec_ref?: string | null;
  norm_pack_ref?: string | null;
  params?: {
  [key: string]: unknown;
};
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
  ): Promise<T> {
    const url = query && query.toString()
      ? `${this.baseUrl}${path}?${query.toString()}`
      : `${this.baseUrl}${path}`;
    const response = await this.fetchImpl(url, { method, headers: this.headers });
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

  async getArtifactManifest(params: {
    artifact_id: string;
  }): Promise<ArtifactManifestResponse> {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}`;
    return this.request<ArtifactManifestResponse>("GET", path);
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
    return this.request<ArtifactSchemaResponse>("GET", path);
  }

  async listBindingProfiles(): Promise<BindingProfilesListResponse> {
    const path = `/api/v1/control/data/binding-profiles`;
    return this.request<BindingProfilesListResponse>("GET", path);
  }

  async getCacheStatus(): Promise<CacheStatusResponse> {
    const path = `/api/v1/control/data/cache`;
    return this.request<CacheStatusResponse>("GET", path);
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
    return this.request<ConnectorsListResponse>("GET", path);
  }

  async getDataIndexStats(): Promise<IndexStatsResponse> {
    const path = `/api/v1/control/data/index/stats`;
    return this.request<IndexStatsResponse>("GET", path);
  }

  async listSourceProfiles(): Promise<SourceProfilesListResponse> {
    const path = `/api/v1/control/data/profiles`;
    return this.request<SourceProfilesListResponse>("GET", path);
  }

  async listDataPromotionCandidates(): Promise<PromotionCandidatesResponse> {
    const path = `/api/v1/control/data/promotion/candidates`;
    return this.request<PromotionCandidatesResponse>("GET", path);
  }

  async listLlmProfiles(): Promise<ModelProfilesListResponse> {
    const path = `/api/v1/control/llm/profiles`;
    return this.request<ModelProfilesListResponse>("GET", path);
  }

  async getRunErrors(params: {
    run_id: string;
  }): Promise<RunErrorsResponse> {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/errors`;
    return this.request<RunErrorsResponse>("GET", path);
  }

  async getGovernanceDebug(params: {
    run_id: string;
  }): Promise<GovernanceDebugResponse> {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/governance`;
    return this.request<GovernanceDebugResponse>("GET", path);
  }

  async getNodeDebug(params: {
    run_id: string;
    alias: string;
  }): Promise<NodeDebugResponse> {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/nodes/${encodeURIComponent(String(params.alias))}`;
    return this.request<NodeDebugResponse>("GET", path);
  }

  async runtimeApiHealth(): Promise<{
  [key: string]: string;
}> {
    const path = `/api/v1/health`;
    return this.request<{
  [key: string]: string;
}>("GET", path);
  }

  async listRuns(params: {
    limit?: number;
    cursor?: string | null;
    status?: string | null;
    from_ts?: string | null;
    to_ts?: string | null;
  }): Promise<RunsListResponse> {
    const path = `/api/v1/runs`;
    const query = this.buildQuery({
      limit: params.limit,
      cursor: params.cursor,
      status: params.status,
      from_ts: params.from_ts,
      to_ts: params.to_ts,
    });
    return this.request<RunsListResponse>("GET", path, query);
  }

  async getRunDetails(params: {
    run_id: string;
  }): Promise<RunDetailsResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}`;
    return this.request<RunDetailsResponse>("GET", path);
  }

  async getRunAgents(params: {
    run_id: string;
  }): Promise<AgentPipelineResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/agents`;
    return this.request<AgentPipelineResponse>("GET", path);
  }

  async getRunLineage(params: {
    run_id: string;
    root_artifact_id?: Array<string> | null;
    max_depth?: number | null;
    max_nodes?: number | null;
  }): Promise<RunLineageResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/lineage`;
    const query = this.buildQuery({
      root_artifact_id: params.root_artifact_id,
      max_depth: params.max_depth,
      max_nodes: params.max_nodes,
    });
    return this.request<RunLineageResponse>("GET", path, query);
  }

  async getRunNodes(params: {
    run_id: string;
  }): Promise<RunNodesResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/nodes`;
    return this.request<RunNodesResponse>("GET", path);
  }

  async getRunTimeline(params: {
    run_id: string;
  }): Promise<RunTimelineResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/timeline`;
    return this.request<RunTimelineResponse>("GET", path);
  }

  async getRunWorkflow(params: {
    run_id: string;
  }): Promise<RunWorkflowResponse> {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/workflow`;
    return this.request<RunWorkflowResponse>("GET", path);
  }

  async health(): Promise<{
  [key: string]: string;
}> {
    const path = `/health`;
    return this.request<{
  [key: string]: string;
}>("GET", path);
  }

  async ready(): Promise<{
  [key: string]: string;
}> {
    const path = `/ready`;
    return this.request<{
  [key: string]: string;
}>("GET", path);
  }

}
