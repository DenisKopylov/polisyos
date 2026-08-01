import type { QuantityValueOutput } from "@polisyos/runtime-api-client";
import { Quantity } from "@/shared/ui/quantity";
import {
  finiteInterval,
  finitePoint,
  type QuantityFormatOptions,
} from "@/shared/ui/quantity/quantity-format";
import { cn } from "@/shared/lib/utils";

export type ChartQuantityInput =
  | QuantityValueOutput
  | readonly QuantityValueOutput[];

export function chartQuantityMembers(
  input: ChartQuantityInput,
): readonly QuantityValueOutput[] {
  return Array.isArray(input) ? input : [input as QuantityValueOutput];
}

export function chartQuantityScalarPoint(
  input: ChartQuantityInput | null | undefined,
): number | null {
  if (input == null) {
    return null;
  }
  const members = chartQuantityMembers(input);
  if (members.length !== 1) {
    return null;
  }
  const point = members[0]?.point;
  return finitePoint(point) ? point : null;
}

export function chartQuantityInterval(
  input: ChartQuantityInput | null | undefined,
): readonly [number, number] | null {
  if (input == null) {
    return null;
  }
  const members = chartQuantityMembers(input);
  if (members.length !== 1) {
    return null;
  }
  return (
    finiteInterval(members[0]?.uncertainty?.ci_95) ??
    finiteInterval(members[0]?.uncertainty?.ci_80)
  );
}

export function ChartQuantityEvidence({
  value,
  className,
  format,
  precision,
}: {
  value: ChartQuantityInput;
  className?: string;
  format?: QuantityFormatOptions["format"];
  precision?: number;
}) {
  const members = chartQuantityMembers(value);
  return (
    <span
      className={cn("inline-flex flex-wrap items-center gap-1.5", className)}
      data-chart-quantity-cardinality={members.length}
      data-testid="chart-quantity-evidence"
    >
      {members.map((quantity, index) => {
        const pointNullEvidence = chartQuantityPointNullEvidence(quantity);
        const quantityProps = {
          value: quantity,
          format,
          precision,
          variant: "dense" as const,
        };
        const key = `${quantity.metric_id ?? quantity.lineage.id}:${index}`;

        return pointNullEvidence === null ? (
          <Quantity key={key} {...quantityProps} />
        ) : (
          <Quantity
            key={key}
            {...quantityProps}
            absentValue={pointNullEvidence}
            absentValueLabel={pointNullEvidence}
          />
        );
      })}
    </span>
  );
}

function chartQuantityPointNullEvidence(
  quantity: QuantityValueOutput,
): string | null {
  if (finitePoint(quantity.point)) {
    return null;
  }

  const evidence = Object.entries(quantity.uncertainty?.quantiles ?? {})
    .filter(([, value]) => finitePoint(value))
    .map(([key, value]) => `${key}: ${value}`);
  for (const [key, value] of [
    ["ci_95", quantity.uncertainty?.ci_95],
    ["ci_80", quantity.uncertainty?.ci_80],
  ] as const) {
    const interval = finiteInterval(value);
    if (interval) {
      evidence.push(`${key}: [${interval[0]}, ${interval[1]}]`);
    }
  }

  return evidence.length === 0 ? null : evidence.join(", ");
}
