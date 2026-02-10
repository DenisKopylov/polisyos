// GENERATED FILE. DO NOT EDIT.
// Source: schemas/runtime_api_v1.openapi.json

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | { [key: string]: JsonValue }
  | JsonValue[];

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

export type CursorPage = {
  count?: number;
  cursor?: string | null;
  limit?: number;
  next_cursor?: string | null;
  total?: number | null;
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

export type InputRef = {
  artifact_id: ArtifactID;
  role: string;
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

export type RunsListResponse = {
  meta: ApiMeta;
  page: CursorPage;
  runs?: Array<RunSummary>;
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
