import { useI18n } from "@/i18n/LocaleProvider";
import { Badge } from "@/shared/ui";

import type { DeltaQuantity } from "../compare-types";

type ProvenanceDriftProps = {
  deltas: DeltaQuantity[];
};

export function ProvenanceDrift({ deltas }: ProvenanceDriftProps) {
  const { t } = useI18n();
  const changed = deltas.filter(
    (delta) =>
      delta.lineage_delta.source_changed ||
      delta.lineage_delta.model_changed ||
      delta.lineage_delta.hash_changed ||
      delta.lineage_delta.freshness_changed ||
      delta.lineage_delta.verification_changed,
  );
  const visible = changed.length ? changed : deltas.slice(0, 5);
  return (
    <section className="panel space-y-3 rounded-[var(--radius-panel)] p-4">
      <div>
        <p className="eyebrow">{t("pages.runs.policyDiff.provenanceTitle")}</p>
        <h3 className="text-lg font-semibold">
          {t("pages.runs.policyDiff.provenanceSubtitle")}
        </h3>
      </div>
      <div className="space-y-2">
        {visible.map((delta) => (
          <article
            key={delta.metric_id}
            className="border-line rounded-lg border p-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h4 className="font-medium">{delta.label}</h4>
              <Badge kind={changed.includes(delta) ? "warn" : "neutral"}>
                {changed.includes(delta)
                  ? t("pages.runs.policyDiff.changed")
                  : t("pages.runs.policyDiff.stable")}
              </Badge>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <DriftPill
                active={delta.lineage_delta.source_changed}
                label={t("pages.runs.policyDiff.source")}
              />
              <DriftPill
                active={delta.lineage_delta.model_changed}
                label={t("pages.runs.policyDiff.model")}
              />
              <DriftPill
                active={delta.lineage_delta.hash_changed}
                label={t("pages.runs.policyDiff.hash")}
              />
              <DriftPill
                active={Boolean(delta.lineage_delta.verification_changed)}
                label={
                  delta.lineage_delta.verification_changed ??
                  t("pages.runs.policyDiff.verification")
                }
              />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function DriftPill({ active, label }: { active: boolean; label: string }) {
  return (
    <span
      className={[
        "rounded-full border px-2 py-1 text-xs font-semibold",
        active
          ? "border-[var(--color-status-pending)] text-[var(--color-status-pending)]"
          : "border-line text-muted",
      ].join(" ")}
    >
      {label}
    </span>
  );
}
