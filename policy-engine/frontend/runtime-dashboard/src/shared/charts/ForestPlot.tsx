import { useId, useMemo } from "react";

import { cn } from "@/lib/utils";

import { ChartDataTable, describeForestPlot } from "./accessibility";
import {
  buildUncertaintyPatternIds,
  resolveUncertaintyPatternFill,
  UncertaintyPatterns,
} from "./patterns";
import { chartDefaults, chartTheme } from "./theme";
import {
  resolveIdentifiabilityPattern,
  resolveUncertaintyIntervalColor,
  resolveUncertaintyPaletteColor,
  type UncertaintyPalette,
} from "./uncertainty-tokens";
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
  const allValues = all.flatMap((estimate) => [
    estimate.ci.lower,
    estimate.ci.upper,
    estimate.estimate,
  ]);
  const minVal = Math.min(referenceValue, ...allValues);
  const maxVal = Math.max(referenceValue, ...allValues);
  const valRange = maxVal - minVal || 1;
  const valPad = valRange * 0.15;

  const totalRows = estimates.length + (pooled ? 2 : 0);
  const padding = { top: 28, bottom: 16 };
  const svgHeight = padding.top + totalRows * ROW_HEIGHT + padding.bottom;
  const plotLeft = LABEL_WIDTH;
  const plotRight = WEIGHT_WIDTH;
  const svgWidth = 600;
  const plotWidth = svgWidth - plotLeft - plotRight;
  const patternSeed = useId();
  const patternIds = useMemo(
    () => buildUncertaintyPatternIds(patternSeed.replace(/:/g, "")),
    [patternSeed],
  );

  function toX(value: number): number {
    return (
      plotLeft +
      plotWidth * ((value - (minVal - valPad)) / (valRange + 2 * valPad))
    );
  }

  const refX = toX(referenceValue);
  const maxWeight = Math.max(
    ...estimates.map((estimate) => estimate.weight ?? 1),
    1,
  );
  const ariaDescription = describeForestPlot(estimates);
  const tableRows = useMemo(
    () =>
      all.map((estimate) => ({
        label: estimate.label,
        values: {
          Estimate: estimate.estimate.toFixed(4),
          "CI Lower": estimate.ci.lower.toFixed(4),
          "CI Upper": estimate.ci.upper.toFixed(4),
          Weight:
            estimate.weight != null
              ? `${(estimate.weight * 100).toFixed(1)}%`
              : "-",
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
      {title ? (
        <figcaption className="text-foreground mb-3 text-sm font-semibold">
          {title}
        </figcaption>
      ) : null}
      <div className="overflow-x-auto">
        <svg width={svgWidth} height={svgHeight} className="overflow-visible">
          <defs>
            {all.map((estimate) => {
              const gradientId = `${patternSeed.replace(/:/g, "")}-${estimate.id}-ci`;
              const palette: UncertaintyPalette = estimate.disputed
                ? "disputed"
                : "default";
              const pointColor = resolveUncertaintyPaletteColor(palette);
              return (
                <linearGradient
                  key={gradientId}
                  id={gradientId}
                  x1="0%"
                  x2="100%"
                  y1="0%"
                  y2="0%"
                >
                  <stop offset="0%" stopColor={pointColor} stopOpacity="0" />
                  <stop
                    offset="50%"
                    stopColor={pointColor}
                    stopOpacity="0.28"
                  />
                  <stop offset="100%" stopColor={pointColor} stopOpacity="0" />
                </linearGradient>
              );
            })}
          </defs>
          <UncertaintyPatterns ids={patternIds} />
          <line
            x1={refX}
            y1={padding.top - 8}
            x2={refX}
            y2={svgHeight - padding.bottom}
            stroke={chartTheme.neutral}
            strokeDasharray="4 3"
          />

          {estimates.map((estimate, index) => {
            const cy = padding.top + index * ROW_HEIGHT + ROW_HEIGHT / 2;
            const pointRadius = 3 + ((estimate.weight ?? 0) / maxWeight) * 5;
            const palette: UncertaintyPalette = estimate.disputed
              ? "disputed"
              : "default";
            const pointColor = resolveUncertaintyPaletteColor(palette);
            const intervalColor = resolveUncertaintyIntervalColor(palette);
            const gradientId = `${patternSeed.replace(/:/g, "")}-${estimate.id}-ci`;
            const patternKind = resolveIdentifiabilityPattern(
              estimate.identifiability ?? "identified",
            );
            const ciX = toX(estimate.ci.lower);
            const ciWidth = toX(estimate.ci.upper) - ciX;

            return (
              <g key={estimate.id}>
                <text
                  x={plotLeft - 8}
                  y={cy}
                  textAnchor="end"
                  dominantBaseline="central"
                  fontSize={chartDefaults.tickFontSize}
                  fill={chartTheme.axis}
                >
                  {estimate.label.length > 22
                    ? `${estimate.label.slice(0, 21)}…`
                    : estimate.label}
                </text>
                <rect
                  x={ciX}
                  y={cy - 4}
                  width={ciWidth}
                  height={8}
                  rx={4}
                  fill={`url(#${gradientId})`}
                />
                <rect
                  x={ciX}
                  y={cy - 4}
                  width={ciWidth}
                  height={8}
                  rx={4}
                  fill="none"
                  stroke={intervalColor}
                  strokeWidth={1}
                  opacity={0.6}
                />
                {patternKind !== "none" ? (
                  <rect
                    x={ciX}
                    y={cy - 4}
                    width={ciWidth}
                    height={8}
                    rx={4}
                    fill={resolveUncertaintyPatternFill(
                      patternKind,
                      patternIds,
                    )}
                    fillOpacity={0.7}
                  />
                ) : null}
                <line
                  x1={toX(estimate.ci.lower)}
                  y1={cy - 5}
                  x2={toX(estimate.ci.lower)}
                  y2={cy + 5}
                  stroke={intervalColor}
                  strokeWidth={1.2}
                />
                <line
                  x1={toX(estimate.ci.upper)}
                  y1={cy - 5}
                  x2={toX(estimate.ci.upper)}
                  y2={cy + 5}
                  stroke={intervalColor}
                  strokeWidth={1.2}
                />
                <rect
                  x={toX(estimate.estimate) - pointRadius}
                  y={cy - pointRadius}
                  width={pointRadius * 2}
                  height={pointRadius * 2}
                  fill={pointColor}
                  rx={1.5}
                />
                {estimate.weight != null ? (
                  <text
                    x={svgWidth - plotRight + 8}
                    y={cy}
                    dominantBaseline="central"
                    fontSize={chartDefaults.tickFontSize}
                    fill={chartTheme.neutral}
                  >
                    {(estimate.weight * 100).toFixed(1)}%
                  </text>
                ) : null}
              </g>
            );
          })}

          {pooled ? (
            <>
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
                const pointColor = resolveUncertaintyPaletteColor(
                  pooled.disputed ? "disputed" : "default",
                );
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
                    <polygon
                      points={`${lx},${cy} ${px},${cy - diamondHalf} ${rx},${cy} ${px},${cy + diamondHalf}`}
                      fill={pointColor}
                      opacity={0.85}
                    />
                  </g>
                );
              })()}
            </>
          ) : null}

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
