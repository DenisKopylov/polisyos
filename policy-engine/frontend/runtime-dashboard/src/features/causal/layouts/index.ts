export { hierarchicalLayout } from "./hierarchicalLayout";
export { forceLayout } from "./forceLayout";
export { sugiyamaLayout } from "./sugiyamaLayout";

import type {
  CausalNodeData,
  CausalEdgeData,
  LayoutResult,
  LayoutOptions,
  LayoutAlgorithm,
} from "../types";
import { hierarchicalLayout } from "./hierarchicalLayout";
import { forceLayout } from "./forceLayout";
import { sugiyamaLayout } from "./sugiyamaLayout";

/** Dispatch to the requested layout algorithm. */
export function computeLayout(
  algorithm: LayoutAlgorithm,
  nodes: CausalNodeData[],
  edges: CausalEdgeData[],
  opts?: Partial<LayoutOptions>,
): LayoutResult {
  switch (algorithm) {
    case "force":
      return forceLayout(nodes, edges, opts);
    case "sugiyama":
      return sugiyamaLayout(nodes, edges, opts);
    case "hierarchical":
    default:
      return hierarchicalLayout(nodes, edges, opts);
  }
}
