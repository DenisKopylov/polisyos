import { graphStratify, sugiyama, coordQuad } from "d3-dag";
import type {
  CausalNodeData,
  CausalEdgeData,
  LayoutResult,
  LayoutOptions,
} from "../types";
import { NODE_WIDTH, NODE_HEIGHT, NODE_HORIZONTAL_GAP, NODE_VERTICAL_GAP } from "../types";
import { hierarchicalLayout } from "./hierarchicalLayout";

/**
 * Sugiyama layout via d3-dag (DAGitty-style constraint-based).
 *
 * Uses the Sugiyama framework: layering → crossing reduction → coordinate assignment.
 * Falls back to hierarchical if d3-dag can't process the graph (e.g. cycles).
 */
export function sugiyamaLayout(
  nodes: CausalNodeData[],
  edges: CausalEdgeData[],
  opts?: Partial<LayoutOptions>,
): LayoutResult {
  const nodeW = opts?.nodeWidth ?? NODE_WIDTH;
  const nodeH = opts?.nodeHeight ?? NODE_HEIGHT;
  const hGap = opts?.horizontalGap ?? NODE_HORIZONTAL_GAP;
  const vGap = opts?.verticalGap ?? NODE_VERTICAL_GAP;
  const padding = 40;

  if (nodes.length === 0) {
    return { positions: new Map(), width: 0, height: 0 };
  }

  // Build parent-id list for graphStratify
  const nodeSet = new Set(nodes.map((n) => n.id));
  const parentMap = new Map<string, string[]>();
  for (const n of nodes) parentMap.set(n.id, []);
  for (const e of edges) {
    if (nodeSet.has(e.source) && nodeSet.has(e.target)) {
      parentMap.get(e.target)?.push(e.source);
    }
  }

  try {
    const stratify = graphStratify();
    const dag = stratify(
      nodes.map((n) => ({
        id: n.id,
        parentIds: parentMap.get(n.id) ?? [],
      })),
    );

    const layout = sugiyama()
      .nodeSize([nodeW + hGap, nodeH + vGap])
      .coord(coordQuad());

    const { width: rawW, height: rawH } = layout(dag);

    const positions = new Map<string, { x: number; y: number }>();
    for (const node of dag.nodes()) {
      positions.set(node.data.id, {
        x: padding + node.x,
        y: padding + node.y,
      });
    }

    return {
      positions,
      width: padding * 2 + rawW + nodeW,
      height: padding * 2 + rawH + nodeH,
    };
  } catch {
    // d3-dag doesn't handle cycles — fall back to hierarchical
    return hierarchicalLayout(nodes, edges, opts);
  }
}
