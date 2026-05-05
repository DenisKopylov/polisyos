import { useEffect, useId, useMemo, useState } from "react";
import { useReducedMotion } from "motion/react";

import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";

import { describeTimeSeries } from "./accessibility";
import { calculateQuantile, QuantileDotplot } from "./QuantileDotplot";
import { DisputedMarker } from "./DisputedMarker";
import { FanChart } from "./FanChart";
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
  SampleRealization,
} from "./types";

const PADDING = { bottom: 22, left: 10, right: 10, top: 10 } as const;

type HypotheticalOutcomePlotProps = {
  samples: SampleRealization[];
  framesPerSecond?: number;
  reducedMotionFallback?: "fan-chart" | "quantile-dotplot";
  label?: string;
  height?: number;
  disputed?: boolean;
  disputes?: DisputeSummary[];
  identifiability?: IdentifiabilityState;
  className?: string;
};

function linePath(
  points: SampleRealization["points"],
  toX: (index: number) => number,
  toY: (value: number) => number,
) {
  if (points.length < 2) {
    return null;
  }
  const [first, ...rest] = points;
  const commands = [`M ${toX(0)} ${toY(first.y)}`];
  for (const [index, point] of rest.entries()) {
    commands.push(`L ${toX(index + 1)} ${toY(point.y)}`);
  }
  return commands.join(" ");
}

function buildFanData(samples: SampleRealization[]): QuantileSeries[] {
  if (samples.length === 0) {
    return [];
  }

  const pointCount = Math.max(
    ...samples.map((sample) => sample.points.length),
    0,
  );
  return Array.from({ length: pointCount }, (_, index) => {
    const values = samples
      .map((sample) => sample.points[index]?.y)
      .filter((value): value is number => typeof value === "number")
      .sort((left, right) => left - right);
    const x =
      samples.find((sample) => sample.points[index])?.points[index]?.x ?? index;

    return {
      x,
      p10: calculateQuantile(values, 0.1),
      p25: calculateQuantile(values, 0.25),
      p50: calculateQuantile(values, 0.5),
      p75: calculateQuantile(values, 0.75),
      p90: calculateQuantile(values, 0.9),
    };
  });
}

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

export function HypotheticalOutcomePlot({
  samples,
  framesPerSecond = 2,
  reducedMotionFallback = "fan-chart",
  label = "Hypothetical outcome plot",
  height = 140,
  disputed = false,
  disputes = [],
  identifiability = "estimated",
  className,
}: HypotheticalOutcomePlotProps) {
  const { t } = useI18n();
  const prefersReducedMotion = useReducedMotion();
  const [frameIndex, setFrameIndex] = useState(0);
  const patternSeed = useId();
  const patternIds = useMemo(
    () => buildUncertaintyPatternIds(patternSeed.replace(/:/g, "")),
    [patternSeed],
  );

  const fanData = useMemo(() => buildFanData(samples), [samples]);

  useEffect(() => {
    if (prefersReducedMotion || samples.length <= 1 || framesPerSecond <= 0) {
      return undefined;
    }
    const interval = window.setInterval(() => {
      setFrameIndex((current) => (current + 1) % samples.length);
    }, 1000 / framesPerSecond);
    return () => window.clearInterval(interval);
  }, [framesPerSecond, prefersReducedMotion, samples.length]);

  if (samples.length === 0) {
    return null;
  }

  if (prefersReducedMotion) {
    if (reducedMotionFallback === "quantile-dotplot") {
      const lastStepSamples = samples
        .map((sample) => sample.points.at(-1)?.y)
        .filter((value): value is number => typeof value === "number");

      return (
        <QuantileDotplot
          className={className}
          label={`${label} fallback`}
          samples={lastStepSamples}
        />
      );
    }

    return (
      <FanChart
        className={className}
        data={fanData}
        disputed={disputed}
        disputes={disputes}
        identifiability={identifiability}
        label={`${label} fallback`}
      />
    );
  }

  const palette: UncertaintyPalette = disputed ? "disputed" : "default";
  const pointColor = resolveUncertaintyPaletteColor(palette);
  const intervalColor = resolveUncertaintyIntervalColor(palette);
  const patternKind = resolveIdentifiabilityPattern(identifiability);
  const svgWidth = 360;
  const plotWidth = svgWidth - PADDING.left - PADDING.right;
  const plotHeight = height - PADDING.top - PADDING.bottom;
  const allValues = samples.flatMap((sample) =>
    sample.points.map((point) => point.y),
  );
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const range = max - min || 1;
  const pad = range * 0.12;
  const yRange: [number, number] = [min - pad, max + pad];
  const toX = (index: number) =>
    PADDING.left + (plotWidth * index) / Math.max(1, fanData.length - 1);
  const toY = (value: number) =>
    PADDING.top +
    plotHeight -
    ((value - yRange[0]) / (yRange[1] - yRange[0])) * plotHeight;
  const outerEnvelope = envelopePath(fanData, "p10", "p90", toX, toY);
  const currentSample = samples[frameIndex] ?? samples[0];

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold">{label}</p>
          {disputed ? <DisputedMarker disputes={disputes} /> : null}
        </div>
        <span className="text-muted font-mono text-[11px] tracking-[0.14em] uppercase">
          {t("shared.charts.hypotheticalOutcomePlot.framesPerSecond", {
            fps: framesPerSecond.toFixed(1),
          })}
        </span>
      </div>
      <div
        className="border-line bg-surface/55 rounded-2xl border px-2 py-2"
        role="img"
        aria-label={describeTimeSeries(label, fanData.length, [min, max])}
      >
        <svg width="100%" height={height} viewBox={`0 0 ${svgWidth} ${height}`}>
          <UncertaintyPatterns ids={patternIds} />
          <path d={outerEnvelope} fill={intervalColor} fillOpacity={0.1} />
          {patternKind !== "none" ? (
            <path
              d={outerEnvelope}
              fill={resolveUncertaintyPatternFill(patternKind, patternIds)}
              fillOpacity={0.68}
            />
          ) : null}
          {samples.map((sample) => {
            const path = linePath(sample.points, toX, toY);
            if (!path) {
              return null;
            }
            const isActive = sample.id === currentSample.id;
            return (
              <path
                key={sample.id}
                d={path}
                fill="none"
                stroke={pointColor}
                strokeWidth={isActive ? chartDefaults.strokeWidth : 1}
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity={isActive ? 0.95 : 0.12}
              />
            );
          })}
          <text
            x={PADDING.left}
            y={height - 4}
            fontSize="10"
            fontFamily="var(--font-mono)"
            fill={chartTheme.neutral}
          >
            {String(samples[0]?.points[0]?.x ?? "")}
          </text>
          <text
            x={svgWidth - PADDING.right}
            y={height - 4}
            textAnchor="end"
            fontSize="10"
            fontFamily="var(--font-mono)"
            fill={chartTheme.neutral}
          >
            {String(samples[0]?.points.at(-1)?.x ?? "")}
          </text>
        </svg>
      </div>
    </div>
  );
}
