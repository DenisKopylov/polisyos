import { motion, useReducedMotion } from "motion/react";

import { cn } from "@/shared/lib/utils";

import {
  ChartQuantityEvidence,
  chartQuantityMembers,
  chartQuantityScalarPoint,
  type ChartQuantityInput,
} from "./quantityChartSemantics";
import type { QuantityFormatOptions } from "@/shared/ui/quantity/quantity-format";

type AnimatedNumberProps = {
  value: ChartQuantityInput;
  formatOptions?: Pick<QuantityFormatOptions, "maximumFractionDigits">;
  duration?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
};

export function AnimatedNumber({
  value,
  formatOptions,
  duration = 0.6,
  prefix = "",
  suffix = "",
  className,
}: AnimatedNumberProps) {
  const prefersReduced = useReducedMotion();
  const members = chartQuantityMembers(value);
  const scalarPoint = chartQuantityScalarPoint(value);
  const animationKey = members
    .map((member) => `${member.metric_id ?? member.lineage.id}:${member.point}`)
    .join("|");

  return (
    <motion.span
      key={animationKey}
      className={cn("tabular-nums", className)}
      data-testid="animated-number"
      aria-live="polite"
      aria-atomic="true"
      initial={
        prefersReduced || scalarPoint === null ? false : { opacity: 0, y: 4 }
      }
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration }}
    >
      {prefix}
      <ChartQuantityEvidence
        value={value}
        precision={formatOptions?.maximumFractionDigits}
      />
      {suffix}
    </motion.span>
  );
}
