import { useId } from "react";

import { cn } from "@/shared/lib/utils";

import {
  resolveUncertaintyIntervalColor,
  resolveUncertaintyPaletteColor,
} from "./uncertainty-tokens";
import type { UncertaintyPalette } from "./uncertainty-tokens";

type ConfidenceDialProps = {
  value: number;
  label?: string;
  size?: number;
  disputed?: boolean;
  className?: string;
};

const STROKE_WIDTH = 14;
const START_ANGLE = -120;
const SWEEP_ANGLE = 240;

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
  sweepAngle: number,
): string {
  const endAngle = startAngle + sweepAngle;
  const start = polarToCartesian(cx, cy, r, startAngle - 90);
  const end = polarToCartesian(cx, cy, r, endAngle - 90);
  const large = sweepAngle > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${large} 1 ${end.x} ${end.y}`;
}

export function ConfidenceDial({
  value,
  label,
  size = 100,
  disputed = false,
  className,
}: ConfidenceDialProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const palette: UncertaintyPalette = disputed ? "disputed" : "default";
  const pointColor = resolveUncertaintyPaletteColor(palette);
  const intervalColor = resolveUncertaintyIntervalColor(palette);
  const gradientId = `${useId().replace(/:/g, "")}-dial-gradient`;

  const cx = size / 2;
  const cy = size / 2 + 4;
  const r = (size - STROKE_WIDTH) / 2 - 6;
  const needleAngle = START_ANGLE + clamped * SWEEP_ANGLE;
  const needleEnd = polarToCartesian(cx, cy, r - 6, needleAngle - 90);
  const activeSweep = Math.max(4, clamped * SWEEP_ANGLE);
  const ariaLabel = `Confidence dial: ${Math.round(clamped * 100)}%${label ? `. ${label}` : ""}`;

  return (
    <div
      className={cn("inline-flex flex-col items-center gap-1", className)}
      role="meter"
      aria-valuenow={Math.round(clamped * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={ariaLabel}
    >
      <svg width={size} height={size * 0.7} viewBox={`0 0 ${size} ${size}`}>
        <defs>
          <linearGradient id={gradientId} x1="0%" x2="100%" y1="0%" y2="0%">
            <stop offset="0%" stopColor={pointColor} stopOpacity="0.16" />
            <stop offset="55%" stopColor={pointColor} stopOpacity="0.75" />
            <stop offset="100%" stopColor={pointColor} stopOpacity="1" />
          </linearGradient>
        </defs>
        <path
          d={describeArc(cx, cy, r, START_ANGLE, SWEEP_ANGLE)}
          fill="none"
          stroke={intervalColor}
          strokeWidth={STROKE_WIDTH}
          strokeLinecap="round"
          opacity={0.45}
        />
        <path
          d={describeArc(cx, cy, r, START_ANGLE, activeSweep)}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth={STROKE_WIDTH}
          strokeLinecap="round"
        />
        <line
          x1={cx}
          y1={cy}
          x2={needleEnd.x}
          y2={needleEnd.y}
          stroke={pointColor}
          strokeWidth={2}
          strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r={4} fill={pointColor} />
      </svg>
      {label ? (
        <span className="text-muted text-xs font-medium">{label}</span>
      ) : null}
    </div>
  );
}
