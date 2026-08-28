// GENERATED FILE. DO NOT EDIT.
// Source: schemas/runtime_api_v1.openapi.json

export class RuntimeApiClient {
  constructor(options) {
    this.baseUrl = String(options.baseUrl || '').replace(/\/$/, '');
    this.headers = options.headers || {};
    this.fetchImpl = options.fetchImpl || fetch;
  }

  async request(method, path, query, body, requestHeaders, responseMode = 'json') {
    const suffix = query && query.toString() ? `?${query.toString()}` : '';
    const url = `${this.baseUrl}${path}${suffix}`;
    const headers = new Headers(this.headers);
    if (body !== undefined && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
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
    if (responseMode === 'arrayBuffer') {
      return await response.arrayBuffer();
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

  async getAttractorAnalysis(params) {
    const path = `/api/v1/analysis/${encodeURIComponent(String(params.analysis_id))}`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getAnalysisBasinMap(params) {
    const path = `/api/v1/analysis/${encodeURIComponent(String(params.analysis_id))}/basin/${encodeURIComponent(String(params.basin_id))}`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getAnalysisContinuationBranch(params) {
    const path = `/api/v1/analysis/${encodeURIComponent(String(params.analysis_id))}/branch/${encodeURIComponent(String(params.branch_id))}`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getArtifactBatch(params) {
    const path = `/api/v1/artifacts/batch`;
    const query = undefined;
    return this.request('POST', path, query, params?.body, undefined);
  }

  async getArtifactManifest(params) {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getArtifactContent(params) {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/content`;
    const query = this.buildQuery({
      max_bytes: params?.max_bytes,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async downloadArtifactContent(params) {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/download`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getArtifactLineage(params) {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/lineage`;
    const query = this.buildQuery({
      max_depth: params?.max_depth,
      max_nodes: params?.max_nodes,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getArtifactSchema(params) {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.artifact_id))}/schema`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async exportBureaucraticArtifact(params) {
    const path = `/api/v1/artifacts/${encodeURIComponent(String(params.packet_id))}/export`;
    const query = this.buildQuery({
      format: params?.format,
      genre: params?.genre,
      jurisdiction: params?.jurisdiction,
      template_version: params?.template_version,
      trust_view: params?.trust_view,
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      export_projection_hash: params?.export_projection_hash,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getAuthMe() {
    const path = `/api/v1/auth/me`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getControlCapabilities() {
    const path = `/api/v1/control/capabilities`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async searchCapabilities(params) {
    const path = `/api/v1/control/capabilities/search`;
    const query = undefined;
    return this.request('POST', path, query, params?.body, undefined);
  }

  async listBindingProfiles() {
    const path = `/api/v1/control/data/binding-profiles`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getCacheStatus() {
    const path = `/api/v1/control/data/cache`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async searchDataCatalog(params) {
    const path = `/api/v1/control/data/catalog/search`;
    const query = this.buildQuery({
      metric: params?.metric,
      geo: params?.geo,
      limit: params?.limit,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async listConnectors() {
    const path = `/api/v1/control/data/connectors`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getDataIndexStats() {
    const path = `/api/v1/control/data/index/stats`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async listSourceProfiles() {
    const path = `/api/v1/control/data/profiles`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async listDataPromotionCandidates() {
    const path = `/api/v1/control/data/promotion/candidates`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getPacketDecisionValidity(params) {
    const path = `/api/v1/control/decision-packets/${encodeURIComponent(String(params.decision_packet_ref))}/decision-validity`;
    const query = this.buildQuery({
      export_projection_hash: params?.export_projection_hash,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async admitEpochValidityBatch(params) {
    const path = `/api/v1/control/decision-validity/epoch-batches`;
    const query = undefined;
    return this.request('POST', path, query, params?.body, undefined);
  }

  async getControlJobStatus(params) {
    const path = `/api/v1/control/jobs/${encodeURIComponent(String(params.job_id))}`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getLexGraphStats(params) {
    const path = `/api/v1/control/lex/graph/stats`;
    const query = this.buildQuery({
      output_dir: params?.output_dir,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getLexPipelineStatus(params) {
    const path = `/api/v1/control/lex/status/${encodeURIComponent(String(params.pipeline_id))}`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async listLlmProfiles() {
    const path = `/api/v1/control/llm/profiles`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async listControlOutbox(params) {
    const path = `/api/v1/control/outbox`;
    const query = this.buildQuery({
      state: params?.state,
      limit: params?.limit,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunDecisionValidity(params) {
    const path = `/api/v1/control/runs/${encodeURIComponent(String(params.run_id))}/decision-validity`;
    const query = this.buildQuery({
      export_projection_hash: params?.export_projection_hash,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async listControlWorkers(params) {
    const path = `/api/v1/control/workers`;
    const query = this.buildQuery({
      active_only: params?.active_only,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunCompare(params) {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.left_run_id))}/compare/${encodeURIComponent(String(params.right_run_id))}`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunEquilibria(params) {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/equilibria`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunErrors(params) {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/errors`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunFeedback(params) {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/feedback`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getGovernanceDebug(params) {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/governance`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getNodeDebug(params) {
    const path = `/api/v1/debug/runs/${encodeURIComponent(String(params.run_id))}/nodes/${encodeURIComponent(String(params.alias))}`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRuntimeChannelRegistry() {
    const path = `/api/v1/exports/channel-registry`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async listGovernedProjections() {
    const path = `/api/v1/exports/governed-projections`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getDepthNCycleBoardProjection(params) {
    const path = `/api/v1/exports/governed-projections/depth-n-cycle-board`;
    const query = this.buildQuery({
      replay_target: params?.replay_target,
      artifact_content_hash: params?.artifact_content_hash,
      projection_hash: params?.projection_hash,
      source_dependency_hash: params?.source_dependency_hash,
      source_as_of: params?.source_as_of,
      projection_rule_version: params?.projection_rule_version,
      composition_manifest_hash: params?.composition_manifest_hash,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getGovernedProjection(params) {
    const path = `/api/v1/exports/governed-projections/${encodeURIComponent(String(params.projection_id))}`;
    const query = this.buildQuery({
      artifact_content_hash: params?.artifact_content_hash,
      projection_hash: params?.projection_hash,
      source_dependency_hash: params?.source_dependency_hash,
      source_as_of: params?.source_as_of,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async analyzeFabricImpact(params) {
    const path = `/api/v1/fabric/impact`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('POST', path, query, params?.body, undefined);
  }

  async getFabricQualityBatch(params) {
    const path = `/api/v1/fabric/quality/batch`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('POST', path, query, params?.body, undefined);
  }

  async getFabricRunReplay(params) {
    const path = `/api/v1/fabric/runs/${encodeURIComponent(String(params.run_id))}/replay`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getFabricSourceScorecards() {
    const path = `/api/v1/fabric/source-scorecards`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getFabricTrustBatch(params) {
    const path = `/api/v1/fabric/trust/batch`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('POST', path, query, params?.body, undefined);
  }

  async runtimeApiHealth() {
    const path = `/api/v1/health`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getLineageBatch(params) {
    const path = `/api/v1/lineage/batch`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('POST', path, query, params?.body, undefined);
  }

  async getLineage(params) {
    const path = `/api/v1/lineage/${encodeURIComponent(String(params.lineage_id))}`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async exportLineageOpenlineage(params) {
    const path = `/api/v1/lineage/${encodeURIComponent(String(params.lineage_id))}/export/openlineage`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
      export_projection_hash: params?.export_projection_hash,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async exportLineageProv(params) {
    const path = `/api/v1/lineage/${encodeURIComponent(String(params.lineage_id))}/export/prov`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
      export_projection_hash: params?.export_projection_hash,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async computeMobilityBounds(params) {
    const path = `/api/v1/mobility/bounds`;
    const query = undefined;
    return this.request('POST', path, query, params?.body, undefined);
  }

  async estimateMobility(params) {
    const path = `/api/v1/mobility/estimate`;
    const query = undefined;
    return this.request('POST', path, query, params?.body, undefined);
  }

  async getMobilityReport(params) {
    const path = `/api/v1/mobility/reports/${encodeURIComponent(String(params.artifact_id))}`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getMobilityReportBounds(params) {
    const path = `/api/v1/mobility/reports/${encodeURIComponent(String(params.artifact_id))}/bounds`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getMobilityReportDiagnostics(params) {
    const path = `/api/v1/mobility/reports/${encodeURIComponent(String(params.artifact_id))}/diagnostics`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
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
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunsBatch(params) {
    const path = `/api/v1/runs/batch`;
    const query = undefined;
    return this.request('POST', path, query, params?.body, undefined);
  }

  async compareRuns(params) {
    const path = `/api/v1/runs/compare`;
    const query = this.buildQuery({
      a: params?.a,
      b: params?.b,
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunDetails(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunAgents(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/agents`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunAuthorityValues(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/authority-values`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getCaseInspection(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/case-inspection`;
    const query = this.buildQuery({
      manifest_artifact_id: params?.manifest_artifact_id,
      manifest_schema_version: params?.manifest_schema_version,
      paper_projection_rule_version: params?.paper_projection_rule_version,
      paper_projection_hash: params?.paper_projection_hash,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunCompareCandidates(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/compare-candidates`;
    const query = this.buildQuery({
      limit: params?.limit,
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunEvidenceContext(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/evidence-context`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunFabricDecisionData(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/fabric-decision-data`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunHumanDecisionEvidenceContent(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/human-decision-evidence/${encodeURIComponent(String(params.artifact_id))}/content`;
    const query = undefined;
    const requestHeaders = new Headers();
    requestHeaders.set("X-PolicyOS-Human-Decision-Exposure", String(params["X-PolicyOS-Human-Decision-Exposure"]));
    return this.request('GET', path, query, undefined, requestHeaders, 'arrayBuffer');
  }

  async getRunHumanDecisionGate(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/human-decision-gate`;
    const query = this.buildQuery({
      source_kind: params?.source_kind,
      source_ref: params?.source_ref,
      production_packet_ref: params?.production_packet_ref,
      decision_request_ref: params?.decision_request_ref,
      principal_binding_ref: params?.principal_binding_ref,
      reviewer_separation_ref: params?.reviewer_separation_ref,
      presentation_contract_ref: params?.presentation_contract_ref,
      exposure_session_ref: params?.exposure_session_ref,
      basis_digest: params?.basis_digest,
      action_kind: params?.action_kind,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunHumanDecisionRecord(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/human-decisions`;
    const query = this.buildQuery({
      record_ref: params?.record_ref,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async createRunHumanDecision(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/human-decisions`;
    const query = undefined;
    const requestHeaders = new Headers();
    requestHeaders.set("X-PolicyOS-Human-Decision-Exposure", String(params["X-PolicyOS-Human-Decision-Exposure"]));
    return this.request('POST', path, query, params?.body, requestHeaders);
  }

  async getRunHumanDecisionReviewEffectiveness(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/human-decisions/review-effectiveness`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunLineage(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/lineage`;
    const query = this.buildQuery({
      root_artifact_id: params?.root_artifact_id,
      max_depth: params?.max_depth,
      max_nodes: params?.max_nodes,
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunCounterfactualMetrics(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/metrics`;
    const query = this.buildQuery({
      scenario_id: params?.scenario_id,
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      regime_shift_forecast_bundle_ref: params?.regime_shift_forecast_bundle_ref,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunNodes(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/nodes`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunPaper(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/paper`;
    const query = this.buildQuery({
      manifest_artifact_id: params?.manifest_artifact_id,
      manifest_schema_version: params?.manifest_schema_version,
      paper_projection_rule_version: params?.paper_projection_rule_version,
      paper_projection_hash: params?.paper_projection_hash,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunQuantities(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/quantities`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async listRunScenarios(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/scenarios`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
      regime_shift_forecast_bundle_ref: params?.regime_shift_forecast_bundle_ref,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunTimeline(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/timeline`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunWorkflow(params) {
    const path = `/api/v1/runs/${encodeURIComponent(String(params.run_id))}/workflow`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getScenarioManifest(params) {
    const path = `/api/v1/scenarios/${encodeURIComponent(String(params.scenario_id))}`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getScenarioCapabilities(params) {
    const path = `/api/v1/scenarios/${encodeURIComponent(String(params.scenario_id))}/capabilities`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      t: params?.t,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      regime_shift_forecast_bundle_ref: params?.regime_shift_forecast_bundle_ref,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getTemporalCapabilities(params) {
    const path = `/api/v1/temporal/capabilities`;
    const query = this.buildQuery({
      run_id: params?.run_id,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async getRunEpochStaleness(params) {
    const path = `/api/v1/temporal/runs/${encodeURIComponent(String(params.run_id))}/epoch-staleness`;
    const query = this.buildQuery({
      valid_at: params?.valid_at,
      tx_at: params?.tx_at,
      branch: params?.branch,
      snapshot_id: params?.snapshot_id,
      scenario_id: params?.scenario_id,
      export_projection_hash: params?.export_projection_hash,
    });
    return this.request('GET', path, query, undefined, undefined);
  }

  async health() {
    const path = `/health`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

  async ready() {
    const path = `/ready`;
    const query = undefined;
    return this.request('GET', path, query, undefined, undefined);
  }

}
