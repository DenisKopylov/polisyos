import { cn } from "@/lib/utils";
import { confidenceColors } from "./theme";
import type { ConfidenceLevel } from "./types";
import { classifyConfidence } from "./types";

type ConfidenceDialProps = {
  value: number;
  label?: string;
  size?: number;
  className?: string;
};

const ZONES: Array<{
  level: ConfidenceLevel;
  label: string;
  startAngle: number;
  sweepAngle: number;
}> = [
  { level: "low", label: "Low", startAngle: -120, sweepAngle: 80 },
  { level: "medium", label: "Med", startAngle: -40, sweepAngle: 80 },
  { level: "high", label: "High", startAngle: 40, sweepAngle: 80 },
];

const STROKE_WIDTH = 14;

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
  className,
}: ConfidenceDialProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const level = classifyConfidence(clamped);

  const cx = size / 2;
  const cy = size / 2 + 4;
  const r = (size - STROKE_WIDTH) / 2 - 6;

  // Needle angle: map 0..1 to -120..120 degrees
  const needleAngle = -120 + clamped * 240;
  const needleEnd = polarToCartesian(cx, cy, r - 6, needleAngle - 90);

  const ariaLabel = `Confidence dial: ${Math.round(clamped * 100)}%, ${level} confidence${label ? `. ${label}` : ""}`;

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
        {/* Zone arcs */}
        {ZONES.map((zone) => (
          <path
            key={zone.level}
            d={describeArc(cx, cy, r, zone.startAngle, zone.sweepAngle)}
            fill="none"
            stroke={confidenceColors[zone.level]}
            strokeWidth={STROKE_WIDTH}
            strokeLinecap="butt"
            opacity={0.3}
          />
        ))}

        {/* Active zone highlight */}
        {ZONES.map((zone) =>
          zone.level === level ? (
            <path
              key={`active-${zone.level}`}
              d={describeArc(cx, cy, r, zone.startAngle, zone.sweepAngle)}
              fill="none"
              stroke={confidenceColors[zone.level]}
              strokeWidth={STROKE_WIDTH}
              strokeLinecap="butt"
              opacity={0.85}
            />
          ) : null,
        )}

        {/* Needle */}
        <line
          x1={cx}
          y1={cy}
          x2={needleEnd.x}
          y2={needleEnd.y}
          stroke="var(--ink)"
          strokeWidth={2}
          strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r={4} fill="var(--ink)" />

        {/* Zone labels */}
        {ZONES.map((zone) => {
          const midAngle = zone.startAngle + zone.sweepAngle / 2;
          const labelPos = polarToCartesian(cx, cy, r + 14, midAngle - 90);
          return (
            <text
              key={`label-${zone.level}`}
              x={labelPos.x}
              y={labelPos.y}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={9}
              fontWeight={zone.level === level ? 700 : 400}
              fill={
                zone.level === level
                  ? confidenceColors[zone.level]
                  : "var(--muted)"
              }
            >
              {zone.label}
            </text>
          );
        })}
      </svg>
      {label && (
        <span className="text-muted-foreground text-xs font-medium">
          {label}
        </span>
      )}
    </div>
  );
}
