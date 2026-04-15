import { memo } from "react";

import type { CausalNodeData, CausalNodeKind } from "../types";
import { NODE_WIDTH, NODE_HEIGHT, NODE_COLORS } from "../types";

type CausalNodeProps = {
  node: CausalNodeData;
  x: number;
  y: number;
  selected?: boolean;
  hovered?: boolean;
  focused?: boolean;
  dimmed?: boolean;
  highlighted?: boolean;
  onClick?: (id: string) => void;
  onMouseEnter?: (id: string) => void;
  onMouseLeave?: () => void;
};

const W = NODE_WIDTH;
const H = NODE_HEIGHT;
const HW = W / 2;
const HH = H / 2;

/** SVG shape path for each node kind, centered at (0,0). */
function shapePath(kind: CausalNodeKind): string {
  switch (kind) {
    case "treatment": // Diamond
      return `M 0 ${-HH} L ${HW} 0 L 0 ${HH} L ${-HW} 0 Z`;
    case "outcome": // Ellipse approximated as rounded path
      return `M ${-HW} 0 A ${HW} ${HH} 0 1 1 ${HW} 0 A ${HW} ${HH} 0 1 1 ${-HW} 0 Z`;
    case "confounder": // Square
      return `M ${-HW} ${-HH} L ${HW} ${-HH} L ${HW} ${HH} L ${-HW} ${HH} Z`;
    case "mediator": // Rounded rect (approx with arcs)
    {
      const r = 12;
      return `M ${-HW + r} ${-HH} L ${HW - r} ${-HH} Q ${HW} ${-HH} ${HW} ${-HH + r} L ${HW} ${HH - r} Q ${HW} ${HH} ${HW - r} ${HH} L ${-HW + r} ${HH} Q ${-HW} ${HH} ${-HW} ${HH - r} L ${-HW} ${-HH + r} Q ${-HW} ${-HH} ${-HW + r} ${-HH} Z`;
    }
    case "collider": // Hexagon
    {
      const s = HW * 0.3;
      return `M ${-HW + s} ${-HH} L ${HW - s} ${-HH} L ${HW} 0 L ${HW - s} ${HH} L ${-HW + s} ${HH} L ${-HW} 0 Z`;
    }
    case "instrument": // Triangle
      return `M 0 ${-HH} L ${HW} ${HH} L ${-HW} ${HH} Z`;
    case "selection": // Diamond with inner diamond (S-node)
      return `M 0 ${-HH} L ${HW} 0 L 0 ${HH} L ${-HW} 0 Z`;
    default:
      return `M ${-HW} ${-HH} L ${HW} ${-HH} L ${HW} ${HH} L ${-HW} ${HH} Z`;
  }
}

export const CausalNode = memo(function CausalNode({
  node,
  x,
  y,
  selected = false,
  hovered = false,
  focused = false,
  dimmed = false,
  highlighted = false,
  onClick,
  onMouseEnter,
  onMouseLeave,
}: CausalNodeProps) {
  const color = NODE_COLORS[node.kind];
  const cx = x + HW;
  const cy = y + HH;

  return (
    <g
      transform={`translate(${cx}, ${cy})`}
      role="treeitem"
      aria-label={`${node.kind}: ${node.label}${node.estimate != null ? `, effect ${node.estimate.toFixed(3)}` : ""}`}
      tabIndex={-1}
      style={{ cursor: "pointer", outline: "none" }}
      onClick={() => onClick?.(node.id)}
      onMouseEnter={() => onMouseEnter?.(node.id)}
      onMouseLeave={() => onMouseLeave?.()}
      data-node-id={node.id}
    >
      {/* Selection ring */}
      {(selected || focused) && (
        <path
          d={shapePath(node.kind)}
          fill="none"
          stroke={color}
          strokeWidth={3}
          opacity={0.4}
          transform="scale(1.12)"
        />
      )}

      {/* Main shape */}
      <path
        d={shapePath(node.kind)}
        fill={dimmed ? "var(--surface)" : color}
        fillOpacity={dimmed ? 0.3 : 0.15}
        stroke={color}
        strokeWidth={selected ? 2.5 : hovered ? 2 : 1.5}
        opacity={dimmed ? 0.4 : 1}
      />

      {/* S-node inner diamond overlay */}
      {node.kind === "selection" && (
        <path
          d={shapePath("selection")}
          fill="none"
          stroke={color}
          strokeWidth={1}
          strokeDasharray="3 2"
          transform="scale(0.6)"
        />
      )}

      {/* Highlighted glow */}
      {highlighted && (
        <path
          d={shapePath(node.kind)}
          fill={color}
          fillOpacity={0.08}
          stroke="none"
          transform="scale(1.25)"
        />
      )}

      {/* Label */}
      <text
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={12}
        fontWeight={600}
        fill={dimmed ? "var(--chart-neutral)" : "var(--text)"}
        opacity={dimmed ? 0.5 : 1}
        className="pointer-events-none select-none"
        y={-4}
      >
        {node.label.length > 18 ? `${node.label.slice(0, 17)}\u2026` : node.label}
      </text>

      {/* Effect estimate subtitle */}
      {node.estimate != null && (
        <text
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={10}
          fill="var(--chart-neutral)"
          className="pointer-events-none select-none"
          y={12}
        >
          {node.estimate >= 0 ? "+" : ""}
          {node.estimate.toFixed(3)}
        </text>
      )}

      {/* Data availability indicator */}
      {node.dataAvailable === false && (
        <circle
          cx={HW - 6}
          cy={-HH + 6}
          r={4}
          fill="var(--chart-warning)"
          stroke="var(--surface)"
          strokeWidth={1.5}
        />
      )}
    </g>
  );
});
