import { useMemo } from "react";

import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/LocaleProvider";
import { chartTheme, ciColors, chartDefaults } from "./theme";
import { ChartDataTable } from "./accessibility";
import type { SpecificationPoint } from "./types";

type SpecificationCurveChartProps = {
  specifications: SpecificationPoint[];
  title?: string;
  referenceValue?: number;
  height?: number;
  className?: string;
};

export function SpecificationCurveChart({
  specifications,
  title,
  referenceValue = 0,
  height = 360,
  className,
}: SpecificationCurveChartProps) {
  const { t } = useI18n();
  const sorted = useMemo(
    () => [...specifications].sort((a, b) => a.estimate - b.estimate),
    [specifications],
  );

  const allValues = sorted.flatMap((s) => [s.ci.lower, s.ci.upper, s.estimate]);
  const minVal = Math.min(referenceValue, ...allValues);
  const maxVal = Math.max(referenceValue, ...allValues);
  const valRange = maxVal - minVal || 1;
  const valPadding = valRange * 0.1;

  const padding = { top: 20, right: 20, bottom: 12, left: 56 };
  const svgWidth = Math.max(
    sorted.length * 8 + padding.left + padding.right,
    400,
  );
  const plotH = height - padding.top - padding.bottom;
  const plotW = svgWidth - padding.left - padding.right;
  const colW = sorted.length > 0 ? plotW / sorted.length : 1;

  function toY(val: number): number {
    return (
      padding.top +
      plotH * (1 - (val - (minVal - valPadding)) / (valRange + 2 * valPadding))
    );
  }

  const positiveCount = sorted.filter(
    (s) => s.estimate > referenceValue,
  ).length;
  const positivePct = sorted.length
    ? Math.round((positiveCount / sorted.length) * 100)
    : 0;

  const mainSpec = sorted.find((s) => s.isMain);

  const tableRows = useMemo(
    () =>
      sorted.map((s) => ({
        label: s.id,
        values: {
          Estimate: s.estimate.toFixed(4),
          "CI Lower": s.ci.lower.toFixed(4),
          "CI Upper": s.ci.upper.toFixed(4),
          Main: s.isMain ? "Yes" : "",
        },
      })),
    [sorted],
  );

  const ariaDescription = `Specification curve chart${title ? `: ${title}` : ""}. ${sorted.length} specifications, ${positivePct}% positive.${mainSpec ? ` Main specification estimate: ${mainSpec.estimate.toFixed(4)}.` : ""}`;

  return (
    <figure
      className={cn("border-border bg-card rounded-xl border p-4", className)}
      role="img"
      aria-label={ariaDescription}
    >
      {title && (
        <figcaption className="text-foreground mb-2 text-sm font-semibold">
          {title}
        </figcaption>
      )}
      <p className="text-muted-foreground mb-3 text-xs">
        {t("shared.charts.specificationCurve.summary", {
          count: sorted.length,
          positivePct,
        })}
      </p>
      <div className="overflow-x-auto">
        <svg width={svgWidth} height={height} className="overflow-visible">
          {/* Reference line */}
          <line
            x1={padding.left}
            y1={toY(referenceValue)}
            x2={svgWidth - padding.right}
            y2={toY(referenceValue)}
            stroke={chartTheme.neutral}
            strokeDasharray="4 3"
            strokeWidth={1}
          />
          <text
            x={padding.left - 4}
            y={toY(referenceValue)}
            textAnchor="end"
            dominantBaseline="central"
            fontSize={chartDefaults.tickFontSize}
            fill={chartTheme.neutral}
          >
            {referenceValue}
          </text>

          {/* Y axis ticks */}
          {[
            minVal - valPadding,
            (minVal + maxVal) / 2,
            maxVal + valPadding,
          ].map((tick) => (
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

          {/* CI bars + point estimates */}
          {sorted.map((spec, i) => {
            const cx = padding.left + i * colW + colW / 2;
            const isMain = spec.isMain;
            return (
              <g key={spec.id}>
                {/* CI bar */}
                <line
                  x1={cx}
                  y1={toY(spec.ci.lower)}
                  x2={cx}
                  y2={toY(spec.ci.upper)}
                  stroke={isMain ? chartTheme.primary : ciColors.boundsStroke}
                  strokeWidth={isMain ? 2.5 : 1.5}
                />
                {/* Point estimate */}
                <circle
                  cx={cx}
                  cy={toY(spec.estimate)}
                  r={isMain ? 4 : 2.5}
                  fill={
                    isMain
                      ? chartTheme.primary
                      : spec.estimate > referenceValue
                        ? chartTheme.success
                        : chartTheme.alert
                  }
                />
              </g>
            );
          })}
        </svg>
      </div>
      <ChartDataTable
        caption={title ?? "Specification curve data"}
        columns={["Estimate", "CI Lower", "CI Upper", "Main"]}
        rows={tableRows}
      />
    </figure>
  );
}
