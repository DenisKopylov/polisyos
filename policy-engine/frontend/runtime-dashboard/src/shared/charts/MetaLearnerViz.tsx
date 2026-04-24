import { useMemo } from "react";

import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/LocaleProvider";
import {
  chartTheme,
  ciColors,
  categoricalPalette,
  chartDefaults,
} from "./theme";
import { ChartDataTable } from "./accessibility";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CATEEstimate = {
  id: string;
  label: string;
  cate: number;
  ci?: { lower: number; upper: number };
};

export type CATEDistributionBin = {
  binStart: number;
  binEnd: number;
  count: number;
};

type MetaLearnerVizProps = {
  estimates: CATEEstimate[];
  distribution?: CATEDistributionBin[];
  ate?: number;
  ateCi?: { lower: number; upper: number };
  learnerType?: string;
  title?: string;
  className?: string;
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SVG_WIDTH = 600;
const SVG_HEIGHT = 340;
const PADDING = { top: 32, right: 24, bottom: 48, left: 120 };
const PLOT_W = SVG_WIDTH - PADDING.left - PADDING.right;
const LOLLIPOP_H = 220;
const HIST_H = 100;
const GAP = 20;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MetaLearnerViz({
  estimates,
  distribution,
  ate,
  ateCi,
  learnerType,
  title,
  className,
}: MetaLearnerVizProps) {
  const { t } = useI18n();
  const showHistogram = distribution && distribution.length > 0;
  const svgHeight = showHistogram
    ? PADDING.top + LOLLIPOP_H + GAP + HIST_H + PADDING.bottom
    : PADDING.top + LOLLIPOP_H + PADDING.bottom;

  // CATE lollipop chart
  const allValues = estimates.flatMap((e) => [
    e.cate,
    ...(e.ci ? [e.ci.lower, e.ci.upper] : []),
  ]);
  if (ate != null) allValues.push(ate);
  if (ateCi) allValues.push(ateCi.lower, ateCi.upper);

  const minVal = Math.min(0, ...allValues);
  const maxVal = Math.max(0, ...allValues);
  const valRange = maxVal - minVal || 1;
  const valPad = valRange * 0.1;

  function toX(v: number) {
    return (
      PADDING.left +
      PLOT_W * ((v - (minVal - valPad)) / (valRange + 2 * valPad))
    );
  }
  const zeroX = toX(0);

  const rowH = Math.min(28, LOLLIPOP_H / Math.max(estimates.length, 1));

  // Histogram Y scale
  const maxCount = distribution
    ? Math.max(...distribution.map((b) => b.count), 1)
    : 1;
  const histTop = PADDING.top + LOLLIPOP_H + GAP;

  function toHistY(count: number) {
    return histTop + HIST_H * (1 - count / maxCount);
  }

  const tableRows = useMemo(
    () =>
      estimates.map((e) => ({
        label: e.label,
        values: {
          CATE: e.cate.toFixed(4),
          ...(e.ci
            ? {
                "CI Lower": e.ci.lower.toFixed(4),
                "CI Upper": e.ci.upper.toFixed(4),
              }
            : {}),
        },
      })),
    [estimates],
  );

  return (
    <figure
      className={cn("border-border bg-card rounded-xl border p-4", className)}
      role="img"
      aria-label={`Meta-Learner CATE estimates: ${estimates.length} subgroups, ATE ${ate?.toFixed(4) ?? "N/A"}`}
    >
      {title && (
        <figcaption className="text-foreground mb-3 flex items-center gap-2 text-sm font-semibold">
          {title}
          {learnerType && (
            <span className="text-muted rounded-md border px-1.5 py-0.5 text-xs font-normal">
              {learnerType}
            </span>
          )}
        </figcaption>
      )}

      <div className="overflow-x-auto">
        <svg width={SVG_WIDTH} height={svgHeight} className="overflow-visible">
          {/* ── Lollipop panel ── */}

          {/* Zero line */}
          <line
            x1={zeroX}
            y1={PADDING.top}
            x2={zeroX}
            y2={PADDING.top + LOLLIPOP_H}
            stroke={chartTheme.neutral}
            strokeDasharray="3 2"
          />

          {/* ATE reference line */}
          {ate != null && (
            <>
              <line
                x1={toX(ate)}
                y1={PADDING.top}
                x2={toX(ate)}
                y2={PADDING.top + LOLLIPOP_H}
                stroke={chartTheme.success}
                strokeWidth={1.5}
                strokeDasharray="6 3"
                opacity={0.7}
              />
              {ateCi && (
                <rect
                  x={toX(ateCi.lower)}
                  y={PADDING.top}
                  width={toX(ateCi.upper) - toX(ateCi.lower)}
                  height={LOLLIPOP_H}
                  fill={chartTheme.success}
                  opacity={0.05}
                />
              )}
              <text
                x={toX(ate)}
                y={PADDING.top - 8}
                textAnchor="middle"
                fontSize={chartDefaults.tickFontSize}
                fontWeight={600}
                fill={chartTheme.success}
              >
                {t("shared.charts.metaLearner.ate", { value: ate.toFixed(3) })}
              </text>
            </>
          )}

          {/* Individual CATE lollipops */}
          {estimates.map((est, i) => {
            const cy = PADDING.top + 12 + i * rowH;
            const color = categoricalPalette[i % categoricalPalette.length];
            return (
              <g key={est.id}>
                {/* Label */}
                <text
                  x={PADDING.left - 8}
                  y={cy}
                  textAnchor="end"
                  dominantBaseline="central"
                  fontSize={chartDefaults.tickFontSize}
                  fill={chartTheme.axis}
                >
                  {est.label.length > 18
                    ? `${est.label.slice(0, 17)}…`
                    : est.label}
                </text>

                {/* CI whisker */}
                {est.ci && (
                  <line
                    x1={toX(est.ci.lower)}
                    y1={cy}
                    x2={toX(est.ci.upper)}
                    y2={cy}
                    stroke={ciColors.boundsStroke}
                    strokeWidth={1.5}
                  />
                )}

                {/* Stem */}
                <line
                  x1={zeroX}
                  y1={cy}
                  x2={toX(est.cate)}
                  y2={cy}
                  stroke={color}
                  strokeWidth={1.5}
                />

                {/* Dot */}
                <circle cx={toX(est.cate)} cy={cy} r={4} fill={color} />
              </g>
            );
          })}

          {/* Lollipop Y axis */}
          <line
            x1={PADDING.left}
            y1={PADDING.top}
            x2={PADDING.left}
            y2={PADDING.top + LOLLIPOP_H}
            stroke={chartTheme.axis}
          />

          {/* ── Histogram panel ── */}
          {showHistogram && distribution && (
            <>
              <text
                x={PADDING.left}
                y={histTop - 6}
                fontSize={chartDefaults.tickFontSize}
                fontWeight={600}
                fill={chartTheme.axis}
              >
                {t("shared.charts.metaLearner.cateDistribution")}
              </text>

              {distribution.map((bin, i) => {
                const bx = toX(bin.binStart);
                const bw = Math.max(toX(bin.binEnd) - bx, 1);
                return (
                  <rect
                    key={i}
                    x={bx}
                    y={toHistY(bin.count)}
                    width={bw}
                    height={histTop + HIST_H - toHistY(bin.count)}
                    fill={chartTheme.primary}
                    opacity={0.35}
                    rx={1}
                  />
                );
              })}

              {/* ATE line on histogram */}
              {ate != null && (
                <line
                  x1={toX(ate)}
                  y1={histTop}
                  x2={toX(ate)}
                  y2={histTop + HIST_H}
                  stroke={chartTheme.success}
                  strokeWidth={1.5}
                  strokeDasharray="4 2"
                />
              )}

              {/* Histogram X axis */}
              <line
                x1={PADDING.left}
                y1={histTop + HIST_H}
                x2={SVG_WIDTH - PADDING.right}
                y2={histTop + HIST_H}
                stroke={chartTheme.axis}
              />

              {/* X label */}
              <text
                x={PADDING.left + PLOT_W / 2}
                y={svgHeight - 6}
                textAnchor="middle"
                fontSize={chartDefaults.tickFontSize}
                fill={chartTheme.axis}
              >
                CATE
              </text>
            </>
          )}
        </svg>
      </div>

      <ChartDataTable
        caption={title ?? "Meta-Learner CATE data"}
        columns={[
          "CATE",
          ...(estimates.some((e) => e.ci) ? ["CI Lower", "CI Upper"] : []),
        ]}
        rows={tableRows}
      />
    </figure>
  );
}
