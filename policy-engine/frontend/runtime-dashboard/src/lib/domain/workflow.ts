import { asArray, asNumber, asRecord, asString, toDisplayLabel } from "../parsing";

export type WorkflowNodeStatus = "ok" | "skip" | "fail" | "unknown";

export type WorkflowNodeView = {
  alias: string;
  label: string;
  nodeId: string | null;
  status: WorkflowNodeStatus;
  depth: number;
  durationMs: number;
  heat: number;
  dependsOn: string[];
  artifactIds: string[];
  inputArtifactIds: string[];
  outputArtifactIds: string[];
  errorCode: string | null;
  errorMessage: string | null;
};

export type WorkflowEdgeView = {
  fromAlias: string;
  toAlias: string;
};

export type WorkflowSummaryView = {
  workflowId: string | null;
  errorPolicy: string | null;
  status: string | null;
  nodeCount: number;
  edgeCount: number;
  okCount: number;
  skipCount: number;
  failCount: number;
  maxDepth: number;
  criticalPathDurationMs: number | null;
};

export type WorkflowModel = {
  runId: string;
  summary: WorkflowSummaryView;
  nodes: WorkflowNodeView[];
  edges: WorkflowEdgeView[];
  notes: string[];
};

function normalizeNodeStatus(value: unknown): WorkflowNodeStatus {
  const status = (asString(value) ?? "").toLowerCase();
  if (status === "ok" || status === "skip" || status === "fail" || status === "unknown") {
    return status;
  }
  return "unknown";
}

function normalizeNode(raw: unknown): WorkflowNodeView | null {
  const node = asRecord(raw);
  if (!node) {
    return null;
  }
  const alias = asString(node.alias);
  if (!alias) {
    return null;
  }

  const durationMs = Math.max(0, asNumber(node.duration_ms) ?? 0);
  return {
    alias,
    label: toDisplayLabel(alias),
    nodeId: asString(node.node_id),
    status: normalizeNodeStatus(node.status),
    depth: Math.max(0, asNumber(node.depth) ?? 0),
    durationMs,
    heat: Math.max(0, asNumber(node.heat) ?? 0),
    dependsOn: asArray(node.depends_on)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
    artifactIds: asArray(node.artifact_ids)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
    inputArtifactIds: asArray(node.input_artifact_ids)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
    outputArtifactIds: asArray(node.output_artifact_ids)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
    errorCode: asString(node.error_code),
    errorMessage: asString(node.error_message),
  };
}

function normalizeEdge(raw: unknown): WorkflowEdgeView | null {
  const edge = asRecord(raw);
  if (!edge) {
    return null;
  }
  const fromAlias = asString(edge.from_alias);
  const toAlias = asString(edge.to_alias);
  if (!fromAlias || !toAlias) {
    return null;
  }
  return {
    fromAlias,
    toAlias,
  };
}

function normalizeSummary(raw: unknown, defaults: { nodeCount: number; edgeCount: number; maxDepth: number }): WorkflowSummaryView {
  const summary = asRecord(raw) ?? {};
  return {
    workflowId: asString(summary.workflow_id),
    errorPolicy: asString(summary.error_policy),
    status: asString(summary.status),
    nodeCount: asNumber(summary.node_count) ?? defaults.nodeCount,
    edgeCount: asNumber(summary.edge_count) ?? defaults.edgeCount,
    okCount: asNumber(summary.ok_count) ?? 0,
    skipCount: asNumber(summary.skip_count) ?? 0,
    failCount: asNumber(summary.fail_count) ?? 0,
    maxDepth: asNumber(summary.max_depth) ?? defaults.maxDepth,
    criticalPathDurationMs: asNumber(summary.critical_path_duration_ms),
  };
}

export function normalizeWorkflow(payload: unknown): WorkflowModel {
  const workflow = asRecord(payload) ?? {};
  const nodes = asArray(workflow.nodes)
    .map((item) => normalizeNode(item))
    .filter((item): item is WorkflowNodeView => item !== null)
    .sort((left, right) => left.depth - right.depth || left.alias.localeCompare(right.alias));
  const edges = asArray(workflow.edges)
    .map((item) => normalizeEdge(item))
    .filter((item): item is WorkflowEdgeView => item !== null);

  const maxDuration = Math.max(...nodes.map((node) => node.durationMs), 0);
  const normalizedNodes = nodes.map((node) => ({
    ...node,
    heat: maxDuration > 0 ? Math.max(node.heat, node.durationMs / maxDuration) : 0,
  }));

  const maxDepth = Math.max(...normalizedNodes.map((node) => node.depth), 0);
  const summary = normalizeSummary(workflow.summary, {
    nodeCount: normalizedNodes.length,
    edgeCount: edges.length,
    maxDepth,
  });

  return {
    runId: asString(workflow.run_id) ?? "unknown",
    summary,
    nodes: normalizedNodes,
    edges,
    notes: asArray(workflow.notes)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
  };
}
