import { useMemo } from "react";

import { cn } from "@/lib/utils";
import { waterfallColors, chartTheme, chartDefaults } from "./theme";
import { ChartDataTable } from "./accessibility";
import type { WaterfallStep } from "./types";

type WaterfallChartProps = {
  steps: WaterfallStep[];
  title?: string;
  height?: number;
  className?: string;
};

type ComputedBar = {
  label: string;
  value: number;
  start: number;
  end: number;
  isTotal: boolean;
  isPositive: boolean;
};

export function WaterfallChart({
  steps,
  title,
  height = 320,
  className,
}: WaterfallChartProps) {
  const bars = useMemo<ComputedBar[]>(() => {
    const result: ComputedBar[] = [];
    let running = 0;
    for (const step of steps) {
      if (step.isTotal) {
        result.push({
          label: step.label,
          value: running,
          start: 0,
          end: running,
          isTotal: true,
          isPositive: running >= 0,
        });
      } else {
        const start = running;
        running += step.value;
        result.push({
          label: step.label,
          value: step.value,
          start,
          end: running,
          isTotal: false,
          isPositive: step.value >= 0,
        });
      }
    }
    return result;
  }, [steps]);

  const allValues = bars.flatMap((b) => [b.start, b.end]);
  const minVal = Math.min(0, ...allValues);
  const maxVal = Math.max(0, ...allValues);
  const range = maxVal - minVal || 1;

  const padding = { top: 28, right: 16, bottom: 48, left: 16 };
  const barGap = 4;

  function toY(val: number): number {
    const plotH = height - padding.top - padding.bottom;
    return padding.top + plotH * (1 - (val - minVal) / range);
  }

  const plotWidth = Math.max(bars.length * 60, 400);
  const barWidth = Math.min(
    (plotWidth - padding.left - padding.right - barGap * (bars.length - 1)) /
      bars.length,
    48,
  );

  const zeroY = toY(0);

  const tableRows = useMemo(
    () =>
      bars.map((b) => ({
        label: b.label,
        values: {
          Value: b.value.toFixed(3),
          Cumulative: b.end.toFixed(3),
        },
      })),
    [bars],
  );

  const ariaDescription = `Waterfall chart${title ? `: ${title}` : ""}. ${bars.length} steps from ${bars[0]?.label ?? ""} to ${bars.at(-1)?.label ?? ""}.`;

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
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${plotWidth} ${height}`}
        className="overflow-visible"
      >
        {/* Zero line */}
        <line
          x1={padding.left}
          y1={zeroY}
          x2={plotWidth - padding.right}
          y2={zeroY}
          stroke={chartTheme.grid}
          strokeDasharray="3 3"
        />

        {bars.map((bar, i) => {
          const x =
            padding.left +
            i * (barWidth + barGap) +
            (plotWidth -
              padding.left -
              padding.right -
              bars.length * barWidth -
              (bars.length - 1) * barGap) /
              2;
          const yTop = toY(Math.max(bar.start, bar.end));
          const yBot = toY(Math.min(bar.start, bar.end));
          const barH = Math.max(yBot - yTop, 1);

          const fill = bar.isTotal
            ? waterfallColors.total
            : bar.isPositive
              ? waterfallColors.positive
              : waterfallColors.negative;

          return (
            <g key={bar.label}>
              {/* Connector line from previous bar */}
              {i > 0 && !bar.isTotal && (
                <line
                  x1={x - barGap}
                  y1={toY(bar.start)}
                  x2={x}
                  y2={toY(bar.start)}
                  stroke={chartTheme.grid}
                  strokeDasharray="2 2"
                />
              )}
              <rect
                x={x}
                y={yTop}
                width={barWidth}
                height={barH}
                rx={3}
                fill={fill}
                opacity={0.85}
              />
              {/* Value label */}
              <text
                x={x + barWidth / 2}
                y={yTop - 6}
                textAnchor="middle"
                fontSize={chartDefaults.tickFontSize}
                fill={chartTheme.axis}
              >
                {bar.isTotal
                  ? bar.value.toFixed(2)
                  : `${bar.value >= 0 ? "+" : ""}${bar.value.toFixed(2)}`}
              </text>
              {/* Category label */}
              <text
                x={x + barWidth / 2}
                y={height - padding.bottom + 16}
                textAnchor="middle"
                fontSize={chartDefaults.tickFontSize}
                fill={chartTheme.axis}
              >
                {bar.label.length > 10
                  ? `${bar.label.slice(0, 9)}…`
                  : bar.label}
              </text>
            </g>
          );
        })}
      </svg>
      <ChartDataTable
        caption={title ?? "Waterfall chart data"}
        columns={["Value", "Cumulative"]}
        rows={tableRows}
      />
    </figure>
  );
}
