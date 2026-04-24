import {
  useState,
  useCallback,
  useMemo,
  useRef,
  useEffect,
  type Dispatch,
  type PointerEvent as ReactPointerEvent,
  type SetStateAction,
  type WheelEvent as ReactWheelEvent,
} from "react";

import { cn } from "@/lib/utils";

import type {
  CausalNodeData,
  CausalEdgeData,
  LayoutAlgorithm,
  OverlayMode,
  GraphTransform,
  GraphInteractionState,
} from "../types";
import { computeLayout } from "../layouts";
import { CausalNode } from "./CausalNode";
import { CausalEdge } from "./CausalEdge";
import { CausalGraphControls } from "./CausalGraphControls";

type CausalGraphCanvasProps = {
  nodes: CausalNodeData[];
  edges: CausalEdgeData[];
  initialLayout?: LayoutAlgorithm;
  initialOverlay?: OverlayMode;
  layoutAlgorithm?: LayoutAlgorithm;
  overlay?: OverlayMode;
  adjustmentSet?: string[];
  highlightedPath?: string[];
  onLayoutChange?: (layout: LayoutAlgorithm) => void;
  onOverlayChange?: (overlay: OverlayMode) => void;
  showControls?: boolean;
  transform?: GraphTransform;
  interaction?: GraphInteractionState;
  onTransformChange?: Dispatch<SetStateAction<GraphTransform>>;
  onInteractionChange?: Dispatch<SetStateAction<GraphInteractionState>>;
  onNodeSelect?: (id: string | null) => void;
  onEdgeSelect?: (id: string | null) => void;
  className?: string;
};

const MIN_SCALE = 0.15;
const MAX_SCALE = 3;
const ZOOM_STEP = 0.15;

export function CausalGraphCanvas({
  nodes,
  edges,
  initialLayout = "hierarchical",
  initialOverlay = "none",
  layoutAlgorithm,
  overlay: overlayMode,
  adjustmentSet = [],
  highlightedPath = [],
  onLayoutChange,
  onOverlayChange,
  showControls = true,
  transform: controlledTransform,
  interaction: controlledInteraction,
  onTransformChange,
  onInteractionChange,
  onNodeSelect,
  onEdgeSelect,
  className,
}: CausalGraphCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [internalLayout, setInternalLayout] =
    useState<LayoutAlgorithm>(initialLayout);
  const [internalOverlay, setInternalOverlay] =
    useState<OverlayMode>(initialOverlay);

  const [internalTransform, setInternalTransform] = useState<GraphTransform>({
    x: 0,
    y: 0,
    scale: 1,
  });

  const [internalInteraction, setInternalInteraction] =
    useState<GraphInteractionState>({
      selectedNodeId: null,
      selectedEdgeId: null,
      hoveredNodeId: null,
      hoveredEdgeId: null,
      focusedNodeId: null,
    });

  const activeLayout = layoutAlgorithm ?? internalLayout;
  const activeOverlay = overlayMode ?? internalOverlay;
  const transform = controlledTransform ?? internalTransform;
  const interaction = controlledInteraction ?? internalInteraction;

  const setLayoutAlg = useCallback(
    (next: LayoutAlgorithm) => {
      if (layoutAlgorithm === undefined) {
        setInternalLayout(next);
      }
      onLayoutChange?.(next);
    },
    [layoutAlgorithm, onLayoutChange],
  );

  const setOverlay = useCallback(
    (next: OverlayMode) => {
      if (overlayMode === undefined) {
        setInternalOverlay(next);
      }
      onOverlayChange?.(next);
    },
    [onOverlayChange, overlayMode],
  );

  const updateTransform = useCallback(
    (next: SetStateAction<GraphTransform>) => {
      if (controlledTransform === undefined) {
        setInternalTransform(next);
      }
      onTransformChange?.(next);
    },
    [controlledTransform, onTransformChange],
  );

  const updateInteraction = useCallback(
    (next: SetStateAction<GraphInteractionState>) => {
      if (controlledInteraction === undefined) {
        setInternalInteraction(next);
      }
      onInteractionChange?.(next);
    },
    [controlledInteraction, onInteractionChange],
  );

  // Panning state
  const panRef = useRef<{
    active: boolean;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
  }>({
    active: false,
    startX: 0,
    startY: 0,
    originX: 0,
    originY: 0,
  });

  // Compute layout
  const layoutResult = useMemo(
    () => computeLayout(activeLayout, nodes, edges),
    [activeLayout, nodes, edges],
  );

  // Derived sets for overlays
  const adjustmentSetIds = useMemo(
    () => new Set(adjustmentSet),
    [adjustmentSet],
  );
  const highlightedEdgeIds = useMemo(
    () => new Set(highlightedPath),
    [highlightedPath],
  );

  // ---- Zoom ----
  const zoom = useCallback(
    (delta: number) => {
      updateTransform((prev) => ({
        ...prev,
        scale: Math.max(MIN_SCALE, Math.min(MAX_SCALE, prev.scale + delta)),
      }));
    },
    [updateTransform],
  );

  const handleWheel = useCallback(
    (e: ReactWheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
      zoom(delta);
    },
    [zoom],
  );

  const fitView = useCallback(() => {
    const container = containerRef.current;
    if (!container || layoutResult.width === 0) return;
    const rect = container.getBoundingClientRect();
    const scaleX = rect.width / layoutResult.width;
    const scaleY = rect.height / layoutResult.height;
    const scale = Math.min(scaleX, scaleY, 1) * 0.9;
    updateTransform({
      x: (rect.width - layoutResult.width * scale) / 2,
      y: (rect.height - layoutResult.height * scale) / 2,
      scale,
    });
  }, [layoutResult, updateTransform]);

  // Fit view on initial load
  useEffect(() => {
    fitView();
  }, [fitView]);

  // ---- Pan ----
  const handlePointerDown = useCallback(
    (e: ReactPointerEvent) => {
      // Only pan on background click (not nodes/edges)
      if ((e.target as HTMLElement).closest("[data-node-id], [data-edge-id]"))
        return;
      panRef.current = {
        active: true,
        startX: e.clientX,
        startY: e.clientY,
        originX: transform.x,
        originY: transform.y,
      };
      (e.target as Element).setPointerCapture?.(e.pointerId);
    },
    [transform.x, transform.y],
  );

  const handlePointerMove = useCallback(
    (e: ReactPointerEvent) => {
      if (!panRef.current.active) return;
      updateTransform((prev) => ({
        ...prev,
        x: panRef.current.originX + (e.clientX - panRef.current.startX),
        y: panRef.current.originY + (e.clientY - panRef.current.startY),
      }));
    },
    [updateTransform],
  );

  const handlePointerUp = useCallback(() => {
    panRef.current.active = false;
  }, []);

  // ---- Selection ----
  const handleNodeClick = useCallback(
    (id: string) => {
      const next = interaction.selectedNodeId === id ? null : id;
      updateInteraction((prev) => ({
        ...prev,
        selectedNodeId: next,
        selectedEdgeId: null,
      }));
      onNodeSelect?.(next);
    },
    [interaction.selectedNodeId, onNodeSelect, updateInteraction],
  );

  const handleEdgeClick = useCallback(
    (id: string) => {
      const next = interaction.selectedEdgeId === id ? null : id;
      updateInteraction((prev) => ({
        ...prev,
        selectedEdgeId: next,
        selectedNodeId: null,
      }));
      onEdgeSelect?.(next);
    },
    [interaction.selectedEdgeId, onEdgeSelect, updateInteraction],
  );

  const handleNodeHover = useCallback(
    (id: string) => {
      updateInteraction((prev) => ({ ...prev, hoveredNodeId: id }));
    },
    [updateInteraction],
  );

  const handleNodeLeave = useCallback(() => {
    updateInteraction((prev) => ({ ...prev, hoveredNodeId: null }));
  }, [updateInteraction]);

  const handleEdgeHover = useCallback(
    (id: string) => {
      updateInteraction((prev) => ({ ...prev, hoveredEdgeId: id }));
    },
    [updateInteraction],
  );

  const handleEdgeLeave = useCallback(() => {
    updateInteraction((prev) => ({ ...prev, hoveredEdgeId: null }));
  }, [updateInteraction]);

  // ---- Keyboard ----
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const nodeIds = nodes.map((n) => n.id);
      const focusedIdx = nodeIds.indexOf(interaction.focusedNodeId ?? "");

      switch (e.key) {
        case "ArrowRight":
        case "ArrowDown": {
          e.preventDefault();
          const next = focusedIdx < nodeIds.length - 1 ? focusedIdx + 1 : 0;
          updateInteraction((prev) => ({
            ...prev,
            focusedNodeId: nodeIds[next],
          }));
          break;
        }
        case "ArrowLeft":
        case "ArrowUp": {
          e.preventDefault();
          const prev = focusedIdx > 0 ? focusedIdx - 1 : nodeIds.length - 1;
          updateInteraction((p) => ({ ...p, focusedNodeId: nodeIds[prev] }));
          break;
        }
        case "Enter":
        case " ": {
          e.preventDefault();
          if (interaction.focusedNodeId)
            handleNodeClick(interaction.focusedNodeId);
          break;
        }
        case "Escape": {
          updateInteraction((prev) => ({
            ...prev,
            selectedNodeId: null,
            selectedEdgeId: null,
          }));
          onNodeSelect?.(null);
          onEdgeSelect?.(null);
          break;
        }
        case "+":
        case "=":
          zoom(ZOOM_STEP);
          break;
        case "-":
          zoom(-ZOOM_STEP);
          break;
        case "0":
          fitView();
          break;
      }
    },
    [
      nodes,
      interaction.focusedNodeId,
      handleNodeClick,
      onNodeSelect,
      onEdgeSelect,
      zoom,
      fitView,
      updateInteraction,
    ],
  );

  // ---- Overlay dimming logic ----
  const isNodeDimmed = useCallback(
    (node: CausalNodeData): boolean => {
      if (activeOverlay === "adjustment_set" && adjustmentSetIds.size > 0) {
        return !adjustmentSetIds.has(node.id);
      }
      if (activeOverlay === "transport") {
        // Dim nodes that have no transportable edges
        return !edges.some(
          (e) =>
            e.transportable && (e.source === node.id || e.target === node.id),
        );
      }
      return false;
    },
    [activeOverlay, adjustmentSetIds, edges],
  );

  const isEdgeDimmed = useCallback(
    (edge: CausalEdgeData): boolean => {
      if (activeOverlay === "identification") {
        return edge.status === "unidentified";
      }
      if (activeOverlay === "transport") {
        return !edge.transportable;
      }
      return false;
    },
    [activeOverlay],
  );

  return (
    <div
      ref={containerRef}
      className={cn(
        "bg-surface border-line relative overflow-hidden rounded-2xl border",
        className,
      )}
      style={{ minHeight: 400 }}
    >
      {showControls ? (
        <CausalGraphControls
          layout={activeLayout}
          overlay={activeOverlay}
          onLayoutChange={setLayoutAlg}
          onOverlayChange={setOverlay}
          onZoomIn={() => zoom(ZOOM_STEP)}
          onZoomOut={() => zoom(-ZOOM_STEP)}
          onFitView={fitView}
          className="absolute top-3 left-3 z-10"
        />
      ) : null}

      <svg
        ref={svgRef}
        width="100%"
        height="100%"
        className="absolute inset-0"
        style={{ touchAction: "none" }}
        role="tree"
        aria-label={`Causal graph with ${nodes.length} nodes and ${edges.length} edges`}
        tabIndex={0}
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onKeyDown={handleKeyDown}
      >
        <g
          transform={`translate(${transform.x}, ${transform.y}) scale(${transform.scale})`}
        >
          {/* Edges first (behind nodes) */}
          {edges.map((edge) => {
            const sp = layoutResult.positions.get(edge.source);
            const tp = layoutResult.positions.get(edge.target);
            if (!sp || !tp) return null;
            return (
              <CausalEdge
                key={edge.id}
                edge={edge}
                sourcePos={sp}
                targetPos={tp}
                selected={interaction.selectedEdgeId === edge.id}
                hovered={interaction.hoveredEdgeId === edge.id}
                dimmed={isEdgeDimmed(edge)}
                highlighted={highlightedEdgeIds.has(edge.id)}
                onClick={handleEdgeClick}
                onMouseEnter={handleEdgeHover}
                onMouseLeave={handleEdgeLeave}
              />
            );
          })}

          {/* Nodes */}
          {nodes.map((node) => {
            const pos = layoutResult.positions.get(node.id);
            if (!pos) return null;
            return (
              <CausalNode
                key={node.id}
                node={node}
                x={pos.x}
                y={pos.y}
                selected={interaction.selectedNodeId === node.id}
                hovered={interaction.hoveredNodeId === node.id}
                focused={interaction.focusedNodeId === node.id}
                dimmed={isNodeDimmed(node)}
                highlighted={adjustmentSetIds.has(node.id)}
                onClick={handleNodeClick}
                onMouseEnter={handleNodeHover}
                onMouseLeave={handleNodeLeave}
              />
            );
          })}
        </g>
      </svg>

      {/* Scale indicator */}
      <div className="text-muted absolute right-3 bottom-2 text-xs">
        {Math.round(transform.scale * 100)}%
      </div>
    </div>
  );
}
