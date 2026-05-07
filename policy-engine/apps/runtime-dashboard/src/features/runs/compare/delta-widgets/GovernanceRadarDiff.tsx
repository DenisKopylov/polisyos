import { useI18n } from "@/shared/i18n/LocaleProvider";

import { saliencePercent } from "../compare-math";
import type { DeltaQuantity } from "../compare-types";

type GovernanceRadarDiffProps = {
  deltas: DeltaQuantity[];
};

const AXES = ["materiality", "uncertainty", "provenance", "risk"] as const;

export function GovernanceRadarDiff({ deltas }: GovernanceRadarDiffProps) {
  const { t } = useI18n();
  const top = deltas[0];
  const values = AXES.map((axis) => ({
    axis,
    value: axisValue(axis, top),
  }));
  return (
    <section className="panel space-y-3 rounded-[var(--radius-panel)] p-4">
      <div>
        <p className="eyebrow">{t("pages.runs.policyDiff.governanceTitle")}</p>
        <h3 className="text-lg font-semibold">
          {t("pages.runs.policyDiff.governanceSubtitle")}
        </h3>
      </div>
      <div className="space-y-3">
        {values.map(({ axis, value }) => (
          <div key={axis}>
            <div className="mb-1 flex justify-between text-sm">
              <span>{t(`pages.runs.policyDiff.axis.${axis}`)}</span>
              <span className="text-muted">{value}%</span>
            </div>
            <div className="bg-muted/25 h-2 rounded-full">
              <div
                className="h-2 rounded-full bg-[var(--color-status-pending)]"
                style={{ width: `${Math.max(value, 4)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function axisValue(
  axis: (typeof AXES)[number],
  delta: DeltaQuantity | undefined,
) {
  if (!delta) {
    return 0;
  }
  if (axis === "materiality") {
    return saliencePercent(delta);
  }
  if (axis === "uncertainty") {
    return delta.significance === "uncertain" ? 80 : 30;
  }
  if (axis === "provenance") {
    return delta.lineage_delta.source_changed ||
      delta.lineage_delta.verification_changed
      ? 75
      : 20;
  }
  return delta.significance === "worsened" ? 85 : 25;
}
