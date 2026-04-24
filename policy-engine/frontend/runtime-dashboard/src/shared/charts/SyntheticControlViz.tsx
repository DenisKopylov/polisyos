import { useMemo } from "react";

import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";
import { chartTheme, ciColors, chartDefaults } from "./theme";
import { ChartDataTable } from "./accessibility";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SCTimePoint = {
  time: number | string;
  actual: number;
  synthetic: number;
  ci95Lower?: number;
  ci95Upper?: number;
};

type SyntheticControlVizProps = {
  data: SCTimePoint[];
  treatmentTime: number | string;
  donorWeights?: Array<{ unit: string; weight: number }>;
  estimatedEffect?: number;
  title?: string;
  className?: string;
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SVG_WIDTH = 600;
const SVG_HEIGHT = 320;
const PADDING = { top: 32, right: 24, bottom: 48, left: 56 };
const PLOT_W = SVG_WIDTH - PADDING.left - PADDING.right;
const PLOT_H = SVG_HEIGHT - PADDING.top - PADDING.bottom;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SyntheticControlViz({
  data,
  treatmentTime,
  donorWeights,
  estimatedEffect,
  title,
  className,
}: SyntheticControlVizProps) {
  const { t } = useI18n();
  const topDonors = useMemo(
    () =>
      donorWeights
        ? donorWeights
            .filter((donor) => donor.weight > 0.01)
            .slice()
            .sort((a, b) => b.weight - a.weight)
            .slice(0, 5)
        : undefined,
    [donorWeights],
  );

  if (data.length === 0) {
    return (
      <figure
        className={cn("border-border bg-card rounded-xl border p-4", className)}
        role="img"
        aria-label={t("shared.charts.syntheticControl.emptyAria")}
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
          caption={title ?? t("shared.charts.syntheticControl.caption")}
          columns={[
            t("shared.charts.syntheticControl.actual"),
            t("shared.charts.syntheticControl.synthetic"),
            t("shared.charts.syntheticControl.gap"),
          ]}
          rows={[]}
        />
      </figure>
    );
  }

  const allY = data.flatMap((d) => [
    d.actual,
    d.synthetic,
    ...(d.ci95Lower != null ? [d.ci95Lower] : []),
    ...(d.ci95Upper != null ? [d.ci95Upper] : []),
  ]);
  const minY = Math.min(...allY);
  const maxY = Math.max(...allY);
  const yRange = maxY - minY || 1;
  const yPad = yRange * 0.1;

  const n = data.length;

  function toX(i: number) {
    return PADDING.left + (i / Math.max(n - 1, 1)) * PLOT_W;
  }
  function toY(v: number) {
    return (
      PADDING.top + PLOT_H * (1 - (v - (minY - yPad)) / (yRange + 2 * yPad))
    );
  }

  const treatmentIdx = data.findIndex((d) => d.time === treatmentTime);
  const treatmentX =
    treatmentIdx >= 0 ? toX(treatmentIdx) : PADDING.left + PLOT_W * 0.5;

  const actualPath = data
    .map((d, i) => `${i === 0 ? "M" : "L"}${toX(i)},${toY(d.actual)}`)
    .join(" ");
  const syntheticPath = data
    .map((d, i) => `${i === 0 ? "M" : "L"}${toX(i)},${toY(d.synthetic)}`)
    .join(" ");

  // CI band path
  const ciBand = (() => {
    const hasCI = data.some((d) => d.ci95Lower != null);
    if (!hasCI) return null;
    const upper = data
      .map(
        (d, i) =>
          `${i === 0 ? "M" : "L"}${toX(i)},${toY(d.ci95Upper ?? d.synthetic)}`,
      )
      .join(" ");
    const lower = [...data]
      .reverse()
      .map(
        (d, i) =>
          `${i === 0 ? "L" : "L"}${toX(n - 1 - i)},${toY(d.ci95Lower ?? d.synthetic)}`,
      )
      .join(" ");
    return `${upper} ${lower} Z`;
  })();

  const tableRows = data.map((d) => ({
    label: String(d.time),
    values: {
      Actual: d.actual.toFixed(3),
      Synthetic: d.synthetic.toFixed(3),
      Gap: (d.actual - d.synthetic).toFixed(3),
    },
  }));

  return (
    <figure
      className={cn("border-border bg-card rounded-xl border p-4", className)}
      role="img"
      aria-label={`Synthetic Control: actual vs synthetic control, estimated effect ${estimatedEffect?.toFixed(4) ?? "N/A"}`}
    >
      {title && (
        <figcaption className="text-foreground mb-3 text-sm font-semibold">
          {title}
        </figcaption>
      )}

      <div className="overflow-x-auto">
        <svg width={SVG_WIDTH} height={SVG_HEIGHT} className="overflow-visible">
          {/* CI band */}
          {ciBand && (
            <path d={ciBand} fill={ciColors.boundsFill} opacity={0.2} />
          )}

          {/* Treatment line */}
          <line
            x1={treatmentX}
            y1={PADDING.top}
            x2={treatmentX}
            y2={SVG_HEIGHT - PADDING.bottom}
            stroke={chartTheme.warning}
            strokeDasharray="6 4"
            opacity={0.6}
          />
          <text
            x={treatmentX}
            y={PADDING.top - 8}
            textAnchor="middle"
            fontSize={chartDefaults.tickFontSize}
            fill={chartTheme.warning}
          >
            {t("shared.charts.syntheticControl.treatment")}
          </text>

          {/* Synthetic path */}
          <path
            d={syntheticPath}
            fill="none"
            stroke={chartTheme.neutral}
            strokeWidth={2}
            strokeDasharray="5 3"
          />

          {/* Actual path */}
          <path
            d={actualPath}
            fill="none"
            stroke={chartTheme.primary}
            strokeWidth={2}
          />

          {/* Gap shading (post-treatment) */}
          {treatmentIdx >= 0 && (
            <path
              d={[
                ...data
                  .slice(treatmentIdx)
                  .map(
                    (d, i) =>
                      `${i === 0 ? "M" : "L"}${toX(treatmentIdx + i)},${toY(d.actual)}`,
                  ),
                ...data
                  .slice(treatmentIdx)
                  .reverse()
                  .map((d, i) => `L${toX(n - 1 - i)},${toY(d.synthetic)}`),
                "Z",
              ].join(" ")}
              fill={chartTheme.primary}
              opacity={0.08}
            />
          )}

          {/* Axes */}
          <line
            x1={PADDING.left}
            y1={PADDING.top}
            x2={PADDING.left}
            y2={SVG_HEIGHT - PADDING.bottom}
            stroke={chartTheme.axis}
          />
          <line
            x1={PADDING.left}
            y1={SVG_HEIGHT - PADDING.bottom}
            x2={SVG_WIDTH - PADDING.right}
            y2={SVG_HEIGHT - PADDING.bottom}
            stroke={chartTheme.axis}
          />

          {/* X tick labels (first, treatment, last) */}
          {[0, treatmentIdx >= 0 ? treatmentIdx : Math.floor(n / 2), n - 1]
            .filter((v, i, a) => a.indexOf(v) === i && v >= 0)
            .map((idx) => (
              <text
                key={idx}
                x={toX(idx)}
                y={SVG_HEIGHT - PADDING.bottom + 18}
                textAnchor="middle"
                fontSize={chartDefaults.tickFontSize}
                fill={chartTheme.axis}
              >
                {String(data[idx]?.time ?? "")}
              </text>
            ))}

          {/* Effect annotation */}
          {estimatedEffect != null && (
            <text
              x={SVG_WIDTH - PADDING.right}
              y={PADDING.top + 16}
              textAnchor="end"
              fontSize={chartDefaults.labelFontSize}
              fontWeight={700}
              fill={chartTheme.success}
            >
              {t("shared.charts.syntheticControl.effect")}{" "}
              {estimatedEffect >= 0 ? "+" : ""}
              {estimatedEffect.toFixed(3)}
            </text>
          )}

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
              {t("shared.charts.syntheticControl.actual")}
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
              {t("shared.charts.syntheticControl.synthetic")}
            </text>
          </g>
        </svg>
      </div>

      {/* Donor weights */}
      {topDonors && topDonors.length > 0 && (
        <div className="mt-3 space-y-1">
          <p className="text-muted text-xs font-semibold">
            {t("shared.charts.syntheticControl.topDonorWeights")}
          </p>
          <div className="flex flex-wrap gap-2">
            {topDonors.map((d) => (
              <span
                key={d.unit}
                className="border-line text-foreground rounded-md border px-2 py-0.5 text-xs"
              >
                {d.unit}: {(d.weight * 100).toFixed(1)}%
              </span>
            ))}
          </div>
        </div>
      )}

      <ChartDataTable
        caption={title ?? t("shared.charts.syntheticControl.caption")}
        columns={[
          t("shared.charts.syntheticControl.actual"),
          t("shared.charts.syntheticControl.synthetic"),
          t("shared.charts.syntheticControl.gap"),
        ]}
        rows={tableRows}
      />
    </figure>
  );
}
