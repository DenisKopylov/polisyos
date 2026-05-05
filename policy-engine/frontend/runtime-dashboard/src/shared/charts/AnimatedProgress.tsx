import { motion, useReducedMotion } from "motion/react";

import { cn } from "@/shared/lib/utils";
import { classifyConfidence, confidenceColor } from "./types";

type AnimatedProgressProps = {
  value: number;
  max?: number;
  label?: string;
  showValue?: boolean;
  colorByConfidence?: boolean;
  color?: string;
  height?: number;
  className?: string;
};

export function AnimatedProgress({
  value,
  max = 100,
  label,
  showValue = true,
  colorByConfidence = false,
  color,
  height = 8,
  className,
}: AnimatedProgressProps) {
  const prefersReduced = useReducedMotion();
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const roundedPct = Math.round(pct);
  const accessibleLabel = label ?? `${roundedPct}%`;

  const resolvedColor =
    color ??
    (colorByConfidence
      ? confidenceColor(classifyConfidence(value / max))
      : "var(--teal)");

  return (
    <div
      className={cn("w-full", className)}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={accessibleLabel}
      aria-valuetext={`${roundedPct}%`}
    >
      {(label || showValue) && (
        <div className="mb-1.5 flex items-baseline justify-between gap-2">
          {label && (
            <span className="text-muted-foreground text-xs font-medium">
              {label}
            </span>
          )}
          {showValue && (
            <span className="text-foreground text-xs font-semibold tabular-nums">
              {roundedPct}%
            </span>
          )}
        </div>
      )}
      <div
        className="bg-muted w-full overflow-hidden rounded-full"
        style={{ height }}
      >
        <motion.div
          className="rounded-full"
          style={{ height, backgroundColor: resolvedColor }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={
            prefersReduced
              ? { duration: 0 }
              : { duration: 0.5, ease: [0.2, 0, 0, 1] }
          }
        />
      </div>
    </div>
  );
}
