import { useI18n } from "@/shared/i18n/LocaleProvider";

import { saliencePercent } from "../compare-math";
import type { DeltaQuantity } from "../compare-types";

type SubgroupDeltaMatrixProps = {
  deltas: DeltaQuantity[];
};

export function SubgroupDeltaMatrix({ deltas }: SubgroupDeltaMatrixProps) {
  const { t } = useI18n();
  return (
    <section className="panel space-y-3 rounded-[var(--radius-panel)] p-4">
      <div>
        <p className="eyebrow">{t("pages.runs.policyDiff.subgroupTitle")}</p>
        <h3 className="text-lg font-semibold">
          {t("pages.runs.policyDiff.subgroupSubtitle")}
        </h3>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {deltas.slice(0, 8).map((delta) => (
          <div
            key={delta.metric_id}
            className="border-line rounded-lg border p-3"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-semibold">{delta.label}</span>
              <span className="text-muted text-xs">
                {saliencePercent(delta)}%
              </span>
            </div>
            <p className="text-muted mt-2 text-xs">
              {t("pages.runs.policyDiff.subgroupPending", {
                significance: t(
                  `pages.runs.policyDiff.significance.${delta.significance}`,
                ),
              })}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
