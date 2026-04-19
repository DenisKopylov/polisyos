import { useEffect, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useCapabilities } from "@/api/hooks/useCapabilities";
import { useConnectors } from "@/api/hooks/useConnectors";
import { useDataIndexStats } from "@/api/hooks/useDataIndexStats";
import { useDataPromotionCandidates } from "@/api/hooks/useDataPromotionCandidates";
import { useRunEvidenceContext } from "@/api/hooks/useRunEvidenceContext";
import { useSourceProfiles } from "@/api/hooks/useSourceProfiles";
import { PrefetchButton } from "@/app/routes/PrefetchButton";
import { parseEvidenceSearchParams } from "@/features/evidence/domain/searchParams";
import DataIntelligencePanel from "@/features/evidence/components/DataIntelligencePanel";
import {
  EVIDENCE_FOCUSES,
  dedupeEvidenceArtifactRefs,
  parseEvidenceFocus,
} from "@/features/evidence/domain/context";
import { useI18n } from "@/i18n/LocaleProvider";
import {
  type EvidenceArtifactRef,
  type EvidenceFocus,
  findRunEvidenceNeed,
  findRunEvidencePlan,
  findRunEvidencePromotion,
  normalizeRunEvidenceContext,
  resolveDefaultEvidenceFocus,
} from "@/lib/domain/evidence";
import { formatDate, formatNumber, formatPercent } from "@/lib/utils";
import {
  markUiMilestone,
  measureUiLatency,
} from "@/shared/telemetry/performance";
import {
  ApiErrorAlert,
  Badge,
  Button,
  Card,
  DataFreshnessBadge,
  EvidenceChain,
  copyShareLink,
} from "@/shared/ui";
import { useIsMobile } from "@/shared/ui/responsive";

export default function EvidenceFabric() {
  const { t, label } = useI18n();
  const isMobile = useIsMobile();
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    artifactId,
    focus: parsedFocus,
    needId,
    planId,
    promotionId,
    runId,
  } = parseEvidenceSearchParams(searchParams);

  const requestedFocus = parsedFocus ? parseEvidenceFocus(parsedFocus) : null;

  const capabilitiesQuery = useCapabilities();
  const connectorsQuery = useConnectors();
  const profilesQuery = useSourceProfiles();
  const indexStatsQuery = useDataIndexStats();
  const promotionCandidatesQuery = useDataPromotionCandidates();
  const runContextQuery = useRunEvidenceContext(
    runId ?? undefined,
    Boolean(runId),
  );

  const profiles = profilesQuery.data?.profiles ?? [];
  const connectors = connectorsQuery.data?.connectors ?? [];
  const availableProfiles = profiles.filter(
    (profile) => profile.connector_available,
  );
  const loadedConnectors = connectors.filter((connector) => connector.loaded);
  const enabledFeatures = (capabilitiesQuery.data?.features ?? []).filter(
    (feature) => feature.category === "evidence",
  );
  const runContext = useMemo(
    () => normalizeRunEvidenceContext(runContextQuery.data?.context),
    [runContextQuery.data],
  );
  const effectiveFocus =
    requestedFocus ?? resolveDefaultEvidenceFocus(runContext);

  const selectedNeed =
    findRunEvidenceNeed(runContext, needId ?? null) ??
    (needId ? null : (runContext?.dataNeeds[0] ?? null));
  const selectedPlan =
    findRunEvidencePlan(runContext, planId ?? null) ??
    (planId ? null : (runContext?.fetchPlans[0] ?? null));
  const selectedPromotion =
    findRunEvidencePromotion(runContext, promotionId ?? null) ??
    (promotionId ? null : (runContext?.promotionCandidates[0] ?? null));

  const contextArtifactRefs = useMemo(
    () =>
      dedupeEvidenceArtifactRefs([
        runContext?.executionPlanRef ?? null,
        runContext?.evidenceBundleRef ?? null,
        runContext?.dataSnapshotRef ?? null,
        runContext?.inputBindingsRef ?? null,
        ...(runContext?.relatedArtifacts ?? []),
      ]),
    [runContext],
  );

  const selectedArtifact =
    contextArtifactRefs.find((ref) => ref.artifact_id === artifactId) ??
    (artifactId ? null : (contextArtifactRefs[0] ?? null));
  const featuredProfiles = availableProfiles.slice(0, 3);
  const featuredPromotions = (
    runId
      ? (runContext?.promotionCandidates ?? [])
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
        }))
  ).slice(0, 3);
  const sourceGapCount = Math.max(
    profiles.length - availableProfiles.length,
    0,
  );
  const averagePromotionConfidence =
    featuredPromotions.length > 0
      ? featuredPromotions.reduce(
          (total, candidate) => total + (candidate.confidence ?? 0),
          0,
        ) / featuredPromotions.length
      : 0;

  const degradedMessages: string[] = [];
  if (runId && needId && !selectedNeed) {
    degradedMessages.push(t("pages.evidence.degraded.needMissing", { needId }));
  }
  if (runId && planId && !selectedPlan) {
    degradedMessages.push(t("pages.evidence.degraded.planMissing", { planId }));
  }
  if (runId && promotionId && !selectedPromotion) {
    degradedMessages.push(
      t("pages.evidence.degraded.promotionMissing", { promotionId }),
    );
  }
  if (runId && artifactId && !selectedArtifact) {
    degradedMessages.push(
      t("pages.evidence.degraded.artifactMissing", { artifactId }),
    );
  }

  useEffect(() => {
    markUiMilestone("evidence.workspace.insight.ready", {
      routeId: "evidence.fabric",
      surface: "workspace-evidence",
    });
    measureUiLatency({
      context: {
        routeId: "evidence.fabric",
        surface: "workspace-evidence",
      },
      endMark: "evidence.workspace.insight.ready",
      metric: "time_to_insight_ms",
    });
  }, []);

  function updateContext(params: {
    focus?: EvidenceFocus;
    needId?: string | null;
    planId?: string | null;
    promotionId?: string | null;
    artifactId?: string | null;
  }) {
    const next = new URLSearchParams(searchParams);
    if (runId) {
      next.set("runId", runId);
    }
    next.set("focus", params.focus ?? effectiveFocus);

    for (const key of ["needId", "planId", "promotionId", "artifactId"]) {
      next.delete(key);
    }
    if (params.needId) {
      next.set("needId", params.needId);
    }
    if (params.planId) {
      next.set("planId", params.planId);
    }
    if (params.promotionId) {
      next.set("promotionId", params.promotionId);
    }
    if (params.artifactId) {
      next.set("artifactId", params.artifactId);
    }
    setSearchParams(next);
  }

  function clearRunContext() {
    const next = new URLSearchParams(searchParams);
    for (const key of [
      "runId",
      "focus",
      "needId",
      "planId",
      "promotionId",
      "artifactId",
    ]) {
      next.delete(key);
    }
    setSearchParams(next);
  }

  return (
    <div className="space-y-5" data-testid="evidence-page">
      <div className="panel space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow">{t("pages.evidence.title")}</p>
            <h3>
              {runId
                ? t("pages.evidence.contextTitle", { runId })
                : t("pages.evidence.heroTitle")}
            </h3>
            <p className="topbar-subtitle">{t("pages.evidence.subtitle")}</p>
          </div>
          <div className="topbar-actions">
            {loadedConnectors.length > 0 ? (
              <Badge kind="ok">
                {t("pages.evidence.totalConnectors", {
                  count: formatNumber(loadedConnectors.length),
                })}
              </Badge>
            ) : null}
            {runId && runContext ? (
              <Badge kind="warn">
                {t("pages.evidence.runContextSummary", {
                  needs: formatNumber(runContext.dataNeeds.length),
                  plans: formatNumber(runContext.fetchPlans.length),
                  promotions: formatNumber(
                    runContext.promotionCandidates.length,
                  ),
                  artifacts: formatNumber(contextArtifactRefs.length),
                })}
              </Badge>
            ) : null}
            <DataFreshnessBadge
              generatedAt={
                runId
                  ? runContextQuery.data?.meta?.generated_at
                  : promotionCandidatesQuery.data?.meta?.generated_at
              }
            />
            {enabledFeatures.slice(0, 2).map((feature) => (
              <Badge key={feature.key} kind="neutral">
                {feature.label}
              </Badge>
            ))}
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
            {runId ? (
              <PrefetchButton
                to={`/runs/${runId}/evidence`}
                prefetch="intent"
                variant="ghost"
              >
                {t("pages.evidence.backToRun")}
              </PrefetchButton>
            ) : null}
          </div>
        </div>

        {runId ? (
          <div className="bg-surface/75 border-line rounded-2xl border p-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">
                  {t("pages.evidence.runContextActive", { runId })}
                </p>
                <p className="text-muted mt-1 text-sm">
                  {t("pages.evidence.runContextSummary", {
                    needs: formatNumber(runContext?.dataNeeds.length ?? 0),
                    plans: formatNumber(runContext?.fetchPlans.length ?? 0),
                    promotions: formatNumber(
                      runContext?.promotionCandidates.length ?? 0,
                    ),
                    artifacts: formatNumber(contextArtifactRefs.length),
                  })}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={clearRunContext} variant="ghost">
                  {t("pages.evidence.clearContext")}
                </Button>
              </div>
            </div>
            {runContext?.warnings.length ? (
              <p className="text-warning mt-3 text-sm">
                {runContext.warnings.join(" · ")}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>

      {isMobile ? (
        <section className="grid gap-3" data-testid="evidence-mobile-overview">
          <Card className="space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="eyebrow">Source Atlas</p>
                <h4>{t("pages.evidence.sourceAtlasTitle")}</h4>
              </div>
              <Badge kind="neutral">
                {t("pages.evidence.docsAdded", {
                  count: formatNumber(
                    indexStatsQuery.data?.stats.docs_added_last_run ?? 0,
                  ),
                })}
              </Badge>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="compact-metric">
                <span>{t("pages.evidence.connectors")}</span>
                <strong>{formatNumber(loadedConnectors.length)}</strong>
              </div>
              <div className="compact-metric">
                <span>{t("pages.evidence.sourceProfiles")}</span>
                <strong>{formatNumber(availableProfiles.length)}</strong>
              </div>
              <div className="compact-metric">
                <span>{t("common.gaps")}</span>
                <strong>{formatNumber(sourceGapCount)}</strong>
              </div>
            </div>
          </Card>

          <div className="grid gap-3 sm:grid-cols-2">
            <Card className="space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="eyebrow">Promotion Lane</p>
                  <h4>{t("pages.evidence.promotionReviewTitle")}</h4>
                </div>
                <Badge kind="warn">
                  {formatNumber(featuredPromotions.length)}
                </Badge>
              </div>
              <p className="text-muted text-sm">
                {t("pages.evidence.promotionReviewBody")}
              </p>
              {runId ? (
                <Button
                  type="button"
                  onClick={() => updateContext({ focus: "promotion" })}
                  variant="ghost"
                >
                  {t("pages.evidence.focus.promotion")}
                </Button>
              ) : null}
            </Card>

            <Card className="space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="eyebrow">Knowledge Weave</p>
                  <h4>{t("pages.evidence.relatedArtifacts")}</h4>
                </div>
                <Badge kind="neutral">
                  {formatNumber(contextArtifactRefs.length)}
                </Badge>
              </div>
              <p className="text-muted text-sm">
                {selectedArtifact
                  ? label(
                      "artifactKinds",
                      selectedArtifact.kind,
                      selectedArtifact.kind ?? selectedArtifact.artifact_id,
                    )
                  : t("pages.evidence.noArtifacts")}
              </p>
              {runId ? (
                <Button
                  type="button"
                  onClick={() => updateContext({ focus: "artifact" })}
                  variant="ghost"
                >
                  {t("pages.evidence.focus.artifact")}
                </Button>
              ) : null}
            </Card>
          </div>
        </section>
      ) : (
        <>
          <section className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(280px,0.8fr)]">
            <article className="panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Source Atlas</p>
                  <h4>{t("pages.evidence.sourceAtlasTitle")}</h4>
                  <p className="topbar-subtitle mt-2">
                    {t("pages.evidence.sourceAtlasBody")}
                  </p>
                </div>
                <span className="text-muted font-mono text-[11px] tracking-[0.18em] uppercase">
                  {t("pages.evidence.docsAdded", {
                    count: formatNumber(
                      indexStatsQuery.data?.stats.docs_added_last_run ?? 0,
                    ),
                  })}
                </span>
              </div>
              <div className="grid gap-3">
                {featuredProfiles.map((profile) => (
                  <div
                    key={profile.profile_id}
                    className="bg-surface/75 border-line rounded-2xl border p-4"
                  >
                    <strong>{profile.display_name}</strong>
                    <p className="text-muted mt-2 text-sm">
                      {profile.source_organization} · {profile.connector_family}{" "}
                      ·{" "}
                      {profile.estimated_datasets != null
                        ? t("pages.evidence.datasetsCount", {
                            count: formatNumber(profile.estimated_datasets),
                          })
                        : t("common.unavailable")}
                    </p>
                  </div>
                ))}
                {featuredProfiles.length === 0 ? (
                  <div className="bg-surface/75 border-line rounded-2xl border p-4">
                    <strong>{t("pages.evidence.sourceProfiles")}</strong>
                    <p className="text-muted mt-2 text-sm">
                      {t("pages.evidence.profilesLoading")}
                    </p>
                  </div>
                ) : null}
                <div className="grid gap-3 md:grid-cols-3">
                  <div className="compact-metric">
                    <span>{t("pages.evidence.connectors")}</span>
                    <strong>{formatNumber(loadedConnectors.length)}</strong>
                  </div>
                  <div className="compact-metric">
                    <span>{t("pages.evidence.sourceProfiles")}</span>
                    <strong>{formatNumber(availableProfiles.length)}</strong>
                  </div>
                  <div className="compact-metric">
                    <span>{t("common.gaps")}</span>
                    <strong>{formatNumber(sourceGapCount)}</strong>
                  </div>
                </div>
              </div>
            </article>

            <article className="panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Knowledge Weave</p>
                  <h4>{t("pages.evidence.knowledgeWeaveTitle")}</h4>
                  <p className="topbar-subtitle mt-2">
                    {t("pages.evidence.knowledgeWeaveBody")}
                  </p>
                </div>
                <span className="text-muted font-mono text-[11px] tracking-[0.18em] uppercase">
                  {t("pages.evidence.indexDocs")}
                </span>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="bg-surface/75 border-line rounded-2xl border p-4">
                  <p className="text-muted text-xs tracking-wide uppercase">
                    {t("pages.evidence.focus.overview")}
                  </p>
                  <p className="mt-2 text-2xl font-semibold">
                    {formatNumber(contextArtifactRefs.length)}
                  </p>
                  <p className="text-muted mt-2 text-sm">
                    {t("pages.evidence.relatedArtifacts")}
                  </p>
                </div>
                <div className="bg-surface/75 border-line rounded-2xl border p-4">
                  <p className="text-muted text-xs tracking-wide uppercase">
                    {t("pages.evidence.dataNeeds")}
                  </p>
                  <p className="mt-2 text-2xl font-semibold">
                    {formatNumber(runContext?.dataNeeds.length ?? 0)}
                  </p>
                  <p className="text-muted mt-2 text-sm">
                    {t("pages.evidence.fetchPlans")}
                  </p>
                </div>
                <div className="bg-surface/75 border-line rounded-2xl border p-4">
                  <p className="text-muted text-xs tracking-wide uppercase">
                    {t("pages.evidence.fetchPlans")}
                  </p>
                  <p className="mt-2 text-2xl font-semibold">
                    {formatNumber(runContext?.fetchPlans.length ?? 0)}
                  </p>
                  <p className="text-muted mt-2 text-sm">
                    {t("pages.evidence.contextRefs")}
                  </p>
                </div>
                <div className="bg-surface/75 border-line rounded-2xl border p-4">
                  <p className="text-muted text-xs tracking-wide uppercase">
                    {t("pages.evidence.promotion")}
                  </p>
                  <p className="mt-2 text-2xl font-semibold">
                    {formatNumber(
                      runId
                        ? (runContext?.promotionCandidates.length ?? 0)
                        : (promotionCandidatesQuery.data?.candidates?.length ??
                            0),
                    )}
                  </p>
                  <p className="text-muted mt-2 text-sm">
                    {t("pages.evidence.runScopedPromotion")}
                  </p>
                </div>
              </div>
            </article>

            <article className="panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Promotion Lane</p>
                  <h4>{t("pages.evidence.promotionReviewTitle")}</h4>
                  <p className="topbar-subtitle mt-2">
                    {t("pages.evidence.promotionReviewBody")}
                  </p>
                </div>
              </div>
              <div className="grid gap-3">
                {featuredPromotions.map((candidate) => (
                  <div
                    key={candidate.promotionId}
                    className="bg-surface/75 border-line rounded-2xl border p-4"
                  >
                    <strong>{candidate.metricId}</strong>
                    <span className="bg-accent/10 text-accent mt-3 inline-flex w-fit rounded-full px-3 py-1 text-[11px] font-semibold tracking-wide uppercase">
                      {candidate.status}
                    </span>
                  </div>
                ))}
                {featuredPromotions.length === 0 ? (
                  <div className="bg-surface/75 border-line rounded-2xl border p-4">
                    <strong>{t("pages.evidence.noPromotionCandidates")}</strong>
                    <span className="bg-surface text-muted mt-3 inline-flex w-fit rounded-full px-3 py-1 text-[11px] font-semibold tracking-wide uppercase">
                      -
                    </span>
                  </div>
                ) : null}
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="compact-metric">
                    <span>{t("pages.evidence.promotionCandidates")}</span>
                    <strong>{formatNumber(featuredPromotions.length)}</strong>
                  </div>
                  <div className="compact-metric">
                    <span>{t("common.confidence")}</span>
                    <strong>
                      {formatPercent(averagePromotionConfidence, {
                        maximumFractionDigits: 0,
                      })}
                    </strong>
                  </div>
                </div>
              </div>
            </article>
          </section>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card>
              <p className="text-muted text-xs uppercase">
                {t("pages.evidence.sourceProfiles")}
              </p>
              <p className="text-2xl font-semibold">
                {formatNumber(availableProfiles.length)}
              </p>
              <p className="text-muted text-xs">
                {t("pages.evidence.totalProfiles", {
                  count: formatNumber(profiles.length),
                })}
              </p>
            </Card>
            <Card>
              <p className="text-muted text-xs uppercase">
                {t("pages.evidence.connectors")}
              </p>
              <p className="text-2xl font-semibold">
                {formatNumber(loadedConnectors.length)}
              </p>
              <p className="text-muted text-xs">
                {t("pages.evidence.totalConnectors", {
                  count: formatNumber(connectors.length),
                })}
              </p>
            </Card>
            <Card>
              <p className="text-muted text-xs uppercase">
                {t("pages.evidence.indexDocs")}
              </p>
              <p className="text-2xl font-semibold">
                {formatNumber(
                  indexStatsQuery.data?.stats.index_docs_total ?? 0,
                )}
              </p>
              <p className="text-muted text-xs">
                {t("pages.evidence.docsAdded", {
                  count: formatNumber(
                    indexStatsQuery.data?.stats.docs_added_last_run ?? 0,
                  ),
                })}
              </p>
            </Card>
            <Card>
              <p className="text-muted text-xs uppercase">
                {t("pages.evidence.promotion")}
              </p>
              <p className="text-2xl font-semibold">
                {formatNumber(
                  runId
                    ? (runContext?.promotionCandidates.length ?? 0)
                    : (promotionCandidatesQuery.data?.candidates?.length ?? 0),
                )}
              </p>
              <p className="text-muted text-xs">
                {runId
                  ? t("pages.evidence.runScopedPromotion")
                  : t("pages.evidence.globalPromotion")}
              </p>
            </Card>
          </div>
        </>
      )}

      {runId ? (
        <Card>
          <div
            className="flex flex-wrap gap-2"
            aria-label={t("pages.evidence.focusNav")}
          >
            {EVIDENCE_FOCUSES.map((focus) => (
              <button
                key={focus}
                type="button"
                data-testid={`evidence-focus-${focus}`}
                onClick={() => updateContext({ focus })}
                className={
                  effectiveFocus === focus
                    ? "border-accent/30 bg-accent/10 text-accent rounded-full border px-3 py-1.5 text-xs font-semibold"
                    : "border-line bg-surface text-muted rounded-full border px-3 py-1.5 text-xs font-semibold"
                }
              >
                {t(`pages.evidence.focus.${focus}`)}
              </button>
            ))}
          </div>
        </Card>
      ) : null}

      <DataIntelligencePanel
        mode={runId ? "context" : "workspace"}
        runId={runId}
        focus={effectiveFocus}
        runContext={runContext}
        selectedNeed={selectedNeed}
        selectedPlan={selectedPlan}
        selectedPromotion={selectedPromotion}
        selectedArtifact={selectedArtifact}
        degradedMessages={degradedMessages}
        onResetContext={() => {
          if (!runId) {
            return;
          }
          updateContext({ focus: "overview" });
        }}
      />

      <div className="grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
        <Card>
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-lg font-semibold">
              {runId
                ? t("pages.evidence.runContextQueue")
                : t("pages.evidence.sourceProfiles")}
            </h3>
            {!runId ? (
              <Link to="/compose" className="text-accent text-xs underline">
                {t("pages.evidence.bindIntoRun")}
              </Link>
            ) : null}
          </div>

          {runId ? (
            <div className="space-y-4">
              {runContextQuery.isLoading ? (
                <p className="text-muted text-sm">
                  {t("pages.evidence.contextLoading")}
                </p>
              ) : null}
              {runContextQuery.isError ? (
                <ApiErrorAlert
                  title={t("pages.evidence.contextLoadError")}
                  error={runContextQuery.error}
                />
              ) : null}
              {runContext ? (
                <>
                  <div>
                    <p className="text-muted mb-2 text-xs font-semibold tracking-wide uppercase">
                      {t("pages.evidence.dataNeeds")}
                    </p>
                    <div className="space-y-2">
                      {runContext.dataNeeds.map((need) => (
                        <button
                          key={need.needId}
                          type="button"
                          data-testid={`evidence-need-${need.needId}`}
                          onClick={() =>
                            updateContext({
                              focus: "need",
                              needId: need.needId,
                            })
                          }
                          className="bg-surface/80 border-line w-full rounded-2xl border p-3 text-left"
                        >
                          <p className="font-semibold">{need.metric}</p>
                          <p className="text-muted mt-1 text-xs">
                            {need.geography ?? "-"} · {need.timeStart ?? "-"} -{" "}
                            {need.timeEnd ?? "-"}
                          </p>
                        </button>
                      ))}
                      {runContext.dataNeeds.length === 0 ? (
                        <p className="text-muted text-sm">
                          {t("pages.evidence.noNeeds")}
                        </p>
                      ) : null}
                    </div>
                  </div>

                  <div>
                    <p className="text-muted mb-2 text-xs font-semibold tracking-wide uppercase">
                      {t("pages.evidence.fetchPlans")}
                    </p>
                    <div className="space-y-2">
                      {runContext.fetchPlans.map((plan) => (
                        <button
                          key={plan.planId}
                          type="button"
                          data-testid={`evidence-plan-${plan.planId}`}
                          onClick={() =>
                            updateContext({
                              focus: "plan",
                              planId: plan.planId,
                            })
                          }
                          className="bg-surface/80 border-line w-full rounded-2xl border p-3 text-left"
                        >
                          <p className="font-semibold">
                            {plan.connectorId} / {plan.datasetId}
                          </p>
                          <p className="text-muted mt-1 text-xs">
                            {label(
                              "retrievalLane",
                              plan.sourceLane,
                              plan.sourceLane,
                            )}{" "}
                            · {plan.metricId}
                          </p>
                        </button>
                      ))}
                      {runContext.fetchPlans.length === 0 ? (
                        <p className="text-muted text-sm">
                          {t("pages.evidence.noPlans")}
                        </p>
                      ) : null}
                    </div>
                  </div>

                  <div>
                    <p className="text-muted mb-2 text-xs font-semibold tracking-wide uppercase">
                      {t("pages.evidence.promotionCandidates")}
                    </p>
                    <div className="space-y-2">
                      {runContext.promotionCandidates.map((candidate) => (
                        <button
                          key={candidate.promotionId}
                          type="button"
                          data-testid={`evidence-promotion-${candidate.promotionId}`}
                          onClick={() =>
                            updateContext({
                              focus: "promotion",
                              promotionId: candidate.promotionId,
                            })
                          }
                          className="bg-surface/80 border-line w-full rounded-2xl border p-3 text-left"
                        >
                          <p className="font-semibold">{candidate.metricId}</p>
                          <p className="text-muted mt-1 text-xs">
                            {candidate.connectorId} / {candidate.datasetId}
                          </p>
                        </button>
                      ))}
                      {runContext.promotionCandidates.length === 0 ? (
                        <p className="text-muted text-sm">
                          {t("pages.evidence.noPromotions")}
                        </p>
                      ) : null}
                    </div>
                  </div>

                  <div>
                    <p className="text-muted mb-2 text-xs font-semibold tracking-wide uppercase">
                      {t("pages.evidence.relatedArtifacts")}
                    </p>
                    <div className="space-y-2">
                      {contextArtifactRefs.map((ref) => (
                        <button
                          key={ref.artifact_id}
                          type="button"
                          data-testid={`evidence-artifact-${ref.artifact_id}`}
                          onClick={() =>
                            updateContext({
                              focus: "artifact",
                              artifactId: ref.artifact_id,
                            })
                          }
                          className="bg-surface/80 border-line w-full rounded-2xl border p-3 text-left"
                        >
                          <p className="font-semibold">
                            {label(
                              "artifactKinds",
                              ref.kind,
                              ref.kind ?? ref.artifact_id,
                            )}
                          </p>
                          <p className="text-muted mt-1 font-mono text-[11px]">
                            {ref.artifact_id}
                          </p>
                        </button>
                      ))}
                      {contextArtifactRefs.length === 0 ? (
                        <p className="text-muted text-sm">
                          {t("pages.evidence.noArtifacts")}
                        </p>
                      ) : null}
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          ) : (
            <>
              {profilesQuery.isLoading ? (
                <p className="text-muted text-sm">
                  {t("pages.evidence.profilesLoading")}
                </p>
              ) : null}
              {profilesQuery.isError ? (
                <ApiErrorAlert
                  title={t("pages.evidence.profilesLoadError")}
                  error={profilesQuery.error}
                />
              ) : null}
              {!profilesQuery.isLoading && !profilesQuery.isError ? (
                <div className="space-y-3">
                  {profiles.slice(0, 6).map((profile) => (
                    <div
                      key={profile.profile_id}
                      className="bg-surface/80 border-line rounded-2xl border p-3"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="font-semibold">
                            {profile.display_name}
                          </p>
                          <p className="text-muted text-xs">
                            {profile.source_organization}
                          </p>
                        </div>
                        <Badge
                          kind={profile.connector_available ? "ok" : "warn"}
                        >
                          {profile.connector_available
                            ? "available"
                            : "coming_soon"}
                        </Badge>
                      </div>
                      <p className="text-muted mt-2 text-sm">
                        {profile.description}
                      </p>
                      <div className="text-muted mt-2 flex flex-wrap gap-2 text-xs">
                        <span className="border-line rounded-full border px-2 py-1">
                          {profile.connector_family}
                        </span>
                        {profile.estimated_datasets != null ? (
                          <span className="border-line rounded-full border px-2 py-1">
                            {t("pages.evidence.datasetsCount", {
                              count: formatNumber(profile.estimated_datasets),
                            })}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </>
          )}
        </Card>

        <div className="space-y-4">
          <Card>
            <h3 className="text-lg font-semibold">
              {t("pages.evidence.connectorsCachePosture")}
            </h3>
            {connectorsQuery.isLoading ? (
              <p className="text-muted mt-3 text-sm">
                {t("pages.evidence.connectorsLoading")}
              </p>
            ) : null}
            {connectorsQuery.isError ? (
              <ApiErrorAlert
                title={t("pages.evidence.connectorsLoadError")}
                error={connectorsQuery.error}
              />
            ) : null}
            {!connectorsQuery.isLoading && !connectorsQuery.isError ? (
              <div className="mt-3 space-y-2">
                {connectors.slice(0, 6).map((connector) => (
                  <div
                    key={connector.connector_id}
                    className="bg-surface/80 border-line rounded-xl border p-3 text-sm"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold">{connector.connector_id}</p>
                      <Badge kind={connector.loaded ? "ok" : "warn"}>
                        {connector.loaded ? "healthy" : "unavailable"}
                      </Badge>
                    </div>
                    <p className="text-muted mt-1 text-xs">
                      {connector.namespace} v{connector.version}
                    </p>
                    <p className="text-muted mt-1 text-xs">
                      {t("pages.evidence.datasetsCount", {
                        count: formatNumber(
                          connector.known_datasets?.length ?? 0,
                        ),
                      })}
                    </p>
                    {connector.last_health_check ? (
                      <p className="text-muted mt-1 text-xs">
                        {t("pages.evidence.checkedAt", {
                          date: formatDate(connector.last_health_check),
                        })}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}
          </Card>

          <Card>
            <h3 className="text-lg font-semibold">
              {runId
                ? t("pages.evidence.contextRefs")
                : t("pages.evidence.promotionLane")}
            </h3>
            {runId ? (
              <div className="mt-3">
                <EvidenceChain
                  title={t("pages.evidence.contextRefs")}
                  emptyBody={t("pages.evidence.noArtifacts")}
                  emptyTitle={t("pages.evidence.relatedArtifacts")}
                  items={[
                    runContext?.executionPlanRef,
                    runContext?.evidenceBundleRef,
                    runContext?.dataSnapshotRef,
                    runContext?.inputBindingsRef,
                  ]
                    .filter((ref): ref is EvidenceArtifactRef => Boolean(ref))
                    .map((ref) => ({
                      artifactId: ref.artifact_id,
                      href: `/artifacts/${ref.artifact_id}`,
                      label: label(
                        "artifactKinds",
                        ref.kind,
                        ref.kind ?? ref.artifact_id,
                      ),
                      meta:
                        selectedArtifact?.artifact_id === ref.artifact_id
                          ? t("pages.evidence.selectedArtifact")
                          : undefined,
                    }))}
                />
              </div>
            ) : (
              <>
                {promotionCandidatesQuery.isError ? (
                  <ApiErrorAlert
                    title={t("pages.evidence.promotionLoadError")}
                    error={promotionCandidatesQuery.error}
                  />
                ) : null}
                <div className="mt-3 space-y-2">
                  {(promotionCandidatesQuery.data?.candidates ?? [])
                    .slice(0, 5)
                    .map((candidate) => (
                      <div
                        key={candidate.promotion_id}
                        className="bg-surface/80 border-line rounded-xl border p-3 text-sm"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="font-semibold">{candidate.metric_id}</p>
                          <Badge kind="warn">{candidate.source_lane}</Badge>
                        </div>
                        <p className="text-muted mt-1 text-xs">
                          {candidate.connector_id} / {candidate.dataset_id}
                        </p>
                      </div>
                    ))}
                  {(promotionCandidatesQuery.data?.candidates ?? []).length ===
                  0 ? (
                    <p className="text-muted text-sm">
                      {t("pages.evidence.noPromotionCandidates")}
                    </p>
                  ) : null}
                </div>
              </>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
