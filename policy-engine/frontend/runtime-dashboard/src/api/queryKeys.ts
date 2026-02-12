export const queryKeys = {
  health: () => ["runtime", "health"] as const,
  runs: (filters: Record<string, unknown>) => ["runtime", "runs", filters] as const,
  run: (runId: string) => ["runtime", "run", runId] as const,
  runTimeline: (runId: string) => ["runtime", "run", runId, "timeline"] as const,
  runNodes: (runId: string) => ["runtime", "run", runId, "nodes"] as const,
  runLineage: (runId: string) => ["runtime", "run", runId, "lineage"] as const,
  runAgents: (runId: string) => ["runtime", "run", runId, "agents"] as const,
  runWorkflow: (runId: string) => ["runtime", "run", runId, "workflow"] as const,
  runGovernanceDebug: (runId: string) => ["runtime", "run", runId, "debug", "governance"] as const,
  runNodeDebug: (runId: string, alias: string) =>
    ["runtime", "run", runId, "debug", "node", alias] as const,
  runErrors: (runId: string) => ["runtime", "run", runId, "debug", "errors"] as const,
  artifactManifest: (artifactId: string) => ["runtime", "artifact", artifactId, "manifest"] as const,
  artifactContent: (artifactId: string, maxBytes: number | null = null) =>
    ["runtime", "artifact", artifactId, "content", { maxBytes }] as const,
  artifactSchema: (artifactId: string) => ["runtime", "artifact", artifactId, "schema"] as const,
  artifactLineage: (artifactId: string) => ["runtime", "artifact", artifactId, "lineage"] as const,

  // Control-plane keys
  connectors: () => ["control", "connectors"] as const,
  cacheStatus: () => ["control", "cache"] as const,
};
