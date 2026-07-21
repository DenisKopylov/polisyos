import { Minus, TrendingDown, TrendingUp } from "lucide-react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

import { counterfactualTokens } from "./counterfactual-colors";
import { Quantity } from "../quantity/Quantity";
import type { QuantityValue } from "../quantity/quantity.types";

type CounterfactualDeltaProps = {
  value: QuantityValue;
  className?: string;
};

export function CounterfactualDelta({
  value,
  className,
}: CounterfactualDeltaProps) {
  const { t } = useI18n();
  const point = value.point;
  const hasPoint = typeof point === "number" && Number.isFinite(point);
  const Icon = hasPoint
    ? point > 0
      ? TrendingUp
      : point < 0
        ? TrendingDown
        : Minus
    : Minus;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1",
        counterfactualTokens.delta.className,
        className,
      )}
      aria-label={
        hasPoint
          ? t("shared.ui.counterfactual.deltaAria", { value: point })
          : undefined
      }
      data-counterfactual-value-state={hasPoint ? "scalar" : "unknown"}
      data-testid="counterfactual-delta"
    >
      <Icon className="size-3.5" aria-hidden="true" />
      <Quantity value={value} variant="dense" provenanceMode="auto" />
    </span>
  );
}
