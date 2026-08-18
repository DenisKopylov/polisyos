import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";

import { useSuspenseArtifactContent } from "@/api/hooks/useArtifactContent";
import { useSuspenseGovernanceDebug } from "@/api/hooks/useGovernanceDebug";
import { useSuspenseRunEvidenceContext } from "@/api/hooks/useRunEvidenceContext";
import { useSuspenseRunTimeline } from "@/api/hooks/useRunTimeline";
import { buildArtifactHref } from "@/features/artifacts";
import { useRunInspector } from "@/features/runs/context/RunInspectorContext";
import { MetricCard } from "@/features/runs/components/MetricCard";
import { ScenarioWorkbench } from "@/features/whatif";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  findRunEvidenceNeed,
  findRunEvidencePlan,
  findRunEvidencePromotion,
  normalizeRunEvidenceContext,
} from "@/shared/lib/domain/evidence";
import { normalizeGovernanceIssues } from "@/shared/lib/domain/governance";
import {
  formatDate,
  formatDuration,
  formatNumber,
  formatPercent,
} from "@/shared/lib/utils";
import { FeatureAsyncBoundary } from "@/shared/components/FeatureAsyncBoundary";
import {
  markUiMilestone,
  measureUiLatency,
} from "@/shared/telemetry/performance";
import { Badge, Card, EmptyState, PanelSkeleton } from "@polisyos/atlas-ui";
import { AuthoredText } from "@/shared/ui/authored-text";
import { Quantity, untracedDecisionQuantity } from "@/shared/ui/quantity";
import { presentDecisionGradeLabel } from "@/shared/ui/compounds/decisionGradePresentation";
import { RunExplainabilityPanel } from "@/features/runs/components/RunExplainabilityPanel";
import { useDepthNCycleBoardProjection } from "@/features/runs/api/useDepthNCycleBoardProjection";

function DecisionPanelContent({ artifactId }: { artifactId: string }) {
  const { t, label } = useI18n();
  const summary = useRunInspector();
  const evaluatorGrade = presentDecisionGradeLabel(
    summary.pipeline?.evaluator?.verdict ?? summary.decisionView?.verdict,
  );
  const decisionArtifactQuery = useSuspenseArtifactContent(artifactId, {
    maxBytes: 256 * 1024,
  });
  const decisionArtifact = decisionArtifactQuery.data.artifact;
  const isDecisionPacket =
    summary.pipeline?.decision_packet_ref?.artifact_id === artifactId ||
    decisionArtifact.kind === "scientist.decision_packet";
  const readingViewHref = isDecisionPacket
    ? buildArtifactHref(artifactId, { tab: "content", view: "reading" })
    : null;

  useEffect(() => {
    markUiMilestone("runs.overview.decision.ready", {
      routeId: "runs.detail.overview",
      surface: "overview",
    });
    measureUiLatency({
      context: {
        routeId: "runs.detail.overview",
        surface: "overview",
      },
      endMark: "runs.overview.decision.ready",
      metric: "time_to_decision_ms",
    });
  }, []);

  if (summary.decisionView) {
    return (
      <div className="space-y-4">
        {readingViewHref ? (
          <div className="flex justify-end">
            <Link
              to={readingViewHref}
              data-testid="overview-reading-view-link"
              className="text-accent text-xs font-semibold underline"
            >
              {t("common.readingView")}
            </Link>
          </div>
        ) : null}
        <AuthoredText
          author="drafter"
          timestamp={
            summary.decisionView.generatedAt ??
            summary.run?.finished_at ??
            summary.run?.started_at ??
            undefined
          }
        >
          {summary.decisionView.policySummary}
        </AuthoredText>
        <div className="grid gap-3 md:grid-cols-2">
          <MetricCard
            label={t("pages.runs.evaluator")}
            value={
              <span
                data-testid="overview-evaluator-grade"
                data-decision-grade-presentation={evaluatorGrade.classification}
                data-owner-decision-grade={
                  evaluatorGrade.ownerLabel ?? undefined
                }
              >
                {evaluatorGrade.ownerLabel ?? t("common.unknown")}
              </span>
            }
          />
          <MetricCard
            label={t("pages.runs.score", {
              score: formatNumber(summary.decisionScore.point, {
                maximumFractionDigits: 2,
              }),
            })}
            value={
              <Quantity
                value={summary.decisionScore}
                format="percent"
                precision={0}
              />
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface/75 border-line rounded-2xl border p-4">
      {readingViewHref ? (
        <div className="mb-3 flex justify-end">
          <Link
            to={readingViewHref}
            data-testid="overview-reading-view-link"
            className="text-accent text-xs font-semibold underline"
          >
            {t("common.readingView")}
          </Link>
        </div>
      ) : null}
      <p className="font-semibold">
        {label("artifactKinds", decisionArtifact.kind, decisionArtifact.kind)}
      </p>
      <p className="text-muted mt-2 text-sm">
        {formatDuration(summary.run?.duration_ms)} · {decisionArtifact.mode}
      </p>
    </div>
  );
}

function GovernancePanelContent({ runId }: { runId: string }) {
  const { t } = useI18n();
  const governanceQuery = useSuspenseGovernanceDebug(runId);
  const governance = governanceQuery.data.debug;
  const governanceIssues = normalizeGovernanceIssues(governance.issues);
  const blockerCount = governance.issue_summary?.blocker_count ?? 0;
  const transportStatus = String(
    governance.transport_summary?.status ?? "not_available",
  );
  const blockerCountQuantity = untracedDecisionQuantity({
    point: blockerCount,
    metricId: "overview_governance_blocker_count",
    label: t("pages.runs.governance"),
    unit: { code: "{blocker}", system: "ucum", display: "blockers" },
  });

  return (
    <>
      <div className="grid gap-3 md:grid-cols-2">
        <MetricCard
          label={t("pages.runs.governance")}
          value={<Quantity value={blockerCountQuantity} />}
        />
        <MetricCard label={t("pages.runs.transport")} value={transportStatus} />
      </div>
      <div className="space-y-2">
        {governanceIssues.slice(0, 4).map((issue) => (
          <div
            key={`${issue.code}-${issue.passId ?? "pass"}`}
            className="bg-surface/75 border-line rounded-2xl border p-4"
          >
            <div className="flex items-center justify-between gap-3">
              <strong>{issue.message}</strong>
              <Badge
                data-owner-severity={issue.severity ?? undefined}
                data-presentation="owner-label-neutral"
                data-testid={`overview-governance-severity-${issue.code}`}
                kind="neutral"
              >
                {issue.severity ?? t("common.unknown")}
              </Badge>
            </div>
            <p className="text-muted mt-2 text-xs">
              {issue.passId ?? issue.code}
            </p>
          </div>
        ))}
        {governanceIssues.length === 0 ? (
          <EmptyState
            title={t("pages.runs.governanceEmptyTitle")}
            body={t("pages.runs.governanceEmptyBody")}
          />
        ) : null}
      </div>
    </>
  );
}

function EvidencePanelContent({ runId }: { runId: string }) {
  const { t, label } = useI18n();
  const evidenceContextQuery = useSuspenseRunEvidenceContext(runId);
  const evidenceContext = normalizeRunEvidenceContext(
    evidenceContextQuery.data.context,
  );

  const selectedNeed = evidenceContext
    ? findRunEvidenceNeed(
        evidenceContext,
        evidenceContext.dataNeeds[0]?.needId ?? null,
      )
    : null;
  const selectedPlan = evidenceContext
    ? findRunEvidencePlan(
        evidenceContext,
        evidenceContext.fetchPlans[0]?.planId ?? null,
      )
    : null;
  const selectedPromotion = evidenceContext
    ? findRunEvidencePromotion(
        evidenceContext,
        evidenceContext.promotionCandidates[0]?.promotionId ?? null,
      )
    : null;

  return (
    <>
      <div className="grid gap-3 md:grid-cols-3">
        <MetricCard
          label={t("pages.runs.evidenceNeeds")}
          value={formatNumber(evidenceContext?.dataNeeds.length ?? 0)}
        />
        <MetricCard
          label={t("pages.runs.fetchPlans")}
          value={formatNumber(evidenceContext?.fetchPlans.length ?? 0)}
        />
        <MetricCard
          label={t("pages.runs.promotionCandidates")}
          value={formatNumber(evidenceContext?.promotionCandidates.length ?? 0)}
        />
      </div>
      <div className="space-y-3">
        {selectedNeed && (
          <div className="bg-surface/75 border-line rounded-2xl border p-4">
            <strong>{selectedNeed.metric}</strong>
            <p className="text-muted mt-2 text-sm">
              {selectedNeed.geography ?? "-"} · {selectedNeed.timeStart ?? "-"}{" "}
              - {selectedNeed.timeEnd ?? "-"}
            </p>
          </div>
        )}
        {selectedPlan && (
          <div className="bg-surface/75 border-line rounded-2xl border p-4">
            <strong>
              {selectedPlan.connectorId} / {selectedPlan.datasetId}
            </strong>
            <p className="text-muted mt-2 text-sm">{selectedPlan.metricId}</p>
          </div>
        )}
        {selectedPromotion && (
          <div className="bg-surface/75 border-line rounded-2xl border p-4">
            <strong>{selectedPromotion.metricId}</strong>
            <p className="text-muted mt-2 text-sm">
              {t("pages.runs.promotionMeta", {
                lane: label(
                  "retrievalLane",
                  selectedPromotion.sourceLane,
                  selectedPromotion.sourceLane,
                ),
                confidence: formatPercent(selectedPromotion.confidence, {
                  maximumFractionDigits: 1,
                }),
                status: selectedPromotion.status,
              })}
            </p>
          </div>
        )}
      </div>
    </>
  );
}

function TimelinePanelContent({ runId }: { runId: string }) {
  const { t } = useI18n();
  const timelineQuery = useSuspenseRunTimeline(runId);
  const timelineEvents = timelineQuery.data.timeline.events ?? [];

  if (timelineEvents.length === 0) {
    return (
      <EmptyState
        title={t("pages.runs.overviewTimelineEmptyTitle")}
        body={t("pages.runs.overviewTimelineEmptyBody")}
      />
    );
  }

  return (
    <div className="space-y-3">
      {timelineEvents.slice(0, 5).map((event) => (
        <div
          key={`${event.index}-${event.event}`}
          className="bg-surface/75 border-line rounded-2xl border p-4"
        >
          <div className="flex items-center justify-between gap-3">
            <strong>{event.event}</strong>
            <span className="text-muted text-xs">
              {formatDate(event.timestamp)}
            </span>
          </div>
          <p className="text-muted mt-2 text-sm">{event.phase}</p>
        </div>
      ))}
    </div>
  );
}

export default function OverviewTab() {
  const { t } = useI18n();
  const { runId } = useParams();
  const summary = useRunInspector();
  const governedProjectionQuery = useDepthNCycleBoardProjection();

  if (!summary.run || !runId) {
    return null;
  }

  return (
    <div className="space-y-5" data-testid="run-tab-overview">
      <div className="grid gap-5 xl:grid-cols-2">
        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.runs.sections.decision")}</p>
              <h4>{summary.decisionHeadline}</h4>
            </div>
          </div>
          {summary.primaryDecisionArtifactId ? (
            <FeatureAsyncBoundary
              feature="runs.overview.decision"
              title={t("pages.runs.decisionLoadError")}
              body={t("common.pageErrorBody")}
              loading={
                <PanelSkeleton
                  rows={4}
                  className="border-0 bg-transparent p-0"
                />
              }
              resetKeys={[summary.primaryDecisionArtifactId]}
            >
              <DecisionPanelContent
                artifactId={summary.primaryDecisionArtifactId}
              />
            </FeatureAsyncBoundary>
          ) : (
            <EmptyState
              title={t("pages.runs.decisionCandidatesEmptyTitle")}
              body={t("pages.runs.decisionCandidatesEmptyBody")}
            />
          )}
        </Card>

        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.runs.sections.governance")}</p>
              <h4>
                {t("pages.runs.blockers", {
                  count: formatNumber(summary.blockerCount),
                })}
              </h4>
            </div>
          </div>
          <FeatureAsyncBoundary
            feature="runs.overview.governance"
            title={t("pages.runs.governanceLoadError")}
            body={t("common.pageErrorBody")}
            loading={
              <PanelSkeleton rows={6} className="border-0 bg-transparent p-0" />
            }
            resetKeys={[runId]}
          >
            <GovernancePanelContent runId={runId} />
          </FeatureAsyncBoundary>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.runs.sections.evidence")}</p>
              <h4>
                {t("pages.runs.evidenceSummary", {
                  plans: formatNumber(
                    summary.evidenceContext?.fetchPlans.length ?? 0,
                  ),
                  promotions: formatNumber(
                    summary.evidenceContext?.promotionCandidates.length ?? 0,
                  ),
                })}
              </h4>
            </div>
            <Link
              to={`/runs/${runId}/evidence`}
              className="text-accent text-xs font-semibold underline"
            >
              {t("pages.runs.openEvidence")}
            </Link>
          </div>
          <FeatureAsyncBoundary
            feature="runs.overview.evidence"
            title={t("pages.runs.evidenceLoadError")}
            body={t("common.pageErrorBody")}
            loading={
              <PanelSkeleton rows={5} className="border-0 bg-transparent p-0" />
            }
            resetKeys={[runId]}
          >
            <EvidencePanelContent runId={runId} />
          </FeatureAsyncBoundary>
        </Card>

        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.runs.timelineEvents")}</p>
              <h4>{t("pages.runs.overviewTimelineTitle")}</h4>
            </div>
          </div>
          <FeatureAsyncBoundary
            feature="runs.overview.timeline"
            title={t("pages.runs.timelineLoadError")}
            body={t("common.pageErrorBody")}
            loading={
              <PanelSkeleton rows={4} className="border-0 bg-transparent p-0" />
            }
            resetKeys={[runId]}
          >
            <TimelinePanelContent runId={runId} />
          </FeatureAsyncBoundary>
        </Card>
      </div>

      <Card className="space-y-4" data-testid="overview-scenario-workbench">
        <ScenarioWorkbench runId={runId} />
      </Card>

      {/* Explainability & Trust (XAI) */}
      <Card className="space-y-4">
        <div className="panel-header">
          <div>
            <p className="eyebrow">{t("pages.runs.sections.explainability")}</p>
            <h4>{t("pages.runs.explainabilitySubtitle")}</h4>
          </div>
        </div>
        <RunExplainabilityPanel
          governedProjection={governedProjectionQuery.data}
          level="summary"
          projectionError={governedProjectionQuery.isError}
          projectionLoading={governedProjectionQuery.isLoading}
          summary={summary}
        />
      </Card>
    </div>
  );
}
