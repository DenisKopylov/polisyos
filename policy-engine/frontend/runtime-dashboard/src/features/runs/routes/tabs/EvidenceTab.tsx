import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";

import { useSuspenseRunEvidenceContext } from "@/api/hooks/useRunEvidenceContext";
import { useRunInspector } from "@/features/runs/context/RunInspectorContext";
import { MetricCard } from "@/features/runs/components/MetricCard";
import { buildEvidenceHref } from "@/features/runs/routes/useRunDetailSummary";
import { useI18n } from "@/i18n/LocaleProvider";
import {
  findRunEvidenceNeed,
  findRunEvidencePlan,
  findRunEvidencePromotion,
  normalizeRunEvidenceContext,
} from "@/lib/domain/evidence";
import { formatNumber, formatPercent } from "@/lib/utils";
import { FeatureAsyncBoundary } from "@/shared/components/FeatureAsyncBoundary";
import {
  markUiMilestone,
  measureUiLatency,
} from "@/shared/telemetry/performance";
import { Card, EmptyState, PanelSkeleton } from "@/shared/ui";

function EvidenceTabContent({ runId }: { runId: string }) {
  const { t, label } = useI18n();
  const summary = useRunInspector();
  const evidenceContextQuery = useSuspenseRunEvidenceContext(runId);
  const context = normalizeRunEvidenceContext(
    evidenceContextQuery.data.context,
  );

  useEffect(() => {
    markUiMilestone("runs.evidence.insight.ready", {
      routeId: "runs.detail.evidence",
      surface: "run-evidence",
    });
    measureUiLatency({
      context: {
        routeId: "runs.detail.evidence",
        surface: "run-evidence",
      },
      endMark: "runs.evidence.insight.ready",
      metric: "time_to_insight_ms",
    });
  }, []);

  if (!context) {
    return (
      <EmptyState
        title={t("pages.runs.evidenceEmptyTitle")}
        body={t("pages.runs.evidenceEmptyBody")}
      />
    );
  }

  const selectedNeed = findRunEvidenceNeed(
    context,
    context.dataNeeds[0]?.needId ?? null,
  );
  const selectedPlan = findRunEvidencePlan(
    context,
    context.fetchPlans[0]?.planId ?? null,
  );
  const selectedPromotion = findRunEvidencePromotion(
    context,
    context.promotionCandidates[0]?.promotionId ?? null,
  );

  return (
    <div className="space-y-5" data-testid="run-tab-evidence">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label={t("pages.runs.evidenceNeeds")}
          value={formatNumber(context.dataNeeds.length)}
          meta={selectedNeed?.metric ?? "-"}
        />
        <MetricCard
          label={t("pages.runs.fetchPlans")}
          value={formatNumber(context.fetchPlans.length)}
          meta={selectedPlan?.connectorId ?? "-"}
        />
        <MetricCard
          label={t("pages.runs.promotionCandidates")}
          value={formatNumber(context.promotionCandidates.length)}
          meta={
            selectedPromotion
              ? formatPercent(selectedPromotion.confidence, {
                  maximumFractionDigits: 1,
                })
              : "-"
          }
        />
        <MetricCard
          label={t("pages.runs.relatedArtifacts")}
          value={formatNumber(context.relatedArtifacts.length)}
          meta={context.warnings[0] ?? "-"}
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.runs.primaryNeed")}</p>
              <h4>{selectedNeed?.metric ?? t("pages.runs.noNeedContext")}</h4>
            </div>
            {selectedNeed ? (
              <Link
                data-testid={`evidence-link-need-${selectedNeed.needId}`}
                to={buildEvidenceHref(runId, "need", {
                  needId: selectedNeed.needId,
                })}
                className="text-accent text-xs font-semibold underline"
              >
                {t("pages.runs.openEvidence")}
              </Link>
            ) : null}
          </div>
          {selectedNeed ? (
            <div className="space-y-2 text-sm">
              <p>
                {selectedNeed.geography ?? "-"} ·{" "}
                {selectedNeed.timeStart ?? "-"} - {selectedNeed.timeEnd ?? "-"}
              </p>
              <p className="text-muted">{selectedNeed.granularity}</p>
              {selectedNeed.notes.length > 0 ? (
                <p className="text-muted">{selectedNeed.notes.join(" · ")}</p>
              ) : null}
            </div>
          ) : (
            <EmptyState
              title={t("pages.runs.evidenceEmptyTitle")}
              body={t("pages.runs.noNeedContext")}
            />
          )}
        </Card>

        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.runs.fetchPlanPreview")}</p>
              <h4>
                {selectedPlan
                  ? `${selectedPlan.connectorId} / ${selectedPlan.datasetId}`
                  : t("pages.runs.noPlanContext")}
              </h4>
            </div>
            {selectedPlan ? (
              <Link
                to={buildEvidenceHref(runId, "plan", {
                  planId: selectedPlan.planId,
                })}
                className="text-accent text-xs font-semibold underline"
              >
                {t("pages.runs.openEvidence")}
              </Link>
            ) : null}
          </div>
          {selectedPlan ? (
            <div className="space-y-2 text-sm">
              <p>
                {label(
                  "retrievalLane",
                  selectedPlan.sourceLane,
                  selectedPlan.sourceLane,
                )}{" "}
                · {selectedPlan.metricId}
              </p>
              <p className="text-muted">
                {t("pages.runs.planMatches", {
                  count: formatNumber(selectedPlan.matchedNeedIds.length),
                })}
              </p>
              {selectedPlan.notes.length > 0 ? (
                <p className="text-muted">{selectedPlan.notes.join(" · ")}</p>
              ) : null}
            </div>
          ) : (
            <EmptyState
              title={t("pages.runs.evidenceEmptyTitle")}
              body={t("pages.runs.noPlanContext")}
            />
          )}
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.runs.promotionCandidate")}</p>
              <h4>
                {selectedPromotion?.metricId ??
                  t("pages.runs.noPromotionContext")}
              </h4>
            </div>
            {selectedPromotion ? (
              <Link
                data-testid={`promotion-action-link-${selectedPromotion.promotionId}`}
                to={buildEvidenceHref(runId, "promotion", {
                  promotionId: selectedPromotion.promotionId,
                })}
                className="text-accent text-xs font-semibold underline"
              >
                {t("pages.runs.reviewPromotion")}
              </Link>
            ) : null}
          </div>
          {selectedPromotion ? (
            <div className="space-y-2 text-sm">
              <p>
                {selectedPromotion.connectorId} / {selectedPromotion.datasetId}
              </p>
              <p className="text-muted">
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
          ) : (
            <EmptyState
              title={t("pages.runs.evidenceEmptyTitle")}
              body={t("pages.runs.noPromotionContext")}
            />
          )}
        </Card>

        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.runs.linkedEvidenceRefs")}</p>
              <h4>
                {t("pages.runs.artifactSummary", {
                  count: formatNumber(summary.artifactRefs.length),
                })}
              </h4>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {summary.artifactRefs.map((ref) => (
              <Link
                key={ref.artifact_id}
                to={buildEvidenceHref(runId, "artifact", {
                  artifactId: ref.artifact_id,
                })}
                className="bg-surface/75 border-line rounded-full border px-3 py-1 text-xs font-semibold"
              >
                {label("artifactKinds", ref.kind, ref.kind ?? ref.artifact_id)}
              </Link>
            ))}
            {summary.artifactRefs.length === 0 ? (
              <p className="text-muted text-sm">
                {t("pages.runs.noEvidenceRefs")}
              </p>
            ) : null}
          </div>
          {context.warnings.length > 0 ? (
            <div className="border-warning/30 bg-warning/5 text-warning rounded-xl border p-3 text-sm">
              {context.warnings.join(" · ")}
            </div>
          ) : null}
        </Card>
      </div>
    </div>
  );
}

export default function EvidenceTab() {
  const { t } = useI18n();
  const { runId } = useParams();

  if (!runId) {
    return null;
  }

  return (
    <FeatureAsyncBoundary
      feature="runs.evidence.context"
      title={t("pages.runs.evidenceLoadError")}
      body={t("common.pageErrorBody")}
      loading={<PanelSkeleton rows={6} />}
      resetKeys={[runId]}
    >
      <EvidenceTabContent runId={runId} />
    </FeatureAsyncBoundary>
  );
}
