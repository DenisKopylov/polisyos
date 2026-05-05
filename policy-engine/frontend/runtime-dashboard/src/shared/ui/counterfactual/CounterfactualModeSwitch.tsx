import type { CounterfactualMode } from "@/app/providers/scenario-scope";
import { useMaybeCounterfactual } from "@/app/providers/useCounterfactual";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

const MODES: CounterfactualMode[] = [
  "actual",
  "actual_vs_scenario",
  "scenario_only",
];

type CounterfactualModeSwitchProps = {
  value?: CounterfactualMode;
  onChange?: (mode: CounterfactualMode) => void;
  disabled?: boolean;
  className?: string;
};

export function CounterfactualModeSwitch({
  value,
  onChange,
  disabled = false,
  className,
}: CounterfactualModeSwitchProps) {
  const { t } = useI18n();
  const counterfactual = useMaybeCounterfactual();
  const activeMode = value ?? counterfactual?.mode ?? "actual";
  const handleChange =
    onChange ??
    ((mode: CounterfactualMode) => {
      counterfactual?.setMode(mode);
    });

  return (
    <div
      className={cn(
        "border-border bg-background inline-flex min-h-8 rounded-md border p-0.5",
        className,
      )}
      role="radiogroup"
      aria-label={t("shared.ui.counterfactual.modeSwitchLabel")}
    >
      {MODES.map((mode) => (
        <button
          key={mode}
          type="button"
          role="radio"
          aria-checked={activeMode === mode}
          disabled={disabled}
          className={cn(
            "focus-visible:ring-ring min-h-7 rounded px-2.5 text-xs font-semibold transition-colors focus-visible:ring-2 focus-visible:outline-none",
            activeMode === mode
              ? "bg-primary text-primary-foreground"
              : "text-muted hover:bg-muted/30",
          )}
          onClick={() => handleChange(mode)}
        >
          {t(`shared.ui.counterfactual.mode.${mode}`)}
        </button>
      ))}
    </div>
  );
}
