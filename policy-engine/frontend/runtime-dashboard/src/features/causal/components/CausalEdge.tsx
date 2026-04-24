import { memo } from "react";

import type { CausalEdgeData, EdgeIdentificationStatus } from "../types";
import { NODE_WIDTH, NODE_HEIGHT } from "../types";

type CausalEdgeProps = {
  edge: CausalEdgeData;
  sourcePos: { x: number; y: number };
  targetPos: { x: number; y: number };
  selected?: boolean;
  hovered?: boolean;
  dimmed?: boolean;
  highlighted?: boolean;
  onClick?: (id: string) => void;
  onMouseEnter?: (id: string) => void;
  onMouseLeave?: () => void;
};

const HW = NODE_WIDTH / 2;
const HH = NODE_HEIGHT / 2;
const ARROW_SIZE = 6;

function edgeStyle(status: EdgeIdentificationStatus): {
  color: string;
  dash: string;
} {
  switch (status) {
    case "identified":
      return { color: "var(--chart-primary)", dash: "none" };
    case "unidentified":
      return { color: "var(--chart-alert)", dash: "6 4" };
    case "bounds_only":
      return { color: "var(--color-confidence-medium)", dash: "3 3" };
  }
}

function edgeWidth(estimate?: number): number {
  if (estimate == null) return 1.5;
  const abs = Math.abs(estimate);
  return Math.max(1.5, Math.min(4, 1.5 + abs * 8));
}

export const CausalEdge = memo(function CausalEdge({
  edge,
  sourcePos,
  targetPos,
  selected = false,
  hovered = false,
  dimmed = false,
  highlighted = false,
  onClick,
  onMouseEnter,
  onMouseLeave,
}: CausalEdgeProps) {
  const { color, dash } = edgeStyle(edge.status);
  const strokeW = edgeWidth(edge.estimate);

  // Compute start/end at node center
  const sx = sourcePos.x + HW;
  const sy = sourcePos.y + HH;
  const tx = targetPos.x + HW;
  const ty = targetPos.y + HH;

  // Direction vector
  const dx = tx - sx;
  const dy = ty - sy;
  const dist = Math.sqrt(dx * dx + dy * dy) || 1;
  const nx = dx / dist;
  const ny = dy / dist;

  // Offset start/end from node edges
  const startOffset = HW * 0.85;
  const endOffset = HW * 0.85 + ARROW_SIZE;
  const x1 = sx + nx * startOffset;
  const y1 = sy + ny * startOffset;
  const x2 = tx - nx * endOffset;
  const y2 = ty - ny * endOffset;

  // Cubic bezier control points
  const cx1 = x1 + dx * 0.35;
  const cy1 = y1;
  const cx2 = x2 - dx * 0.35;
  const cy2 = y2;

  const pathD = `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`;

  // Arrowhead at end
  const arrowTip = { x: tx - nx * (HW * 0.85), y: ty - ny * (HW * 0.85) };
  const arrowLeft = {
    x: arrowTip.x - nx * ARROW_SIZE - ny * ARROW_SIZE * 0.5,
    y: arrowTip.y - ny * ARROW_SIZE + nx * ARROW_SIZE * 0.5,
  };
  const arrowRight = {
    x: arrowTip.x - nx * ARROW_SIZE + ny * ARROW_SIZE * 0.5,
    y: arrowTip.y - ny * ARROW_SIZE - nx * ARROW_SIZE * 0.5,
  };

  // Label position at midpoint
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;

  const opacity = dimmed ? 0.2 : highlighted ? 1 : hovered ? 1 : 0.7;

  return (
    <g
      role="treeitem"
      aria-label={`Edge from ${edge.source} to ${edge.target}, ${edge.status}${edge.estimate != null ? `, effect ${edge.estimate.toFixed(3)}` : ""}`}
      style={{ cursor: "pointer" }}
      onClick={() => onClick?.(edge.id)}
      onMouseEnter={() => onMouseEnter?.(edge.id)}
      onMouseLeave={() => onMouseLeave?.()}
      data-edge-id={edge.id}
    >
      {/* Hit area (wider invisible stroke for easier clicking) */}
      <path d={pathD} fill="none" stroke="transparent" strokeWidth={12} />

      {/* Highlight glow */}
      {(selected || highlighted) && (
        <path
          d={pathD}
          fill="none"
          stroke={color}
          strokeWidth={strokeW + 4}
          opacity={0.15}
        />
      )}

      {/* Main line */}
      <path
        d={pathD}
        fill="none"
        stroke={color}
        strokeWidth={selected ? strokeW + 1 : strokeW}
        strokeDasharray={dash}
        opacity={opacity}
      />

      {/* Arrowhead */}
      <polygon
        points={`${arrowTip.x},${arrowTip.y} ${arrowLeft.x},${arrowLeft.y} ${arrowRight.x},${arrowRight.y}`}
        fill={color}
        opacity={opacity}
      />

      {/* Transport marker */}
      {edge.transportable && (
        <circle
          cx={midX}
          cy={midY - 12}
          r={4}
          fill="var(--chart-secondary)"
          stroke="var(--surface)"
          strokeWidth={1.5}
        />
      )}

      {/* Effect label */}
      {edge.estimate != null && !dimmed && (
        <g transform={`translate(${midX}, ${midY})`}>
          <rect
            x={-24}
            y={-9}
            width={48}
            height={18}
            rx={4}
            fill="var(--surface)"
            fillOpacity={0.9}
            stroke={color}
            strokeWidth={0.5}
          />
          <text
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={10}
            fontWeight={600}
            fontFamily="var(--font-mono)"
            fill={color}
            className="pointer-events-none select-none"
          >
            {edge.estimate >= 0 ? "+" : ""}
            {edge.estimate.toFixed(3)}
          </text>
        </g>
      )}
    </g>
  );
});
