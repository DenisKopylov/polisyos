import { useRef, useEffect, useCallback, useState } from "react";

import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";

import type {
  CausalNodeData,
  CausalEdgeData,
  LayoutAlgorithm,
  GraphTransform,
} from "../types";
import { NODE_WIDTH, NODE_HEIGHT, NODE_COLORS, NODE_SHAPES } from "../types";
import { computeLayout } from "../layouts";

type CausalGraphCanvasLargeProps = {
  nodes: CausalNodeData[];
  edges: CausalEdgeData[];
  layout?: LayoutAlgorithm;
  onNodeSelect?: (id: string | null) => void;
  className?: string;
};

const MIN_SCALE = 0.05;
const MAX_SCALE = 2;
const ZOOM_STEP = 0.1;

/**
 * Canvas-based renderer for large causal graphs (100+ nodes).
 *
 * Uses HTML Canvas 2D for performance — no SVG DOM overhead.
 * Supports zoom/pan and node click detection via hit testing.
 */
export function CausalGraphCanvasLarge({
  nodes,
  edges,
  layout: layoutAlg = "hierarchical",
  onNodeSelect,
  className,
}: CausalGraphCanvasLargeProps) {
  const { t } = useI18n();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const transformRef = useRef<GraphTransform>({ x: 0, y: 0, scale: 0.5 });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const layoutResult = computeLayout(layoutAlg, nodes, edges);
  const positions = layoutResult.positions;

  // Color resolver (CSS var → hex fallback for canvas)
  const colorCache = useRef(new Map<string, string>());
  const resolveColor = useCallback((cssVar: string): string => {
    if (colorCache.current.has(cssVar)) return colorCache.current.get(cssVar)!;
    if (!cssVar.startsWith("var(")) {
      colorCache.current.set(cssVar, cssVar);
      return cssVar;
    }
    const el = containerRef.current;
    if (!el) return "#888";
    const varName = cssVar.replace("var(", "").replace(")", "");
    const resolved =
      getComputedStyle(el).getPropertyValue(varName).trim() || "#888";
    colorCache.current.set(cssVar, resolved);
    return resolved;
  }, []);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const t = transformRef.current;
    ctx.clearRect(0, 0, rect.width, rect.height);
    ctx.save();
    ctx.translate(t.x, t.y);
    ctx.scale(t.scale, t.scale);

    // Draw edges
    ctx.lineWidth = 1;
    for (const edge of edges) {
      const sp = positions.get(edge.source);
      const tp = positions.get(edge.target);
      if (!sp || !tp) continue;

      const sx = sp.x + NODE_WIDTH / 2;
      const sy = sp.y + NODE_HEIGHT / 2;
      const tx = tp.x + NODE_WIDTH / 2;
      const ty = tp.y + NODE_HEIGHT / 2;

      ctx.beginPath();
      ctx.moveTo(sx, sy);
      const mx = (sx + tx) / 2;
      ctx.bezierCurveTo(mx, sy, mx, ty, tx, ty);

      if (edge.status === "identified") {
        ctx.strokeStyle = resolveColor("var(--chart-primary)");
        ctx.setLineDash([]);
      } else if (edge.status === "unidentified") {
        ctx.strokeStyle = resolveColor("var(--chart-alert)");
        ctx.setLineDash([6, 4]);
      } else {
        ctx.strokeStyle = resolveColor("var(--color-confidence-medium)");
        ctx.setLineDash([3, 3]);
      }
      ctx.stroke();
      ctx.setLineDash([]);

      // Arrow
      const dx = tx - mx;
      const dy = ty - (sy + ty) / 2;
      const angle = Math.atan2(ty - sy, tx - sx);
      const arrowLen = 6;
      ctx.beginPath();
      ctx.moveTo(tx, ty);
      ctx.lineTo(
        tx - arrowLen * Math.cos(angle - 0.4),
        ty - arrowLen * Math.sin(angle - 0.4),
      );
      ctx.moveTo(tx, ty);
      ctx.lineTo(
        tx - arrowLen * Math.cos(angle + 0.4),
        ty - arrowLen * Math.sin(angle + 0.4),
      );
      ctx.stroke();
    }

    // Draw nodes
    for (const node of nodes) {
      const pos = positions.get(node.id);
      if (!pos) continue;

      const color = resolveColor(NODE_COLORS[node.kind]);
      const cx = pos.x + NODE_WIDTH / 2;
      const cy = pos.y + NODE_HEIGHT / 2;
      const isSelected = selectedId === node.id;

      // Fill
      ctx.fillStyle = color;
      ctx.globalAlpha = isSelected ? 0.3 : 0.15;

      ctx.beginPath();
      const shape = NODE_SHAPES[node.kind];
      if (shape === "circle") {
        ctx.ellipse(cx, cy, NODE_WIDTH / 2, NODE_HEIGHT / 2, 0, 0, Math.PI * 2);
      } else if (shape === "diamond" || shape === "diamond-overlay") {
        ctx.moveTo(cx, cy - NODE_HEIGHT / 2);
        ctx.lineTo(cx + NODE_WIDTH / 2, cy);
        ctx.lineTo(cx, cy + NODE_HEIGHT / 2);
        ctx.lineTo(cx - NODE_WIDTH / 2, cy);
        ctx.closePath();
      } else {
        ctx.rect(pos.x, pos.y, NODE_WIDTH, NODE_HEIGHT);
      }
      ctx.fill();

      // Stroke
      ctx.globalAlpha = 1;
      ctx.strokeStyle = color;
      ctx.lineWidth = isSelected ? 2.5 : 1.5;
      ctx.stroke();

      // Label
      ctx.fillStyle = resolveColor("var(--text)");
      ctx.font = "bold 11px var(--font-sans), system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const label =
        node.label.length > 16
          ? `${node.label.slice(0, 15)}\u2026`
          : node.label;
      ctx.fillText(label, cx, cy);
    }

    ctx.restore();
  }, [nodes, edges, positions, selectedId, resolveColor]);

  useEffect(() => {
    draw();
  }, [draw]);

  // Resize observer
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const ro = new ResizeObserver(() => draw());
    ro.observe(container);
    return () => ro.disconnect();
  }, [draw]);

  // Pan
  const panRef = useRef({ active: false, sx: 0, sy: 0, ox: 0, oy: 0 });

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    const t = transformRef.current;
    panRef.current = {
      active: true,
      sx: e.clientX,
      sy: e.clientY,
      ox: t.x,
      oy: t.y,
    };
    (e.target as Element).setPointerCapture?.(e.pointerId);
  }, []);

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!panRef.current.active) return;
      transformRef.current = {
        ...transformRef.current,
        x: panRef.current.ox + (e.clientX - panRef.current.sx),
        y: panRef.current.oy + (e.clientY - panRef.current.sy),
      };
      draw();
    },
    [draw],
  );

  const handlePointerUp = useCallback(() => {
    panRef.current.active = false;
  }, []);

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
      transformRef.current = {
        ...transformRef.current,
        scale: Math.max(
          MIN_SCALE,
          Math.min(MAX_SCALE, transformRef.current.scale + delta),
        ),
      };
      draw();
    },
    [draw],
  );

  // Click hit-testing
  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const t = transformRef.current;
      const mx = (e.clientX - rect.left - t.x) / t.scale;
      const my = (e.clientY - rect.top - t.y) / t.scale;

      let hit: string | null = null;
      for (const node of nodes) {
        const pos = positions.get(node.id);
        if (!pos) continue;
        if (
          mx >= pos.x &&
          mx <= pos.x + NODE_WIDTH &&
          my >= pos.y &&
          my <= pos.y + NODE_HEIGHT
        ) {
          hit = node.id;
          break;
        }
      }

      setSelectedId(hit);
      onNodeSelect?.(hit);
    },
    [nodes, positions, onNodeSelect],
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
      <div className="bg-surface/90 border-line absolute top-3 left-3 z-10 rounded-xl border px-3 py-1.5 text-xs backdrop-blur-sm">
        <span className="text-muted">
          {t("causal.canvas.modeSummary", { count: nodes.length })}
        </span>
      </div>
      <canvas
        ref={canvasRef}
        className="absolute inset-0 size-full"
        style={{ touchAction: "none" }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onWheel={handleWheel}
        onClick={handleClick}
      />
    </div>
  );
}
