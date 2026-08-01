import type { ScenarioManifest } from "@polisyos/runtime-api-client";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

type ScenarioValidationProjection = Pick<
  ScenarioManifest,
  "known_limitations" | "stale_reasons" | "status"
>;

type ScenarioValidationPanelProps = {
  scenario: ScenarioValidationProjection | null;
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
  const limitations = scenario?.known_limitations ?? [];
  const ownerState = scenario?.status ?? "scenario unavailable";
  const findings = [...staleReasons, ...unsupportedReasons, ...limitations];
  return (
    <section className={cn("border-border rounded-md border p-3", className)}>
      <h3 className="text-sm font-semibold">
        {t("shared.ui.counterfactual.validation")}
      </h3>
      <p className="text-muted mt-1 text-sm">{ownerState}</p>
      {findings.length > 0 ? (
        <ul className="text-muted mt-2 list-inside list-disc text-sm">
          {findings.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
