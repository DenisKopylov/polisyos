import { useMemo } from "react";

import { cn } from "@/shared/lib/utils";
import { Card } from "@polisyos/atlas-ui";
import { chartTheme, chartDefaults } from "@/shared/charts/theme";
import { ChartDataTable } from "@/shared/charts/accessibility";

export type ImportanceFactor = {
  label: string;
  importance: number;
  direction: "positive" | "negative" | "neutral";
  detail?: string;
};

type FactorChartGeometry = {
  numericColumnWidth: number;
};

const FACTOR_CHART_GEOMETRY = {
  numericColumnWidth: 60,
} as const satisfies FactorChartGeometry;

type FactorImportanceChartProps = {
  factors: ImportanceFactor[];
  title?: string;
  maxBars?: number;
  height?: number;
  className?: string;
};

export function FactorImportanceChart({
  factors,
  title = "Factor Importance",
  maxBars = 12,
  height: heightOverride,
  className,
}: FactorImportanceChartProps) {
  const sorted = useMemo(
    () =>
      [...factors]
        .sort((a, b) => Math.abs(b.importance) - Math.abs(a.importance))
        .slice(0, maxBars),
    [factors, maxBars],
  );

  const maxVal = Math.max(...sorted.map((f) => Math.abs(f.importance)), 0.01);

  const barHeight = 28;
  const gap = 6;
  const labelWidth = 120;
  const padding = { top: 8, right: 16, bottom: 8, left: 8 };
  const svgWidth = 480;
  const barAreaWidth =
    svgWidth -
    padding.left -
    padding.right -
    labelWidth -
    FACTOR_CHART_GEOMETRY.numericColumnWidth;

  const computedHeight =
    heightOverride ??
    padding.top + padding.bottom + sorted.length * (barHeight + gap) - gap;

  function barColor(dir: ImportanceFactor["direction"]): string {
    switch (dir) {
      case "positive":
        return chartTheme.success;
      case "negative":
        return chartTheme.alert;
      default:
        return chartTheme.neutral;
    }
  }

  function dirArrow(dir: ImportanceFactor["direction"]): string {
    switch (dir) {
      case "positive":
        return "\u2191";
      case "negative":
        return "\u2193";
      default:
        return "\u2022";
    }
  }

  const tableRows = useMemo(
    () =>
      sorted.map((f) => ({
        label: f.label,
        values: {
          Importance: Math.abs(f.importance).toFixed(4),
          Direction: f.direction,
        },
      })),
    [sorted],
  );

  return (
    <Card className={cn("space-y-3", className)}>
      <h3 className="text-lg font-semibold">{title}</h3>

      <div className="overflow-x-auto">
        <svg
          width={svgWidth}
          height={computedHeight}
          className="overflow-visible"
          role="img"
          aria-label={`${title}: ${sorted.length} factors sorted by importance`}
        >
          {sorted.map((f, i) => {
            const y = padding.top + i * (barHeight + gap);
            const barW = (Math.abs(f.importance) / maxVal) * barAreaWidth;
            const barX = padding.left + labelWidth;

            return (
              <g key={f.label}>
                {/* Label */}
                <text
                  x={padding.left + labelWidth - 8}
                  y={y + barHeight / 2}
                  textAnchor="end"
                  dominantBaseline="central"
                  fontSize={chartDefaults.tickFontSize}
                  fill={chartTheme.axis}
                  className="select-none"
                >
                  {f.label.length > 16
                    ? `${f.label.slice(0, 15)}\u2026`
                    : f.label}
                </text>

                {/* Bar */}
                <rect
                  x={barX}
                  y={y + 2}
                  width={Math.max(barW, 2)}
                  height={barHeight - 4}
                  rx={4}
                  fill={barColor(f.direction)}
                  opacity={0.85}
                />

                {/* Value + direction arrow */}
                <text
                  x={barX + barW + 6}
                  y={y + barHeight / 2}
                  dominantBaseline="central"
                  fontSize={chartDefaults.tickFontSize}
                  fill={barColor(f.direction)}
                  fontWeight={600}
                >
                  {dirArrow(f.direction)} {Math.abs(f.importance).toFixed(3)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <ChartDataTable
        caption={title}
        columns={["Importance", "Direction"]}
        rows={tableRows}
      />
    </Card>
  );
}
