import { cn } from "@/lib/utils";
import { classifyConfidence, confidenceColor } from "./types";

type ConfidenceGaugeProps = {
  value: number;
  label?: string;
  size?: number;
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
  className,
}: ConfidenceGaugeProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const level = classifyConfidence(clamped);
  const color = confidenceColor(level);

  const cx = size / 2;
  const cy = size / 2;
  const r = (size - STROKE_WIDTH) / 2 - 4;

  const bgPath = describeArc(cx, cy, r, ARC_START, ARC_START + ARC_SWEEP);
  const fillAngle = ARC_START + ARC_SWEEP * clamped;
  const fillPath =
    clamped > 0
      ? describeArc(cx, cy, r, ARC_START, fillAngle)
      : "";

  const pct = Math.round(clamped * 100);
  const ariaLabel = `Confidence gauge: ${pct}%, ${level} confidence${label ? `. ${label}` : ""}`;

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
        {/* Background track */}
        <path
          d={bgPath}
          fill="none"
          stroke="var(--line)"
          strokeWidth={STROKE_WIDTH}
          strokeLinecap="round"
        />
        {/* Filled arc */}
        {fillPath && (
          <path
            d={fillPath}
            fill="none"
            stroke={color}
            strokeWidth={STROKE_WIDTH}
            strokeLinecap="round"
          />
        )}
        {/* Center label */}
        <text
          x={cx}
          y={cy + 4}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={size * 0.24}
          fontWeight={700}
          fill="var(--ink)"
        >
          {pct}%
        </text>
      </svg>
      {label && (
        <span className="text-muted-foreground text-xs font-medium">
          {label}
        </span>
      )}
    </div>
  );
}
