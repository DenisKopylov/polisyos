import type {
  LineageCompactSummaryItem,
  LineageGraphView,
} from "./quantity.types";

export type ProvenanceSummaryKind =
  | "source"
  | "transform"
  | "model"
  | "agent"
  | "result"
  | "artifact"
  | "unknown";

export type ProvenanceSummaryNode = {
  id: string;
  kind: ProvenanceSummaryKind;
  label: string;
  count: number;
  hiddenCount: number;
};

export type ProvenanceSummaryEdge = {
  sourceId: string;
  targetId: string;
};

export type ProvenanceSummary = {
  nodes: ProvenanceSummaryNode[];
  edges: ProvenanceSummaryEdge[];
  hiddenByKind: Partial<Record<ProvenanceSummaryKind, number>>;
  hiddenTotal: number;
};

const KIND_ORDER: ProvenanceSummaryKind[] = [
  "source",
  "transform",
  "model",
  "agent",
  "result",
  "artifact",
  "unknown",
];

export function summarizeLineageGraph(
  lineage: LineageGraphView | null | undefined,
  options: { maxVisibleNodes?: number } = {},
): ProvenanceSummary {
  const maxVisibleNodes = Math.min(
    Math.max(options.maxVisibleNodes ?? 7, 5),
    7,
  );
  const compactItems = lineage?.compact_summary ?? [];
  const sourceItems =
    compactItems.length > /* policyos-quantity: telemetry */ 0
      ? compactItems
      : graphNodesToCompactItems(lineage);

  const staged = sourceItems.map((item, index) => ({
    id: item.id ?? `${normalizeKind(item.kind)}:${index}:${item.label}`,
    kind: normalizeKind(item.kind),
    label: item.label,
  }));
  const buckets = new Map<ProvenanceSummaryKind, typeof staged>();
  for (const kind of KIND_ORDER) {
    buckets.set(kind, []);
  }
  for (const item of staged) {
    buckets.get(item.kind)?.push(item);
  }

  const visible: ProvenanceSummaryNode[] = [];
  const hiddenByKind: Partial<Record<ProvenanceSummaryKind, number>> = {};
  for (const kind of KIND_ORDER) {
    const bucket = buckets.get(kind) ?? [];
    if (bucket.length === /* policyos-quantity: telemetry */ 0) {
      continue;
    }
    const [first, ...rest] = bucket;
    if (visible.length < maxVisibleNodes) {
      visible.push({
        id: first.id,
        kind,
        label: first.label,
        count: bucket.length,
        hiddenCount: rest.length,
      });
      if (rest.length > /* policyos-quantity: telemetry */ 0) {
        hiddenByKind[kind] = rest.length;
      }
      continue;
    }
    hiddenByKind[kind] = (hiddenByKind[kind] ?? 0) + bucket.length;
  }

  const hiddenTotal = Object.values(hiddenByKind).reduce(
    (sum, count) => sum + (count ?? /* policyos-quantity: telemetry */ 0),
    /* policyos-quantity: telemetry */ 0,
  );

  return {
    nodes: visible,
    edges: visible.slice(1).map((node, index) => ({
      sourceId: visible[index].id,
      targetId: node.id,
    })),
    hiddenByKind,
    hiddenTotal,
  };
}

function graphNodesToCompactItems(
  lineage: LineageGraphView | null | undefined,
): LineageCompactSummaryItem[] {
  const nodes = lineage?.nodes ?? [];
  if (nodes.length === 0) {
    return [];
  }
  return nodes.map((node) => ({
    id: node.id,
    kind: normalizeKind(node.kind),
    label: node.label,
  }));
}

export function normalizeKind(
  kind: string | null | undefined,
): ProvenanceSummaryKind {
  const normalized = String(kind ?? "").toLowerCase();
  if (
    normalized.includes("source") ||
    normalized.includes("dataset") ||
    normalized.includes("data")
  ) {
    return "source";
  }
  if (
    normalized.includes("transform") ||
    normalized.includes("activity") ||
    normalized.includes("stage")
  ) {
    return "transform";
  }
  if (
    normalized.includes("model") ||
    normalized.includes("method") ||
    normalized.includes("estimator")
  ) {
    return "model";
  }
  if (normalized.includes("agent")) {
    return "agent";
  }
  if (
    normalized.includes("result") ||
    normalized.includes("metric") ||
    normalized.includes("value")
  ) {
    return "result";
  }
  if (normalized.includes("artifact")) {
    return "artifact";
  }
  return "unknown";
}
