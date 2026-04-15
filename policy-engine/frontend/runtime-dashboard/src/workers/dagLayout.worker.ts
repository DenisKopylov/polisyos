/// <reference lib="webworker" />

/**
 * Web Worker for offloading DAG layout computation.
 *
 * Receives a graph definition and returns computed node positions.
 * Keeps the main thread free for user interactions while the
 * d3-dag layout algorithm runs (can take 100ms+ for large graphs).
 */

export type DagNode = {
  id: string;
  label: string;
  type?: string;
  parentIds?: string[];
};

export type DagLayoutResult = {
  nodes: Array<{ id: string; x: number; y: number }>;
  edges: Array<{ source: string; target: string; points?: [number, number][] }>;
  width: number;
  height: number;
};

type DagLayoutRequest = {
  type: "layout";
  nodes: DagNode[];
  options?: {
    algorithm?: "hierarchical" | "force" | "sugiyama";
    nodeWidth?: number;
    nodeHeight?: number;
    rankSep?: number;
    nodeSep?: number;
  };
};

type DagLayoutResponse =
  | { type: "layout.result"; result: DagLayoutResult }
  | { type: "layout.error"; error: string };

function computeHierarchicalLayout(
  nodes: DagNode[],
  options: NonNullable<DagLayoutRequest["options"]>,
): DagLayoutResult {
  const nodeWidth = options.nodeWidth ?? 160;
  const nodeHeight = options.nodeHeight ?? 60;
  const rankSep = options.rankSep ?? 80;
  const nodeSep = options.nodeSep ?? 40;

  // Build adjacency and compute ranks (topological layers)
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const childrenOf = new Map<string, string[]>();
  const parentCount = new Map<string, number>();

  for (const node of nodes) {
    parentCount.set(node.id, node.parentIds?.length ?? 0);
    for (const pid of node.parentIds ?? []) {
      const children = childrenOf.get(pid) ?? [];
      children.push(node.id);
      childrenOf.set(pid, children);
    }
  }

  // BFS to assign ranks
  const ranks = new Map<string, number>();
  const queue = nodes.filter((n) => !n.parentIds?.length).map((n) => n.id);
  for (const id of queue) ranks.set(id, 0);

  let i = 0;
  while (i < queue.length) {
    const current = queue[i]!;
    i++;
    for (const child of childrenOf.get(current) ?? []) {
      const childRank = Math.max(ranks.get(child) ?? 0, (ranks.get(current) ?? 0) + 1);
      ranks.set(child, childRank);
      if (!queue.includes(child)) queue.push(child);
    }
  }

  // Group by rank
  const rankGroups = new Map<number, string[]>();
  for (const [id, rank] of ranks) {
    const group = rankGroups.get(rank) ?? [];
    group.push(id);
    rankGroups.set(rank, group);
  }

  // Position nodes
  const positioned: DagLayoutResult["nodes"] = [];
  let maxWidth = 0;

  for (const [rank, group] of rankGroups) {
    const y = rank * (nodeHeight + rankSep);
    const totalWidth = group.length * nodeWidth + (group.length - 1) * nodeSep;
    const startX = -totalWidth / 2;
    maxWidth = Math.max(maxWidth, totalWidth);

    group.forEach((id, idx) => {
      positioned.push({
        id,
        x: startX + idx * (nodeWidth + nodeSep) + nodeWidth / 2,
        y,
      });
    });
  }

  const maxRank = Math.max(...ranks.values(), 0);
  const height = (maxRank + 1) * (nodeHeight + rankSep);

  // Build edges
  const posMap = new Map(positioned.map((p) => [p.id, p]));
  const edges: DagLayoutResult["edges"] = [];
  for (const node of nodes) {
    for (const pid of node.parentIds ?? []) {
      const from = posMap.get(pid);
      const to = posMap.get(node.id);
      if (from && to) {
        edges.push({
          source: pid,
          target: node.id,
          points: [[from.x, from.y], [to.x, to.y]],
        });
      }
    }
  }

  return { nodes: positioned, edges, width: maxWidth, height };
}

self.addEventListener("message", (event: MessageEvent<DagLayoutRequest>) => {
  const { data } = event;
  if (data.type !== "layout") return;

  try {
    const result = computeHierarchicalLayout(data.nodes, data.options ?? {});
    const response: DagLayoutResponse = { type: "layout.result", result };
    self.postMessage(response);
  } catch (err) {
    const response: DagLayoutResponse = {
      type: "layout.error",
      error: err instanceof Error ? err.message : "Unknown layout error",
    };
    self.postMessage(response);
  }
});
