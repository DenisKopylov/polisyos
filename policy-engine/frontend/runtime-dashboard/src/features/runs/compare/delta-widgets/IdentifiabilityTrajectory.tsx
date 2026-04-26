import { useI18n } from "@/i18n/LocaleProvider";

import type { DeltaQuantity } from "../compare-types";

type IdentifiabilityTrajectoryProps = {
  deltas: DeltaQuantity[];
};

export function IdentifiabilityTrajectory({
  deltas,
}: IdentifiabilityTrajectoryProps) {
  const { t } = useI18n();
  return (
    <section className="panel space-y-3 rounded-[var(--radius-panel)] p-4">
      <div>
        <p className="eyebrow">
          {t("pages.runs.policyDiff.identifiabilityTitle")}
        </p>
        <h3 className="text-lg font-semibold">
          {t("pages.runs.policyDiff.identifiabilitySubtitle")}
        </h3>
      </div>
      <ol className="space-y-2">
        {deltas.slice(0, 6).map((delta) => (
          <li
            key={delta.metric_id}
            className="grid gap-2 sm:grid-cols-[1fr_auto_1fr]"
          >
            <IdentifiabilityPill
              label={t("pages.runs.policyDiff.runA")}
              value={delta.a?.uncertainty?.identifiability}
            />
            <span className="text-muted hidden text-center text-xs sm:block">
              {t("pages.runs.policyDiff.to")}
            </span>
            <IdentifiabilityPill
              label={delta.label}
              value={delta.b?.uncertainty?.identifiability}
            />
          </li>
        ))}
      </ol>
    </section>
  );
}

function IdentifiabilityPill({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined;
}) {
  const { t } = useI18n();
  return (
    <span className="border-line flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-sm">
      <span className="truncate">{label}</span>
      <span className="text-muted text-xs font-semibold uppercase">
        {value ?? t("pages.runs.policyDiff.unknown")}
      </span>
    </span>
  );
}
