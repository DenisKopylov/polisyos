import { useEffect, useMemo } from "react";
import { Outlet, useLocation, useNavigate, useParams } from "react-router-dom";

import { useCapabilities } from "@/api/hooks/useCapabilities";
import { useMaybeAuthz } from "@/app/authz/AuthzProvider";
import { getRunReviewTabPermission } from "@/app/authz/permissions";
import { useTelemetryReadyMark } from "@/app/providers/TelemetryProvider";
import { PrefetchButton } from "@/app/routes/PrefetchButton";
import { PrefetchNavLink } from "@/app/routes/PrefetchNavLink";
import { buildArtifactHref } from "@/features/artifacts";
import {
  RunInspectorProvider,
  useRunInspector,
} from "@/features/runs/context/RunInspectorContext";
import { AmbientTelemetryHud } from "@/features/runs/components/AmbientTelemetryHud";
import { OperatorCraftPanel } from "@/features/runs/components/OperatorCraftPanel";
import { PublicSectorReadinessPanel } from "@/features/runs/components/PublicSectorReadinessPanel";
import { PublicationReadinessPanel } from "@/features/runs/components/PublicationReadinessPanel";
import { RunBreadcrumbs } from "@/features/runs/components/RunBreadcrumbs";
import { getVisibleRunInspectorTabs } from "@/features/runs/domain/tabs";
import { MetricCard } from "@/features/runs/components/MetricCard";
import { ScientificDepthPanel } from "@/features/runs/components/ScientificDepthPanel";
import { getRunBadgeKind } from "@/features/runs/domain/status";
import { LEGACY_RUN_DETAIL_TAB_MAP } from "@/features/runs/routes/useRunDetailSummary";
import { buildEvidenceHref } from "@/features/evidence";
import {
  buildRunDeckSnapshot,
  buildRunReportSnapshot,
} from "@/features/runs/domain/compare";
import {
  buildRunDeckHref,
  parseRunDetailLegacySearchParams,
} from "@/features/runs/domain/searchParams";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  cn,
  formatDate,
  formatDuration,
  formatNumber,
} from "@/shared/lib/utils";
import {
  PageErrorBoundary,
  PanelErrorBoundary,
} from "@/shared/components/ErrorBoundary";
import { Badge, Button, Card } from "@polisyos/atlas-ui";
import {
  ApiErrorAlert,
  DetailLayout,
  OperatorDiagnosticPanel,
  ProvenanceStrip,
} from "@/shared/ui";
import {
  AuthoredText,
  AuthorshipTimeline,
  useAuthorship,
} from "@/shared/ui/authored-text";
import { Quantity, untracedDecisionQuantity } from "@/shared/ui/quantity";
import { UncertaintyBand, type IdentifiabilityState } from "@/shared/charts";
import type { ProvenanceItem } from "@/shared/brand/provenance-adapter";

function badgeKind(kind: ReturnType<typeof getRunBadgeKind>) {
  return kind === "unknown" ? "neutral" : kind;
}

function runDetailProvenance(
  summary: ReturnType<typeof useRunInspector>,
): ProvenanceItem[] {
  const items: ProvenanceItem[] = [
    {
      id: "intervention",
      glyph: "intervention",
      label: "Policy run",
      intent: "default",
    },
  ];
  if (summary.blockerCount > 0) {
    items.push({
      id: "governance",
      glyph: "blocker",
      label: "Governance blocked",
      intent: "blocked",
    });
  } else {
    items.push({
      id: "governance",
      glyph: "governance-pass",
      label: "Governance pass",
      intent: "verified",
    });
  }
  items.push({
    id: "reproducibility",
    glyph: "reproducibility",
    label: "Replayable",
    intent: "default",
  });
  return items;
}

function RunBootstrapState({ runId }: { runId: string }) {
  const { t } = useI18n();
  const capabilitiesQuery = useCapabilities();
  const authz = useMaybeAuthz();
  const tabs = getVisibleRunInspectorTabs(capabilitiesQuery.data, {
    canAccessTab: (tab) => {
      const permission = getRunReviewTabPermission(tab);
      return permission ? (authz ? authz.can(permission) : true) : true;
    },
  });

  return (
    <div className="space-y-5" data-testid="run-detail-page">
      <Card
        className="space-y-4"
        data-authored-exempt="true"
        data-authored-exempt-reason="Run bootstrap copy is structural route chrome, not decision-packet prose."
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-muted text-xs font-semibold tracking-[0.24em] uppercase">
              {t("pages.runs.title")}
            </p>
            <h2 className="mt-2 text-3xl font-semibold">
              {t("pages.runs.detailTitle", { runId })}
            </h2>
            <p className="text-muted mt-2 max-w-3xl text-sm">
              {t("pages.runs.initializingBody")}
            </p>
          </div>
          <Badge kind="warn">{t("common.pending")}</Badge>
        </div>
        <div className="bg-surface/70 border-line text-muted rounded-2xl border p-4 text-sm">
          {t("pages.runs.initializingHint")}
        </div>
      </Card>
      <nav
        aria-label={t("pages.runs.sectionNav")}
        data-testid="run-tab-nav"
        className="bg-panel/85 border-line shadow-panel rounded-2xl border px-3 py-3 backdrop-blur"
      >
        <div className="flex min-w-max gap-2 overflow-x-auto">
          {tabs.map((tab) => (
            <span
              key={tab.key}
              className="border-line bg-surface text-muted rounded-full border px-3 py-1.5 text-xs font-semibold tracking-wide uppercase"
            >
              {t(tab.labelKey)}
            </span>
          ))}
        </div>
      </nav>
    </div>
  );
}

function RunInspectorContent() {
  const { t, label } = useI18n();
  const capabilitiesQuery = useCapabilities();
  const { runId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const authz = useMaybeAuthz();
  const summary = useRunInspector();
  const decisionPacket = useMemo(
    () => buildRunReportSnapshot(summary, []),
    [summary],
  );
  const primaryUncertaintyMetric = useMemo(() => {
    const metric = summary.decisionView?.keyMetrics.find(
      (candidate) =>
        typeof candidate.ciLower === "number" &&
        typeof candidate.ciUpper === "number",
    );
    if (
      !metric ||
      typeof metric.ciLower !== "number" ||
      typeof metric.ciUpper !== "number"
    ) {
      return null;
    }
    return {
      bands: [
        {
          level: metric.ciLevel ?? 0.95,
          lower: metric.ciLower,
          upper: metric.ciUpper,
        },
      ],
      disputed: Boolean(metric.assumptionWarnings?.length),
      estimate: metric.value,
      identifiability: metric.assumptionWarnings?.length
        ? ("estimated" as IdentifiabilityState)
        : ("identified" as IdentifiabilityState),
      label: metric.name,
      level: metric.ciLevel ?? 0.95,
      unit: metric.unit,
    };
  }, [summary.decisionView?.keyMetrics]);
  const deckSnapshot = useMemo(
    () => buildRunDeckSnapshot(summary, decisionPacket),
    [decisionPacket, summary],
  );
  const tabs = getVisibleRunInspectorTabs(capabilitiesQuery.data, {
    canAccessTab: (tab) => {
      const permission = getRunReviewTabPermission(tab);
      return permission ? (authz ? authz.can(permission) : true) : true;
    },
  });
  const legacySearch = parseRunDetailLegacySearchParams(location.search);
  const canOpenEvidence = authz ? authz.can("evidence.view") : true;
  const canLaunchRuns = authz ? authz.can("runs.launch") : true;
  const { highlightMode } = useAuthorship();
  const readingViewHref = useMemo(() => {
    if (!summary.primaryDecisionArtifactId) {
      return null;
    }
    const decisionPacketId = summary.pipeline?.decision_packet_ref?.artifact_id;
    const isDecisionPacket =
      decisionPacketId === summary.primaryDecisionArtifactId ||
      summary.decisionArtifact?.kind === "scientist.decision_packet";
    if (!isDecisionPacket) {
      return null;
    }
    return buildArtifactHref(summary.primaryDecisionArtifactId, {
      tab: "content",
      view: "reading",
    });
  }, [
    summary.decisionArtifact?.kind,
    summary.pipeline?.decision_packet_ref?.artifact_id,
    summary.primaryDecisionArtifactId,
  ]);

  const activeTab =
    tabs.find((tab) => location.pathname.endsWith(`/${tab.key}`))?.key ??
    "overview";

  useTelemetryReadyMark(`runs.detail.page.${activeTab}`, {
    routeId: "runs.detail",
    runId,
    tab: activeTab,
  });

  useEffect(() => {
    if (!runId) {
      return;
    }
    const hashSection = location.hash.replace("#", "");
    const legacyTab = legacySearch.tab;
    const requested = hashSection || legacyTab;
    const mapped = requested ? LEGACY_RUN_DETAIL_TAB_MAP[requested] : null;
    if (mapped && mapped !== activeTab) {
      navigate(`/runs/${runId}/${mapped}`, { replace: true });
    }
  }, [activeTab, legacySearch.tab, location.hash, navigate, runId]);

  useEffect(() => {
    if (!runId || tabs.some((tab) => tab.key === activeTab)) {
      return;
    }

    navigate(`/runs/${runId}/${tabs[0]?.key ?? "overview"}`, {
      replace: true,
    });
  }, [activeTab, navigate, runId, tabs]);

  if (!runId) {
    return <Card>{t("pages.runs.requiredRunId")}</Card>;
  }
  if (summary.runBootstrapPending) {
    return <RunBootstrapState runId={runId} />;
  }
  if (summary.runDetailsQuery.isError) {
    return (
      <div className="space-y-5" data-testid="run-detail-page">
        <ApiErrorAlert
          title={t("pages.runs.loadRunDetailsError")}
          error={summary.runDetailsQuery.error}
        />
      </div>
    );
  }
  if (!summary.run) {
    return <Card>{t("pages.runs.unavailableRun")}</Card>;
  }

  const run = summary.run;
  const pipelineState = summary.pipeline?.iteration_lifecycle?.state ?? null;
  const decisionPacketTimestamp =
    summary.decisionView?.generatedAt ??
    run.finished_at ??
    run.started_at ??
    undefined;
  const strongestEvidenceHref = buildEvidenceHref({
    artifactId: summary.primaryDecisionArtifactId ?? undefined,
    focus: summary.primaryDecisionArtifactId ? "artifact" : "overview",
    runId,
  });
  const evaluatorScoreQuantity = untracedDecisionQuantity({
    point: summary.pipeline?.evaluator?.scores?.total_score,
    metricId: "evaluator_total_score",
    label: t("pages.runs.score", {
      score: formatNumber(summary.pipeline?.evaluator?.scores?.total_score, {
        maximumFractionDigits: 3,
      }),
    }),
    time: { valid_at: decisionPacketTimestamp },
  });
  const blockerCountQuantity = untracedDecisionQuantity({
    point: summary.blockerCount,
    metricId: "governance_blocker_count",
    label: t("pages.runs.blockers", {
      count: formatNumber(summary.blockerCount),
    }),
    unit: { code: "{blocker}", system: "ucum", display: "blockers" },
    time: { valid_at: decisionPacketTimestamp },
  });
  const decisionPacketBlockerQuantity = untracedDecisionQuantity({
    point: decisionPacket.blockerCount,
    metricId: "decision_packet_blocker_count",
    label: t("pages.runs.blockerStateLabel"),
    unit: { code: "{blocker}", system: "ucum", display: "blockers" },
    time: { valid_at: decisionPacketTimestamp },
  });

  return (
    <div className="space-y-5" data-testid="run-detail-page">
      <AmbientTelemetryHud
        activeTab={activeTab}
        runId={runId}
        summary={summary}
      />
      <DetailLayout
        sidebar={
          <section
            data-testid="run-detail-summary"
            className="border-line bg-panel rounded-[28px] border p-5"
            aria-label={t("pages.runs.detailTitle", { runId })}
            data-authored-exempt="true"
            data-authored-exempt-reason="Run summary rail labels are structural inspector chrome, not authored prose."
          >
            <RunBreadcrumbs runId={runId} />
            <p className="eyebrow mt-4">{t("pages.runs.decisionArtifact")}</p>
            <h2>{summary.decisionHeadline}</h2>
            <div className="score-ring" style={summary.decisionScoreStyle}>
              <Quantity
                value={summary.decisionScore}
                precision={2}
                variant="hero"
              />
            </div>
            <div className="space-y-3">
              <div className="bg-surface/80 border-line rounded-2xl border p-3">
                <span className="text-muted text-xs tracking-wide uppercase">
                  {t("pages.runs.evaluator")}
                </span>
                <strong className="mt-2 block">
                  {label(
                    "evaluatorVerdicts",
                    summary.pipeline?.evaluator?.verdict,
                    summary.decisionView?.verdict ??
                      summary.pipeline?.evaluator?.verdict ??
                      t("common.unknown"),
                  )}
                </strong>
              </div>
              <div className="bg-surface/80 border-line rounded-2xl border p-3">
                <span className="text-muted text-xs tracking-wide uppercase">
                  {t("pages.runs.governance")}
                </span>
                <strong className="mt-2 block">
                  <Quantity value={blockerCountQuantity} variant="dense" />
                </strong>
              </div>
              <details className="bg-surface/80 border-line rounded-2xl border p-3">
                <summary className="text-muted cursor-pointer list-none text-xs tracking-wide uppercase">
                  {t("pages.runs.diagnostics")}
                </summary>
                <div className="mt-3 space-y-3">
                  <div>
                    <span className="text-muted text-xs tracking-wide uppercase">
                      {t("pages.runs.evidence")}
                    </span>
                    <strong className="mt-2 block">
                      {t("pages.runs.evidenceSummary", {
                        plans: formatNumber(
                          summary.evidenceContext?.fetchPlans.length ?? 0,
                        ),
                        promotions: formatNumber(
                          summary.evidenceContext?.promotionCandidates.length ??
                            0,
                        ),
                      })}
                    </strong>
                  </div>
                  <div>
                    <span className="text-muted text-xs tracking-wide uppercase">
                      {t("pages.runs.transport")}
                    </span>
                    <strong className="mt-2 block">
                      {summary.transportStatus}
                    </strong>
                  </div>
                </div>
              </details>
            </div>
          </section>
        }
        content={
          <div className="space-y-5">
            <Card
              className="space-y-4"
              data-authored-exempt="true"
              data-authored-exempt-reason="Run detail header and metrics are structural inspector chrome, not authored prose."
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <ProvenanceStrip
                    title={t("pages.runs.title")}
                    items={runDetailProvenance(summary)}
                    density="compact"
                  />
                  <h3>{t("pages.runs.detailTitle", { runId })}</h3>
                  <p className="topbar-subtitle">{t("pages.runs.subtitle")}</p>
                </div>
                <div className="topbar-actions">
                  <Badge kind={badgeKind(getRunBadgeKind(run.status))}>
                    {label("runStatuses", run.status, run.status)}
                  </Badge>
                  <Badge kind="neutral">
                    {label("runSourceKinds", run.source_kind, run.source_kind)}
                  </Badge>
                  {pipelineState ? (
                    <Badge kind="neutral">
                      {label("workflowStates", pipelineState, pipelineState)}
                    </Badge>
                  ) : null}
                  {canOpenEvidence ? (
                    <PrefetchButton
                      to={buildEvidenceHref({ focus: "overview", runId })}
                      prefetch="intent"
                      variant="ghost"
                    >
                      {t("pages.runs.openEvidence")}
                    </PrefetchButton>
                  ) : (
                    <Button
                      type="button"
                      disabled
                      title={t("common.accessDenied")}
                      variant="ghost"
                    >
                      {t("pages.runs.openEvidence")}
                    </Button>
                  )}
                  <PrefetchButton
                    to={`/runs/${runId}/report`}
                    prefetch="intent"
                    variant="ghost"
                  >
                    {t("pages.runs.auditReport")}
                  </PrefetchButton>
                  <PrefetchButton
                    to={buildRunDeckHref(runId)}
                    prefetch="intent"
                    variant="ghost"
                  >
                    {t("pages.runs.openDeck")}
                  </PrefetchButton>
                  {readingViewHref ? (
                    <PrefetchButton
                      to={readingViewHref}
                      data-testid="run-reading-view-link"
                      prefetch="intent"
                      variant="ghost"
                    >
                      {t("common.readingView")}
                    </PrefetchButton>
                  ) : null}
                  {summary.pipeline?.preflight?.ready_to_run === false ||
                  summary.pipeline?.evaluator?.verdict?.startsWith("REPLAN") ? (
                    canLaunchRuns ? (
                      <PrefetchButton
                        to={`/compose?fromRun=${runId}`}
                        data-testid="run-replan-link"
                        prefetch="intent"
                        variant="primary"
                      >
                        {t("pages.runs.replan")}
                      </PrefetchButton>
                    ) : (
                      <Button
                        type="button"
                        data-testid="run-replan-link"
                        disabled
                        title={t("common.accessDenied")}
                        variant="primary"
                      >
                        {t("pages.runs.replan")}
                      </Button>
                    )
                  ) : summary.primaryDecisionArtifactId ? (
                    <PrefetchButton
                      to={`/artifacts/${summary.primaryDecisionArtifactId}`}
                      prefetch="intent"
                      variant="primary"
                    >
                      {t("common.openArtifact")}
                    </PrefetchButton>
                  ) : null}
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <MetricCard
                  label={t("pages.runs.started")}
                  value={formatDate(run.started_at)}
                  meta={`${t("pages.runs.duration")}: ${formatDuration(run.duration_ms)}`}
                />
                <MetricCard
                  label={t("pages.runs.preflight")}
                  value={
                    summary.pipeline?.preflight?.ready_to_run
                      ? t("common.ready")
                      : t("common.blocked")
                  }
                  meta={t("pages.runs.diagnosticsCount", {
                    count: formatNumber(
                      summary.pipeline?.preflight?.diagnostics?.length ?? 0,
                    ),
                  })}
                />
                <MetricCard
                  label={t("pages.runs.evaluator")}
                  value={label(
                    "evaluatorVerdicts",
                    summary.pipeline?.evaluator?.verdict,
                    summary.pipeline?.evaluator?.verdict ?? t("common.unknown"),
                  )}
                  meta={
                    <Quantity
                      value={evaluatorScoreQuantity}
                      precision={3}
                      variant="dense"
                    />
                  }
                />
                <MetricCard
                  label={t("pages.runs.governance")}
                  value={<Quantity value={blockerCountQuantity} />}
                  meta={summary.transportStatus}
                />
                <MetricCard
                  label={t("pages.runs.rootArtifacts")}
                  value={formatNumber(run.root_artifacts?.length ?? 0)}
                  meta={t("pages.runs.artifactSummary", {
                    count: formatNumber(summary.artifactRefs.length),
                  })}
                />
              </div>
            </Card>

            <div
              className={cn(
                "gap-4",
                highlightMode === "prominent" &&
                  "xl:grid xl:grid-cols-[minmax(0,1fr)_20rem] xl:items-start",
              )}
            >
              <Card
                className="space-y-4"
                data-testid="run-decision-packet"
                data-authored-exempt="true"
                data-authored-exempt-reason="Decision-packet surface headings and metric labels are structural chrome; narrative bodies are explicitly authored."
              >
                <div className="panel-header">
                  <div>
                    <p className="eyebrow">
                      {t("pages.runs.decisionPacketTitle")}
                    </p>
                    <h3>{t("pages.runs.decisionPacketHeading")}</h3>
                  </div>
                  <Badge kind="neutral">{decisionPacket.transportStatus}</Badge>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <MetricCard
                    label={t("pages.runs.verdictLabel")}
                    value={
                      label(
                        "evaluatorVerdicts",
                        decisionPacket.primaryVerdict,
                        decisionPacket.primaryVerdict ?? t("common.unknown"),
                      ) ?? t("common.unknown")
                    }
                    meta={decisionPacket.decisionHeadline}
                  />
                  <MetricCard
                    label={t("pages.runs.confidenceLabel")}
                    value={
                      decisionPacket.decisionConfidence ?? t("common.unknown")
                    }
                    meta={t("pages.runs.report.decisionScore")}
                  />
                  <MetricCard
                    label={t("pages.runs.blockerStateLabel")}
                    value={<Quantity value={decisionPacketBlockerQuantity} />}
                    meta={t("pages.runs.governance")}
                  />
                </div>

                <div className="grid gap-3 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.95fr)_minmax(0,0.95fr)]">
                  <section
                    className="bg-surface/80 border-line rounded-2xl border p-4"
                    data-authored-exempt="true"
                    data-authored-exempt-reason="Impact delta labels are metric chrome; empty state prose is explicitly authored."
                  >
                    <p className="eyebrow">
                      {t("pages.runs.impactDeltasTitle")}
                    </p>
                    <div className="mt-4 space-y-3">
                      {decisionPacket.impactRows.length > 0 ? (
                        decisionPacket.impactRows.slice(0, 4).map((row) => (
                          <div
                            key={row.label}
                            className="flex items-center justify-between gap-3"
                          >
                            <span className="text-sm font-semibold">
                              {row.label}
                            </span>
                            <span
                              className="text-muted font-mono text-sm"
                              data-quantity-metric-id={row.quantity.metric_id}
                            >
                              <Quantity value={row.quantity} variant="dense" />
                            </span>
                          </div>
                        ))
                      ) : (
                        <AuthoredText
                          author="human"
                          className="text-muted text-sm"
                          timestamp={decisionPacketTimestamp}
                        >
                          {t("pages.runs.impactDeltasEmpty")}
                        </AuthoredText>
                      )}
                    </div>
                  </section>

                  <section
                    className="bg-surface/80 border-line rounded-2xl border p-4"
                    data-authored-exempt="true"
                    data-authored-exempt-reason="Evidence card heading is structural chrome; evidence body is explicitly authored."
                  >
                    <p className="eyebrow">
                      {t("pages.runs.strongestEvidenceTitle")}
                    </p>
                    <strong className="mt-4 block text-base">
                      {decisionPacket.strongestEvidence.title}
                    </strong>
                    <AuthoredText
                      author="citation"
                      className="mt-3 text-sm leading-6 text-[var(--ink)]"
                      sourceHref={strongestEvidenceHref}
                      sourceRef={decisionPacket.strongestEvidence.provenance}
                      timestamp={decisionPacketTimestamp}
                    >
                      {decisionPacket.strongestEvidence.body}
                    </AuthoredText>
                  </section>

                  <section
                    className="bg-surface/80 border-line rounded-2xl border p-4"
                    data-authored-exempt="true"
                    data-authored-exempt-reason="Uncertainty chart labels are structural chart chrome; uncertainty prose is explicitly authored."
                  >
                    <p className="eyebrow">
                      {t("pages.runs.uncertaintyTitle")}
                    </p>
                    <AuthoredText
                      author="formalizer"
                      className="mt-4 text-sm leading-6 font-semibold"
                      timestamp={decisionPacketTimestamp}
                    >
                      {decisionPacket.mainUncertainty}
                    </AuthoredText>
                    {primaryUncertaintyMetric ? (
                      <div
                        className="border-line bg-background/55 mt-4 space-y-3 rounded-2xl border p-3"
                        data-testid="run-detail-uncertainty-visual"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold">
                              {primaryUncertaintyMetric.label}
                            </p>
                            <p className="text-muted mt-1 text-xs leading-5">
                              {t("shared.uncertainty.defaultFraming.range", {
                                confidence: Math.round(
                                  primaryUncertaintyMetric.level * 100,
                                ),
                                lower: `${primaryUncertaintyMetric.bands[0].lower.toFixed(2)}${
                                  primaryUncertaintyMetric.unit
                                }`,
                                upper: `${primaryUncertaintyMetric.bands[0].upper.toFixed(2)}${
                                  primaryUncertaintyMetric.unit
                                }`,
                              })}
                            </p>
                          </div>
                          <Badge
                            kind={
                              primaryUncertaintyMetric.disputed
                                ? "warn"
                                : "neutral"
                            }
                          >
                            {t("pages.runs.confidenceIntervalShort", {
                              confidence: Math.round(
                                primaryUncertaintyMetric.level * 100,
                              ),
                            })}
                          </Badge>
                        </div>
                        <UncertaintyBand
                          estimate={primaryUncertaintyMetric.estimate}
                          bands={primaryUncertaintyMetric.bands}
                          label={primaryUncertaintyMetric.label}
                          unit={primaryUncertaintyMetric.unit}
                          disputed={primaryUncertaintyMetric.disputed}
                          identifiability={
                            primaryUncertaintyMetric.identifiability as
                              | IdentifiabilityState
                              | undefined
                          }
                          className="w-full"
                        />
                      </div>
                    ) : null}
                  </section>
                </div>

                <section
                  className="bg-surface/80 border-line rounded-2xl border p-4"
                  data-authored-exempt="true"
                  data-authored-exempt-reason="Downstream dependency helper text is structural deck chrome, not authored prose."
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="eyebrow">
                        {t("pages.runs.downstreamDependenciesTitle")}
                      </p>
                      <p className="text-muted mt-2 text-sm">
                        {t("pages.runs.deck.dependencies")}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {deckSnapshot.close.downstreamDependencies.map((item) => (
                        <Badge key={item} kind="neutral">
                          {item}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </section>

                <ScientificDepthPanel runId={runId} summary={summary} />
                {run.operator_diagnostic ? (
                  <OperatorDiagnosticPanel
                    diagnostic={run.operator_diagnostic}
                  />
                ) : null}
                <PublicSectorReadinessPanel runId={runId} summary={summary} />
                <PublicationReadinessPanel runId={runId} summary={summary} />
                <OperatorCraftPanel runId={runId} summary={summary} />
              </Card>
              <AuthorshipTimeline />
            </div>

            <nav
              aria-label={t("pages.runs.sectionNav")}
              data-testid="run-tab-nav"
              className="bg-panel/85 border-line shadow-panel rounded-2xl border px-3 py-3 backdrop-blur"
            >
              <div className="flex min-w-max gap-2 overflow-x-auto">
                {tabs.map((tab) => (
                  <PrefetchNavLink
                    key={tab.key}
                    to={tab.key}
                    data-testid={`run-tab-link-${tab.key}`}
                    prefetch="intent"
                    className={({ isActive }) =>
                      cn(
                        "rounded-full border px-3 py-1.5 text-xs font-semibold tracking-wide uppercase",
                        isActive
                          ? "border-accent/30 bg-accent/10 text-accent"
                          : "border-line bg-surface text-muted",
                      )
                    }
                  >
                    {t(tab.labelKey)}
                  </PrefetchNavLink>
                ))}
              </div>
            </nav>

            <PageErrorBoundary
              resetKey={location.pathname}
              title={t("pages.runs.tabErrorTitle")}
              body={t("pages.runs.tabErrorBody")}
            >
              <PanelErrorBoundary
                resetKey={location.pathname}
                title={t("pages.runs.tabErrorTitle")}
                body={t("pages.runs.tabErrorBody")}
              >
                <Outlet />
              </PanelErrorBoundary>
            </PageErrorBoundary>
          </div>
        }
      />
    </div>
  );
}

export default function RunDetailLayout() {
  const { runId } = useParams();
  const { t } = useI18n();

  if (!runId) {
    return <Card>{t("pages.runs.requiredRunId")}</Card>;
  }

  return (
    <RunInspectorProvider runId={runId}>
      <RunInspectorContent />
    </RunInspectorProvider>
  );
}
