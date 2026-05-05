import type { ScenarioListPayload } from "@/api/validators";
import { useMaybeCounterfactual } from "@/app/providers/useCounterfactual";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

import { CounterfactualBadge } from "./CounterfactualBadge";

type Scenario = NonNullable<ScenarioListPayload["scenarios"]>[number];

type ScenarioPickerProps = {
  scenarios?: Scenario[];
  value?: string | null;
  onChange?: (scenarioId: string | null) => void;
  disabledReason?: string | null;
  className?: string;
};

export function ScenarioPicker({
  scenarios = [],
  value,
  onChange,
  disabledReason,
  className,
}: ScenarioPickerProps) {
  const { t } = useI18n();
  const counterfactual = useMaybeCounterfactual();
  const selectedId = value ?? counterfactual?.scenarioId ?? "";
  const disabled = Boolean(disabledReason) || scenarios.length === 0;
  const handleChange =
    onChange ??
    ((scenarioId: string | null) => {
      counterfactual?.setScenarioId(scenarioId);
      if (scenarioId && counterfactual?.mode === "actual") {
        counterfactual.setMode("actual_vs_scenario");
      }
    });
  const selected = scenarios.find((scenario) => scenario.id === selectedId);

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between gap-2">
        <label className="text-xs font-semibold" htmlFor="scenario-picker">
          {t("shared.ui.counterfactual.scenario")}
        </label>
        {selected ? (
          <CounterfactualBadge
            status={selected.status}
            mode="actual_vs_scenario"
          />
        ) : null}
      </div>
      <select
        id="scenario-picker"
        className="border-border bg-background focus-visible:ring-ring min-h-9 w-full rounded-md border px-2 text-sm focus-visible:ring-2 focus-visible:outline-none disabled:opacity-60"
        disabled={disabled}
        value={selectedId}
        onChange={(event) => handleChange(event.target.value || null)}
      >
        <option value="">
          {disabled
            ? t("shared.ui.counterfactual.noScenarioSupport")
            : t("shared.ui.counterfactual.chooseScenario")}
        </option>
        {scenarios.map((scenario) => (
          <option key={scenario.id} value={scenario.id}>
            {scenario.policy_question} ·{" "}
            {t(`shared.ui.counterfactual.status.${scenario.status}`)}
          </option>
        ))}
      </select>
      {disabledReason ? (
        <p className="text-muted text-xs">{disabledReason}</p>
      ) : null}
    </div>
  );
}
