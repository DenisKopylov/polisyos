import { useId, useMemo } from "react";

import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";

import {
  describeConfidenceInterval,
  describeTimeSeries,
} from "./accessibility";
import { DisputedMarker } from "./DisputedMarker";
import { GradedErrorBar } from "./GradedErrorBar";
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
  resolveCounterfactualColor,
  resolveUncertaintyPaletteColor,
  type UncertaintyPalette,
} from "./uncertainty-tokens";
import type {
  ConfidenceInterval,
  DisputeSummary,
  IdentifiabilityState,
  SeriesPoint,
  TimeSeriesDataPoint,
} from "./types";

const BAND_CONFIGS = [
  { level: 0.95, lowerKey: "ci95Lower", upperKey: "ci95Upper" },
  { level: 0.8, lowerKey: "ci80Lower", upperKey: "ci80Upper" },
  { level: 0.5, lowerKey: "ci50Lower", upperKey: "ci50Upper" },
] as const;

const PADDING = { bottom: 22, left: 10, right: 10, top: 10 } as const;

type UncertaintyBandProps = {
  data?: SeriesPoint[];
  lower?: number;
  upper?: number;
  estimate?: number;
  bands?: ConfidenceInterval[];
  counterfactual?: SeriesPoint[];
  label?: string;
  unit?: string;
  height?: number;
  asOf?: string;
  asOfIndex?: number;
  disputed?: boolean;
  disputes?: DisputeSummary[];
  identifiability?: IdentifiabilityState;
  className?: string;
};

function definedBands(data: TimeSeriesDataPoint[]) {
  return BAND_CONFIGS.filter(({ lowerKey, upperKey }) =>
    data.some(
      (point) =>
        typeof point[lowerKey] === "number" &&
        typeof point[upperKey] === "number",
    ),
  );
}

function resolveRequestedBand(lower?: number, upper?: number) {
  if (typeof lower !== "number" || typeof upper !== "number") {
    return null;
  }
  const level = upper - lower;
  return (
    BAND_CONFIGS.find((config) => Math.abs(config.level - level) < 0.001) ??
    null
  );
}

function bandPath(
  data: TimeSeriesDataPoint[],
  lowerKey: keyof TimeSeriesDataPoint,
  upperKey: keyof TimeSeriesDataPoint,
  toX: (index: number) => number,
  toY: (value: number) => number,
) {
  const upperPoints = data.flatMap((point, index) =>
    typeof point[upperKey] === "number"
      ? [[toX(index), toY(point[upperKey])]]
      : [],
  );
  const lowerPoints = data
    .flatMap((point, index) =>
      typeof point[lowerKey] === "number"
        ? [[toX(index), toY(point[lowerKey])]]
        : [],
    )
    .reverse();

  if (upperPoints.length < 2 || lowerPoints.length < 2) {
    return null;
  }

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

function linePath(
  data: TimeSeriesDataPoint[],
  toX: (index: number) => number,
  toY: (value: number) => number,
) {
  const points = data.flatMap((point, index) =>
    typeof point.y === "number" ? [[toX(index), toY(point.y)]] : [],
  );
  if (points.length < 2) {
    return null;
  }
  const [firstX, firstY] = points[0];
  const commands = [`M ${firstX} ${firstY}`];
  for (const [x, y] of points.slice(1)) {
    commands.push(`L ${x} ${y}`);
  }
  return commands.join(" ");
}

export function UncertaintyBand({
  data,
  lower,
  upper,
  estimate,
  bands,
  counterfactual,
  label,
  unit = "",
  height = 120,
  asOf,
  asOfIndex,
  disputed = false,
  disputes = [],
  identifiability = "identified",
  className,
}: UncertaintyBandProps) {
  const { t } = useI18n();
  const resolvedLabel = label ?? t("shared.charts.uncertaintyBand.label");
  const patternSeed = useId();
  const patternIds = useMemo(
    () => buildUncertaintyPatternIds(patternSeed.replace(/:/g, "")),
    [patternSeed],
  );

  if (typeof estimate === "number" && bands && bands.length > 0) {
    const primaryBand = [...bands].sort(
      (left, right) => right.level - left.level,
    )[0];
    const ariaLabel = primaryBand
      ? describeConfidenceInterval(
          estimate,
          primaryBand.lower,
          primaryBand.upper,
          primaryBand.level,
        )
      : resolvedLabel;

    return (
      <div className={cn("space-y-2", className)}>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold">{resolvedLabel}</p>
            {disputed ? <DisputedMarker disputes={disputes} /> : null}
          </div>
          <span className="text-muted font-mono text-[11px] tracking-[0.14em] uppercase">
            {t("shared.charts.uncertaintyBand.scalar")}
          </span>
        </div>
        <div
          className="border-line bg-surface/55 rounded-2xl border px-2 py-2"
          role="img"
          aria-label={ariaLabel}
        >
          <GradedErrorBar
            estimate={estimate}
            bands={bands}
            label={resolvedLabel}
            unit={unit}
            disputed={disputed}
            identifiability={identifiability}
            className="block w-full"
            height={Math.max(74, height)}
          />
        </div>
      </div>
    );
  }

  if (!data || data.length < 2) {
    return null;
  }

  const requestedBand = resolveRequestedBand(lower, upper);
  const seriesData = data;
  const bandConfigs = requestedBand
    ? [requestedBand]
    : definedBands(seriesData);
  const palette: UncertaintyPalette = disputed ? "disputed" : "default";
  const pointColor = resolveUncertaintyPaletteColor(palette);
  const intervalColor = resolveUncertaintyIntervalColor(palette);
  const counterfactualColor = resolveCounterfactualColor(palette);
  const patternKind = resolveIdentifiabilityPattern(identifiability);
  const svgWidth = 360;
  const plotWidth = svgWidth - PADDING.left - PADDING.right;
  const plotHeight = height - PADDING.top - PADDING.bottom;

  const allValues = [
    ...seriesData.flatMap((point) =>
      [
        point.y,
        point.ci50Lower,
        point.ci50Upper,
        point.ci80Lower,
        point.ci80Upper,
        point.ci95Lower,
        point.ci95Upper,
      ].filter((value): value is number => typeof value === "number"),
    ),
    ...(counterfactual ?? []).flatMap((point) =>
      typeof point.y === "number" ? [point.y] : [],
    ),
  ];

  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const range = max - min || 1;
  const pad = range * 0.12;
  const yRange: [number, number] = [min - pad, max + pad];

  function toX(index: number) {
    if (seriesData.length === 1) {
      return PADDING.left + plotWidth / 2;
    }
    return PADDING.left + (plotWidth * index) / (seriesData.length - 1);
  }

  function toY(value: number) {
    return (
      PADDING.top +
      plotHeight -
      ((value - yRange[0]) / (yRange[1] - yRange[0])) * plotHeight
    );
  }

  const seriesPath = linePath(seriesData, toX, toY);
  const counterfactualPath =
    counterfactual && counterfactual.length === seriesData.length
      ? linePath(counterfactual, toX, toY)
      : null;
  const ariaLabel = describeTimeSeries(resolvedLabel, seriesData.length, [
    min,
    max,
  ]);
  const effectiveAsOfIndex =
    typeof asOfIndex === "number" &&
    asOfIndex >= 0 &&
    asOfIndex < seriesData.length
      ? asOfIndex
      : null;
  const asOfX = effectiveAsOfIndex === null ? null : toX(effectiveAsOfIndex);

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold">{resolvedLabel}</p>
          {disputed ? <DisputedMarker disputes={disputes} /> : null}
        </div>
        <span className="text-muted font-mono text-[11px] tracking-[0.14em] uppercase">
          {requestedBand
            ? `${Math.round(requestedBand.level * 100)}% band`
            : `${seriesData.length} pts`}
        </span>
      </div>
      <div
        className="border-line bg-surface/55 rounded-2xl border px-2 py-2"
        role="img"
        aria-label={ariaLabel}
      >
        <svg width="100%" height={height} viewBox={`0 0 ${svgWidth} ${height}`}>
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
          {bandConfigs.map((config) => {
            const path = bandPath(
              seriesData,
              config.lowerKey,
              config.upperKey,
              toX,
              toY,
            );
            if (!path) {
              return null;
            }
            return (
              <g key={config.level}>
                <path
                  d={path}
                  fill={intervalColor}
                  fillOpacity={resolveUncertaintyBandOpacity(config.level)}
                />
                {patternKind !== "none" ? (
                  <path
                    d={path}
                    fill={resolveUncertaintyPatternFill(
                      patternKind,
                      patternIds,
                    )}
                    fillOpacity={0.68}
                  />
                ) : null}
              </g>
            );
          })}
          {counterfactualPath ? (
            <path
              d={counterfactualPath}
              fill="none"
              stroke={counterfactualColor}
              strokeDasharray="6 6"
              strokeWidth={1.5}
              opacity={0.9}
            />
          ) : null}
          {seriesPath ? (
            <path
              d={seriesPath}
              fill="none"
              stroke={pointColor}
              strokeWidth={chartDefaults.strokeWidth}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ) : null}
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
            {String(seriesData[0]?.x ?? "")}
          </text>
          <text
            x={svgWidth - PADDING.right}
            y={height - 4}
            textAnchor="end"
            fontSize="10"
            fontFamily="var(--font-mono)"
            fill={chartTheme.neutral}
          >
            {asOf ?? String(seriesData.at(-1)?.x ?? "")}
          </text>
        </svg>
      </div>
    </div>
  );
}
