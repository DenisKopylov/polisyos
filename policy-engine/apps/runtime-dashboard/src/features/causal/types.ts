import {
  createInteractionState,
  type InteractionState,
} from "@/shared/lib/domain/statusOwnership";

// ---------------------------------------------------------------------------
// Causal Graph domain types
// ---------------------------------------------------------------------------

/** Node archetypes in a causal DAG. */
export type CausalNodeKind =
  | "treatment"
  | "outcome"
  | "confounder"
  | "mediator"
  | "collider"
  | "instrument"
  | "selection"; // S-node for transportability

/** Interaction-only rendering state for a candidate causal edge. */
export type CausalDraftIdentificationDisplay = InteractionState;

export function createCausalDraftIdentificationDisplay(
  label: string,
): CausalDraftIdentificationDisplay {
  return createInteractionState(label, "candidate_display");
}

/** Interaction-only progress state; it is never workflow authority. */
export type CausalPipelineProgressState = InteractionState;

export function createCausalPipelineProgressState(
  label: string,
): CausalPipelineProgressState {
  return createInteractionState(label, "progress");
}

// ---------------------------------------------------------------------------
// Graph elements
// ---------------------------------------------------------------------------

export type CausalNodeData = {
  id: string;
  label: string;
  kind: CausalNodeKind;
  /** Optional variable metadata. */
  description?: string;
  /** Effect estimate on this node (e.g. ATE). */
  estimate?: number;
  /** Confidence interval. */
  ci?: { lower: number; upper: number; level: number };
  /** Data availability flag. */
  dataAvailable?: boolean;
  /** Evidence sources count. */
  evidenceCount?: number;
  /** Whether this node is in the adjustment set. */
  inAdjustmentSet?: boolean;
  /** Custom metadata. */
  meta?: Record<string, string>;
};

export type CausalEdgeData = {
  id: string;
  source: string;
  target: string;
  /** Identification status. */
  status: CausalDraftIdentificationDisplay;
  /** Point estimate of causal effect. */
  estimate?: number;
  /** Confidence interval for the effect. */
  ci?: { lower: number; upper: number; level: number };
  /** Methodology used. */
  methodology?: string;
  /** Whether this edge is transportable across contexts. */
  transportable?: boolean;
  /** Literature support count. */
  literatureCount?: number;
  /** Custom metadata. */
  meta?: Record<string, string>;
};

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------

export type LayoutAlgorithm = "hierarchical" | "force" | "sugiyama";

export type NodePosition = {
  id: string;
  x: number;
  y: number;
};

export type LayoutResult = {
  positions: Map<string, { x: number; y: number }>;
  width: number;
  height: number;
};

export type LayoutOptions = {
  nodeWidth: number;
  nodeHeight: number;
  horizontalGap: number;
  verticalGap: number;
};

// ---------------------------------------------------------------------------
// Graph state
// ---------------------------------------------------------------------------

export type GraphInteractionState = {
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  hoveredNodeId: string | null;
  hoveredEdgeId: string | null;
  focusedNodeId: string | null;
};

export type GraphTransform = {
  x: number;
  y: number;
  scale: number;
};

export type OverlayMode =
  | "none"
  | "identification"
  | "transport"
  | "adjustment_set";

export type CausalGraphState = {
  nodes: CausalNodeData[];
  edges: CausalEdgeData[];
  layout: LayoutAlgorithm;
  overlay: OverlayMode;
  transform: GraphTransform;
  interaction: GraphInteractionState;
  /** IDs of nodes in current adjustment set highlight. */
  adjustmentSet: string[];
  /** IDs of edges in current path highlight. */
  highlightedPath: string[];
};

// ---------------------------------------------------------------------------
// Pipeline progress
// ---------------------------------------------------------------------------

export type PipelineStage = {
  id: string;
  label: string;
  status: CausalPipelineProgressState;
  durationMs?: number;
  detail?: string;
  /** Dependent stage IDs. */
  dependsOn: string[];
};

// ---------------------------------------------------------------------------
// Visual constants
// ---------------------------------------------------------------------------

export const NODE_WIDTH = 160;
export const NODE_HEIGHT = 56;
export const NODE_HORIZONTAL_GAP = 80;
export const NODE_VERTICAL_GAP = 40;

/** Shape for each node kind. */
export const NODE_SHAPES: Record<CausalNodeKind, string> = {
  treatment: "diamond",
  outcome: "circle",
  confounder: "square",
  mediator: "rounded-rect",
  collider: "hexagon",
  instrument: "triangle",
  selection: "diamond-overlay",
};

/** Color token for each node kind. */
export const NODE_COLORS: Record<CausalNodeKind, string> = {
  treatment: "var(--chart-primary)",
  outcome: "var(--color-confidence-medium)",
  confounder: "var(--chart-neutral)",
  mediator: "var(--chart-tertiary)",
  collider: "var(--chart-warning)",
  instrument: "var(--chart-secondary)",
  selection: "var(--chart-alert)",
};
