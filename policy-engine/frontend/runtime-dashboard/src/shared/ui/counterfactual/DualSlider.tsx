import { useId } from "react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

type DualSliderProps = {
  label: string;
  min: number;
  max: number;
  step?: number;
  baselineValue: number;
  scenarioValue: number;
  onScenarioChange: (value: number) => void;
  constraintMessage?: string | null;
  className?: string;
};

export function DualSlider({
  label,
  min,
  max,
  step = 1,
  baselineValue,
  scenarioValue,
  onScenarioChange,
  constraintMessage,
  className,
}: DualSliderProps) {
  const { t } = useI18n();
  const id = useId();
  return (
    <div className={cn("space-y-2", className)}>
      <label className="text-sm font-semibold" htmlFor={id}>
        {label}
      </label>
      <div className="grid gap-2">
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted w-24">
            {t("shared.ui.counterfactual.baselineValue")}
          </span>
          <input
            aria-label={t("shared.ui.counterfactual.baselineValue")}
            className="accent-muted h-2 flex-1"
            disabled
            max={max}
            min={min}
            type="range"
            value={baselineValue}
          />
          <span className="w-16 text-right font-mono">{baselineValue}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted w-24">
            {t("shared.ui.counterfactual.scenarioValue")}
          </span>
          <input
            id={id}
            aria-describedby={
              constraintMessage ? `${id}-constraint` : undefined
            }
            aria-label={t("shared.ui.counterfactual.scenarioValue")}
            className="h-2 flex-1 accent-[var(--chart-info)]"
            max={max}
            min={min}
            step={step}
            type="range"
            value={scenarioValue}
            onChange={(event) => onScenarioChange(Number(event.target.value))}
          />
          <span className="w-16 text-right font-mono">{scenarioValue}</span>
        </div>
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
