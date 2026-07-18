import { useMemo } from "react";
import { useParams } from "react-router-dom";

import { useRunErrors } from "@/api/hooks/useRunErrors";
import { useRunTimeline } from "@/api/hooks/useRunTimeline";
import { useTelemetryReadyMark } from "@/app/providers/TelemetryProvider";
import { PrefetchButton } from "@/app/routes/PrefetchButton";
import {
  RunInspectorProvider,
  useRunInspector,
} from "@/features/runs/context/RunInspectorContext";
import { AuditTimeline } from "@/features/runs/components/AuditTimeline";
import { RunBreadcrumbs } from "@/features/runs/components/RunBreadcrumbs";
import {
  buildAuditTrail,
  buildRunReportSnapshot,
} from "@/features/runs/domain/compare";
import { buildRunDeckHref } from "@/features/runs/domain/searchParams";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { formatNumber } from "@/shared/lib/utils";
import { Button, Card, EmptyState } from "@polisyos/atlas-ui";
import { ApiErrorAlert, copyShareLink, exportJson } from "@/shared/ui";
import { Quantity, untracedDecisionQuantity } from "@/shared/ui/quantity";

function RunReportContent({ runId }: { runId: string }) {
  const { t } = useI18n();
  const summary = useRunInspector();
  const timelineQuery = useRunTimeline(runId, Boolean(summary.run));
  const errorsQuery = useRunErrors(runId, Boolean(summary.run));
  const auditTrail = useMemo(
    () =>
      buildAuditTrail({
        errors: errorsQuery.data?.errors ?? [],
        governanceIssues: summary.governanceIssues,
        timelineEvents: timelineQuery.data?.timeline.events ?? [],
      }),
    [
      errorsQuery.data?.errors,
      summary.governanceIssues,
      timelineQuery.data?.timeline.events,
    ],
  );
  const snapshot = useMemo(
    () => buildRunReportSnapshot(summary, auditTrail),
    [auditTrail, summary],
  );
  const decisionScoreQuantity = untracedDecisionQuantity({
    point: summary.decisionScore,
    metricId: "report_decision_score",
    label: t("pages.runs.report.decisionScore"),
    time: { valid_at: summary.decisionView?.generatedAt },
  });
  const blockerCountQuantity = untracedDecisionQuantity({
    point: summary.blockerCount,
    metricId: "report_blocker_count",
    label: t("pages.runs.report.blockers"),
    unit: { code: "{blocker}", system: "ucum", display: "blockers" },
    time: { valid_at: summary.decisionView?.generatedAt },
  });

  if (summary.runDetailsQuery.isError) {
    return (
      <ApiErrorAlert
        title={t("pages.runs.loadRunDetailsError")}
        error={summary.runDetailsQuery.error}
      />
    );
  }

  if (!summary.run) {
    return (
      <EmptyState
        title={t("pages.runs.unavailableRun")}
        body={t("pages.runs.report.unavailableBody")}
      />
    );
  }

  return (
    <div className="space-y-5 print:space-y-4">
      <Card className="space-y-4 print:shadow-none">
        <RunBreadcrumbs runId={runId} />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow">{t("pages.runs.report.eyebrow")}</p>
            <h3>{t("pages.runs.detailTitle", { runId })}</h3>
            <p className="topbar-subtitle">{summary.decisionHeadline}</p>
          </div>
          <div className="flex flex-wrap gap-2 print:hidden">
            <Button
              type="button"
              onClick={() => exportJson(`run-${runId}-snapshot.json`, snapshot)}
              variant="ghost"
            >
              {t("pages.runs.report.exportJson")}
            </Button>
            <Button
              type="button"
              onClick={() =>
                void copyShareLink(
                  new URL(
                    window.location.pathname + window.location.search,
                    window.location.origin,
                  ),
                )
              }
              variant="ghost"
            >
              {t("common.shareView")}
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={() => window.print()}
            >
              {t("pages.runs.report.printPdf")}
            </Button>
            <PrefetchButton
              prefetch="intent"
              to={buildRunDeckHref(runId)}
              variant="ghost"
            >
              {t("pages.runs.openDeck")}
            </PrefetchButton>
          </div>
        </div>
        <div className="grid gap-3 md:grid-cols-4">
          <div className="bg-surface/75 border-line rounded-2xl border p-4">
            <p className="text-muted text-xs tracking-wide uppercase">
              {t("pages.runs.report.decisionScore")}
            </p>
            <p className="mt-2 text-2xl font-semibold">
              <Quantity
                value={decisionScoreQuantity}
                precision={2}
                variant="hero"
              />
            </p>
          </div>
          <div className="bg-surface/75 border-line rounded-2xl border p-4">
            <p className="text-muted text-xs tracking-wide uppercase">
              {t("pages.runs.report.blockers")}
            </p>
            <p className="mt-2 text-2xl font-semibold">
              <Quantity value={blockerCountQuantity} variant="hero" />
            </p>
          </div>
          <div className="bg-surface/75 border-line rounded-2xl border p-4">
            <p className="text-muted text-xs tracking-wide uppercase">
              {t("pages.runs.report.artifacts")}
            </p>
            <p className="mt-2 text-2xl font-semibold">
              {formatNumber(summary.artifactRefs.length)}
            </p>
          </div>
          <div className="bg-surface/75 border-line rounded-2xl border p-4">
            <p className="text-muted text-xs tracking-wide uppercase">
              {t("pages.runs.report.transport")}
            </p>
            <p className="mt-2 text-2xl font-semibold">
              {summary.transportStatus}
            </p>
          </div>
        </div>
      </Card>

      <Card className="space-y-4">
        <div>
          <p className="eyebrow">{t("pages.runs.report.timelineEyebrow")}</p>
          <h4 className="text-xl font-semibold">
            {t("pages.runs.report.auditTrailTitle")}
          </h4>
        </div>
        <AuditTimeline
          entries={auditTrail}
          emptyTitle={t("pages.runs.overviewTimelineEmptyTitle")}
          emptyBody={t("pages.runs.overviewTimelineEmptyBody")}
        />
      </Card>
    </div>
  );
}

export default function RunReportPage() {
  const { t } = useI18n();
  const { runId } = useParams();

  useTelemetryReadyMark("runs.report.page", {
    routeId: "runs.report",
    runId,
  });

  if (!runId) {
    return (
      <Card>
        <EmptyState
          title={t("pages.runs.report.requiredTitle")}
          body={t("pages.runs.report.requiredBody")}
        />
      </Card>
    );
  }

  return (
    <RunInspectorProvider runId={runId}>
      <div data-testid="run-report-page">
        <RunReportContent runId={runId} />
      </div>
    </RunInspectorProvider>
  );
}
