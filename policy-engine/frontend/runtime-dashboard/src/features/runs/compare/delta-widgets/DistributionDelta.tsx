import { useI18n } from "@/i18n/LocaleProvider";

import { hasDistribution, saliencePercent } from "../compare-math";
import type { DeltaQuantity } from "../compare-types";

type DistributionDeltaProps = {
  deltas: DeltaQuantity[];
};

export function DistributionDelta({ deltas }: DistributionDeltaProps) {
  const { t } = useI18n();
  const visible = deltas.filter(hasDistribution).slice(0, 6);
  const rows = visible.length ? visible : deltas.slice(0, 6);
  return (
    <section className="panel space-y-3 rounded-[var(--radius-panel)] p-4">
      <div>
        <p className="eyebrow">
          {t("pages.runs.policyDiff.distributionTitle")}
        </p>
        <h3 className="text-lg font-semibold">
          {t("pages.runs.policyDiff.distributionSubtitle")}
        </h3>
      </div>
      <div className="space-y-3">
        {rows.map((delta) => (
          <div key={delta.metric_id} className="space-y-1">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-medium">{delta.label}</span>
              <span className="text-muted text-xs">
                {delta.delta_distribution?.ci_overlap === true
                  ? t("pages.runs.policyDiff.ciOverlaps")
                  : delta.delta_distribution?.ci_overlap === false
                    ? t("pages.runs.policyDiff.ciSeparates")
                    : t("pages.runs.policyDiff.ciUnknown")}
              </span>
            </div>
            <div className="bg-muted/25 h-2 rounded-full">
              <div
                className="h-2 rounded-full bg-[var(--color-transport-live)]"
                style={{ width: `${Math.max(saliencePercent(delta), 4)}%` }}
              />
            </div>
            <p className="text-muted text-xs">
              {t("pages.runs.policyDiff.meanShift")}{" "}
              {delta.delta_distribution?.mean_shift ??
                t("pages.runs.policyDiff.notAvailable")}{" "}
              · {t("pages.runs.policyDiff.medianShift")}{" "}
              {delta.delta_distribution?.median_shift ??
                t("pages.runs.policyDiff.notAvailable")}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
