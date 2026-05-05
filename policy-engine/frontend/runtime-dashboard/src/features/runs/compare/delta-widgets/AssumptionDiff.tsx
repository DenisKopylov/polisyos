import { useI18n } from "@/shared/i18n/LocaleProvider";

import type { ComparisonFrame, DeltaQuantity } from "../compare-types";

type AssumptionDiffProps = {
  frame: ComparisonFrame;
  deltas: DeltaQuantity[];
};

export function AssumptionDiff({ deltas, frame }: AssumptionDiffProps) {
  const { t } = useI18n();
  return (
    <section className="panel space-y-3 rounded-[var(--radius-panel)] p-4">
      <div>
        <p className="eyebrow">{t("pages.runs.policyDiff.assumptionTitle")}</p>
        <h3 className="text-lg font-semibold">
          {t("pages.runs.policyDiff.assumptionSubtitle")}
        </h3>
      </div>
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted text-xs font-semibold uppercase">
            {t("pages.runs.policyDiff.scenario")}
          </dt>
          <dd className="mt-1">
            {frame.temporal_scope?.scenario_id ??
              t("pages.runs.policyDiff.observedBaseline")}
          </dd>
        </div>
        <div>
          <dt className="text-muted text-xs font-semibold uppercase">
            {t("pages.runs.policyDiff.metrics")}
          </dt>
          <dd className="mt-1">{deltas.length}</dd>
        </div>
      </dl>
      {frame.assumption_set?.length ? (
        <ul className="space-y-1 text-sm">
          {frame.assumption_set.map((assumption) => (
            <li key={assumption}>{assumption}</li>
          ))}
        </ul>
      ) : (
        <p className="text-muted text-sm">
          {t("pages.runs.policyDiff.noAssumptions")}
        </p>
      )}
    </section>
  );
}
