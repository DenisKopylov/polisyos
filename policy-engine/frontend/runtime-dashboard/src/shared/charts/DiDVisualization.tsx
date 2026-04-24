import { useMemo } from "react";

import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/LocaleProvider";
import { chartTheme, ciColors, chartDefaults } from "./theme";
import { ChartDataTable } from "./accessibility";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type DiDGroup = {
  id: string;
  label: string;
  preTreatment: number;
  postTreatment: number;
  ci?: { lower: number; upper: number };
};

type DiDVisualizationProps = {
  treated: DiDGroup;
  control: DiDGroup;
  treatmentTime: string;
  estimatedEffect?: number;
  effectCi?: { lower: number; upper: number };
  title?: string;
  className?: string;
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SVG_WIDTH = 560;
const SVG_HEIGHT = 320;
const PADDING = { top: 36, right: 24, bottom: 48, left: 64 };
const PLOT_W = SVG_WIDTH - PADDING.left - PADDING.right;
const PLOT_H = SVG_HEIGHT - PADDING.top - PADDING.bottom;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DiDVisualization({
  treated,
  control,
  treatmentTime,
  estimatedEffect,
  effectCi,
  title,
  className,
}: DiDVisualizationProps) {
  const { t } = useI18n();
  const allValues = [
    treated.preTreatment,
    treated.postTreatment,
    control.preTreatment,
    control.postTreatment,
    ...(treated.ci ? [treated.ci.lower, treated.ci.upper] : []),
    ...(control.ci ? [control.ci.lower, control.ci.upper] : []),
  ];
  const minY = Math.min(...allValues);
  const maxY = Math.max(...allValues);
  const yRange = maxY - minY || 1;
  const yPad = yRange * 0.15;

  function toY(v: number) {
    return (
      PADDING.top + PLOT_H * (1 - (v - (minY - yPad)) / (yRange + 2 * yPad))
    );
  }

  const xPre = PADDING.left + PLOT_W * 0.25;
  const xPost = PADDING.left + PLOT_W * 0.75;
  const xTreatment = PADDING.left + PLOT_W * 0.5;

  // Counterfactual: treated group's pre-treatment slope applied post
  const controlSlope = control.postTreatment - control.preTreatment;
  const counterfactual = treated.preTreatment + controlSlope;

  const tableRows = useMemo(
    () => [
      {
        label: `${treated.label} (pre)`,
        values: { Value: treated.preTreatment.toFixed(3) },
      },
      {
        label: `${treated.label} (post)`,
        values: { Value: treated.postTreatment.toFixed(3) },
      },
      {
        label: `${control.label} (pre)`,
        values: { Value: control.preTreatment.toFixed(3) },
      },
      {
        label: `${control.label} (post)`,
        values: { Value: control.postTreatment.toFixed(3) },
      },
      ...(estimatedEffect != null
        ? [
            {
              label: "DiD Estimate",
              values: {
                Value: estimatedEffect.toFixed(4),
                ...(effectCi
                  ? {
                      "CI Lower": effectCi.lower.toFixed(4),
                      "CI Upper": effectCi.upper.toFixed(4),
                    }
                  : {}),
              },
            },
          ]
        : []),
    ],
    [treated, control, estimatedEffect, effectCi],
  );

  return (
    <figure
      className={cn("border-border bg-card rounded-xl border p-4", className)}
      role="img"
      aria-label={`Difference-in-Differences: estimated effect ${estimatedEffect?.toFixed(4) ?? "N/A"}`}
    >
      {title && (
        <figcaption className="text-foreground mb-3 text-sm font-semibold">
          {title}
        </figcaption>
      )}

      <div className="overflow-x-auto">
        <svg width={SVG_WIDTH} height={SVG_HEIGHT} className="overflow-visible">
          {/* Treatment time vertical line */}
          <line
            x1={xTreatment}
            y1={PADDING.top}
            x2={xTreatment}
            y2={SVG_HEIGHT - PADDING.bottom}
            stroke={chartTheme.neutral}
            strokeDasharray="6 4"
            opacity={0.5}
          />
          <text
            x={xTreatment}
            y={PADDING.top - 10}
            textAnchor="middle"
            fontSize={chartDefaults.tickFontSize}
            fill={chartTheme.neutral}
          >
            {treatmentTime}
          </text>

          {/* Control group line */}
          <line
            x1={xPre}
            y1={toY(control.preTreatment)}
            x2={xPost}
            y2={toY(control.postTreatment)}
            stroke={chartTheme.neutral}
            strokeWidth={2}
          />

          {/* Treated group line */}
          <line
            x1={xPre}
            y1={toY(treated.preTreatment)}
            x2={xPost}
            y2={toY(treated.postTreatment)}
            stroke={chartTheme.primary}
            strokeWidth={2}
          />

          {/* Counterfactual (dashed) */}
          <line
            x1={xTreatment}
            y1={toY(treated.preTreatment + controlSlope * 0.5)}
            x2={xPost}
            y2={toY(counterfactual)}
            stroke={chartTheme.primary}
            strokeWidth={1.5}
            strokeDasharray="4 3"
            opacity={0.5}
          />

          {/* Effect bracket */}
          {estimatedEffect != null && (
            <g>
              <line
                x1={xPost + 12}
                y1={toY(counterfactual)}
                x2={xPost + 12}
                y2={toY(treated.postTreatment)}
                stroke={chartTheme.success}
                strokeWidth={2}
                markerEnd="url(#did-arrow)"
                markerStart="url(#did-arrow)"
              />
              <text
                x={xPost + 20}
                y={(toY(counterfactual) + toY(treated.postTreatment)) / 2}
                dominantBaseline="central"
                fontSize={chartDefaults.labelFontSize}
                fontWeight={700}
                fill={chartTheme.success}
              >
                {estimatedEffect >= 0 ? "+" : ""}
                {estimatedEffect.toFixed(3)}
              </text>
              <defs>
                <marker
                  id="did-arrow"
                  viewBox="0 0 6 6"
                  refX="3"
                  refY="3"
                  markerWidth="6"
                  markerHeight="6"
                >
                  <circle cx="3" cy="3" r="2" fill={chartTheme.success} />
                </marker>
              </defs>
            </g>
          )}

          {/* CI bands */}
          {treated.ci && (
            <rect
              x={xPost - 6}
              y={toY(treated.ci.upper)}
              width={12}
              height={toY(treated.ci.lower) - toY(treated.ci.upper)}
              fill={ciColors.boundsFill}
              opacity={0.3}
              rx={2}
            />
          )}

          {/* Dots */}
          <circle
            cx={xPre}
            cy={toY(treated.preTreatment)}
            r={4}
            fill={chartTheme.primary}
          />
          <circle
            cx={xPost}
            cy={toY(treated.postTreatment)}
            r={4}
            fill={chartTheme.primary}
          />
          <circle
            cx={xPre}
            cy={toY(control.preTreatment)}
            r={4}
            fill={chartTheme.neutral}
          />
          <circle
            cx={xPost}
            cy={toY(control.postTreatment)}
            r={4}
            fill={chartTheme.neutral}
          />
          <circle
            cx={xPost}
            cy={toY(counterfactual)}
            r={3}
            fill={chartTheme.primary}
            opacity={0.4}
          />

          {/* X axis labels */}
          <text
            x={xPre}
            y={SVG_HEIGHT - PADDING.bottom + 20}
            textAnchor="middle"
            fontSize={chartDefaults.tickFontSize}
            fill={chartTheme.axis}
          >
            {t("shared.charts.did.preTreatment")}
          </text>
          <text
            x={xPost}
            y={SVG_HEIGHT - PADDING.bottom + 20}
            textAnchor="middle"
            fontSize={chartDefaults.tickFontSize}
            fill={chartTheme.axis}
          >
            {t("shared.charts.did.postTreatment")}
          </text>

          {/* Y axis */}
          <line
            x1={PADDING.left}
            y1={PADDING.top}
            x2={PADDING.left}
            y2={SVG_HEIGHT - PADDING.bottom}
            stroke={chartTheme.axis}
          />

          {/* Legend */}
          <g transform={`translate(${PADDING.left}, ${SVG_HEIGHT - 8})`}>
            <rect width={10} height={3} fill={chartTheme.primary} y={-2} />
            <text
              x={14}
              fontSize={chartDefaults.tickFontSize}
              fill={chartTheme.axis}
            >
              {treated.label}
            </text>
            <rect
              x={120}
              width={10}
              height={3}
              fill={chartTheme.neutral}
              y={-2}
            />
            <text
              x={134}
              fontSize={chartDefaults.tickFontSize}
              fill={chartTheme.axis}
            >
              {control.label}
            </text>
            <rect
              x={240}
              width={10}
              height={3}
              fill={chartTheme.primary}
              opacity={0.4}
              y={-2}
              strokeDasharray="3 2"
            />
            <text
              x={254}
              fontSize={chartDefaults.tickFontSize}
              fill={chartTheme.axis}
            >
              {t("shared.charts.did.counterfactual")}
            </text>
          </g>
        </svg>
      </div>

      <ChartDataTable
        caption={title ?? "Difference-in-Differences data"}
        columns={["Value", ...(effectCi ? ["CI Lower", "CI Upper"] : [])]}
        rows={tableRows}
      />
    </figure>
  );
}
