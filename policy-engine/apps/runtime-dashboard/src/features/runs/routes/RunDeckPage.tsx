import { useMemo, useRef } from "react";
import { useParams } from "react-router-dom";

import { useRunErrors } from "@/api/hooks/useRunErrors";
import { useRunTimeline } from "@/api/hooks/useRunTimeline";
import { useEpochStaleness } from "@/features/runs/api/useEpochStaleness";
import { useTelemetryReadyMark } from "@/app/providers/TelemetryProvider";
import { PrefetchButton } from "@/app/routes/PrefetchButton";
import {
  RunInspectorProvider,
  useRunInspector,
} from "@/features/runs/context/RunInspectorContext";
import { RunBreadcrumbs } from "@/features/runs/components/RunBreadcrumbs";
import { epochSemanticsFromProjection } from "@/features/runs/components/EpochStalenessView";
import {
  AtlasRunDeck,
  type AtlasRunDeckCopy,
  type AtlasRunDeckSlideId,
} from "@/features/runs/components/AtlasRunDeck";
import {
  buildAuditTrail,
  buildRunDeckSnapshot,
  buildRunReportSnapshot,
} from "@/features/runs/domain/compare";
import {
  buildRunDetailHref,
  buildRunReportHref,
} from "@/features/runs/domain/searchParams";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { formatNumber } from "@/shared/lib/utils";
import {
  exportElementAsImage,
  triggerPrint,
} from "@/shared/export/printExport";
import { Button, Card, EmptyState } from "@polisyos/atlas-ui";
import { ApiErrorAlert, copyShareLink, exportJson } from "@/shared/ui";
import { Quantity, untracedDecisionQuantity } from "@/shared/ui/quantity";
import {
  epochNonreceipt,
  TimeSemanticsLabel,
} from "@/shared/ui/temporal/TimeSemanticsLabel";

function RunDeckContent({ runId }: { runId: string }) {
  const { t } = useI18n();
  const summary = useRunInspector();
  const epochQuery = useEpochStaleness({ runId });
  const epochProjection = epochQuery.data?.projection;
  const epochSemantics = epochProjection
    ? epochSemanticsFromProjection(epochProjection)
    : epochNonreceipt();
  const timelineQuery = useRunTimeline(runId, Boolean(summary.run));
  const errorsQuery = useRunErrors(runId, Boolean(summary.run));
  const deckRef = useRef<HTMLDivElement | null>(null);
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
  const report = useMemo(
    () => buildRunReportSnapshot(summary, auditTrail),
    [auditTrail, summary],
  );
  const blockerCountQuantity = untracedDecisionQuantity({
    point: report.blockerCount,
    metricId: "deck_blocker_count",
    label: t("pages.runs.report.blockers"),
    unit: { code: "{blocker}", system: "ucum", display: "blockers" },
    time: { valid_at: summary.decisionView?.generatedAt },
  });
  const deck = useMemo(
    () => buildRunDeckSnapshot(summary, report),
    [report, summary],
  );
  const deckCopy = useMemo<AtlasRunDeckCopy>(
    () => ({
      blockerState: t("pages.runs.deck.blockerState"),
      closingEyebrow: t("pages.runs.deck.closingEyebrow"),
      closingTitle: t("pages.runs.deck.closingTitle"),
      confidence: t("pages.runs.deck.confidence"),
      dependencies: t("pages.runs.deck.dependencies"),
      evidenceEyebrow: t("pages.runs.deck.evidenceEyebrow"),
      exportSlide: t("pages.runs.deck.exportSlidePng"),
      holdForReview: t("pages.runs.deck.holdForReview"),
      metricsEyebrow: t("pages.runs.deck.metricsEyebrow"),
      ratifyNow: t("pages.runs.deck.ratifyNow"),
      recommendation: t("pages.runs.deck.recommendation"),
      tradeoffEyebrow: t("pages.runs.deck.tradeoffEyebrow"),
      verdictEyebrow: t("pages.runs.deck.verdictEyebrow"),
      verdictTitle: t("pages.runs.deck.verdictTitle"),
    }),
    [t],
  );

  async function exportSlide(id: AtlasRunDeckSlideId) {
    const element = deckRef.current?.querySelector<HTMLElement>(
      `#run-deck-slide-${id}`,
    );
    if (!element) {
      return;
    }
    await exportElementAsImage(element, `run-${runId}-${id}.png`);
  }

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
        body={t("pages.runs.deck.unavailableBody")}
      />
    );
  }

  return (
    <div className="space-y-5">
      <Card className="space-y-4 print:hidden">
        <RunBreadcrumbs runId={runId} />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow">{t("pages.runs.deck.eyebrow")}</p>
            <h3>{deck.cover.title}</h3>
            <p className="topbar-subtitle">{deck.verdict.headline}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={() => exportJson(`run-${runId}-deck.json`, deck)}
              variant="ghost"
            >
              {t("pages.runs.deck.exportJson")}
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
              onClick={async () => {
                if (!deckRef.current) {
                  return;
                }
                await exportElementAsImage(
                  deckRef.current,
                  `run-${runId}-deck.png`,
                );
              }}
              variant="ghost"
            >
              {t("pages.runs.deck.exportDeckPng")}
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={() =>
                triggerPrint({
                  contentSelector: "#run-deck-root",
                  includeTimestamp: true,
                  title: `Atlas decision deck ${runId}`,
                })
              }
            >
              {t("pages.runs.deck.printPdf")}
            </Button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <PrefetchButton
            prefetch="intent"
            to={buildRunDetailHref(runId)}
            variant="ghost"
          >
            {t("pages.runs.deck.backToRun")}
          </PrefetchButton>
          <PrefetchButton
            prefetch="intent"
            to={buildRunReportHref(runId)}
            variant="ghost"
          >
            {t("pages.runs.auditReport")}
          </PrefetchButton>
        </div>
      </Card>

      <div
        className="space-y-3"
        data-testid="run-deck-root"
        id="run-deck-root"
        ref={deckRef}
      >
        <TimeSemanticsLabel
          epochSemantics={epochSemantics}
          payloadAsOf={epochProjection?.owner_as_of}
          txAt={epochProjection?.temporal_scope.tx_at}
          validAt={epochProjection?.temporal_scope.valid_at}
        />
        <AtlasRunDeck
          copy={deckCopy}
          deck={deck}
          onExportSlide={exportSlide}
          rootId="run-deck-content"
        />
      </div>

      <Card className="space-y-4">
        <div className="grid gap-3 md:grid-cols-4">
          <div className="bg-surface/75 border-line rounded-2xl border p-4">
            <p className="text-muted text-xs tracking-wide uppercase">
              {t("pages.runs.report.decisionScore")}
            </p>
            <p className="mt-2 text-2xl font-semibold">
              <Quantity
                value={report.decisionScore}
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
              {formatNumber(report.artifactRefs.length)}
            </p>
          </div>
          <div className="bg-surface/75 border-line rounded-2xl border p-4">
            <p className="text-muted text-xs tracking-wide uppercase">
              {t("pages.runs.report.transport")}
            </p>
            <p className="mt-2 text-2xl font-semibold">
              {report.transportStatus}
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}

export default function RunDeckPage() {
  const { t } = useI18n();
  const { runId } = useParams();

  useTelemetryReadyMark("runs.deck.page", {
    routeId: "runs.deck",
    runId,
  });

  if (!runId) {
    return (
      <Card>
        <EmptyState
          title={t("pages.runs.deck.requiredTitle")}
          body={t("pages.runs.deck.requiredBody")}
        />
      </Card>
    );
  }

  return (
    <RunInspectorProvider runId={runId}>
      <RunDeckContent runId={runId} />
    </RunInspectorProvider>
  );
}
