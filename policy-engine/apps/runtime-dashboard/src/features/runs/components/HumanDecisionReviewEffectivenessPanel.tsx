import { Badge, Card } from "@polisyos/atlas-ui";

import type { HumanDecisionReviewEffectiveness } from "@/features/runs/api/useHumanDecisions";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  authorityStatusBadgeProps,
  issueHumanDecisionReviewCoveragePresentation,
} from "@/shared/ui/AuthorityStatusPresentation";

export function HumanDecisionReviewEffectivenessPanel({
  report,
}: Readonly<{ report: HumanDecisionReviewEffectiveness }>) {
  const { t } = useI18n();
  return (
    <Card
      className="space-y-4"
      data-testid="human-decision-review-effectiveness"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow">
            {t("pages.runs.report.humanDecision.review.eyebrow")}
          </p>
          <h2 className="text-xl font-semibold">
            {t("pages.runs.report.humanDecision.review.title")}
          </h2>
        </div>
        <Badge
          {...authorityStatusBadgeProps(
            issueHumanDecisionReviewCoveragePresentation(
              report.coverage_status,
            ),
          )}
        >
          {report.coverage_status}
        </Badge>
      </div>
      <p className="font-mono text-sm">
        {report.measurement_status} · {report.review_posture} ·{" "}
        {report.threshold_status}
      </p>
      <dl className="grid gap-2 text-sm sm:grid-cols-3">
        <div>
          <dt>
            {t("pages.runs.report.humanDecision.review.authorizationAllows")}
          </dt>
          <dd>{report.authorization_allow_count}</dd>
        </div>
        <div>
          <dt>
            {t("pages.runs.report.humanDecision.review.completedDecisions")}
          </dt>
          <dd>{report.completed_human_decision_count}</dd>
        </div>
        <div>
          <dt>{t("pages.runs.report.humanDecision.review.exactJoins")}</dt>
          <dd>{report.exact_join_count}</dd>
        </div>
        <div>
          <dt>{t("pages.runs.report.humanDecision.review.approvals")}</dt>
          <dd>{report.approval_count}</dd>
        </div>
        <div>
          <dt>{t("pages.runs.report.humanDecision.review.overrides")}</dt>
          <dd>{report.override_count}</dd>
        </div>
        <div>
          <dt>{t("pages.runs.report.humanDecision.review.blocks")}</dt>
          <dd>{report.blocking_count}</dd>
        </div>
      </dl>
      {report.advisory_signal_codes.length > 0 ? (
        <ul className="list-disc space-y-1 pl-5 font-mono text-sm">
          {report.advisory_signal_codes.map((code) => (
            <li key={code}>{code}</li>
          ))}
        </ul>
      ) : null}
      <dl className="grid gap-2 font-mono text-xs sm:grid-cols-2">
        <div>
          <dt>{t("pages.runs.report.humanDecision.review.coverageClaim")}</dt>
          <dd>{report.coverage_claim_scope}</dd>
        </div>
        <div>
          <dt>{t("pages.runs.report.humanDecision.review.auditPredicate")}</dt>
          <dd>{report.audit_predicate_provenance}</dd>
        </div>
        <div>
          <dt>{t("pages.runs.report.humanDecision.review.thresholdScope")}</dt>
          <dd>{report.threshold_scope}</dd>
        </div>
        <div>
          <dt>{t("pages.runs.report.humanDecision.review.statusEffect")}</dt>
          <dd>{report.report_status_effect}</dd>
        </div>
      </dl>
      <section>
        <h3 className="font-semibold">
          {t("pages.runs.report.humanDecision.review.authoritativeFor")}
        </h3>
        <ul className="list-disc pl-5 font-mono text-xs">
          {report.authoritative_for.map((purpose) => (
            <li key={purpose}>{purpose}</li>
          ))}
        </ul>
      </section>
      <section>
        <h3 className="font-semibold">
          {t("pages.runs.report.humanDecision.review.mayNotUseFor")}
        </h3>
        <ul className="list-disc pl-5 font-mono text-xs">
          {report.may_not_use_for.map((purpose) => (
            <li key={purpose}>{purpose}</li>
          ))}
        </ul>
      </section>
    </Card>
  );
}
