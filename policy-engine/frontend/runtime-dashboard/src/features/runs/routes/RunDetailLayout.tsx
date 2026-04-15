import { useEffect } from "react";
import { Outlet, useLocation, useNavigate, useParams } from "react-router-dom";

import { useCapabilities } from "@/api/hooks/useCapabilities";
import { useMaybeAuthz } from "@/app/authz/AuthzProvider";
import { getRunReviewTabPermission } from "@/app/authz/permissions";
import { useTelemetryReadyMark } from "@/app/providers/TelemetryProvider";
import { PrefetchButton } from "@/app/routes/PrefetchButton";
import { PrefetchNavLink } from "@/app/routes/PrefetchNavLink";
import {
  RunInspectorProvider,
  useRunInspector,
} from "@/features/runs/context/RunInspectorContext";
import { RunBreadcrumbs } from "@/features/runs/components/RunBreadcrumbs";
import { getVisibleRunInspectorTabs } from "@/features/runs/domain/tabs";
import { MetricCard } from "@/features/runs/components/MetricCard";
import { getRunBadgeKind } from "@/features/runs/domain/status";
import { LEGACY_RUN_DETAIL_TAB_MAP } from "@/features/runs/routes/useRunDetailSummary";
import { buildEvidenceHref } from "@/features/evidence";
import { parseRunDetailLegacySearchParams } from "@/features/runs/domain/searchParams";
import { useI18n } from "@/i18n/LocaleProvider";
import { cn, formatDate, formatDuration, formatNumber } from "@/lib/utils";
import {
  PageErrorBoundary,
  PanelErrorBoundary,
} from "@/shared/components/ErrorBoundary";
import { ApiErrorAlert, Badge, Button, Card, DetailLayout } from "@/shared/ui";

function badgeKind(kind: ReturnType<typeof getRunBadgeKind>) {
  return kind === "unknown" ? "neutral" : kind;
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
      <Card className="space-y-4">
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
  const tabs = getVisibleRunInspectorTabs(capabilitiesQuery.data, {
    canAccessTab: (tab) => {
      const permission = getRunReviewTabPermission(tab);
      return permission ? (authz ? authz.can(permission) : true) : true;
    },
  });
  const legacySearch = parseRunDetailLegacySearchParams(location.search);
  const canOpenEvidence = authz ? authz.can("evidence.view") : true;
  const canLaunchRuns = authz ? authz.can("runs.launch") : true;

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

  return (
    <div className="space-y-5" data-testid="run-detail-page">
      <DetailLayout
        sidebar={
          <section
            data-testid="run-detail-summary"
            className="border-line bg-panel rounded-[28px] border p-5"
            aria-label={t("pages.runs.detailTitle", { runId })}
          >
            <RunBreadcrumbs runId={runId} />
            <p className="eyebrow mt-4">{t("pages.runs.decisionArtifact")}</p>
            <h2>{summary.decisionHeadline}</h2>
            <div className="score-ring" style={summary.decisionScoreStyle}>
              <span>
                {formatNumber(summary.decisionScore, {
                  maximumFractionDigits: 2,
                })}
              </span>
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
                  {t("pages.runs.blockers", {
                    count: formatNumber(summary.blockerCount),
                  })}
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
            <Card className="space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="eyebrow">{t("pages.runs.title")}</p>
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
                  meta={t("pages.runs.score", {
                    score: formatNumber(
                      summary.pipeline?.evaluator?.scores?.total_score,
                      {
                        maximumFractionDigits: 3,
                      },
                    ),
                  })}
                />
                <MetricCard
                  label={t("pages.runs.governance")}
                  value={formatNumber(summary.blockerCount)}
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

  if (!runId) {
    return <Card>Run id is required.</Card>;
  }

  return (
    <RunInspectorProvider runId={runId}>
      <RunInspectorContent />
    </RunInspectorProvider>
  );
}
