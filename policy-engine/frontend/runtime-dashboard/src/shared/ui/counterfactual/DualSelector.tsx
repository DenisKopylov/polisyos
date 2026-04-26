import { useId } from "react";

import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

type DualSelectorOption = {
  value: string;
  label: string;
};

type DualSelectorProps = {
  label: string;
  options: DualSelectorOption[];
  baselineValue: string;
  scenarioValue: string;
  onScenarioChange: (value: string) => void;
  constraintMessage?: string | null;
  className?: string;
};

export function DualSelector({
  label,
  options,
  baselineValue,
  scenarioValue,
  onScenarioChange,
  constraintMessage,
  className,
}: DualSelectorProps) {
  const { t } = useI18n();
  const id = useId();
  return (
    <div className={cn("space-y-2", className)}>
      <p className="text-sm font-semibold">{label}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <label className="space-y-1 text-xs">
          <span className="text-muted">
            {t("shared.ui.counterfactual.baselineValue")}
          </span>
          <select
            className="border-border bg-muted/20 min-h-9 w-full rounded-md border px-2"
            disabled
            value={baselineValue}
          >
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-xs" htmlFor={id}>
          <span className="text-muted">
            {t("shared.ui.counterfactual.scenarioValue")}
          </span>
          <select
            id={id}
            aria-describedby={
              constraintMessage ? `${id}-constraint` : undefined
            }
            className="border-border bg-background focus-visible:ring-ring min-h-9 w-full rounded-md border px-2 focus-visible:ring-2 focus-visible:outline-none"
            value={scenarioValue}
            onChange={(event) => onScenarioChange(event.target.value)}
          >
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {constraintMessage ? (
        <p
          id={`${id}-constraint`}
          className="text-xs text-[var(--chart-warning)]"
        >
          {constraintMessage}
        </p>
      ) : null}
    </div>
  );
}
