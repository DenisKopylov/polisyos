import { useId } from "react";

import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

type DualInputProps = {
  label: string;
  baselineValue: number;
  scenarioValue: number;
  onScenarioChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  constraintMessage?: string | null;
  className?: string;
};

export function DualInput({
  label,
  baselineValue,
  scenarioValue,
  onScenarioChange,
  min,
  max,
  step,
  constraintMessage,
  className,
}: DualInputProps) {
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
          <input
            className="border-border bg-muted/20 min-h-9 w-full rounded-md border px-2 font-mono"
            readOnly
            value={baselineValue}
          />
        </label>
        <label className="space-y-1 text-xs" htmlFor={id}>
          <span className="text-muted">
            {t("shared.ui.counterfactual.scenarioValue")}
          </span>
          <input
            id={id}
            aria-describedby={
              constraintMessage ? `${id}-constraint` : undefined
            }
            className="border-border bg-background focus-visible:ring-ring min-h-9 w-full rounded-md border px-2 font-mono focus-visible:ring-2 focus-visible:outline-none"
            max={max}
            min={min}
            step={step}
            type="number"
            value={scenarioValue}
            onChange={(event) => onScenarioChange(Number(event.target.value))}
          />
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
