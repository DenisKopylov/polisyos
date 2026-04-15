import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { useDataCatalogSearch } from "@/api/hooks/useDataCatalogSearch";
import { useDataIndexStats } from "@/api/hooks/useDataIndexStats";
import { useDataPromotionCandidates } from "@/api/hooks/useDataPromotionCandidates";
import { useDiscoverDataSources } from "@/api/hooks/useDiscoverDataSources";
import { usePreviewFetchPlan } from "@/api/hooks/usePreviewFetchPlan";
import { useResolveDataNeeds } from "@/api/hooks/useResolveDataNeeds";
import type { components } from "@/api/types";
import {
  usePermission,
  useReviewCollaborationEnabled,
} from "@/app/authz/AuthzProvider";
import {
  ReviewCursorLayer,
  ReviewLockNotice,
  ReviewPresenceSummary,
} from "@/app/realtime/ReviewCollaborationIndicators";
import { buildPromotionReviewId } from "@/app/realtime/reviewIds";
import { useReviewCollaborationSurface } from "@/app/realtime/useReviewCollaborationSurface";
import { useQueuedPromotionDecision } from "@/features/evidence/hooks/useQueuedPromotionDecision";
import { useI18n } from "@/i18n/LocaleProvider";
import type {
  EvidenceArtifactRef,
  EvidenceFocus,
  RunEvidenceContext,
  RunEvidenceNeed,
  RunEvidencePlan,
  RunEvidencePromotion,
} from "@/lib/domain/evidence";
import {
  formatBytes,
  formatDate,
  formatNumber,
  formatPercent,
} from "@/lib/utils";
import { useDebouncedValue } from "@/lib/hooks";
import { useAlertDialog } from "@/app/providers/AlertDialogProvider";
import { useToast } from "@/app/providers/ToastProvider";
import {
  ApiErrorAlert,
  Button,
  Card,
  exportCsv,
  exportJson,
  Label,
  VirtualList,
  VIRTUALIZATION_THRESHOLD,
} from "@/shared/ui";

type RetrievalMode = "fastlane" | "hybrid" | "explorelane";
type FetchPlan = components["schemas"]["FetchPlan"];
type DataNeed = components["schemas"]["DataNeed"];

type DataIntelligencePanelProps = {
  mode?: "workspace" | "context";
  runId?: string | null;
  focus?: EvidenceFocus;
  runContext?: RunEvidenceContext | null;
  selectedNeed?: RunEvidenceNeed | null;
  selectedPlan?: RunEvidencePlan | null;
  selectedPromotion?: RunEvidencePromotion | null;
  selectedArtifact?: EvidenceArtifactRef | null;
  degradedMessages?: string[];
  onResetContext?: () => void;
};

function toFetchPlan(plan: RunEvidencePlan): FetchPlan {
  return {
    plan_id: plan.planId,
    metric_id: plan.metricId,
    connector_id: plan.connectorId,
    dataset_id: plan.datasetId,
    profile_id: plan.profileId,
    source_lane: plan.sourceLane === "explorelane" ? "explorelane" : "fastlane",
    quality_min: plan.qualityMin,
    filters: plan.filters,
    date_start: plan.dateStart,
    date_end: plan.dateEnd,
    granularity: plan.granularity,
    max_preview_rows: 20,
    persist_payload: false,
    metadata: {},
    fallbacks: [],
  };
}

function focusLabel(
  focus: EvidenceFocus | undefined,
  t: ReturnType<typeof useI18n>["t"],
) {
  if (!focus) {
    return t("pages.evidence.focus.overview");
  }
  return t(`pages.evidence.focus.${focus}`);
}

export default function DataIntelligencePanel({
  mode = "workspace",
  runId = null,
  focus = "overview",
  runContext = null,
  selectedNeed = null,
  selectedPlan = null,
  selectedPromotion = null,
  selectedArtifact = null,
  degradedMessages = [],
  onResetContext,
}: DataIntelligencePanelProps) {
  const { t, label } = useI18n();
  const { confirm } = useAlertDialog();
  const { pushToast } = useToast();
  const canReviewEvidence = usePermission("evidence.review");
  const canApprovePromotions = usePermission("evidence.promotions.approve");
  const canRejectPromotions = usePermission("evidence.promotions.reject");
  const reviewCollaborationEnabled = useReviewCollaborationEnabled();
  const promotionReviewSurfaceRef = useRef<HTMLDivElement | null>(null);

  const [metric, setMetric] = useState("");
  const [geography, setGeography] = useState("");
  const [timeStart, setTimeStart] = useState("");
  const [timeEnd, setTimeEnd] = useState("");
  const [granularity, setGranularity] = useState("annual");
  const [qualityMin, setQualityMin] = useState(0.6);
  const [modeSelection, setModeSelection] = useState<RetrievalMode>("hybrid");
  const [allowExploreFallback, setAllowExploreFallback] = useState(true);

  const [maxSourcesPerQuery, setMaxSourcesPerQuery] = useState(5);
  const [maxDiscoveryCallsPerSource, setMaxDiscoveryCallsPerSource] =
    useState(25);
  const [maxCandidatesTotal, setMaxCandidatesTotal] = useState(50);
  const [timeBudgetMs, setTimeBudgetMs] = useState(5000);

  const [lastPreviewPlanId, setLastPreviewPlanId] = useState<string | null>(
    null,
  );
  const [promotionReason, setPromotionReason] = useState("");

  const indexStatsQuery = useDataIndexStats();
  const promotionCandidatesQuery = useDataPromotionCandidates();
  const resolveMutation = useResolveDataNeeds();
  const discoverMutation = useDiscoverDataSources();
  const previewMutation = usePreviewFetchPlan();
  const {
    approve,
    approveError,
    isDecisionPending,
    queuedStateByPromotionId,
    reject,
    rejectError,
  } = useQueuedPromotionDecision();

  useEffect(() => {
    if (!selectedNeed) {
      return;
    }
    setMetric(selectedNeed.metric);
    setGeography(selectedNeed.geography ?? "");
    setTimeStart(selectedNeed.timeStart ?? "");
    setTimeEnd(selectedNeed.timeEnd ?? "");
    setGranularity(selectedNeed.granularity);
    setQualityMin(selectedNeed.qualityMin);
  }, [selectedNeed]);

  useEffect(() => {
    if (!selectedPlan) {
      return;
    }
    setMetric(selectedPlan.metricId);
    setGranularity(selectedPlan.granularity ?? "annual");
    setTimeStart(selectedPlan.dateStart ?? "");
    setTimeEnd(selectedPlan.dateEnd ?? "");
    setQualityMin(selectedPlan.qualityMin);
    setModeSelection(
      selectedPlan.sourceLane === "explorelane" ? "explorelane" : "fastlane",
    );
  }, [selectedPlan]);

  useEffect(() => {
    if (mode !== "context" || !selectedPlan) {
      return;
    }
    if (
      lastPreviewPlanId === selectedPlan.planId ||
      previewMutation.isPending
    ) {
      return;
    }
    setLastPreviewPlanId(selectedPlan.planId);
    previewMutation.mutate({
      fetch_plan: toFetchPlan(selectedPlan),
      allow_fallback: true,
    });
  }, [lastPreviewPlanId, mode, previewMutation, selectedPlan]);

  const debouncedMetricQuery = useDebouncedValue(metric.trim(), 250);
  const debouncedGeography = useDebouncedValue(geography.trim(), 250);

  const catalogQuery = useDataCatalogSearch({
    metricQuery: debouncedMetricQuery,
    geography: debouncedGeography || null,
    limit: 20,
    enabled: debouncedMetricQuery.length >= 2,
  });

  const canRun = metric.trim().length > 0;
  const currentNeed = useMemo<DataNeed | null>(() => {
    if (!canRun) {
      return null;
    }
    return {
      metric: metric.trim(),
      geography: geography.trim() || null,
      time_start: timeStart.trim() || null,
      time_end: timeEnd.trim() || null,
      granularity: granularity.trim() || "annual",
      quality_min: qualityMin,
      purpose: mode === "context" ? "run_context" : "data_intelligence_ui",
    };
  }, [
    canRun,
    geography,
    granularity,
    metric,
    mode,
    qualityMin,
    timeEnd,
    timeStart,
  ]);

  const resolvedPlans = resolveMutation.data?.fetch_plans ?? [];
  const discoverCandidates = discoverMutation.data?.candidates ?? [];
  const selectedPreview = previewMutation.data?.preview ?? null;
  const activePromotionQueue: RunEvidencePromotion[] =
    mode === "context" && runContext
      ? runContext.promotionCandidates
      : (promotionCandidatesQuery.data?.candidates ?? []).map((candidate) => ({
          promotionId: candidate.promotion_id,
          metricId: candidate.metric_id,
          connectorId: candidate.connector_id,
          datasetId: candidate.dataset_id,
          profileId: candidate.profile_id ?? null,
          sourceLane: candidate.source_lane,
          confidence: candidate.confidence ?? 0,
          status: candidate.status ?? "pending",
          createdAt: candidate.created_at ?? null,
          signals: candidate.signals ?? [],
          matchedPlanId: null,
          metadata: candidate.metadata ?? {},
        }));
  const promotionQueueWithOverrides = activePromotionQueue.map((candidate) => ({
    ...candidate,
    queuedState: queuedStateByPromotionId.get(candidate.promotionId) ?? null,
    status:
      queuedStateByPromotionId.get(candidate.promotionId)?.decision ??
      candidate.status,
  }));
  const activePromotionForReview =
    selectedPromotion ??
    (mode === "context" ? (promotionQueueWithOverrides[0] ?? null) : null);
  const promotionCollaboration = useReviewCollaborationSurface({
    enabled:
      reviewCollaborationEnabled &&
      mode === "context" &&
      Boolean(runId) &&
      Boolean(activePromotionForReview?.promotionId),
    reviewId:
      runId && activePromotionForReview
        ? buildPromotionReviewId(runId, activePromotionForReview.promotionId)
        : null,
    runId,
    surfaceRef: promotionReviewSurfaceRef,
  });
  const promotionLockReason =
    promotionCollaboration.lock && !promotionCollaboration.lock.isSelf
      ? t("panels.reviewCollaboration.lockedBy", {
          name: promotionCollaboration.lock.displayName,
        })
      : null;
  const promotionColumns = useMemo(
    () => [
      {
        key: "metric",
        header: "metric",
        exportValue: (row: (typeof promotionQueueWithOverrides)[number]) =>
          row.metricId,
      },
      {
        key: "connector",
        header: "connector",
        exportValue: (row: (typeof promotionQueueWithOverrides)[number]) =>
          row.connectorId,
      },
      {
        key: "dataset",
        header: "dataset",
        exportValue: (row: (typeof promotionQueueWithOverrides)[number]) =>
          row.datasetId,
      },
      {
        key: "status",
        header: "status",
        exportValue: (row: (typeof promotionQueueWithOverrides)[number]) =>
          row.status,
      },
      {
        key: "confidence",
        header: "confidence",
        exportValue: (row: (typeof promotionQueueWithOverrides)[number]) =>
          row.confidence,
      },
    ],
    [promotionQueueWithOverrides],
  );

  function renderSimpleList<
    T extends { candidate_id?: string; promotionId?: string },
  >(items: T[], renderItem: (item: T) => ReactNode, estimateSize = 84) {
    if (items.length < VIRTUALIZATION_THRESHOLD) {
      return <div className="space-y-2">{items.map(renderItem)}</div>;
    }

    return (
      <VirtualList
        className="rounded-2xl"
        estimateSize={estimateSize}
        itemKey={(item, index) =>
          item.candidate_id ?? item.promotionId ?? String(index)
        }
        items={items}
        maxHeight={360}
        renderItem={renderItem}
      />
    );
  }

  function handleResolve() {
    if (!currentNeed || !canReviewEvidence) {
      return;
    }
    resolveMutation.mutate({
      data_needs: [currentNeed],
      mode: modeSelection,
      allow_explore_fallback: allowExploreFallback,
    });
  }

  function handleDiscover() {
    if (!currentNeed || !canReviewEvidence) {
      return;
    }
    discoverMutation.mutate({
      data_needs: [currentNeed],
      max_sources_per_query: maxSourcesPerQuery,
      max_discovery_calls_per_source: maxDiscoveryCallsPerSource,
      max_candidates_total: maxCandidatesTotal,
      time_budget_ms: timeBudgetMs,
      cost_budget_usd: 0,
    });
  }

  function handlePreview(plan: FetchPlan) {
    if (!canReviewEvidence) {
      return;
    }
    setLastPreviewPlanId(plan.plan_id);
    previewMutation.mutate({
      fetch_plan: plan,
      allow_fallback: true,
    });
  }

  async function requestPromotionDecision(
    decision: "approve" | "reject",
    candidate: RunEvidencePromotion,
  ) {
    const confirmed = await confirm({
      title:
        decision === "approve"
          ? t("panels.dataIntelligence.confirmApproveTitle")
          : t("panels.dataIntelligence.confirmRejectTitle"),
      description: t("panels.dataIntelligence.confirmDecisionDescription", {
        connector: candidate.connectorId,
        dataset: candidate.datasetId,
        metric: candidate.metricId,
      }),
      confirmLabel:
        decision === "approve"
          ? t("panels.dataIntelligence.approve")
          : t("panels.dataIntelligence.reject"),
      cancelLabel: t("common.cancel"),
      tone: decision === "approve" ? "primary" : "danger",
    });

    if (!confirmed) {
      return;
    }

    const mutation = decision === "approve" ? approve : reject;

    mutation(
      {
        promotionId: candidate.promotionId,
        reason: promotionReason.trim() || undefined,
        ...(runId ? { runId } : {}),
      },
      {
        onQueued: () => {
          pushToast({
            title:
              decision === "approve"
                ? t("panels.dataIntelligence.approveQueuedTitle")
                : t("panels.dataIntelligence.rejectQueuedTitle"),
            description: t(
              "panels.dataIntelligence.promotionQueuedDescription",
            ),
            tone: "warning",
          });
        },
      },
    );
  }

  return (
    <div className="space-y-4">
      <div className="panel">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-muted text-sm font-semibold tracking-wider uppercase">
              {t("panels.dataIntelligence.title")}
            </h3>
            <p className="text-muted mt-2 text-sm">
              {t("panels.dataIntelligence.subtitle")}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="border-accent/20 bg-accent/10 text-accent rounded-full border px-3 py-1 text-xs font-semibold">
              {mode === "context"
                ? t("panels.dataIntelligence.contextMode")
                : t("panels.dataIntelligence.workspaceMode")}
            </span>
            <span className="border-line bg-surface text-muted rounded-full border px-3 py-1 text-xs font-semibold">
              {focusLabel(focus, t)}
            </span>
          </div>
        </div>

        {mode === "context" ? (
          <div className="bg-surface/80 border-line mb-4 rounded-2xl border p-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-1 text-sm">
                <p className="font-semibold">
                  {t("panels.dataIntelligence.boundRun", {
                    runId: runId ?? "-",
                  })}
                </p>
                <p className="text-muted">
                  {t("panels.dataIntelligence.focusSummary", {
                    focus: focusLabel(focus, t),
                    needs: formatNumber(runContext?.dataNeeds.length ?? 0),
                    plans: formatNumber(runContext?.fetchPlans.length ?? 0),
                    promotions: formatNumber(
                      runContext?.promotionCandidates.length ?? 0,
                    ),
                  })}
                </p>
              </div>
              {onResetContext ? (
                <Button type="button" onClick={onResetContext} variant="ghost">
                  {t("panels.dataIntelligence.clearRunContext")}
                </Button>
              ) : null}
            </div>

            <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <div className="compact-metric">
                <p className="text-muted text-xs uppercase">
                  {t("panels.dataIntelligence.dataNeed")}
                </p>
                <p className="mt-1 font-semibold">
                  {selectedNeed?.metric ?? t("common.unavailable")}
                </p>
                {selectedNeed ? (
                  <p className="text-muted mt-1 text-xs">
                    {selectedNeed.geography ?? "-"} ·{" "}
                    {selectedNeed.timeStart ?? "-"} -{" "}
                    {selectedNeed.timeEnd ?? "-"}
                  </p>
                ) : null}
              </div>
              <div className="compact-metric">
                <p className="text-muted text-xs uppercase">
                  {t("panels.dataIntelligence.fetchPlan")}
                </p>
                <p className="mt-1 font-semibold">
                  {selectedPlan
                    ? `${selectedPlan.connectorId} / ${selectedPlan.datasetId}`
                    : t("common.unavailable")}
                </p>
                {selectedPlan ? (
                  <p className="text-muted mt-1 text-xs">
                    {label(
                      "retrievalLane",
                      selectedPlan.sourceLane,
                      selectedPlan.sourceLane,
                    )}
                  </p>
                ) : null}
              </div>
              <div className="compact-metric">
                <p className="text-muted text-xs uppercase">
                  {t("panels.dataIntelligence.promotion")}
                </p>
                <p className="mt-1 font-semibold">
                  {selectedPromotion?.metricId ?? t("common.unavailable")}
                </p>
                {selectedPromotion ? (
                  <p className="text-muted mt-1 text-xs">
                    {formatPercent(selectedPromotion.confidence, {
                      maximumFractionDigits: 1,
                    })}{" "}
                    · {selectedPromotion.status}
                  </p>
                ) : null}
              </div>
              <div className="compact-metric">
                <p className="text-muted text-xs uppercase">
                  {t("panels.dataIntelligence.artifactRef")}
                </p>
                <p className="mt-1 font-semibold">
                  {selectedArtifact?.artifact_id ?? t("common.unavailable")}
                </p>
                {selectedArtifact?.kind ? (
                  <p className="text-muted mt-1 text-xs">
                    {label(
                      "artifactKinds",
                      selectedArtifact.kind,
                      selectedArtifact.kind,
                    )}
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}

        {degradedMessages.length > 0 ? (
          <div className="border-warning/30 bg-warning/5 text-warning mb-4 rounded-2xl border p-3 text-sm">
            <p className="font-semibold">
              {t("panels.dataIntelligence.degradedTitle")}
            </p>
            <ul className="mt-2 space-y-1">
              {degradedMessages.map((message) => (
                <li key={message}>- {message}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="grid gap-3 md:grid-cols-3">
          <div>
            <Label
              htmlFor="evidence-metric-input"
              className="text-muted mb-1 block text-xs"
            >
              {t("panels.dataIntelligence.metric")}
            </Label>
            <input
              id="evidence-metric-input"
              type="text"
              value={metric}
              onChange={(event) => setMetric(event.target.value)}
              aria-label={t("panels.dataIntelligence.metric")}
              placeholder="us.macro.gdp_nominal"
              data-testid="evidence-metric-input"
              className="atlas-input atlas-input--mono"
            />
          </div>
          <div>
            <Label
              htmlFor="evidence-geography-input"
              className="text-muted mb-1 block text-xs"
            >
              {t("panels.dataIntelligence.geography")}
            </Label>
            <input
              id="evidence-geography-input"
              type="text"
              value={geography}
              onChange={(event) => setGeography(event.target.value)}
              aria-label={t("panels.dataIntelligence.geography")}
              placeholder="USA / EU*"
              className="atlas-input"
            />
          </div>
          <div>
            <Label
              htmlFor="evidence-granularity-select"
              className="text-muted mb-1 block text-xs"
            >
              {t("panels.dataIntelligence.granularity")}
            </Label>
            <select
              id="evidence-granularity-select"
              value={granularity}
              onChange={(event) => setGranularity(event.target.value)}
              aria-label={t("panels.dataIntelligence.granularity")}
              className="atlas-select"
            >
              <option value="annual">annual</option>
              <option value="quarterly">quarterly</option>
              <option value="monthly">monthly</option>
            </select>
          </div>
          <div>
            <Label
              htmlFor="evidence-time-start-input"
              className="text-muted mb-1 block text-xs"
            >
              {t("panels.dataIntelligence.timeStart")}
            </Label>
            <input
              id="evidence-time-start-input"
              type="text"
              value={timeStart}
              onChange={(event) => setTimeStart(event.target.value)}
              aria-label={t("panels.dataIntelligence.timeStart")}
              placeholder="2015"
              className="atlas-input atlas-input--mono"
            />
          </div>
          <div>
            <Label
              htmlFor="evidence-time-end-input"
              className="text-muted mb-1 block text-xs"
            >
              {t("panels.dataIntelligence.timeEnd")}
            </Label>
            <input
              id="evidence-time-end-input"
              type="text"
              value={timeEnd}
              onChange={(event) => setTimeEnd(event.target.value)}
              aria-label={t("panels.dataIntelligence.timeEnd")}
              placeholder="2024"
              className="atlas-input atlas-input--mono"
            />
          </div>
          <div>
            <Label
              htmlFor="evidence-quality-min-input"
              className="text-muted mb-1 block text-xs"
            >
              {t("panels.dataIntelligence.qualityMin")}
            </Label>
            <input
              id="evidence-quality-min-input"
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={qualityMin}
              onChange={(event) => setQualityMin(Number(event.target.value))}
              aria-label={t("panels.dataIntelligence.qualityMin")}
              className="atlas-input"
            />
          </div>
        </div>

        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <div>
            <Label
              htmlFor="evidence-retrieval-mode-select"
              className="text-muted mb-1 block text-xs"
            >
              {t("panels.dataIntelligence.retrievalMode")}
            </Label>
            <select
              id="evidence-retrieval-mode-select"
              value={modeSelection}
              onChange={(event) =>
                setModeSelection(event.target.value as RetrievalMode)
              }
              aria-label={t("panels.dataIntelligence.retrievalMode")}
              className="atlas-select"
            >
              <option value="fastlane">fastlane</option>
              <option value="hybrid">hybrid</option>
              <option value="explorelane">explorelane</option>
            </select>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={allowExploreFallback}
                onChange={(event) =>
                  setAllowExploreFallback(event.target.checked)
                }
                aria-label={t("panels.dataIntelligence.allowExploreFallback")}
                className="accent-accent"
              />
              {t("panels.dataIntelligence.allowExploreFallback")}
            </label>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            type="button"
            disabled={
              !canRun || resolveMutation.isPending || !canReviewEvidence
            }
            title={!canReviewEvidence ? t("common.accessDenied") : undefined}
            onClick={handleResolve}
            data-testid="evidence-resolve"
            variant="primary"
          >
            {resolveMutation.isPending
              ? t("panels.dataIntelligence.resolving")
              : t("panels.dataIntelligence.resolve")}
          </Button>
          <Button
            type="button"
            disabled={
              !canRun || discoverMutation.isPending || !canReviewEvidence
            }
            title={!canReviewEvidence ? t("common.accessDenied") : undefined}
            onClick={handleDiscover}
            data-testid="evidence-discover"
            variant="ghost"
          >
            {discoverMutation.isPending
              ? t("panels.dataIntelligence.discovering")
              : t("panels.dataIntelligence.discover")}
          </Button>
          {selectedPlan ? (
            <Button
              type="button"
              disabled={!canReviewEvidence}
              title={!canReviewEvidence ? t("common.accessDenied") : undefined}
              onClick={() => handlePreview(toFetchPlan(selectedPlan))}
              data-testid="evidence-preview"
              variant="ghost"
            >
              {t("panels.dataIntelligence.preview")}
            </Button>
          ) : null}
        </div>

        {resolveMutation.error ? (
          <div className="mt-3">
            <ApiErrorAlert
              title={t("panels.dataIntelligence.resolveFailed")}
              error={resolveMutation.error}
            />
          </div>
        ) : null}
        {discoverMutation.error ? (
          <div className="mt-3">
            <ApiErrorAlert
              title={t("panels.dataIntelligence.discoverFailed")}
              error={discoverMutation.error}
            />
          </div>
        ) : null}
      </div>

      <Card>
        <h3 className="text-muted mb-3 text-sm font-semibold tracking-wider uppercase">
          {t("panels.dataIntelligence.indexStats")}
        </h3>
        {indexStatsQuery.isLoading ? (
          <p className="text-muted text-sm">
            {t("panels.dataIntelligence.indexLoading")}
          </p>
        ) : null}
        {indexStatsQuery.error ? (
          <ApiErrorAlert error={indexStatsQuery.error} />
        ) : null}
        {indexStatsQuery.data ? (
          <>
            <div className="grid gap-2 md:grid-cols-4">
              <div className="bg-surface/40 border-line rounded-lg border p-2 text-xs">
                <p className="text-muted">
                  {t("panels.dataIntelligence.indexDocs")}
                </p>
                <p className="text-sm font-semibold">
                  {formatNumber(indexStatsQuery.data.stats.index_docs_total)}
                </p>
              </div>
              <div className="bg-surface/40 border-line rounded-lg border p-2 text-xs">
                <p className="text-muted">
                  {t("panels.dataIntelligence.indexSize")}
                </p>
                <p className="text-sm font-semibold">
                  {formatBytes(indexStatsQuery.data.stats.index_size_bytes)}
                </p>
              </div>
              <div className="bg-surface/40 border-line rounded-lg border p-2 text-xs">
                <p className="text-muted">
                  {t("panels.dataIntelligence.indexedSources")}
                </p>
                <p className="text-sm font-semibold">
                  {formatNumber(indexStatsQuery.data.stats.indexed_sources)}
                </p>
              </div>
              <div className="bg-surface/40 border-line rounded-lg border p-2 text-xs">
                <p className="text-muted">
                  {t("panels.dataIntelligence.docsAddedLastRun")}
                </p>
                <p className="text-sm font-semibold">
                  {formatNumber(indexStatsQuery.data.stats.docs_added_last_run)}
                </p>
              </div>
            </div>
            {discoverMutation.data ? (
              <p className="text-muted mt-3 text-xs">
                {t("panels.dataIntelligence.lastDiscoverSummary", {
                  docs: formatNumber(discoverMutation.data.docs_fetched_total),
                  candidates: formatNumber(
                    (discoverMutation.data.candidates ?? []).length,
                  ),
                })}
              </p>
            ) : null}
          </>
        ) : null}
      </Card>

      <Card>
        <h3 className="text-muted mb-3 text-sm font-semibold tracking-wider uppercase">
          {t("panels.dataIntelligence.resolveResults")}
        </h3>
        {catalogQuery.isLoading ? (
          <p className="text-muted text-sm">
            {t("panels.dataIntelligence.catalogLoading")}
          </p>
        ) : null}
        {catalogQuery.error ? (
          <ApiErrorAlert error={catalogQuery.error} />
        ) : null}
        {catalogQuery.data ? (
          <p className="text-muted mb-2 text-xs">
            {t("panels.dataIntelligence.catalogMatches", {
              count: formatNumber(catalogQuery.data.total_matches),
              query: catalogQuery.data.query,
            })}
          </p>
        ) : null}

        {renderSimpleList(catalogQuery.data?.matches ?? [], (candidate) => (
          <div
            key={candidate.candidate_id}
            className="bg-surface/50 border-line rounded-lg border p-2 text-xs"
          >
            <p className="font-mono">
              {candidate.metric_id} {"->"} {candidate.connector_id} /{" "}
              {candidate.dataset_id}
            </p>
            <p className="text-muted">
              {t("panels.dataIntelligence.catalogCandidateMeta", {
                confidence: formatPercent(candidate.confidence),
                lane: candidate.source_lane,
              })}
            </p>
          </div>
        ))}

        {resolveMutation.data ? (
          <div className="mt-3 space-y-2">
            <p className="text-muted text-xs">
              {t("panels.dataIntelligence.resolvedSummary", {
                plans: formatNumber(resolvedPlans.length),
                candidates: formatNumber(
                  (resolveMutation.data.candidates ?? []).length,
                ),
              })}
            </p>
            {(resolveMutation.data.warnings ?? []).length > 0 ? (
              <ul className="text-warning text-xs">
                {(resolveMutation.data.warnings ?? []).map((warning, index) => (
                  <li key={`${warning}-${index}`}>{warning}</li>
                ))}
              </ul>
            ) : null}
            {resolvedPlans.map((plan) => (
              <div
                key={plan.plan_id}
                className="bg-surface/50 border-line rounded-lg border p-2 text-xs"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-mono">
                    {plan.metric_id} {"->"} {plan.connector_id} /{" "}
                    {plan.dataset_id}
                  </p>
                  <button
                    type="button"
                    onClick={() => handlePreview(plan)}
                    disabled={previewMutation.isPending}
                    className="border-line bg-panel rounded border px-2 py-1 text-[11px] font-semibold"
                  >
                    {t("panels.dataIntelligence.preview")}
                  </button>
                </div>
                <p className="text-muted">
                  {t("panels.dataIntelligence.resolvePlanMeta", {
                    lane: plan.source_lane,
                    quality: formatNumber(plan.quality_min, {
                      maximumFractionDigits: 2,
                    }),
                    fallbacks: formatNumber((plan.fallbacks ?? []).length),
                  })}
                </p>
                {lastPreviewPlanId === plan.plan_id && selectedPreview ? (
                  <div className="bg-canvas/40 border-line mt-2 rounded border p-2">
                    <p>
                      {t("panels.dataIntelligence.previewMeta", {
                        status: selectedPreview.status,
                        rows: formatNumber(selectedPreview.row_count),
                        completeness: formatPercent(
                          selectedPreview.completeness,
                        ),
                        coverage: selectedPreview.coverage_ok
                          ? t("common.yes")
                          : t("common.no"),
                      })}
                    </p>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}

        {discoverCandidates.length > 0 ? (
          <div className="mt-3">
            <p className="text-muted mb-1 text-xs">
              {t("panels.dataIntelligence.discoverCandidates", {
                count: formatNumber(discoverCandidates.length),
              })}
            </p>
            {renderSimpleList(discoverCandidates, (candidate) => (
              <div
                key={candidate.candidate_id}
                className="bg-canvas/40 border-line rounded border p-2 text-xs"
              >
                <p className="font-mono">
                  {candidate.metric_id} {"->"} {candidate.connector_id} /{" "}
                  {candidate.dataset_id}
                </p>
                <p className="text-muted">
                  {t("panels.dataIntelligence.discoverCandidateMeta", {
                    confidence: formatPercent(candidate.confidence),
                  })}
                </p>
              </div>
            ))}
          </div>
        ) : null}
      </Card>

      <Card>
        <div ref={promotionReviewSurfaceRef} className="relative">
          <ReviewCursorLayer cursors={promotionCollaboration.cursors} />
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-muted text-sm font-semibold tracking-wider uppercase">
              {t("panels.dataIntelligence.promotionQueue")}
            </h3>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                onClick={() =>
                  exportCsv(
                    "evidence-promotion-queue.csv",
                    promotionQueueWithOverrides,
                    promotionColumns,
                  )
                }
                variant="ghost"
              >
                {t("common.exportCsv")}
              </Button>
              <Button
                type="button"
                onClick={() =>
                  exportJson("evidence-promotion-queue.json", {
                    mode,
                    promotions: promotionQueueWithOverrides,
                    runId,
                  })
                }
                variant="ghost"
              >
                {t("common.exportJson")}
              </Button>
            </div>
          </div>
          {reviewCollaborationEnabled &&
          mode === "context" &&
          activePromotionForReview ? (
            <div className="mb-3 space-y-2">
              <ReviewPresenceSummary
                participants={promotionCollaboration.participants}
                status={promotionCollaboration.status}
              />
              <ReviewLockNotice lock={promotionCollaboration.lock} />
              <p className="text-muted text-xs">
                {t("panels.reviewCollaboration.activeTarget", {
                  target: activePromotionForReview.metricId,
                })}
              </p>
            </div>
          ) : null}
          {promotionCandidatesQuery.isLoading && mode !== "context" ? (
            <p className="text-muted text-sm">
              {t("panels.dataIntelligence.promotionLoading")}
            </p>
          ) : null}
          {promotionCandidatesQuery.error && mode !== "context" ? (
            <ApiErrorAlert error={promotionCandidatesQuery.error} />
          ) : null}
          <div className="mb-3">
            <Label
              htmlFor="evidence-decision-reason-input"
              className="text-muted mb-1 block text-xs"
            >
              {t("panels.dataIntelligence.decisionReason")}
            </Label>
            <input
              id="evidence-decision-reason-input"
              type="text"
              value={promotionReason}
              onChange={(event) => setPromotionReason(event.target.value)}
              disabled={!canReviewEvidence}
              aria-label={t("panels.dataIntelligence.decisionReason")}
              placeholder={t(
                "panels.dataIntelligence.decisionReasonPlaceholder",
              )}
              className="atlas-input"
            />
          </div>
          {promotionQueueWithOverrides.length === 0 ? (
            <p className="text-muted text-sm">
              {t("panels.dataIntelligence.noPromotionCandidates")}
            </p>
          ) : null}
          {renderSimpleList(
            promotionQueueWithOverrides,
            (candidate) => (
              <div
                key={candidate.promotionId}
                className={[
                  "bg-surface/50 border-line rounded-lg border p-2",
                  candidate.promotionId ===
                  activePromotionForReview?.promotionId
                    ? "border-accent/40 ring-accent/20 ring-1"
                    : "",
                ].join(" ")}
              >
                <p className="font-mono text-xs">
                  {candidate.metricId} {"->"} {candidate.connectorId} /{" "}
                  {candidate.datasetId}
                </p>
                <p className="text-muted text-xs">
                  {t("panels.dataIntelligence.promotionCandidateMeta", {
                    status: candidate.queuedState
                      ? `${candidate.status} (${candidate.queuedState.queueStatus})`
                      : candidate.status,
                    confidence: formatPercent(candidate.confidence),
                    createdAt: formatDate(candidate.createdAt),
                  })}
                </p>
                <div className="mt-2 flex gap-2">
                  <Button
                    type="button"
                    disabled={
                      isDecisionPending(candidate.promotionId) ||
                      !canApprovePromotions ||
                      (candidate.promotionId ===
                        activePromotionForReview?.promotionId &&
                        promotionCollaboration.isLockedByAnother)
                    }
                    title={
                      !canApprovePromotions
                        ? t("common.accessDenied")
                        : candidate.promotionId ===
                              activePromotionForReview?.promotionId &&
                            promotionLockReason
                          ? promotionLockReason
                          : undefined
                    }
                    data-testid={`promotion-approve-${candidate.promotionId}`}
                    onClick={() =>
                      void requestPromotionDecision("approve", candidate)
                    }
                    className="text-success"
                    variant="ghost"
                  >
                    {t("panels.dataIntelligence.approve")}
                  </Button>
                  <Button
                    type="button"
                    disabled={
                      isDecisionPending(candidate.promotionId) ||
                      !canRejectPromotions ||
                      (candidate.promotionId ===
                        activePromotionForReview?.promotionId &&
                        promotionCollaboration.isLockedByAnother)
                    }
                    title={
                      !canRejectPromotions
                        ? t("common.accessDenied")
                        : candidate.promotionId ===
                              activePromotionForReview?.promotionId &&
                            promotionLockReason
                          ? promotionLockReason
                          : undefined
                    }
                    data-testid={`promotion-reject-${candidate.promotionId}`}
                    onClick={() =>
                      void requestPromotionDecision("reject", candidate)
                    }
                    className="text-danger"
                    variant="ghost"
                  >
                    {t("panels.dataIntelligence.reject")}
                  </Button>
                </div>
              </div>
            ),
            96,
          )}
          {approveError ? (
            <div className="mt-2">
              <ApiErrorAlert
                title={t("panels.dataIntelligence.approveFailed")}
                error={approveError}
              />
            </div>
          ) : null}
          {rejectError ? (
            <div className="mt-2">
              <ApiErrorAlert
                title={t("panels.dataIntelligence.rejectFailed")}
                error={rejectError}
              />
            </div>
          ) : null}
        </div>
      </Card>

      <Card>
        <h3 className="text-muted mb-3 text-sm font-semibold tracking-wider uppercase">
          {t("panels.dataIntelligence.exploreBudget")}
        </h3>
        <div className="grid gap-3 md:grid-cols-4">
          <div>
            <Label
              htmlFor="evidence-max-sources-input"
              className="text-muted mb-1 block text-xs"
            >
              {t("panels.dataIntelligence.maxSourcesPerQuery")}
            </Label>
            <input
              id="evidence-max-sources-input"
              type="number"
              min={1}
              max={50}
              value={maxSourcesPerQuery}
              onChange={(event) =>
                setMaxSourcesPerQuery(Number(event.target.value))
              }
              aria-label={t("panels.dataIntelligence.maxSourcesPerQuery")}
              className="atlas-input"
            />
          </div>
          <div>
            <Label
              htmlFor="evidence-max-calls-input"
              className="text-muted mb-1 block text-xs"
            >
              {t("panels.dataIntelligence.maxCallsPerSource")}
            </Label>
            <input
              id="evidence-max-calls-input"
              type="number"
              min={1}
              max={500}
              value={maxDiscoveryCallsPerSource}
              onChange={(event) =>
                setMaxDiscoveryCallsPerSource(Number(event.target.value))
              }
              aria-label={t("panels.dataIntelligence.maxCallsPerSource")}
              className="atlas-input"
            />
          </div>
          <div>
            <Label
              htmlFor="evidence-max-candidates-input"
              className="text-muted mb-1 block text-xs"
            >
              {t("panels.dataIntelligence.maxCandidatesTotal")}
            </Label>
            <input
              id="evidence-max-candidates-input"
              type="number"
              min={1}
              max={500}
              value={maxCandidatesTotal}
              onChange={(event) =>
                setMaxCandidatesTotal(Number(event.target.value))
              }
              aria-label={t("panels.dataIntelligence.maxCandidatesTotal")}
              className="atlas-input"
            />
          </div>
          <div>
            <Label
              htmlFor="evidence-time-budget-input"
              className="text-muted mb-1 block text-xs"
            >
              {t("panels.dataIntelligence.timeBudgetMs")}
            </Label>
            <input
              id="evidence-time-budget-input"
              type="number"
              min={100}
              max={120000}
              value={timeBudgetMs}
              onChange={(event) => setTimeBudgetMs(Number(event.target.value))}
              aria-label={t("panels.dataIntelligence.timeBudgetMs")}
              className="atlas-input"
            />
          </div>
        </div>
      </Card>
    </div>
  );
}
