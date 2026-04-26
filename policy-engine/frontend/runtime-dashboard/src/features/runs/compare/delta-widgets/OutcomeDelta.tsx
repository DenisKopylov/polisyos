import { useI18n } from "@/i18n/LocaleProvider";
import { Quantity } from "@/shared/ui/quantity";

import { formatSignedNumber, significanceTone } from "../compare-math";
import type { DeltaQuantity } from "../compare-types";

type OutcomeDeltaProps = {
  deltas: DeltaQuantity[];
  activeMetricId?: string | null;
};

export function OutcomeDelta({ activeMetricId, deltas }: OutcomeDeltaProps) {
  const { t } = useI18n();
  const visible = activeMetricId
    ? deltas.filter((delta) => delta.metric_id === activeMetricId)
    : deltas.slice(0, 5);
  return (
    <section className="panel space-y-3 rounded-[var(--radius-panel)] p-4">
      <div>
        <p className="eyebrow">{t("pages.runs.policyDiff.outcomeTitle")}</p>
        <h3 className="text-lg font-semibold">
          {t("pages.runs.policyDiff.outcomeSubtitle")}
        </h3>
      </div>
      <div className="space-y-3">
        {visible.map((delta) => (
          <article
            key={delta.metric_id}
            className="border-line rounded-lg border p-3"
            aria-label={`${delta.label} ${t(
              `pages.runs.policyDiff.significance.${delta.significance}`,
            )}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h4 className="font-semibold">{delta.label}</h4>
                <p className="text-muted text-sm">
                  {t(
                    `pages.runs.policyDiff.significance.${delta.significance}`,
                  )}
                </p>
              </div>
              <span
                className={`rounded-full px-2 py-1 text-xs font-semibold ${toneClass(
                  significanceTone(delta.significance),
                )}`}
              >
                {formatSignedNumber(delta.delta_absolute?.point)}
              </span>
            </div>
            <div className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
              <MetricCell
                label={t("pages.runs.policyDiff.runA")}
                value={delta.a}
              />
              <MetricCell
                label={t("pages.runs.policyDiff.runB")}
                value={delta.b}
              />
              <MetricCell
                label={t("pages.runs.policyDiff.delta")}
                value={delta.delta_absolute}
              />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function MetricCell({
  label,
  value,
}: {
  label: string;
  value: DeltaQuantity["a"];
}) {
  const { t } = useI18n();
  return (
    <div>
      <p className="text-muted text-xs font-semibold uppercase">{label}</p>
      <div className="mt-1">
        {value ? (
          <Quantity value={value} variant="dense" provenanceMode="auto" />
        ) : (
          <span className="text-muted text-sm">
            {t("pages.runs.policyDiff.notAvailable")}
          </span>
        )}
      </div>
    </div>
  );
}

function toneClass(tone: "ok" | "fail" | "warn" | "neutral") {
  if (tone === "ok") {
    return "bg-[color-mix(in_srgb,var(--color-status-approved)_14%,transparent)] text-[var(--color-status-approved)]";
  }
  if (tone === "fail") {
    return "bg-[color-mix(in_srgb,var(--color-status-rejected)_14%,transparent)] text-[var(--color-status-rejected)]";
  }
  if (tone === "warn") {
    return "bg-[color-mix(in_srgb,var(--color-status-pending)_16%,transparent)] text-[var(--color-status-pending)]";
  }
  return "bg-muted/30 text-muted";
}
