import type { ScenarioListPayload } from "@/api/validators";
import { useI18n } from "@/i18n/LocaleProvider";
import { DualInput, DualSlider } from "@/shared/ui/counterfactual";

type ScenarioManifest = NonNullable<ScenarioListPayload["scenarios"]>[number];
type ScenarioIntervention = ScenarioManifest["interventions"][number];

type ScenarioInterventionEditorProps = {
  intervention: ScenarioIntervention;
  onScenarioValueChange?: (value: number) => void;
};

export function ScenarioInterventionEditor({
  intervention,
  onScenarioValueChange,
}: ScenarioInterventionEditorProps) {
  const { t } = useI18n();
  const baselinePoint = intervention.baseline_value?.point ?? 0;
  const scenarioPoint = intervention.value.point ?? baselinePoint;
  const min = Math.min(baselinePoint, scenarioPoint) * 0.5;
  const max = Math.max(baselinePoint, scenarioPoint) * 1.5 || 1;
  const label =
    intervention.value.label ??
    intervention.baseline_value?.label ??
    intervention.field;
  const constraintIds = intervention.constraint_ids ?? [];
  const constraintMessage = constraintIds.length
    ? t("shared.ui.counterfactual.constraintHint", {
        count: constraintIds.length,
      })
    : null;

  if (!onScenarioValueChange) {
    return (
      <DualInput
        baselineValue={baselinePoint}
        constraintMessage={constraintMessage}
        label={label}
        scenarioValue={scenarioPoint}
        onScenarioChange={() => undefined}
      />
    );
  }

  return (
    <DualSlider
      baselineValue={baselinePoint}
      constraintMessage={constraintMessage}
      label={label}
      max={max}
      min={min}
      scenarioValue={scenarioPoint}
      step={(max - min) / 100}
      onScenarioChange={onScenarioValueChange}
    />
  );
}
