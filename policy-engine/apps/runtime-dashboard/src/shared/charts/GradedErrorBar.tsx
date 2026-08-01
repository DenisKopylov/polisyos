import { useId, useMemo } from "react";

import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";

import { describeConfidenceInterval } from "./accessibility";
import {
  buildUncertaintyPatternIds,
  resolveUncertaintyPatternFill,
  UncertaintyPatterns,
} from "./patterns";
import { chartDefaults, chartTheme } from "./theme";
import {
  resolveIdentifiabilityPattern,
  resolveUncertaintyBandOpacity,
  resolveUncertaintyIntervalColor,
  resolveUncertaintyPaletteColor,
  type UncertaintyPalette,
} from "./uncertainty-tokens";
import type { IdentifiabilityState } from "./types";

type CIBand = { lower: number; upper: number; level: number };

type GradedErrorBarProps = {
  estimate: number;
  bands: CIBand[];
  label?: string;
  unit?: string;
  height?: number;
  disputed?: boolean;
  identifiability?: IdentifiabilityState;
  className?: string;
};

const BAR_HEIGHT = 16;
const PADDING = { left: 8, right: 8 };

export function GradedErrorBar({
  estimate,
  bands,
  label,
  unit = "",
  height = 80,
  disputed = false,
  identifiability = "unknown",
  className,
}: GradedErrorBarProps) {
  const { t } = useI18n();
  const sorted = useMemo(
    () => [...bands].sort((left, right) => right.level - left.level),
    [bands],
  );
  const palette: UncertaintyPalette = disputed ? "disputed" : "default";
  const pointColor = resolveUncertaintyPaletteColor(palette);
  const intervalColor = resolveUncertaintyIntervalColor(palette);
  const patternKind = resolveIdentifiabilityPattern(identifiability);
  const patternSeed = useId();
  const patternIds = useMemo(
    () => buildUncertaintyPatternIds(patternSeed.replace(/:/g, "")),
    [patternSeed],
  );

  const allValues = [
    estimate,
    ...sorted.flatMap((band) => [band.lower, band.upper]),
  ];
  const minVal = Math.min(...allValues);
  const maxVal = Math.max(...allValues);
  const range = maxVal - minVal || 1;
  const pad = range * 0.15;

  const svgWidth = 320;
  const plotW = svgWidth - PADDING.left - PADDING.right;

  function toX(value: number): number {
    return (
      PADDING.left + plotW * ((value - (minVal - pad)) / (range + 2 * pad))
    );
  }

  const centerY = height / 2;
  const ariaDescription =
    sorted.length > 0
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
      {label ? (
        <p className="text-foreground mb-1 text-sm font-semibold">{label}</p>
      ) : null}
      <svg width="100%" height={height} viewBox={`0 0 ${svgWidth} ${height}`}>
        <UncertaintyPatterns ids={patternIds} />
        <line
          x1={PADDING.left}
          y1={centerY}
          x2={svgWidth - PADDING.right}
          y2={centerY}
          stroke={chartTheme.neutral}
          strokeWidth={1}
          opacity={0.45}
        />

        {sorted.map((band) => {
          const bandHeight = BAR_HEIGHT * (1 + (band.level - 0.5));
          const x = toX(band.lower);
          const width = toX(band.upper) - x;
          const y = centerY - bandHeight / 2;

          return (
            <g key={band.level}>
              <rect
                x={x}
                y={y}
                width={width}
                height={bandHeight}
                rx={bandHeight / 2}
                fill={intervalColor}
                fillOpacity={resolveUncertaintyBandOpacity(band.level)}
              />
              {patternKind !== "none" ? (
                <rect
                  x={x}
                  y={y}
                  width={width}
                  height={bandHeight}
                  rx={bandHeight / 2}
                  fill={resolveUncertaintyPatternFill(patternKind, patternIds)}
                  fillOpacity={0.7}
                />
              ) : null}
            </g>
          );
        })}

        <circle
          cx={toX(estimate)}
          cy={centerY}
          r={5}
          fill={pointColor}
          stroke="var(--paper)"
          strokeWidth={2}
        />

        <text
          x={toX(estimate)}
          y={centerY - BAR_HEIGHT - 6}
          textAnchor="middle"
          fontSize={chartDefaults.labelFontSize}
          fontWeight={700}
          fill={pointColor}
        >
          {estimate.toFixed(3)}
          {unit}
        </text>

        {sorted.map((band) => (
          <g key={`${band.level}-labels`}>
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

        {sorted.map((band, index) => (
          <text
            key={`${band.level}-legend`}
            x={svgWidth - PADDING.right}
            y={centerY + BAR_HEIGHT + 14 + index * 12}
            textAnchor="end"
            fontSize={10}
            fill={chartTheme.neutral}
          >
            {t("shared.charts.common.confidenceIntervalShort", {
              confidence: Math.round(band.level * 100),
            })}
          </text>
        ))}
      </svg>
    </div>
  );
}
