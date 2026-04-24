import { useId, useMemo } from "react";

import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

import { describeTimeSeries } from "./accessibility";
import { DisputedMarker } from "./DisputedMarker";
import {
  buildUncertaintyPatternIds,
  resolveUncertaintyPatternFill,
  UncertaintyPatterns,
} from "./patterns";
import { chartDefaults, chartTheme } from "./theme";
import {
  resolveIdentifiabilityPattern,
  resolveUncertaintyIntervalColor,
  resolveUncertaintyPaletteColor,
  type UncertaintyPalette,
} from "./uncertainty-tokens";
import type {
  DisputeSummary,
  IdentifiabilityState,
  QuantileSeries,
} from "./types";

const PADDING = { bottom: 22, left: 10, right: 10, top: 10 } as const;

type FanChartProps = {
  data: QuantileSeries[];
  quantiles?: [0.1, 0.25, 0.5, 0.75, 0.9];
  label?: string;
  height?: number;
  asOf?: string;
  asOfIndex?: number;
  disputed?: boolean;
  disputes?: DisputeSummary[];
  identifiability?: IdentifiabilityState;
  className?: string;
};

function envelopePath(
  data: QuantileSeries[],
  lowerKey: "p10" | "p25",
  upperKey: "p75" | "p90",
  toX: (index: number) => number,
  toY: (value: number) => number,
) {
  const upperPoints = data.map((point, index) => [
    toX(index),
    toY(point[upperKey]),
  ]);
  const lowerPoints = data
    .map((point, index) => [toX(index), toY(point[lowerKey])])
    .reverse();
  const [firstX, firstY] = upperPoints[0];
  const commands = [`M ${firstX} ${firstY}`];
  for (const [x, y] of upperPoints.slice(1)) {
    commands.push(`L ${x} ${y}`);
  }
  for (const [x, y] of lowerPoints) {
    commands.push(`L ${x} ${y}`);
  }
  commands.push("Z");
  return commands.join(" ");
}

function medianPath(
  data: QuantileSeries[],
  toX: (index: number) => number,
  toY: (value: number) => number,
) {
  const [first, ...rest] = data;
  const commands = [`M ${toX(0)} ${toY(first.p50)}`];
  for (const [index, point] of rest.entries()) {
    commands.push(`L ${toX(index + 1)} ${toY(point.p50)}`);
  }
  return commands.join(" ");
}

export function FanChart({
  data,
  quantiles = [0.1, 0.25, 0.5, 0.75, 0.9],
  label = "Fan chart",
  height = 120,
  asOf,
  asOfIndex,
  disputed = false,
  disputes = [],
  identifiability = "identified",
  className,
}: FanChartProps) {
  const { t } = useI18n();
  const patternSeed = useId();
  const patternIds = useMemo(
    () => buildUncertaintyPatternIds(patternSeed.replace(/:/g, "")),
    [patternSeed],
  );

  if (data.length === 0) {
    return null;
  }

  const palette: UncertaintyPalette = disputed ? "disputed" : "default";
  const pointColor = resolveUncertaintyPaletteColor(palette);
  const intervalColor = resolveUncertaintyIntervalColor(palette);
  const patternKind = resolveIdentifiabilityPattern(identifiability);
  const quantilePrefix = t("shared.charts.fanChart.quantilePrefix");
  const gradientId = `${patternSeed.replace(/:/g, "")}-fan-gradient`;
  const svgWidth = 360;
  const plotWidth = svgWidth - PADDING.left - PADDING.right;
  const plotHeight = height - PADDING.top - PADDING.bottom;
  const allValues = data.flatMap((point) => [
    point.p10,
    point.p25,
    point.p50,
    point.p75,
    point.p90,
  ]);
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const range = max - min || 1;
  const pad = range * 0.12;
  const yRange: [number, number] = [min - pad, max + pad];
  const toX = (index: number) =>
    PADDING.left + (plotWidth * index) / Math.max(1, data.length - 1);
  const toY = (value: number) =>
    PADDING.top +
    plotHeight -
    ((value - yRange[0]) / (yRange[1] - yRange[0])) * plotHeight;
  const outerEnvelope = envelopePath(data, "p10", "p90", toX, toY);
  const innerEnvelope = envelopePath(data, "p25", "p75", toX, toY);
  const centerPath = medianPath(data, toX, toY);
  const effectiveAsOfIndex =
    typeof asOfIndex === "number" && asOfIndex >= 0 && asOfIndex < data.length
      ? asOfIndex
      : null;
  const asOfX = effectiveAsOfIndex === null ? null : toX(effectiveAsOfIndex);

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold">{label}</p>
          {disputed ? <DisputedMarker disputes={disputes} /> : null}
        </div>
        <span className="text-muted font-mono text-[11px] tracking-[0.14em] uppercase">
          {quantilePrefix}
          {Math.round(quantiles[0] * 100)} {quantilePrefix}
          {Math.round(quantiles[1] * 100)} {quantilePrefix}
          {Math.round(quantiles[2] * 100)} {quantilePrefix}
          {Math.round(quantiles[3] * 100)} {quantilePrefix}
          {Math.round(quantiles[4] * 100)}
        </span>
      </div>
      <div
        className="border-line bg-surface/55 rounded-2xl border px-2 py-2"
        role="img"
        aria-label={describeTimeSeries(label, data.length, [min, max])}
      >
        <svg width="100%" height={height} viewBox={`0 0 ${svgWidth} ${height}`}>
          <defs>
            <linearGradient id={gradientId} x1="0%" x2="0%" y1="0%" y2="100%">
              <stop offset="0%" stopColor={pointColor} stopOpacity="0.24" />
              <stop offset="100%" stopColor={pointColor} stopOpacity="0" />
            </linearGradient>
          </defs>
          <UncertaintyPatterns ids={patternIds} />
          {[0.25, 0.5, 0.75].map((fraction) => {
            const y = PADDING.top + plotHeight * fraction;
            return (
              <line
                key={fraction}
                x1={PADDING.left}
                y1={y}
                x2={svgWidth - PADDING.right}
                y2={y}
                stroke={chartTheme.grid}
                strokeDasharray="3 5"
                strokeWidth={1}
              />
            );
          })}
          <path d={outerEnvelope} fill={intervalColor} fillOpacity={0.12} />
          {patternKind !== "none" ? (
            <path
              d={outerEnvelope}
              fill={resolveUncertaintyPatternFill(patternKind, patternIds)}
              fillOpacity={0.68}
            />
          ) : null}
          <path d={innerEnvelope} fill={`url(#${gradientId})`} />
          <path
            d={centerPath}
            fill="none"
            stroke={pointColor}
            strokeWidth={chartDefaults.strokeWidth}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {asOfX !== null ? (
            <>
              <line
                x1={asOfX}
                y1={PADDING.top}
                x2={asOfX}
                y2={height - PADDING.bottom}
                stroke={chartTheme.axis}
                strokeDasharray="4 5"
                strokeWidth={1}
                opacity={0.6}
              />
              <text
                x={asOfX + 4}
                y={PADDING.top + 10}
                fontSize="9"
                fontFamily="var(--font-mono)"
                fill={chartTheme.axis}
                letterSpacing="0.14em"
              >
                {t("shared.charts.fanChart.asOf")}
              </text>
            </>
          ) : null}
          <text
            x={PADDING.left}
            y={height - 4}
            fontSize="10"
            fontFamily="var(--font-mono)"
            fill={chartTheme.neutral}
          >
            {String(data[0]?.x ?? "")}
          </text>
          <text
            x={svgWidth - PADDING.right}
            y={height - 4}
            textAnchor="end"
            fontSize="10"
            fontFamily="var(--font-mono)"
            fill={chartTheme.neutral}
          >
            {asOf ?? String(data.at(-1)?.x ?? "")}
          </text>
        </svg>
      </div>
    </div>
  );
}
