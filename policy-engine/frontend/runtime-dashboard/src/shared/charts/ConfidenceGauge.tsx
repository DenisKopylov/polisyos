import { useId, useMemo } from "react";

import { cn } from "@/lib/utils";

import {
  buildUncertaintyPatternIds,
  resolveUncertaintyPatternFill,
  UncertaintyPatterns,
} from "./patterns";
import { resolveIdentifiabilityPattern } from "./uncertainty-tokens";
import {
  resolveUncertaintyIntervalColor,
  resolveUncertaintyPaletteColor,
  type UncertaintyPalette,
} from "./uncertainty-tokens";
import type { IdentifiabilityState } from "./types";

type ConfidenceGaugeProps = {
  value: number;
  label?: string;
  size?: number;
  disputed?: boolean;
  identifiability?: IdentifiabilityState;
  className?: string;
};

const ARC_START = -135;
const ARC_SWEEP = 270;
const STROKE_WIDTH = 10;

function polarToCartesian(
  cx: number,
  cy: number,
  r: number,
  angleDeg: number,
): { x: number; y: number } {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function describeArc(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number,
): string {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`;
}

export function ConfidenceGauge({
  value,
  label,
  size = 120,
  disputed = false,
  identifiability = "identified",
  className,
}: ConfidenceGaugeProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const palette: UncertaintyPalette = disputed ? "disputed" : "default";
  const pointColor = resolveUncertaintyPaletteColor(palette);
  const intervalColor = resolveUncertaintyIntervalColor(palette);
  const patternKind = resolveIdentifiabilityPattern(identifiability);
  const patternSeed = useId();
  const patternIds = useMemo(
    () => buildUncertaintyPatternIds(patternSeed.replace(/:/g, "")),
    [patternSeed],
  );

  const cx = size / 2;
  const cy = size / 2;
  const r = (size - STROKE_WIDTH) / 2 - 4;

  const bgPath = describeArc(cx, cy, r, ARC_START, ARC_START + ARC_SWEEP);
  const fillAngle = ARC_START + ARC_SWEEP * clamped;
  const fillPath =
    clamped > 0 ? describeArc(cx, cy, r, ARC_START, fillAngle) : "";

  const pct = Math.round(clamped * 100);
  const ariaLabel = `Confidence gauge: ${pct}%${label ? `. ${label}` : ""}`;

  return (
    <div
      className={cn("inline-flex flex-col items-center gap-1", className)}
      role="meter"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={ariaLabel}
    >
      <svg width={size} height={size * 0.75} viewBox={`0 0 ${size} ${size}`}>
        <UncertaintyPatterns ids={patternIds} />
        <path
          d={bgPath}
          fill="none"
          stroke={intervalColor}
          strokeWidth={STROKE_WIDTH}
          strokeLinecap="round"
          opacity={0.45}
        />
        {fillPath ? (
          <>
            <path
              d={fillPath}
              fill="none"
              stroke={pointColor}
              strokeWidth={STROKE_WIDTH}
              strokeLinecap="round"
            />
            {patternKind !== "none" ? (
              <path
                d={fillPath}
                fill="none"
                stroke={resolveUncertaintyPatternFill(patternKind, patternIds)}
                strokeWidth={STROKE_WIDTH}
                strokeLinecap="round"
              />
            ) : null}
          </>
        ) : null}
        <text
          x={cx}
          y={cy + 4}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={size * 0.24}
          fontWeight={700}
          fill={pointColor}
        >
          {pct}%
        </text>
      </svg>
      {label ? (
        <span className="text-muted text-xs font-medium">{label}</span>
      ) : null}
    </div>
  );
}
