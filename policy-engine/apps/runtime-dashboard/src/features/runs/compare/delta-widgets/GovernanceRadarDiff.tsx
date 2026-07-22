import { useI18n } from "@/shared/i18n/LocaleProvider";

import type { DeltaQuantity } from "../compare-types";

type GovernanceRadarDiffProps = {
  deltas: DeltaQuantity[];
};

export function GovernanceRadarDiff({ deltas }: GovernanceRadarDiffProps) {
  const { t } = useI18n();
  const top = deltas[0];
  return (
    <section
      className="panel space-y-3 rounded-[var(--radius-panel)] p-4"
      data-testid="governance-radar-diff"
    >
      <div>
        <p className="eyebrow">{t("pages.runs.policyDiff.governanceTitle")}</p>
        <h3 className="text-lg font-semibold">
          {t("pages.runs.policyDiff.governanceSubtitle")}
        </h3>
      </div>
      {top ? (
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <ProducerFact label="significance">
            <span className="text-muted" data-testid="governance-significance">
              {top.significance}
            </span>
          </ProducerFact>
          <ProducerFact label="decision_salience">
            {String(top.decision_salience)}
          </ProducerFact>
          <ProducerFact label="source_changed">
            {String(top.lineage_delta.source_changed)}
          </ProducerFact>
          <ProducerFact label="verification_changed">
            {top.lineage_delta.verification_changed ?? t("common.unavailable")}
          </ProducerFact>
        </dl>
      ) : (
        <p className="text-muted text-sm">{t("common.unavailable")}</p>
      )}
    </section>
  );
}

function ProducerFact({
  children,
  label,
}: {
  children: React.ReactNode;
  label: string;
}) {
  return (
    <div className="border-line rounded-lg border p-3">
      <dt className="font-mono text-xs">{label}</dt>
      <dd className="text-muted mt-1 break-words">{children}</dd>
    </div>
  );
}
