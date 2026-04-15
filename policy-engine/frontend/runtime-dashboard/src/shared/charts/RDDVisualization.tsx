import { useMemo } from "react";

import { cn } from "@/lib/utils";
import { chartTheme, ciColors, chartDefaults } from "./theme";
import { ChartDataTable } from "./accessibility";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RDDDataPoint = {
  x: number;
  y: number;
};

type RDDVisualizationProps = {
  dataBelow: RDDDataPoint[];
  dataAbove: RDDDataPoint[];
  cutoff: number;
  fittedBelow?: Array<{ x: number; y: number }>;
  fittedAbove?: Array<{ x: number; y: number }>;
  bandwidth?: number;
  estimatedEffect?: number;
  effectCi?: { lower: number; upper: number };
  title?: string;
  className?: string;
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SVG_WIDTH = 600;
const SVG_HEIGHT = 340;
const PADDING = { top: 32, right: 24, bottom: 48, left: 56 };
const PLOT_W = SVG_WIDTH - PADDING.left - PADDING.right;
const PLOT_H = SVG_HEIGHT - PADDING.top - PADDING.bottom;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RDDVisualization({
  dataBelow,
  dataAbove,
  cutoff,
  fittedBelow,
  fittedAbove,
  bandwidth,
  estimatedEffect,
  effectCi,
  title,
  className,
}: RDDVisualizationProps) {
  const allX = [...dataBelow, ...dataAbove].map((d) => d.x);
  const allY = [...dataBelow, ...dataAbove].map((d) => d.y);

  const sortedFittedBelow = useMemo(
    () => fittedBelow ? [...fittedBelow].sort((a, b) => a.x - b.x) : undefined,
    [fittedBelow],
  );
  const sortedFittedAbove = useMemo(
    () => fittedAbove ? [...fittedAbove].sort((a, b) => a.x - b.x) : undefined,
    [fittedAbove],
  );

  if (allX.length === 0 || allY.length === 0) {
    return (
      <figure
        className={cn("border-border bg-card rounded-xl border p-4", className)}
        role="img"
        aria-label="Regression Discontinuity Design: no data available"
      >
        {title && (
          <figcaption className="text-foreground mb-3 text-sm font-semibold">
            {title}
          </figcaption>
        )}
        <div className="text-muted flex min-h-40 items-center justify-center rounded-lg border border-dashed text-sm">
          No data available.
        </div>
        <ChartDataTable
          caption={title ?? "Regression Discontinuity Design data"}
          columns={["N points"]}
          rows={[]}
        />
      </figure>
    );
  }

  const minX = Math.min(...allX);
  const maxX = Math.max(...allX);
  const minY = Math.min(...allY);
  const maxY = Math.max(...allY);
  const xRange = maxX - minX || 1;
  const yRange = maxY - minY || 1;
  const xPad = xRange * 0.05;
  const yPad = yRange * 0.1;

  function toSvgX(v: number) {
    return PADDING.left + PLOT_W * ((v - (minX - xPad)) / (xRange + 2 * xPad));
  }
  function toSvgY(v: number) {
    return PADDING.top + PLOT_H * (1 - (v - (minY - yPad)) / (yRange + 2 * yPad));
  }

  const cutoffX = toSvgX(cutoff);

  // Fitted line paths
  const fittedBelowPath = sortedFittedBelow
    ? sortedFittedBelow
        .map((p, i) => `${i === 0 ? "M" : "L"}${toSvgX(p.x)},${toSvgY(p.y)}`)
        .join(" ")
    : undefined;
  const fittedAbovePath = sortedFittedAbove
    ? sortedFittedAbove
        .map((p, i) => `${i === 0 ? "M" : "L"}${toSvgX(p.x)},${toSvgY(p.y)}`)
        .join(" ")
    : undefined;

  // Discontinuity gap at cutoff
  const belowAtCutoff = sortedFittedBelow?.length
    ? sortedFittedBelow[sortedFittedBelow.length - 1]
    : undefined;
  const aboveAtCutoff = sortedFittedAbove?.length
    ? sortedFittedAbove[0]
    : undefined;

  const tableRows = (() => {
    const rows = [
      {
        label: "Below cutoff",
        values: { "N points": String(dataBelow.length) },
      },
      {
        label: "Above cutoff",
        values: { "N points": String(dataAbove.length) },
      },
    ];
    if (estimatedEffect != null) {
      rows.push({
        label: "LATE",
        values: {
          "N points": estimatedEffect.toFixed(4) +
            (effectCi
              ? ` [${effectCi.lower.toFixed(4)}, ${effectCi.upper.toFixed(4)}]`
              : ""),
        },
      });
    }
    return rows;
  })();

  return (
    <figure
      className={cn("border-border bg-card rounded-xl border p-4", className)}
      role="img"
      aria-label={`Regression Discontinuity Design: cutoff at ${cutoff}, estimated effect ${estimatedEffect?.toFixed(4) ?? "N/A"}`}
    >
      {title && (
        <figcaption className="text-foreground mb-3 text-sm font-semibold">
          {title}
        </figcaption>
      )}

      <div className="overflow-x-auto">
        <svg width={SVG_WIDTH} height={SVG_HEIGHT} className="overflow-visible">
          {/* Bandwidth shading */}
          {bandwidth != null && (
            <rect
              x={toSvgX(cutoff - bandwidth)}
              y={PADDING.top}
              width={toSvgX(cutoff + bandwidth) - toSvgX(cutoff - bandwidth)}
              height={PLOT_H}
              fill={chartTheme.primary}
              opacity={0.04}
            />
          )}

          {/* Cutoff line */}
          <line
            x1={cutoffX}
            y1={PADDING.top}
            x2={cutoffX}
            y2={SVG_HEIGHT - PADDING.bottom}
            stroke={chartTheme.warning}
            strokeWidth={2}
            strokeDasharray="6 4"
          />
          <text
            x={cutoffX}
            y={PADDING.top - 8}
            textAnchor="middle"
            fontSize={chartDefaults.tickFontSize}
            fontWeight={600}
            fill={chartTheme.warning}
          >
            Cutoff = {cutoff}
          </text>

          {/* Scatter below */}
          {dataBelow.map((d, i) => (
            <circle
              key={`b${i}`}
              cx={toSvgX(d.x)}
              cy={toSvgY(d.y)}
              r={2.5}
              fill={chartTheme.primary}
              opacity={0.4}
            />
          ))}

          {/* Scatter above */}
          {dataAbove.map((d, i) => (
            <circle
              key={`a${i}`}
              cx={toSvgX(d.x)}
              cy={toSvgY(d.y)}
              r={2.5}
              fill={chartTheme.secondary}
              opacity={0.4}
            />
          ))}

          {/* Fitted lines */}
          {fittedBelowPath && (
            <path d={fittedBelowPath} fill="none" stroke={chartTheme.primary} strokeWidth={2.5} />
          )}
          {fittedAbovePath && (
            <path d={fittedAbovePath} fill="none" stroke={chartTheme.secondary} strokeWidth={2.5} />
          )}

          {/* Discontinuity bracket */}
          {belowAtCutoff && aboveAtCutoff && (
            <g>
              <line
                x1={cutoffX + 4}
                y1={toSvgY(belowAtCutoff.y)}
                x2={cutoffX + 4}
                y2={toSvgY(aboveAtCutoff.y)}
                stroke={chartTheme.success}
                strokeWidth={2}
              />
              <circle cx={cutoffX + 4} cy={toSvgY(belowAtCutoff.y)} r={3} fill={chartTheme.primary} />
              <circle cx={cutoffX + 4} cy={toSvgY(aboveAtCutoff.y)} r={3} fill={chartTheme.secondary} />

              {/* CI whiskers */}
              {effectCi && (
                <>
                  <rect
                    x={cutoffX + 10}
                    y={toSvgY(aboveAtCutoff.y) - 2}
                    width={4}
                    height={
                      toSvgY(belowAtCutoff.y) - toSvgY(aboveAtCutoff.y) + 4
                    }
                    fill={ciColors.boundsFill}
                    opacity={0.3}
                    rx={1}
                  />
                </>
              )}
            </g>
          )}

          {/* Effect label */}
          {estimatedEffect != null && (
            <text
              x={SVG_WIDTH - PADDING.right}
              y={PADDING.top + 16}
              textAnchor="end"
              fontSize={chartDefaults.labelFontSize}
              fontWeight={700}
              fill={chartTheme.success}
            >
              LATE = {estimatedEffect >= 0 ? "+" : ""}{estimatedEffect.toFixed(3)}
            </text>
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

          {/* X label */}
          <text
            x={PADDING.left + PLOT_W / 2}
            y={SVG_HEIGHT - 6}
            textAnchor="middle"
            fontSize={chartDefaults.tickFontSize}
            fill={chartTheme.axis}
          >
            Running variable
          </text>
        </svg>
      </div>

      <ChartDataTable
        caption={title ?? "Regression Discontinuity data"}
        columns={["N points"]}
        rows={tableRows}
      />
    </figure>
  );
}
