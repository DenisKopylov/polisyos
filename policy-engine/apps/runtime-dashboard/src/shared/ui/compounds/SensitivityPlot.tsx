import { useMemo } from "react";

import { cn } from "@/shared/lib/utils";
import { Card } from "@polisyos/atlas-ui";
import { chartTheme, chartDefaults } from "@/shared/charts/theme";
import { ChartDataTable } from "@/shared/charts/accessibility";

export type SensitivityPoint = {
  gamma: number;
  upperBound: number;
  lowerBound: number;
};

type SensitivityPlotProps = {
  points: SensitivityPoint[];
  breakdownGamma?: number;
  referenceValue?: number;
  title?: string;
  height?: number;
  className?: string;
};

export function SensitivityPlot({
  points,
  breakdownGamma,
  referenceValue = 0,
  title = "Sensitivity Analysis (Rosenbaum Bounds)",
  height = 280,
  className,
}: SensitivityPlotProps) {
  const sorted = useMemo(
    () => [...points].sort((a, b) => a.gamma - b.gamma),
    [points],
  );

  const allValues = sorted.flatMap((p) => [p.lowerBound, p.upperBound]);
  const minY = Math.min(referenceValue, ...allValues);
  const maxY = Math.max(referenceValue, ...allValues);
  const yRange = maxY - minY || 1;
  const yPad = yRange * 0.12;

  const minX = sorted[0]?.gamma ?? 1;
  const maxX = sorted.at(-1)?.gamma ?? 2;
  const xRange = maxX - minX || 1;
  const xPad = xRange * 0.05;

  const padding = { top: 20, right: 20, bottom: 36, left: 56 };
  const svgWidth = 480;
  const plotW = svgWidth - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  function toX(gamma: number): number {
    return (
      padding.left + plotW * ((gamma - (minX - xPad)) / (xRange + 2 * xPad))
    );
  }

  function toY(val: number): number {
    return (
      padding.top + plotH * (1 - (val - (minY - yPad)) / (yRange + 2 * yPad))
    );
  }

  const upperPath = sorted
    .map((p, i) => `${i === 0 ? "M" : "L"}${toX(p.gamma)},${toY(p.upperBound)}`)
    .join(" ");
  const lowerPath = sorted
    .map((p, i) => `${i === 0 ? "M" : "L"}${toX(p.gamma)},${toY(p.lowerBound)}`)
    .join(" ");
  const fillPath = `${upperPath} ${[...sorted]
    .reverse()
    .map((p, i) => `${i === 0 ? "L" : "L"}${toX(p.gamma)},${toY(p.lowerBound)}`)
    .join(" ")} Z`;

  const robustLabel = breakdownGamma
    ? `Robust up to \u0393=${breakdownGamma.toFixed(1)}`
    : null;

  const tableRows = useMemo(
    () =>
      sorted.map((p) => ({
        label: `\u0393=${p.gamma.toFixed(1)}`,
        values: {
          Upper: p.upperBound.toFixed(4),
          Lower: p.lowerBound.toFixed(4),
        },
      })),
    [sorted],
  );

  return (
    <Card className={cn("space-y-3", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">{title}</h3>
        {robustLabel && (
          <span className="text-xs font-semibold text-[var(--color-status-approved)]">
            {robustLabel}
          </span>
        )}
      </div>

      <div className="overflow-x-auto">
        <svg width={svgWidth} height={height} className="overflow-visible">
          {/* Fill band */}
          <path d={fillPath} fill="var(--color-ci-80)" />

          {/* Reference line */}
          <line
            x1={padding.left}
            y1={toY(referenceValue)}
            x2={svgWidth - padding.right}
            y2={toY(referenceValue)}
            stroke={chartTheme.neutral}
            strokeDasharray="4 3"
          />

          {/* Upper bound line */}
          <path
            d={upperPath}
            fill="none"
            stroke={chartTheme.alert}
            strokeWidth={2}
          />

          {/* Lower bound line */}
          <path
            d={lowerPath}
            fill="none"
            stroke={chartTheme.primary}
            strokeWidth={2}
          />

          {/* Breakdown gamma vertical */}
          {breakdownGamma != null && (
            <line
              x1={toX(breakdownGamma)}
              y1={padding.top}
              x2={toX(breakdownGamma)}
              y2={padding.top + plotH}
              stroke={chartTheme.warning}
              strokeDasharray="4 2"
              strokeWidth={1.5}
            />
          )}

          {/* X axis */}
          <line
            x1={padding.left}
            y1={padding.top + plotH}
            x2={svgWidth - padding.right}
            y2={padding.top + plotH}
            stroke={chartTheme.axis}
          />
          {sorted
            .filter(
              (_, i) =>
                i % Math.ceil(sorted.length / 6) === 0 ||
                i === sorted.length - 1,
            )
            .map((p) => (
              <text
                key={p.gamma}
                x={toX(p.gamma)}
                y={height - 6}
                textAnchor="middle"
                fontSize={chartDefaults.tickFontSize}
                fill={chartTheme.axis}
              >
                {p.gamma.toFixed(1)}
              </text>
            ))}
          <text
            x={padding.left + plotW / 2}
            y={height}
            textAnchor="middle"
            fontSize={chartDefaults.tickFontSize}
            fill={chartTheme.neutral}
          >
            {"\u0393 (sensitivity parameter)"}
          </text>

          {/* Y axis ticks */}
          {[minY, (minY + maxY) / 2, maxY].map((tick) => (
            <text
              key={tick}
              x={padding.left - 4}
              y={toY(tick)}
              textAnchor="end"
              dominantBaseline="central"
              fontSize={chartDefaults.tickFontSize}
              fill={chartTheme.axis}
            >
              {tick.toFixed(2)}
            </text>
          ))}
        </svg>
      </div>

      <ChartDataTable
        caption={title}
        columns={["Upper", "Lower"]}
        rows={tableRows}
      />
    </Card>
  );
}
