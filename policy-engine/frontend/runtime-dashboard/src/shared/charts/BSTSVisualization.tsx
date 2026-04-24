import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";
import { chartTheme, ciColors, chartDefaults } from "./theme";
import { ChartDataTable } from "./accessibility";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type BSTSTimePoint = {
  time: number | string;
  actual: number;
  predicted: number;
  ci95Lower?: number;
  ci95Upper?: number;
  ci80Lower?: number;
  ci80Upper?: number;
};

type BSTSVisualizationProps = {
  data: BSTSTimePoint[];
  interventionTime: number | string;
  cumulativeEffect?: number;
  cumulativeCi?: { lower: number; upper: number };
  pointwiseEffect?: number;
  pValue?: number;
  title?: string;
  className?: string;
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SVG_WIDTH = 600;
const SVG_HEIGHT = 360;
const PADDING = { top: 32, right: 24, bottom: 48, left: 56 };
const PLOT_W = SVG_WIDTH - PADDING.left - PADDING.right;
const MAIN_H = 200;
const GAP_H = 24;
const DIFF_H = 80;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BSTSVisualization({
  data,
  interventionTime,
  cumulativeEffect,
  cumulativeCi,
  pointwiseEffect,
  pValue,
  title,
  className,
}: BSTSVisualizationProps) {
  const { t } = useI18n();
  const n = data.length;

  if (n === 0) {
    return (
      <figure
        className={cn("border-border bg-card rounded-xl border p-4", className)}
        role="img"
        aria-label={t("shared.charts.bsts.emptyAria")}
      >
        {title && (
          <figcaption className="text-foreground mb-3 text-sm font-semibold">
            {title}
          </figcaption>
        )}
        <div className="text-muted flex min-h-40 items-center justify-center rounded-lg border border-dashed text-sm">
          {t("shared.charts.common.noDataAvailable")}
        </div>
        <ChartDataTable
          caption={title ?? t("shared.charts.bsts.caption")}
          columns={[
            t("shared.charts.bsts.actual"),
            t("shared.charts.bsts.predicted"),
            t("shared.charts.bsts.difference"),
          ]}
          rows={[]}
        />
      </figure>
    );
  }

  // Y domain for main panel
  const allMainY = data.flatMap((d) => [
    d.actual,
    d.predicted,
    ...(d.ci95Lower != null ? [d.ci95Lower] : []),
    ...(d.ci95Upper != null ? [d.ci95Upper] : []),
  ]);
  const minMainY = Math.min(...allMainY);
  const maxMainY = Math.max(...allMainY);
  const mainRange = maxMainY - minMainY || 1;
  const mainPad = mainRange * 0.1;

  // Differences for bottom panel
  const diffs = data.map((d) => d.actual - d.predicted);
  const minDiff = Math.min(0, ...diffs);
  const maxDiff = Math.max(0, ...diffs);
  const diffRange = maxDiff - minDiff || 1;
  const diffPad = diffRange * 0.15;

  function toX(i: number) {
    return PADDING.left + (i / Math.max(n - 1, 1)) * PLOT_W;
  }
  function toMainY(v: number) {
    return (
      PADDING.top +
      MAIN_H * (1 - (v - (minMainY - mainPad)) / (mainRange + 2 * mainPad))
    );
  }
  function toDiffY(v: number) {
    const top = PADDING.top + MAIN_H + GAP_H;
    return (
      top + DIFF_H * (1 - (v - (minDiff - diffPad)) / (diffRange + 2 * diffPad))
    );
  }

  const interventionIdx = data.findIndex((d) => d.time === interventionTime);
  const interventionX =
    interventionIdx >= 0 ? toX(interventionIdx) : PADDING.left + PLOT_W * 0.5;

  const svgHeight = PADDING.top + MAIN_H + GAP_H + DIFF_H + PADDING.bottom;

  // Paths
  const actualPath = data
    .map((d, i) => `${i === 0 ? "M" : "L"}${toX(i)},${toMainY(d.actual)}`)
    .join(" ");
  const predictedPath = data
    .map((d, i) => `${i === 0 ? "M" : "L"}${toX(i)},${toMainY(d.predicted)}`)
    .join(" ");

  const ci95Band = (() => {
    if (!data.some((d) => d.ci95Lower != null)) return null;
    const upper = data
      .map(
        (d, i) =>
          `${i === 0 ? "M" : "L"}${toX(i)},${toMainY(d.ci95Upper ?? d.predicted)}`,
      )
      .join(" ");
    const lower = [...data]
      .reverse()
      .map(
        (d, i) => `L${toX(n - 1 - i)},${toMainY(d.ci95Lower ?? d.predicted)}`,
      )
      .join(" ");
    return `${upper} ${lower} Z`;
  })();

  const ci80Band = (() => {
    if (!data.some((d) => d.ci80Lower != null)) return null;
    const upper = data
      .map(
        (d, i) =>
          `${i === 0 ? "M" : "L"}${toX(i)},${toMainY(d.ci80Upper ?? d.predicted)}`,
      )
      .join(" ");
    const lower = [...data]
      .reverse()
      .map(
        (d, i) => `L${toX(n - 1 - i)},${toMainY(d.ci80Lower ?? d.predicted)}`,
      )
      .join(" ");
    return `${upper} ${lower} Z`;
  })();

  // Diff bars
  const diffZeroY = toDiffY(0);

  const tableRows = data.map((d) => ({
    label: String(d.time),
    values: {
      Actual: d.actual.toFixed(3),
      Predicted: d.predicted.toFixed(3),
      Difference: (d.actual - d.predicted).toFixed(3),
    },
  }));

  return (
    <figure
      className={cn("border-border bg-card rounded-xl border p-4", className)}
      role="img"
      aria-label={`Bayesian Structural Time Series: cumulative effect ${cumulativeEffect?.toFixed(4) ?? "N/A"}, p-value ${pValue?.toFixed(4) ?? "N/A"}`}
    >
      {title && (
        <figcaption className="text-foreground mb-3 text-sm font-semibold">
          {title}
        </figcaption>
      )}

      <div className="overflow-x-auto">
        <svg width={SVG_WIDTH} height={svgHeight} className="overflow-visible">
          {/* ── Main panel ── */}

          {/* CI bands */}
          {ci95Band && (
            <path d={ci95Band} fill={ciColors.ci95} opacity={0.15} />
          )}
          {ci80Band && <path d={ci80Band} fill={ciColors.ci80} opacity={0.2} />}

          {/* Intervention line (spans both panels) */}
          <line
            x1={interventionX}
            y1={PADDING.top}
            x2={interventionX}
            y2={svgHeight - PADDING.bottom}
            stroke={chartTheme.warning}
            strokeDasharray="6 4"
            opacity={0.6}
          />
          <text
            x={interventionX}
            y={PADDING.top - 8}
            textAnchor="middle"
            fontSize={chartDefaults.tickFontSize}
            fill={chartTheme.warning}
          >
            {t("shared.charts.bsts.intervention")}
          </text>

          {/* Predicted line */}
          <path
            d={predictedPath}
            fill="none"
            stroke={chartTheme.neutral}
            strokeWidth={2}
            strokeDasharray="5 3"
          />

          {/* Actual line */}
          <path
            d={actualPath}
            fill="none"
            stroke={chartTheme.primary}
            strokeWidth={2}
          />

          {/* Main Y axis */}
          <line
            x1={PADDING.left}
            y1={PADDING.top}
            x2={PADDING.left}
            y2={PADDING.top + MAIN_H}
            stroke={chartTheme.axis}
          />

          {/* ── Difference panel ── */}
          {data.map((d, i) => {
            const diff = d.actual - d.predicted;
            const barY = diff >= 0 ? toDiffY(diff) : diffZeroY;
            const barH = Math.abs(toDiffY(diff) - diffZeroY);
            const barW = Math.max(PLOT_W / n - 1, 1);
            return (
              <rect
                key={i}
                x={toX(i) - barW / 2}
                y={barY}
                width={barW}
                height={barH}
                fill={
                  i < interventionIdx
                    ? chartTheme.neutral
                    : diff >= 0
                      ? chartTheme.success
                      : chartTheme.alert
                }
                opacity={0.6}
                rx={0.5}
              />
            );
          })}

          {/* Zero line in diff panel */}
          <line
            x1={PADDING.left}
            y1={diffZeroY}
            x2={SVG_WIDTH - PADDING.right}
            y2={diffZeroY}
            stroke={chartTheme.axis}
            strokeDasharray="3 2"
          />

          {/* Diff Y axis */}
          <line
            x1={PADDING.left}
            y1={PADDING.top + MAIN_H + GAP_H}
            x2={PADDING.left}
            y2={PADDING.top + MAIN_H + GAP_H + DIFF_H}
            stroke={chartTheme.axis}
          />

          {/* X axis */}
          <line
            x1={PADDING.left}
            y1={svgHeight - PADDING.bottom}
            x2={SVG_WIDTH - PADDING.right}
            y2={svgHeight - PADDING.bottom}
            stroke={chartTheme.axis}
          />

          {/* Labels */}
          <text
            x={PADDING.left - 4}
            y={PADDING.top + MAIN_H / 2}
            textAnchor="end"
            dominantBaseline="central"
            fontSize={9}
            fill={chartTheme.neutral}
            transform={`rotate(-90, ${PADDING.left - 16}, ${PADDING.top + MAIN_H / 2})`}
          >
            {t("shared.charts.bsts.outcome")}
          </text>
          <text
            x={PADDING.left - 4}
            y={PADDING.top + MAIN_H + GAP_H + DIFF_H / 2}
            textAnchor="end"
            dominantBaseline="central"
            fontSize={9}
            fill={chartTheme.neutral}
            transform={`rotate(-90, ${PADDING.left - 16}, ${PADDING.top + MAIN_H + GAP_H + DIFF_H / 2})`}
          >
            {t("shared.charts.bsts.difference")}
          </text>

          {/* Summary stats */}
          <g
            transform={`translate(${SVG_WIDTH - PADDING.right - 8}, ${PADDING.top + 16})`}
            textAnchor="end"
          >
            {cumulativeEffect != null && (
              <text
                fontSize={chartDefaults.tickFontSize}
                fontWeight={700}
                fill={chartTheme.success}
              >
                {t("shared.charts.bsts.cumulative")}{" "}
                {cumulativeEffect >= 0 ? "+" : ""}
                {cumulativeEffect.toFixed(3)}
              </text>
            )}
            {pValue != null && (
              <text
                y={16}
                fontSize={chartDefaults.tickFontSize}
                fill={pValue < 0.05 ? chartTheme.success : chartTheme.neutral}
              >
                {t("shared.charts.bsts.pValue")} {pValue.toFixed(4)}
              </text>
            )}
          </g>

          {/* Legend */}
          <g transform={`translate(${PADDING.left + 8}, ${PADDING.top + 8})`}>
            <line
              x1={0}
              y1={0}
              x2={16}
              y2={0}
              stroke={chartTheme.primary}
              strokeWidth={2}
            />
            <text
              x={20}
              y={4}
              fontSize={chartDefaults.tickFontSize}
              fill={chartTheme.axis}
            >
              {t("shared.charts.bsts.actual")}
            </text>
            <line
              x1={80}
              y1={0}
              x2={96}
              y2={0}
              stroke={chartTheme.neutral}
              strokeWidth={2}
              strokeDasharray="5 3"
            />
            <text
              x={100}
              y={4}
              fontSize={chartDefaults.tickFontSize}
              fill={chartTheme.axis}
            >
              {t("shared.charts.bsts.predicted")}
            </text>
          </g>
        </svg>
      </div>

      <ChartDataTable
        caption={title ?? t("shared.charts.bsts.caption")}
        columns={[
          t("shared.charts.bsts.actual"),
          t("shared.charts.bsts.predicted"),
          t("shared.charts.bsts.difference"),
        ]}
        rows={tableRows}
      />
    </figure>
  );
}
