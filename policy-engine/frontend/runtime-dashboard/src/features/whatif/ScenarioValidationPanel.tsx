import type { ScenarioListPayload } from "@/api/validators";
import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

type ScenarioManifest = NonNullable<ScenarioListPayload["scenarios"]>[number];

type ScenarioValidationPanelProps = {
  scenario: ScenarioManifest | null;
  unsupportedReasons?: string[];
  className?: string;
};

export function ScenarioValidationPanel({
  scenario,
  unsupportedReasons = [],
  className,
}: ScenarioValidationPanelProps) {
  const { t } = useI18n();
  const staleReasons = scenario?.stale_reasons ?? [];
  const hasIssues = staleReasons.length > 0 || unsupportedReasons.length > 0;
  return (
    <section className={cn("border-border rounded-md border p-3", className)}>
      <h3 className="text-sm font-semibold">
        {t("shared.ui.counterfactual.validation")}
      </h3>
      {!hasIssues ? (
        <p className="text-muted mt-1 text-sm">
          {t("shared.ui.counterfactual.validationReady")}
        </p>
      ) : (
        <ul className="text-muted mt-2 list-inside list-disc text-sm">
          {[...staleReasons, ...unsupportedReasons].map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
