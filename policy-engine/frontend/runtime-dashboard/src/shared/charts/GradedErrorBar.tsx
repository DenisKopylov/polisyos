import { useMemo } from "react";

import { cn } from "@/lib/utils";
import { chartTheme, ciColors, chartDefaults } from "./theme";
import { describeConfidenceInterval } from "./accessibility";

type CIBand = { lower: number; upper: number; level: number };

type GradedErrorBarProps = {
  estimate: number;
  bands: CIBand[];
  label?: string;
  unit?: string;
  height?: number;
  className?: string;
};

const BAR_HEIGHT = 16;
const PADDING = { left: 8, right: 8 };

function bandColor(level: number): string {
  if (level <= 0.5) return ciColors.ci50;
  if (level <= 0.8) return ciColors.ci80;
  return ciColors.ci95;
}

export function GradedErrorBar({
  estimate,
  bands,
  label,
  unit = "",
  height = 80,
  className,
}: GradedErrorBarProps) {
  const sorted = useMemo(
    () => [...bands].sort((a, b) => b.level - a.level),
    [bands],
  );

  const allValues = [
    estimate,
    ...sorted.flatMap((b) => [b.lower, b.upper]),
  ];
  const minVal = Math.min(...allValues);
  const maxVal = Math.max(...allValues);
  const range = maxVal - minVal || 1;
  const pad = range * 0.15;

  const svgWidth = 320;
  const plotW = svgWidth - PADDING.left - PADDING.right;

  function toX(val: number): number {
    return PADDING.left + plotW * ((val - (minVal - pad)) / (range + 2 * pad));
  }

  const centerY = height / 2;

  const ariaDescription = sorted.length > 0
    ? describeConfidenceInterval(
        estimate,
        sorted[0].lower,
        sorted[0].upper,
        sorted[0].level,
      )
    : `Point estimate: ${estimate.toFixed(3)}`;

  return (
    <div
      className={cn("inline-block", className)}
      role="img"
      aria-label={ariaDescription}
    >
      {label && (
        <p className="text-foreground mb-1 text-sm font-semibold">{label}</p>
      )}
      <svg width="100%" height={height} viewBox={`0 0 ${svgWidth} ${height}`}>
        {/* Center line */}
        <line
          x1={PADDING.left}
          y1={centerY}
          x2={svgWidth - PADDING.right}
          y2={centerY}
          stroke="var(--line)"
          strokeWidth={1}
        />

        {/* CI bands (widest first) */}
        {sorted.map((band) => {
          const bandH = BAR_HEIGHT * (1 + (band.level - 0.5));
          return (
            <rect
              key={band.level}
              x={toX(band.lower)}
              y={centerY - bandH / 2}
              width={toX(band.upper) - toX(band.lower)}
              height={bandH}
              rx={bandH / 2}
              fill={bandColor(band.level)}
            />
          );
        })}

        {/* Point estimate marker */}
        <circle
          cx={toX(estimate)}
          cy={centerY}
          r={5}
          fill={chartTheme.primary}
          stroke="var(--panel)"
          strokeWidth={2}
        />

        {/* Labels */}
        <text
          x={toX(estimate)}
          y={centerY - BAR_HEIGHT - 6}
          textAnchor="middle"
          fontSize={chartDefaults.labelFontSize}
          fontWeight={700}
          fill="var(--ink)"
        >
          {estimate.toFixed(3)}{unit}
        </text>

        {sorted.map((band) => (
          <g key={band.level}>
            <text
              x={toX(band.lower)}
              y={centerY + BAR_HEIGHT + 14}
              textAnchor="middle"
              fontSize={10}
              fill={chartTheme.neutral}
            >
              {band.lower.toFixed(2)}
            </text>
            <text
              x={toX(band.upper)}
              y={centerY + BAR_HEIGHT + 14}
              textAnchor="middle"
              fontSize={10}
              fill={chartTheme.neutral}
            >
              {band.upper.toFixed(2)}
            </text>
          </g>
        ))}

        {/* Band legend */}
        {sorted.map((band, i) => (
          <text
            key={band.level}
            x={svgWidth - PADDING.right}
            y={centerY + BAR_HEIGHT + 14 + i * 12}
            textAnchor="end"
            fontSize={10}
            fill={chartTheme.neutral}
          >
            {Math.round(band.level * 100)}% CI
          </text>
        ))}
      </svg>
    </div>
  );
}
