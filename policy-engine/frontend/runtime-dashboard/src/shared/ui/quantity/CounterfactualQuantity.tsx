import type { ComponentPropsWithoutRef } from "react";

import type { TemporalScope } from "@/app/providers/temporal-scope";
import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";
import { CounterfactualBadge } from "@/shared/ui/counterfactual/CounterfactualBadge";
import { CounterfactualDelta } from "@/shared/ui/counterfactual/CounterfactualDelta";

import { Quantity } from "./Quantity";
import type { CounterfactualMetric } from "./quantity.types";

type CounterfactualQuantityProps = {
  value: CounterfactualMetric;
  variant?: "inline" | "table" | "hero" | "dense";
  temporalScope?: TemporalScope | null;
} & Omit<ComponentPropsWithoutRef<"span">, "children" | "value">;

export function CounterfactualQuantity({
  value,
  variant = "inline",
  temporalScope,
  className,
  ...rest
}: CounterfactualQuantityProps) {
  const { t } = useI18n();
  const validationError = validateCounterfactualMetric(value);
  if (validationError) {
    return (
      <span
        {...rest}
        className={cn(
          "inline-flex min-h-8 items-center gap-2 rounded-md border border-[color-mix(in_srgb,var(--color-status-rejected)_30%,transparent)] px-2 py-1 text-xs font-semibold",
          className,
        )}
        role="status"
      >
        {t("shared.ui.counterfactual.invalidScenarioValue")}
      </span>
    );
  }

  return (
    <span
      {...rest}
      className={cn("inline-flex flex-wrap items-center gap-2", className)}
      aria-label={t("shared.ui.counterfactual.quantityAria", {
        label: value.label,
        scenarioId: value.scenario_ref.id,
      })}
      data-scenario-id={value.scenario_ref.id}
      data-scenario-status={value.scenario_ref.status}
    >
      <span className="inline-flex items-center gap-1.5">
        <span className="text-muted text-xs font-semibold">
          {t("shared.ui.counterfactual.actual")}
        </span>
        <Quantity
          aria-label={t("shared.ui.counterfactual.actualValueAria", {
            label: value.label,
          })}
          value={value.actual}
          variant={variant}
          temporalScope={temporalScope}
        />
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="text-muted text-xs font-semibold">
          {t("shared.ui.counterfactual.scenario")}
        </span>
        <Quantity
          aria-label={t("shared.ui.counterfactual.scenarioValueAria", {
            label: value.label,
            scenarioId: value.scenario_ref.id,
          })}
          value={value.counterfactual}
          variant={variant}
          temporalScope={temporalScope}
        />
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="text-muted text-xs font-semibold">
          {t("shared.ui.counterfactual.delta")}
        </span>
        <CounterfactualDelta value={value.delta} />
      </span>
      <CounterfactualBadge
        mode="actual_vs_scenario"
        status={value.scenario_ref.status}
      />
    </span>
  );
}

function validateCounterfactualMetric(value: CounterfactualMetric) {
  if (!value.scenario_ref?.id) {
    return "missing_scenario_ref";
  }
  if (
    !value.scenario_ref.assumption_ids?.length ||
    !value.assumption_ids.length
  ) {
    return "missing_assumptions";
  }
  if (value.counterfactual.time?.scenario_id !== value.scenario_ref.id) {
    return "counterfactual_scenario_mismatch";
  }
  if (value.delta.time?.scenario_id !== value.scenario_ref.id) {
    return "delta_scenario_mismatch";
  }
  return null;
}
