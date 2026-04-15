import { useMemo, useState, useCallback } from "react";

import { cn } from "@/lib/utils";
import { chartTheme, categoricalPalette, chartDefaults } from "./theme";
import { ChartDataTable } from "./accessibility";
import type { ParallelAxis, ParallelRow } from "./types";

type ParallelCoordinatesChartProps = {
  axes: ParallelAxis[];
  data: ParallelRow[];
  title?: string;
  highlightedIds?: Set<string>;
  onLineHover?: (id: string | null) => void;
  height?: number;
  className?: string;
};

const AXIS_PADDING = 40;
const PADDING = { top: 32, bottom: 28, left: 16, right: 16 };

export function ParallelCoordinatesChart({
  axes,
  data,
  title,
  highlightedIds,
  onLineHover,
  height = 360,
  className,
}: ParallelCoordinatesChartProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  function toNumericValue(row: ParallelRow, key: string): number {
    const value = row[key];
    return typeof value === "number" ? value : 0;
  }

  const handleHover = useCallback(
    (id: string | null) => {
      setHoveredId(id);
      onLineHover?.(id);
    },
    [onLineHover],
  );

  const svgWidth = Math.max(axes.length * 120, 400);
  const plotW = svgWidth - PADDING.left - PADDING.right;
  const plotH = height - PADDING.top - PADDING.bottom;

  const axisPositions = useMemo(
    () =>
      axes.map((_, i) =>
        PADDING.left + (plotW / (axes.length - 1 || 1)) * i,
      ),
    [axes.length, plotW],
  );

  const scales = useMemo(() => {
    return axes.map((axis) => {
      if (axis.domain) {
        return { min: axis.domain[0], max: axis.domain[1] };
      }
      const vals = data.map((row) => toNumericValue(row, axis.key));
      const min = Math.min(...vals);
      const max = Math.max(...vals);
      const pad = (max - min) * 0.05 || 1;
      return { min: min - pad, max: max + pad };
    });
  }, [axes, data]);

  function toY(value: number, axisIdx: number): number {
    const { min, max } = scales[axisIdx];
    const range = max - min || 1;
    return PADDING.top + plotH * (1 - (value - min) / range);
  }

  const lines = useMemo(
    () =>
      data.map((row) => {
        const points = axes.map((axis, i) => ({
          x: axisPositions[i],
          y: toY(toNumericValue(row, axis.key), i),
        }));
        const d = points
          .map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`)
          .join(" ");
        return { id: row.id, d };
      }),
    [data, axes, axisPositions, scales],
  );

  const tableRows = useMemo(
    () =>
      data.slice(0, 30).map((row) => ({
        label: row.id,
        values: Object.fromEntries(
          axes.map((axis) => [axis.label, String(row[axis.key] ?? "-")]),
        ),
      })),
    [data, axes],
  );

  const ariaDescription = `Parallel coordinates chart${title ? `: ${title}` : ""}. ${axes.length} axes, ${data.length} observations.`;

  return (
    <figure
      className={cn("border-border bg-card rounded-xl border p-4", className)}
      role="img"
      aria-label={ariaDescription}
    >
      {title && (
        <figcaption className="text-foreground mb-3 text-sm font-semibold">
          {title}
        </figcaption>
      )}
      <div className="overflow-x-auto">
        <svg
          width={svgWidth}
          height={height}
          className="overflow-visible"
          onMouseLeave={() => handleHover(null)}
        >
          {/* Axis lines */}
          {axes.map((axis, i) => {
            const x = axisPositions[i];
            return (
              <g key={axis.key}>
                <line
                  x1={x}
                  y1={PADDING.top}
                  x2={x}
                  y2={PADDING.top + plotH}
                  stroke={chartTheme.grid}
                  strokeWidth={1}
                />
                {/* Axis label */}
                <text
                  x={x}
                  y={PADDING.top - 10}
                  textAnchor="middle"
                  fontSize={chartDefaults.tickFontSize}
                  fontWeight={600}
                  fill={chartTheme.axis}
                >
                  {axis.label}
                </text>
                {/* Min/max ticks */}
                <text
                  x={x}
                  y={PADDING.top + plotH + 14}
                  textAnchor="middle"
                  fontSize={10}
                  fill={chartTheme.neutral}
                >
                  {scales[i].min.toFixed(1)}
                </text>
                <text
                  x={x}
                  y={PADDING.top - 24}
                  textAnchor="middle"
                  fontSize={10}
                  fill={chartTheme.neutral}
                >
                  {scales[i].max.toFixed(1)}
                </text>
              </g>
            );
          })}

          {/* Data lines — background (dimmed) */}
          {lines.map((line, i) => {
            const isHighlighted =
              highlightedIds?.has(line.id) || hoveredId === line.id;
            const isAnyHighlighted = hoveredId !== null || (highlightedIds?.size ?? 0) > 0;
            return (
              <path
                key={line.id}
                d={line.d}
                fill="none"
                stroke={
                  isHighlighted
                    ? categoricalPalette[i % categoricalPalette.length]
                    : chartTheme.neutral
                }
                strokeWidth={isHighlighted ? 2 : 1}
                opacity={
                  isAnyHighlighted ? (isHighlighted ? 0.9 : 0.08) : 0.35
                }
                className="cursor-pointer"
                onMouseEnter={() => handleHover(line.id)}
              />
            );
          })}
        </svg>
      </div>
      <ChartDataTable
        caption={title ?? "Parallel coordinates data"}
        columns={axes.map((a) => a.label)}
        rows={tableRows}
      />
    </figure>
  );
}
