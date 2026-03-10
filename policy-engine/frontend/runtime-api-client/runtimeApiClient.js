// GENERATED FILE. DO NOT EDIT.
// Source: schemas/runtime_api_v1.openapi.json

export class RuntimeApiClient {
  constructor(options) {
    this.baseUrl = String(options.baseUrl || '').replace(/\/$/, '');
    this.headers = options.headers || {};
    this.fetchImpl = options.fetchImpl || fetch;
  }

  async request(method, path, query) {
    const suffix = query && query.toString() ? `?${query.toString()}` : '';
    const url = `${this.baseUrl}${path}${suffix}`;
    const response = await this.fetchImpl(url, { method, headers: this.headers });
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

  async getArtifactManifest(params) {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}`;
    return this.request('GET', path);
  }

  async getArtifactContent(params) {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/content`;
    const query = this.buildQuery({
      max_bytes: params?.max_bytes,
    });
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
    return this.request('GET', path);
  }

  async getControlCapabilities() {
    const path = `/api/v1/control/capabilities`;
    return this.request('GET', path);
  }

  async listBindingProfiles() {
    const path = `/api/v1/control/data/binding-profiles`;
    return this.request('GET', path);
  }

  async getCacheStatus() {
    const path = `/api/v1/control/data/cache`;
    return this.request('GET', path);
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
    return this.request('GET', path);
  }

  async getDataIndexStats() {
    const path = `/api/v1/control/data/index/stats`;
    return this.request('GET', path);
  }

  async listSourceProfiles() {
    const path = `/api/v1/control/data/profiles`;
    return this.request('GET', path);
  }

  async listDataPromotionCandidates() {
    const path = `/api/v1/control/data/promotion/candidates`;
    return this.request('GET', path);
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
    return this.request('GET', path);
  }

  async listLlmProfiles() {
    const path = `/api/v1/control/llm/profiles`;
    return this.request('GET', path);
  }

  async getRunErrors(params) {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/errors`;
    return this.request('GET', path);
  }

  async getGovernanceDebug(params) {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/governance`;
    return this.request('GET', path);
  }

  async getNodeDebug(params) {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/nodes/${encodeURIComponent(String(params.alias))}`;
    return this.request('GET', path);
  }

  async runtimeApiHealth() {
    const path = `/api/v1/health`;
    return this.request('GET', path);
  }

  async listRuns(params) {
    const path = `/api/v1/runs`;
    const query = this.buildQuery({
      limit: params?.limit,
      cursor: params?.cursor,
      status: params?.status,
      from_ts: params?.from_ts,
      to_ts: params?.to_ts,
    });
    return this.request('GET', path, query);
  }

  async getRunDetails(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}`;
    return this.request('GET', path);
  }

  async getRunAgents(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/agents`;
    return this.request('GET', path);
  }

  async getRunEvidenceContext(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/evidence-context`;
    return this.request('GET', path);
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
    return this.request('GET', path);
  }

  async getRunTimeline(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/timeline`;
    return this.request('GET', path);
  }

  async getRunWorkflow(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/workflow`;
    return this.request('GET', path);
  }

  async health() {
    const path = `/health`;
    return this.request('GET', path);
  }

  async ready() {
    const path = `/ready`;
    return this.request('GET', path);
  }

}
