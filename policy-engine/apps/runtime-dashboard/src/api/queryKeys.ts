import {
  temporalScopeKey,
  type TemporalScope,
} from "@/shared/lib/domain/temporal";
import {
  artifactRefForRequest,
  evidenceArtifactRefKey,
  type EvidenceArtifactRef,
} from "@/shared/lib/domain/evidence";
import {
  scenarioScopeKey,
  type ScenarioScope,
} from "@/app/providers/scenario-scope";
import type { ProjectionId } from "@polisyos/runtime-api-client";
import type { components } from "./types";

export const queryKeys = {
  authMe: () => ["auth", "me"] as const,
  health: () => ["runtime", "health"] as const,
  capabilities: () => ["control", "capabilities"] as const,
  capabilitySearch: (
    request: components["schemas"]["CapabilityDiscoveryRequest"],
    serverEpoch: string | null = null,
  ) =>
    [
      "control",
      "capabilities",
      "search",
      { serverEpoch: serverEpoch ?? "unobserved" },
      request,
    ] as const,
  governedProjection: (projectionId: ProjectionId) =>
    ["runtime", "governed-projection", projectionId] as const,
  cycleBoardProjection: () =>
    [
      "runtime",
      "exports",
      "governed-projections",
      "depth-n-cycle-board",
      { representation: "composed-v2" },
    ] as const,
  acquisitionGrowth: () =>
    [
      "runtime",
      "exports",
      "governed-projections",
      "acquisition-growth",
    ] as const,
  temporalCapabilities: (runId: string | null | undefined) =>
    ["runtime", "temporal", "capabilities", { runId: runId ?? null }] as const,
  runsRoot: () => ["runtime", "runs"] as const,
  runs: (filters: Record<string, unknown>) =>
    ["runtime", "runs", filters] as const,
  run: (runId: string, temporalScope?: TemporalScope | null) =>
    [
      "runtime",
      "run",
      runId,
      { temporal: temporalScopeKey(temporalScope) },
    ] as const,
  runAcquisitionRoutes: (runId: string) =>
    ["runtime", "run", runId, "acquisition-routes"] as const,
  runAcquisitionRoute: (runId: string, routeId: string) =>
    ["runtime", "run", runId, "acquisition-routes", routeId] as const,
  runPaper: (runId: string, rawReplaySearch: string) =>
    ["runtime", "run", runId, "paper", { rawReplaySearch }] as const,
  humanDecisionGate: (runId: string, selectorKey: string) =>
    ["runtime", "run", runId, "human-decision-gate", { selectorKey }] as const,
  humanDecisionReviewEffectiveness: (runId: string) =>
    ["runtime", "run", runId, "human-decision-review-effectiveness"] as const,
  runTimeline: (runId: string, temporalScope?: TemporalScope | null) =>
    [
      "runtime",
      "run",
      runId,
      "timeline",
      { temporal: temporalScopeKey(temporalScope) },
    ] as const,
  runNodes: (runId: string) => ["runtime", "run", runId, "nodes"] as const,
  runLineage: (runId: string, temporalScope?: TemporalScope | null) =>
    [
      "runtime",
      "run",
      runId,
      "lineage",
      { temporal: temporalScopeKey(temporalScope) },
    ] as const,
  runQuantities: (runId: string, temporalScope?: TemporalScope | null) =>
    [
      "runtime",
      "run",
      runId,
      "quantities",
      { temporal: temporalScopeKey(temporalScope) },
    ] as const,
  runFabricDecisionData: (
    runId: string,
    temporalScope?: TemporalScope | null,
  ) =>
    [
      "runtime",
      "run",
      runId,
      "fabric-decision-data",
      { temporal: temporalScopeKey(temporalScope) },
    ] as const,
  runCompare: (
    runAId: string,
    runBId: string,
    temporalScope?: TemporalScope | null,
  ) =>
    [
      "runtime",
      "runs",
      "compare",
      { a: runAId, b: runBId },
      { temporal: temporalScopeKey(temporalScope) },
    ] as const,
  runCompareCandidates: (runId: string, temporalScope?: TemporalScope | null) =>
    [
      "runtime",
      "run",
      runId,
      "compare-candidates",
      { temporal: temporalScopeKey(temporalScope) },
    ] as const,
  runScenarios: (
    runId: string,
    temporalScope?: TemporalScope | null,
    scenarioScope?: ScenarioScope | null,
  ) =>
    [
      "runtime",
      "run",
      runId,
      "scenarios",
      { temporal: temporalScopeKey(temporalScope) },
      { scenario: scenarioScopeKey(scenarioScope) },
    ] as const,
  scenarioManifest: (
    scenarioId: string,
    temporalScope?: TemporalScope | null,
  ) =>
    [
      "runtime",
      "scenario",
      scenarioId,
      { temporal: temporalScopeKey(temporalScope) },
    ] as const,
  scenarioCapabilities: (
    scenarioId: string,
    temporalScope?: TemporalScope | null,
  ) =>
    [
      "runtime",
      "scenario",
      scenarioId,
      "capabilities",
      { temporal: temporalScopeKey(temporalScope) },
    ] as const,
  counterfactualMetrics: (
    runId: string,
    scenarioId: string,
    temporalScope?: TemporalScope | null,
    scenarioScope?: ScenarioScope | null,
  ) =>
    [
      "runtime",
      "run",
      runId,
      "counterfactual-metrics",
      { scenarioId },
      { temporal: temporalScopeKey(temporalScope) },
      { scenario: scenarioScopeKey(scenarioScope) },
    ] as const,
  runEvidenceContext: (runId: string) =>
    ["runtime", "run", runId, "evidence-context"] as const,
  runAgents: (runId: string) => ["runtime", "run", runId, "agents"] as const,
  runWorkflow: (runId: string) =>
    ["runtime", "run", runId, "workflow"] as const,
  runGovernanceDebug: (runId: string) =>
    ["runtime", "run", runId, "debug", "governance"] as const,
  runNodeDebug: (runId: string, alias: string) =>
    ["runtime", "run", runId, "debug", "node", alias] as const,
  runErrors: (runId: string) =>
    ["runtime", "run", runId, "debug", "errors"] as const,
  artifactManifest: (
    artifact: string | EvidenceArtifactRef,
    manifestProfileSha256?: string | null,
  ) => {
    const ref = artifactRefForRequest(artifact, manifestProfileSha256);
    const artifactId = ref?.artifact_id ?? "unknown";
    return [
      "runtime",
      "artifact",
      artifactId,
      "manifest",
      { reference: evidenceArtifactRefKey(ref ?? { artifact_id: artifactId }) },
    ] as const;
  },
  artifactContent: (
    artifact: string | EvidenceArtifactRef,
    maxBytes: number | null = null,
    manifestProfileSha256?: string | null,
  ) => {
    const ref = artifactRefForRequest(artifact, manifestProfileSha256);
    const artifactId = ref?.artifact_id ?? "unknown";
    return [
      "runtime",
      "artifact",
      artifactId,
      "content",
      {
        maxBytes,
        reference: evidenceArtifactRefKey(ref ?? { artifact_id: artifactId }),
      },
    ] as const;
  },
  artifactSchema: (
    artifact: string | EvidenceArtifactRef,
    manifestProfileSha256?: string | null,
  ) => {
    const ref = artifactRefForRequest(artifact, manifestProfileSha256);
    const artifactId = ref?.artifact_id ?? "unknown";
    return [
      "runtime",
      "artifact",
      artifactId,
      "schema",
      { reference: evidenceArtifactRefKey(ref ?? { artifact_id: artifactId }) },
    ] as const;
  },
  artifactLineage: (
    artifact: string | EvidenceArtifactRef,
    manifestProfileSha256?: string | null,
  ) => {
    const ref = artifactRefForRequest(artifact, manifestProfileSha256);
    const artifactId = ref?.artifact_id ?? "unknown";
    return [
      "runtime",
      "artifact",
      artifactId,
      "lineage",
      { reference: evidenceArtifactRefKey(ref ?? { artifact_id: artifactId }) },
    ] as const;
  },
  bureaucraticRender: (
    artifact: string | EvidenceArtifactRef,
    request: {
      genre: string;
      jurisdiction?: string;
      templateVersion?: string | null;
      trustView?: boolean;
      temporalScope?: unknown;
    },
  ) =>
    [
      "runtime",
      "artifact",
      artifactRefForRequest(artifact)?.artifact_id ?? "unknown",
      "bureaucratic-render",
      {
        reference: evidenceArtifactRefKey(
          artifactRefForRequest(artifact) ?? { artifact_id: "unknown" },
        ),
      },
      request,
    ] as const,
  lineage: (lineageId: string, temporalScope?: TemporalScope | null) =>
    [
      "runtime",
      "lineage",
      lineageId,
      { temporal: temporalScopeKey(temporalScope) },
    ] as const,
  lineageBatch: (
    lineageIds: readonly string[],
    temporalScope?: TemporalScope | null,
  ) =>
    [
      "runtime",
      "lineage",
      "batch",
      { lineageIds: [...lineageIds] },
      { temporal: temporalScopeKey(temporalScope) },
    ] as const,
  lineageExport: (
    lineageId: string,
    format: "openlineage" | "prov",
    temporalScope?: TemporalScope | null,
  ) =>
    [
      "runtime",
      "lineage",
      lineageId,
      "export",
      format,
      { temporal: temporalScopeKey(temporalScope) },
    ] as const,

  // Control-plane keys
  controlJobStatus: (jobId: string) =>
    ["control", "jobs", jobId, "status"] as const,
  connectors: () => ["control", "connectors"] as const,
  cacheStatus: () => ["control", "cache"] as const,
  sourceProfiles: () => ["control", "profiles"] as const,
  llmProfiles: () => ["control", "llm", "profiles"] as const,
  dataIndexStats: () => ["control", "data", "index", "stats"] as const,
  dataPromotionCandidates: () =>
    ["control", "data", "promotion", "candidates"] as const,
  // Lex knowledge graph
  lexPipelineStatus: (pipelineId: string) =>
    ["lex", "pipeline", pipelineId] as const,
  lexGraphStats: (outputDir: string) =>
    ["lex", "graph", "stats", outputDir] as const,
  lexSearchProfile: (outputDir: string) =>
    ["lex", "search-profile", outputDir] as const,
};

/** Distinct authority-query key kept outside the governed shared-key identity. */
export const confidenceLedgerRiskSpendQueryKey = () =>
  [
    "runtime",
    "exports",
    "governed-projections",
    "confidence-ledger-risk-spend",
    { representation: "specialized-v1" },
  ] as const;
