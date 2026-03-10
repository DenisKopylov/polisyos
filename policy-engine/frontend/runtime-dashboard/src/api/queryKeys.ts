export const queryKeys = {
  authMe: () => ["auth", "me"] as const,
  health: () => ["runtime", "health"] as const,
  capabilities: () => ["control", "capabilities"] as const,
  runsRoot: () => ["runtime", "runs"] as const,
  runs: (filters: Record<string, unknown>) =>
    ["runtime", "runs", filters] as const,
  run: (runId: string) => ["runtime", "run", runId] as const,
  runTimeline: (runId: string) =>
    ["runtime", "run", runId, "timeline"] as const,
  runNodes: (runId: string) => ["runtime", "run", runId, "nodes"] as const,
  runLineage: (runId: string) => ["runtime", "run", runId, "lineage"] as const,
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
  artifactManifest: (artifactId: string) =>
    ["runtime", "artifact", artifactId, "manifest"] as const,
  artifactContent: (artifactId: string, maxBytes: number | null = null) =>
    ["runtime", "artifact", artifactId, "content", { maxBytes }] as const,
  artifactSchema: (artifactId: string) =>
    ["runtime", "artifact", artifactId, "schema"] as const,
  artifactLineage: (artifactId: string) =>
    ["runtime", "artifact", artifactId, "lineage"] as const,

  // Control-plane keys
  connectors: () => ["control", "connectors"] as const,
  cacheStatus: () => ["control", "cache"] as const,
  sourceProfiles: () => ["control", "profiles"] as const,
  llmProfiles: () => ["control", "llm", "profiles"] as const,
  dataIndexStats: () => ["control", "data", "index", "stats"] as const,
  dataPromotionCandidates: () =>
    ["control", "data", "promotion", "candidates"] as const,
  dataCatalogSearch: (
    metricQuery: string,
    geography: string | null,
    limit: number,
  ) =>
    [
      "control",
      "data",
      "catalog",
      "search",
      { metricQuery, geography, limit },
    ] as const,

  // Lex knowledge graph
  lexPipelineStatus: (pipelineId: string) =>
    ["lex", "pipeline", pipelineId] as const,
  lexGraphStats: (outputDir: string) =>
    ["lex", "graph", "stats", outputDir] as const,
};
