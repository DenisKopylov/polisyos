import { useI18n } from "@/i18n/LocaleProvider";
import { Quantity } from "@/shared/ui/quantity";

import type { DeltaQuantity } from "../compare-types";

type BudgetFlowDiffProps = {
  deltas: DeltaQuantity[];
};

export function BudgetFlowDiff({ deltas }: BudgetFlowDiffProps) {
  const { t } = useI18n();
  const budgetDeltas = deltas.filter((delta) =>
    /budget|cost|spend|fiscal/i.test(delta.metric_id),
  );
  const visible = budgetDeltas.length ? budgetDeltas : deltas.slice(0, 3);
  return (
    <section className="panel space-y-3 rounded-[var(--radius-panel)] p-4">
      <div>
        <p className="eyebrow">{t("pages.runs.policyDiff.budgetTitle")}</p>
        <h3 className="text-lg font-semibold">
          {t("pages.runs.policyDiff.budgetSubtitle")}
        </h3>
      </div>
      <div className="space-y-2">
        {visible.map((delta) => (
          <div
            key={delta.metric_id}
            className="border-line flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3"
          >
            <span className="font-medium">{delta.label}</span>
            {delta.delta_absolute ? (
              <Quantity
                value={delta.delta_absolute}
                variant="dense"
                provenanceMode="auto"
              />
            ) : (
              <span className="text-muted text-sm">
                {t("pages.runs.policyDiff.notAvailable")}
              </span>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
