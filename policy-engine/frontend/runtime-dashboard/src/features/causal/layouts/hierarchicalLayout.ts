import type {
  CausalNodeData,
  CausalEdgeData,
  LayoutResult,
  LayoutOptions,
} from "../types";
import { NODE_WIDTH, NODE_HEIGHT, NODE_HORIZONTAL_GAP, NODE_VERTICAL_GAP } from "../types";

/**
 * Simple top-down hierarchical layout (Sugiyama-lite).
 *
 * 1. Compute depth of each node via BFS from roots.
 * 2. Place nodes in columns by depth.
 * 3. Center each column vertically.
 */
export function hierarchicalLayout(
  nodes: CausalNodeData[],
  edges: CausalEdgeData[],
  opts?: Partial<LayoutOptions>,
): LayoutResult {
  const nodeW = opts?.nodeWidth ?? NODE_WIDTH;
  const nodeH = opts?.nodeHeight ?? NODE_HEIGHT;
  const hGap = opts?.horizontalGap ?? NODE_HORIZONTAL_GAP;
  const vGap = opts?.verticalGap ?? NODE_VERTICAL_GAP;

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const childrenOf = new Map<string, string[]>();
  const parentCount = new Map<string, number>();

  for (const n of nodes) {
    childrenOf.set(n.id, []);
    parentCount.set(n.id, 0);
  }
  for (const e of edges) {
    childrenOf.get(e.source)?.push(e.target);
    parentCount.set(e.target, (parentCount.get(e.target) ?? 0) + 1);
  }

  // BFS to assign depths
  const depth = new Map<string, number>();
  const queue: string[] = [];
  for (const [id, count] of parentCount) {
    if (count === 0) {
      depth.set(id, 0);
      queue.push(id);
    }
  }
  // Fallback: if no roots found (cycle), pick first node
  if (queue.length === 0 && nodes.length > 0) {
    depth.set(nodes[0].id, 0);
    queue.push(nodes[0].id);
  }

  let head = 0;
  while (head < queue.length) {
    const current = queue[head++];
    const d = depth.get(current) ?? 0;
    for (const child of childrenOf.get(current) ?? []) {
      const existing = depth.get(child);
      if (existing === undefined || existing < d + 1) {
        depth.set(child, d + 1);
      }
      if (existing === undefined) {
        queue.push(child);
      }
    }
  }

  // Assign depth 0 to any unreachable node
  for (const n of nodes) {
    if (!depth.has(n.id)) depth.set(n.id, 0);
  }

  // Group by depth
  const columns = new Map<number, string[]>();
  for (const [id, d] of depth) {
    const col = columns.get(d) ?? [];
    col.push(id);
    columns.set(d, col);
  }

  // Sort columns by node label for determinism
  for (const col of columns.values()) {
    col.sort((a, b) => {
      const na = nodeMap.get(a)?.label ?? a;
      const nb = nodeMap.get(b)?.label ?? b;
      return na.localeCompare(nb);
    });
  }

  const maxDepth = Math.max(...depth.values(), 0);
  const maxColSize = Math.max(
    ...Array.from(columns.values()).map((c) => c.length),
    1,
  );

  const padding = 40;
  const positions = new Map<string, { x: number; y: number }>();

  for (const [d, col] of columns) {
    const colHeight = col.length * (nodeH + vGap) - vGap;
    const startY = padding + (maxColSize * (nodeH + vGap) - vGap - colHeight) / 2;

    col.forEach((id, i) => {
      positions.set(id, {
        x: padding + d * (nodeW + hGap),
        y: startY + i * (nodeH + vGap),
      });
    });
  }

  const width = padding * 2 + (maxDepth + 1) * (nodeW + hGap) - hGap;
  const height = padding * 2 + maxColSize * (nodeH + vGap) - vGap;

  return { positions, width, height };
}
