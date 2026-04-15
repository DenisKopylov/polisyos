import { useMemo } from "react";

import { cn } from "@/lib/utils";
import { chartTheme, ciColors, chartDefaults } from "./theme";
import { describeForestPlot, ChartDataTable } from "./accessibility";
import type { EffectEstimate } from "./types";

type ForestPlotProps = {
  estimates: EffectEstimate[];
  pooled?: EffectEstimate;
  referenceValue?: number;
  title?: string;
  className?: string;
};

const ROW_HEIGHT = 32;
const LABEL_WIDTH = 160;
const WEIGHT_WIDTH = 48;

export function ForestPlot({
  estimates,
  pooled,
  referenceValue = 0,
  title,
  className,
}: ForestPlotProps) {
  const all = pooled ? [...estimates, pooled] : estimates;
  const allValues = all.flatMap((e) => [e.ci.lower, e.ci.upper, e.estimate]);
  const minVal = Math.min(referenceValue, ...allValues);
  const maxVal = Math.max(referenceValue, ...allValues);
  const valRange = maxVal - minVal || 1;
  const valPad = valRange * 0.15;

  const totalRows = estimates.length + (pooled ? 2 : 0); // +1 separator +1 pooled
  const padding = { top: 28, bottom: 16 };
  const svgHeight = padding.top + totalRows * ROW_HEIGHT + padding.bottom;
  const plotLeft = LABEL_WIDTH;
  const plotRight = WEIGHT_WIDTH;
  const svgWidth = 600;
  const plotW = svgWidth - plotLeft - plotRight;

  function toX(val: number): number {
    return plotLeft + plotW * ((val - (minVal - valPad)) / (valRange + 2 * valPad));
  }

  const refX = toX(referenceValue);

  const maxWeight = Math.max(...estimates.map((e) => e.weight ?? 1), 1);

  const ariaDescription = describeForestPlot(estimates);

  const tableRows = useMemo(
    () =>
      all.map((e) => ({
        label: e.label,
        values: {
          Estimate: e.estimate.toFixed(4),
          "CI Lower": e.ci.lower.toFixed(4),
          "CI Upper": e.ci.upper.toFixed(4),
          Weight: e.weight != null ? `${(e.weight * 100).toFixed(1)}%` : "-",
        },
      })),
    [all],
  );

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
        <svg width={svgWidth} height={svgHeight} className="overflow-visible">
          {/* Reference line */}
          <line
            x1={refX}
            y1={padding.top - 8}
            x2={refX}
            y2={svgHeight - padding.bottom}
            stroke={chartTheme.neutral}
            strokeDasharray="4 3"
          />

          {/* Study rows */}
          {estimates.map((est, i) => {
            const cy = padding.top + i * ROW_HEIGHT + ROW_HEIGHT / 2;
            const dotR = 3 + ((est.weight ?? 0) / maxWeight) * 5;
            return (
              <g key={est.id}>
                {/* Label */}
                <text
                  x={plotLeft - 8}
                  y={cy}
                  textAnchor="end"
                  dominantBaseline="central"
                  fontSize={chartDefaults.tickFontSize}
                  fill={chartTheme.axis}
                >
                  {est.label.length > 22
                    ? `${est.label.slice(0, 21)}…`
                    : est.label}
                </text>
                {/* CI line */}
                <line
                  x1={toX(est.ci.lower)}
                  y1={cy}
                  x2={toX(est.ci.upper)}
                  y2={cy}
                  stroke={ciColors.boundsStroke}
                  strokeWidth={1.5}
                />
                {/* CI caps */}
                <line
                  x1={toX(est.ci.lower)}
                  y1={cy - 4}
                  x2={toX(est.ci.lower)}
                  y2={cy + 4}
                  stroke={ciColors.boundsStroke}
                  strokeWidth={1.5}
                />
                <line
                  x1={toX(est.ci.upper)}
                  y1={cy - 4}
                  x2={toX(est.ci.upper)}
                  y2={cy + 4}
                  stroke={ciColors.boundsStroke}
                  strokeWidth={1.5}
                />
                {/* Point estimate (square sized by weight) */}
                <rect
                  x={toX(est.estimate) - dotR}
                  y={cy - dotR}
                  width={dotR * 2}
                  height={dotR * 2}
                  fill={chartTheme.primary}
                  rx={1}
                />
                {/* Weight label */}
                {est.weight != null && (
                  <text
                    x={svgWidth - plotRight + 8}
                    y={cy}
                    dominantBaseline="central"
                    fontSize={chartDefaults.tickFontSize}
                    fill={chartTheme.neutral}
                  >
                    {(est.weight * 100).toFixed(1)}%
                  </text>
                )}
              </g>
            );
          })}

          {/* Pooled estimate */}
          {pooled && (
            <>
              {/* Separator */}
              <line
                x1={plotLeft}
                y1={
                  padding.top +
                  estimates.length * ROW_HEIGHT +
                  ROW_HEIGHT * 0.25
                }
                x2={svgWidth - plotRight}
                y2={
                  padding.top +
                  estimates.length * ROW_HEIGHT +
                  ROW_HEIGHT * 0.25
                }
                stroke={chartTheme.grid}
              />
              {(() => {
                const cy =
                  padding.top +
                  (estimates.length + 1) * ROW_HEIGHT +
                  ROW_HEIGHT / 2;
                const diamondHalf = 7;
                const px = toX(pooled.estimate);
                const lx = toX(pooled.ci.lower);
                const rx = toX(pooled.ci.upper);
                return (
                  <g>
                    <text
                      x={plotLeft - 8}
                      y={cy}
                      textAnchor="end"
                      dominantBaseline="central"
                      fontSize={chartDefaults.tickFontSize}
                      fontWeight={700}
                      fill={chartTheme.axis}
                    >
                      {pooled.label}
                    </text>
                    {/* Diamond */}
                    <polygon
                      points={`${lx},${cy} ${px},${cy - diamondHalf} ${rx},${cy} ${px},${cy + diamondHalf}`}
                      fill={chartTheme.primary}
                      opacity={0.85}
                    />
                  </g>
                );
              })()}
            </>
          )}

          {/* X axis */}
          <line
            x1={plotLeft}
            y1={svgHeight - padding.bottom}
            x2={svgWidth - plotRight}
            y2={svgHeight - padding.bottom}
            stroke={chartTheme.axis}
          />
          {[minVal - valPad, referenceValue, maxVal + valPad].map((tick) => (
            <text
              key={tick}
              x={toX(tick)}
              y={svgHeight - 2}
              textAnchor="middle"
              fontSize={chartDefaults.tickFontSize}
              fill={chartTheme.axis}
            >
              {tick.toFixed(2)}
            </text>
          ))}
        </svg>
      </div>
      <ChartDataTable
        caption={title ?? "Forest plot data"}
        columns={["Estimate", "CI Lower", "CI Upper", "Weight"]}
        rows={tableRows}
      />
    </figure>
  );
}
