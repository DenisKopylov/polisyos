import { AlertTriangle, CheckCircle2, CircleSlash } from "lucide-react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Badge } from "@polisyos/atlas-ui";

import { comparabilityTone } from "./compare-math";
import type { ComparabilityReport, ComparisonFrame } from "./compare-types";

type ComparisonFramePanelProps = {
  frame: ComparisonFrame;
  comparability: ComparabilityReport;
};

export function ComparisonFramePanel({
  comparability,
  frame,
}: ComparisonFramePanelProps) {
  const { t } = useI18n();
  const Icon =
    comparability.status === "compatible"
      ? CheckCircle2
      : comparability.status === "warning"
        ? AlertTriangle
        : CircleSlash;
  return (
    <section
      className="panel space-y-4 rounded-[var(--radius-panel)] p-4"
      aria-label={t("pages.runs.policyDiff.comparisonFrame")}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow">
            {t("pages.runs.policyDiff.comparisonFrame")}
          </p>
          <h2 className="text-xl font-semibold">
            {frame.run_a} {t("pages.runs.policyDiff.to")} {frame.run_b}
          </h2>
          <p className="text-muted mt-1 text-sm">
            {t("pages.runs.policyDiff.comparableMetrics", {
              count: frame.metric_set?.length ?? 0,
            })}{" "}
            · {frame.population ?? t("pages.runs.policyDiff.populationUnknown")}{" "}
            · {frame.unit_policy}
          </p>
        </div>
        <Badge kind={comparabilityTone(comparability.status)}>
          <Icon className="mr-1.5 size-3.5" aria-hidden="true" />
          {t(`pages.runs.policyDiff.status.${comparability.status}`)}
        </Badge>
      </div>

      <dl className="grid gap-3 text-sm md:grid-cols-3">
        <div>
          <dt className="text-muted text-xs font-semibold uppercase">
            {t("pages.runs.policyDiff.policyTime")}
          </dt>
          <dd className="mt-1 break-words">
            {frame.temporal_scope?.valid_at ??
              t("pages.runs.policyDiff.current")}
          </dd>
        </div>
        <div>
          <dt className="text-muted text-xs font-semibold uppercase">
            {t("pages.runs.policyDiff.knowledgeTime")}
          </dt>
          <dd className="mt-1 break-words">
            {frame.temporal_scope?.tx_at ?? t("pages.runs.policyDiff.latest")}
          </dd>
        </div>
        <div>
          <dt className="text-muted text-xs font-semibold uppercase">
            {t("pages.runs.policyDiff.scenario")}
          </dt>
          <dd className="mt-1 break-words">
            {frame.temporal_scope?.scenario_id ??
              t("pages.runs.policyDiff.observed")}
          </dd>
        </div>
      </dl>

      {comparability.warnings?.length ? (
        <div className="border-line rounded-lg border p-3">
          <p className="text-sm font-semibold">
            {t("pages.runs.policyDiff.warnings")}
          </p>
          <ul className="mt-2 space-y-1 text-sm">
            {comparability.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {comparability.blocked_reasons?.length ? (
        <div className="border-danger/30 bg-danger/5 rounded-lg border p-3">
          <p className="text-sm font-semibold">
            {t("pages.runs.policyDiff.blockedReasons")}
          </p>
          <ul className="mt-2 space-y-1 text-sm">
            {comparability.blocked_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
