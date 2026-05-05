import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

import { chartTheme } from "./theme";
import { uncertaintyTokens } from "./uncertainty-tokens";

type QuantileDotplotProps = {
  samples: number[];
  bins?: number;
  label?: string;
  orientation?: "horizontal" | "vertical";
  unit?: string;
  className?: string;
};

type QuantileDot = {
  bucket: number;
  index: number;
  isTail: boolean;
  value: number;
};

const SVG_HEIGHT = 148;
const SVG_WIDTH = 320;
const DOT_SIZE = 8;
const PADDING = 14;

export function calculateQuantile(sorted: number[], q: number) {
  if (sorted.length === 0) {
    return 0;
  }
  const position = (sorted.length - 1) * q;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  if (lower === upper) {
    return sorted[lower];
  }
  const weight = position - lower;
  return sorted[lower] * (1 - weight) + sorted[upper] * weight;
}

export function buildQuantileDots(
  samples: number[],
  bins: number,
): QuantileDot[] {
  if (samples.length === 0 || bins <= 0) {
    return [];
  }

  const sorted = [...samples].sort((left, right) => left - right);
  const min = sorted[0];
  const max = sorted.at(-1) ?? min;
  const range = max - min || 1;
  const p10 = calculateQuantile(sorted, 0.1);
  const p90 = calculateQuantile(sorted, 0.9);
  const stacks = Array.from({ length: bins }, () => 0);

  return Array.from({ length: bins }, (_, index) => {
    const q = (index + 0.5) / bins;
    const value = calculateQuantile(sorted, q);
    const rawBucket = Math.round(((value - min) / range) * (bins - 1));
    const bucket = Math.max(0, Math.min(bins - 1, rawBucket));
    const stackIndex = stacks[bucket];
    stacks[bucket] += 1;

    return {
      bucket,
      index: stackIndex,
      isTail: value < p10 || value > p90,
      value,
    };
  });
}

export function QuantileDotplot({
  samples,
  bins = 20,
  label = "Quantile dotplot",
  orientation = "horizontal",
  unit = "",
  className,
}: QuantileDotplotProps) {
  const { t } = useI18n();
  const sorted = [...samples].sort((left, right) => left - right);

  if (sorted.length === 0) {
    return (
      <div
        className={cn(
          "border-line bg-surface/55 rounded-2xl border p-4 text-sm",
          className,
        )}
        role="img"
        aria-label={`${label}. No samples available.`}
      >
        <p className="font-semibold">{label}</p>
        <p className="text-muted mt-2">
          {t("shared.charts.quantileDotplot.noSamples")}
        </p>
      </div>
    );
  }

  const min = sorted[0];
  const max = sorted.at(-1) ?? min;
  const range = max - min || 1;
  const p10 = calculateQuantile(sorted, 0.1);
  const p50 = calculateQuantile(sorted, 0.5);
  const p90 = calculateQuantile(sorted, 0.9);
  const dots = buildQuantileDots(sorted, bins);
  const maxStack = Math.max(...dots.map((dot) => dot.index), 0) + 1;
  const plotWidth = SVG_WIDTH - PADDING * 2;
  const plotHeight = SVG_HEIGHT - PADDING * 2;

  const xFor = (value: number) => PADDING + ((value - min) / range) * plotWidth;
  const yFor = (stackIndex: number) =>
    SVG_HEIGHT - PADDING - DOT_SIZE / 2 - stackIndex * (DOT_SIZE + 2);

  const verticalXFor = (stackIndex: number) =>
    PADDING + DOT_SIZE / 2 + stackIndex * (DOT_SIZE + 2);
  const verticalYFor = (value: number) =>
    SVG_HEIGHT - PADDING - ((value - min) / range) * plotHeight;

  const ariaLabel = `${label}. ${samples.length} samples from ${min.toFixed(
    2,
  )}${unit} to ${max.toFixed(2)}${unit}. Median ${p50.toFixed(2)}${unit}.`;

  return (
    <div
      className={cn("space-y-2", className)}
      role="img"
      aria-label={ariaLabel}
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold">{label}</p>
        <span className="text-muted font-mono text-[11px] tracking-[0.14em] uppercase">
          {t("shared.charts.quantileDotplot.quantileDots")}
        </span>
      </div>
      <div className="border-line bg-surface/55 rounded-2xl border p-4">
        <svg
          width="100%"
          height={SVG_HEIGHT}
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
        >
          <line
            x1={orientation === "horizontal" ? PADDING : verticalXFor(maxStack)}
            y1={orientation === "horizontal" ? SVG_HEIGHT - PADDING : PADDING}
            x2={
              orientation === "horizontal"
                ? SVG_WIDTH - PADDING
                : verticalXFor(maxStack)
            }
            y2={
              orientation === "horizontal"
                ? SVG_HEIGHT - PADDING
                : SVG_HEIGHT - PADDING
            }
            stroke={chartTheme.neutral}
            strokeDasharray="3 5"
            strokeWidth={1}
            opacity={0.7}
          />
          {dots.map((dot, index) => (
            <circle
              key={`${dot.bucket}-${dot.index}-${index}`}
              cx={
                orientation === "horizontal"
                  ? xFor(dot.value)
                  : verticalXFor(dot.index)
              }
              cy={
                orientation === "horizontal"
                  ? yFor(dot.index)
                  : verticalYFor(dot.value)
              }
              r={DOT_SIZE / 2}
              fill={uncertaintyTokens.pointEstimate}
              fillOpacity={0.85}
              stroke={dot.isTail ? "var(--gold-vibrant)" : "transparent"}
              strokeWidth={dot.isTail ? 1 : 0}
            />
          ))}
          <line
            x1={orientation === "horizontal" ? xFor(p50) : PADDING}
            y1={orientation === "horizontal" ? PADDING : verticalYFor(p50)}
            x2={
              orientation === "horizontal"
                ? xFor(p50)
                : PADDING + maxStack * (DOT_SIZE + 2)
            }
            y2={
              orientation === "horizontal"
                ? SVG_HEIGHT - PADDING
                : verticalYFor(p50)
            }
            stroke={chartTheme.axis}
            strokeDasharray="4 4"
            strokeWidth={1}
            opacity={0.7}
          />
        </svg>
        <div className="mt-4 flex items-center justify-between gap-3 text-[11px]">
          <span className="text-muted font-mono">
            {min.toFixed(2)}
            {unit}
          </span>
          <span className="font-mono text-[var(--color-uncertainty-point-estimate)]">
            {t("shared.charts.quantileDotplot.p50Label")} {p50.toFixed(2)}
            {unit}
          </span>
          <span className="text-muted font-mono">
            {max.toFixed(2)}
            {unit}
          </span>
        </div>
        <p className="text-muted mt-2 text-xs leading-5">
          {t("shared.charts.quantileDotplot.tailSummary", {
            bins,
            p10: `${p10.toFixed(2)}${unit}`,
            p90: `${p90.toFixed(2)}${unit}`,
          })}
        </p>
      </div>
    </div>
  );
}
