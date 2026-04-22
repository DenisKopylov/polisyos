// GENERATED FILE. DO NOT EDIT.
// Source: schemas/runtime_api_v1.openapi.json

export class RuntimeApiClient {
  constructor(options) {
    this.baseUrl = String(options.baseUrl || '').replace(/\/$/, '');
    this.headers = options.headers || {};
    this.fetchImpl = options.fetchImpl || fetch;
  }

  async request(method, path, query, body) {
    const suffix = query && query.toString() ? `?${query.toString()}` : '';
    const url = `${this.baseUrl}${path}${suffix}`;
    const headers = body === undefined
      ? this.headers
      : { 'Content-Type': 'application/json', ...this.headers };
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
    return await response.json();
  }

  buildQuery(params) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params || {})) {
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

  async getArtifactBatch() {
    const path = `/api/v1/artifacts/batch`;
    const query = undefined;
    return this.request('POST', path, query, params?.body);
  }

  async getArtifactManifest(params) {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getArtifactContent(params) {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/content`;
    const query = this.buildQuery({
      max_bytes: params?.max_bytes,
    });
    return this.request('GET', path, query);
  }

  async downloadArtifactContent(params) {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/download`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getArtifactLineage(params) {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/lineage`;
    const query = this.buildQuery({
      max_depth: params?.max_depth,
      max_nodes: params?.max_nodes,
    });
    return this.request('GET', path, query);
  }

  async getArtifactSchema(params) {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/schema`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getAuthMe() {
    const path = `/api/v1/auth/me`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getControlCapabilities() {
    const path = `/api/v1/control/capabilities`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async listBindingProfiles() {
    const path = `/api/v1/control/data/binding-profiles`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getCacheStatus() {
    const path = `/api/v1/control/data/cache`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async searchDataCatalog(params) {
    const path = `/api/v1/control/data/catalog/search`;
    const query = this.buildQuery({
      metric: params?.metric,
      geo: params?.geo,
      limit: params?.limit,
    });
    return this.request('GET', path, query);
  }

  async listConnectors() {
    const path = `/api/v1/control/data/connectors`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getDataIndexStats() {
    const path = `/api/v1/control/data/index/stats`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async listSourceProfiles() {
    const path = `/api/v1/control/data/profiles`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async listDataPromotionCandidates() {
    const path = `/api/v1/control/data/promotion/candidates`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getPacketDecisionValidity(params) {
    const path = `/api/v1/control/decision-packets/${encodeURIComponent(String(params.decision_packet_ref))}/decision-validity`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getControlJobStatus(params) {
    const path = `/api/v1/control/jobs/${encodeURIComponent(String(params.job_id))}`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getLexGraphStats(params) {
    const path = `/api/v1/control/lex/graph/stats`;
    const query = this.buildQuery({
      output_dir: params?.output_dir,
    });
    return this.request('GET', path, query);
  }

  async getLexPipelineStatus(params) {
    const path = `/api/v1/control/lex/status/${encodeURIComponent(String(params.pipeline_id))}`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async listLlmProfiles() {
    const path = `/api/v1/control/llm/profiles`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async listControlOutbox(params) {
    const path = `/api/v1/control/outbox`;
    const query = this.buildQuery({
      state: params?.state,
      limit: params?.limit,
    });
    return this.request('GET', path, query);
  }

  async getRunDecisionValidity(params) {
    const path = `/api/v1/control/runs/${encodeURIComponent(String(params.run_id))}/decision-validity`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async listControlWorkers(params) {
    const path = `/api/v1/control/workers`;
    const query = this.buildQuery({
      active_only: params?.active_only,
    });
    return this.request('GET', path, query);
  }

  async getRunCompare(params) {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.left_run_id))}/compare/${encodeURIComponent(String(params.right_run_id))}`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getRunErrors(params) {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/errors`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getRunFeedback(params) {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/feedback`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getGovernanceDebug(params) {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/governance`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getNodeDebug(params) {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/nodes/${encodeURIComponent(String(params.alias))}`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async runtimeApiHealth() {
    const path = `/api/v1/health`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async computeMobilityBounds() {
    const path = `/api/v1/mobility/bounds`;
    const query = undefined;
    return this.request('POST', path, query, params?.body);
  }

  async estimateMobility() {
    const path = `/api/v1/mobility/estimate`;
    const query = undefined;
    return this.request('POST', path, query, params?.body);
  }

  async getMobilityReport(params) {
    const path = `/api/v1/mobility/reports/${encodeURIComponent(String(params.artifact_id))}`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getMobilityReportBounds(params) {
    const path = `/api/v1/mobility/reports/${encodeURIComponent(String(params.artifact_id))}/bounds`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getMobilityReportDiagnostics(params) {
    const path = `/api/v1/mobility/reports/${encodeURIComponent(String(params.artifact_id))}/diagnostics`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async listRuns(params) {
    const path = `/api/v1/runs`;
    const query = this.buildQuery({
      limit: params?.limit,
      cursor: params?.cursor,
      q: params?.q,
      status: params?.status,
      from_ts: params?.from_ts,
      to_ts: params?.to_ts,
    });
    return this.request('GET', path, query);
  }

  async getRunsBatch() {
    const path = `/api/v1/runs/batch`;
    const query = undefined;
    return this.request('POST', path, query, params?.body);
  }

  async getRunDetails(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getRunAgents(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/agents`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getRunEvidenceContext(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/evidence-context`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getRunLineage(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/lineage`;
    const query = this.buildQuery({
      root_artifact_id: params?.root_artifact_id,
      max_depth: params?.max_depth,
      max_nodes: params?.max_nodes,
    });
    return this.request('GET', path, query);
  }

  async getRunNodes(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/nodes`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getRunTimeline(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/timeline`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async getRunWorkflow(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/workflow`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async health() {
    const path = `/health`;
    const query = undefined;
    return this.request('GET', path, query);
  }

  async ready() {
    const path = `/ready`;
    const query = undefined;
    return this.request('GET', path, query);
  }

}
