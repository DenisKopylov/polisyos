import type { ReactNode } from "react";
import { useMemo } from "react";
import { useReducedMotion } from "motion/react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PrefetchLink } from "@/app/routes/PrefetchLink";
import { useSuspenseDataIndexStats } from "@/api/hooks/useDataIndexStats";
import { useSuspenseDataPromotionCandidates } from "@/api/hooks/useDataPromotionCandidates";
import { useLexGraphStats } from "@/api/hooks/useLexGraphStats";
import { useSuspenseHealth } from "@/api/hooks/useHealth";
import {
  getAverageRunDuration,
  getDecisionQueue,
  groupRunsByStatus,
  useSuspenseRunsSample,
} from "@/features/runs";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { DEFAULT_LEX_OUTPUT_DIR } from "@/shared/lib/constants";
import {
  formatDuration,
  formatNumber,
  formatPercent,
} from "@/shared/lib/utils";
import { FeatureAsyncBoundary } from "@/shared/components/FeatureAsyncBoundary";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  MetricsSkeleton,
  PanelSkeleton,
} from "@polisyos/atlas-ui";
import { DataFreshnessBadge, chartTheme } from "@/shared/ui";

function DashboardMetric({
  label,
  value,
  hint,
  badge,
}: {
  label: string;
  value: string;
  hint: string;
  badge?: ReactNode;
}) {
  return (
    <article className="border-line bg-panel rounded-2xl border p-4">
      <div className="flex items-start justify-between gap-3">
        <span className="text-muted text-xs tracking-wide uppercase">
          {label}
        </span>
        {badge}
      </div>
      <strong className="text-text mt-3 block text-3xl font-semibold">
        {value}
      </strong>
      <p className="text-muted mt-2 text-sm">{hint}</p>
    </article>
  );
}

function DashboardHeroContent() {
  const { t } = useI18n();
  const healthQuery = useSuspenseHealth();
  const runsQuery = useSuspenseRunsSample();
  const lexStatsQuery = useLexGraphStats(DEFAULT_LEX_OUTPUT_DIR);

  const runs = runsQuery.data?.runs ?? [];
  const decisionQueue = useMemo(() => getDecisionQueue(runs), [runs]);
  const avgDurationMs = useMemo(() => getAverageRunDuration(runs), [runs]);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">{t("pages.dashboard.heroEyebrow")}</p>
          <h1>{t("pages.dashboard.title")}</h1>
          <p className="topbar-subtitle">{t("pages.dashboard.heroTitle")}</p>
          <p className="text-muted mt-2 max-w-3xl text-sm">
            {t("pages.dashboard.subtitle")}
          </p>
        </div>
        <div className="topbar-actions">
          <Badge kind="neutral">
            {t("pages.dashboard.healthStatus", {
              status: healthQuery.data?.status ?? t("common.unknown"),
            })}
          </Badge>
          <DataFreshnessBadge />
          <Badge kind={lexStatsQuery.data?.db_exists ? "ok" : "warn"}>
            {lexStatsQuery.data?.db_exists
              ? t("pages.dashboard.graphReady")
              : t("pages.dashboard.graphPending")}
          </Badge>
        </div>
      </div>

      <div className="bg-surface/70 border-line rounded-2xl border p-4">
        <p className="text-muted text-sm">{t("pages.dashboard.heroBody")}</p>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div>
            <span className="text-muted text-xs tracking-wide uppercase">
              {t("pages.dashboard.activeRuns")}
            </span>
            <strong className="mt-2 block text-2xl font-semibold">
              {t("common.unavailable")}
            </strong>
          </div>
          <div>
            <span className="text-muted text-xs tracking-wide uppercase">
              {t("pages.dashboard.latestDecisions")}
            </span>
            <strong className="mt-2 block text-2xl font-semibold">
              {formatNumber(decisionQueue.length)}
            </strong>
          </div>
          <div>
            <span className="text-muted text-xs tracking-wide uppercase">
              {t("pages.dashboard.avgDuration")}
            </span>
            <strong className="mt-2 block text-2xl font-semibold">
              {formatDuration(avgDurationMs)}
            </strong>
          </div>
        </div>
      </div>
    </div>
  );
}

function DashboardActionQueueContent() {
  const { t } = useI18n();
  const runsQuery = useSuspenseRunsSample();
  const decisionQueue = getDecisionQueue(runsQuery.data?.runs ?? []);

  if (decisionQueue.length === 0) {
    return (
      <EmptyState
        title={t("pages.dashboard.queueEmptyTitle")}
        body={t("pages.dashboard.queueEmptyBody")}
        actions={
          <Button to="/compose" variant="ghost">
            {t("pages.dashboard.openComposer")}
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      {decisionQueue.slice(0, 4).map((run) => (
        <PrefetchLink
          key={run.run_id}
          prefetch="intent"
          to={`/runs/${run.run_id}/overview`}
          className="bg-surface/75 hover:border-accent/35 border-line block rounded-2xl border p-4 transition"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold">{run.run_id}</p>
              <p className="text-muted mt-1 text-sm">
                {t("pages.dashboard.runCardMeta", {
                  duration: formatDuration(run.duration_ms),
                  artifacts: formatNumber(run.root_artifact_count ?? 0),
                })}
              </p>
            </div>
            <Badge kind="neutral">{run.status}</Badge>
          </div>
        </PrefetchLink>
      ))}
    </div>
  );
}

function DashboardMetricsContent() {
  const { t } = useI18n();
  const runsQuery = useSuspenseRunsSample();
  const indexStatsQuery = useSuspenseDataIndexStats();
  const runs = runsQuery.data?.runs ?? [];
  const unavailable = t("common.unavailable");

  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <DashboardMetric
        label={t("pages.dashboard.activeRuns")}
        value={unavailable}
        hint={t("pages.dashboard.activeRunsHint")}
        badge={<Badge kind="neutral">{unavailable}</Badge>}
      />
      <DashboardMetric
        label={t("pages.dashboard.blockedRuns")}
        value={unavailable}
        hint={t("pages.dashboard.blockedRunsHint")}
        badge={<Badge kind="neutral">{unavailable}</Badge>}
      />
      <DashboardMetric
        label={t("pages.dashboard.successRateTitle")}
        value={unavailable}
        hint={t("pages.dashboard.successRateHint", {
          count: formatNumber(runs.length),
        })}
      />
      <DashboardMetric
        label={t("pages.dashboard.indexFreshness")}
        value={formatNumber(
          indexStatsQuery.data?.stats.docs_added_last_run ?? 0,
        )}
        hint={t("pages.dashboard.indexFreshnessHint")}
      />
    </section>
  );
}

function DashboardNarrativeContent() {
  const { t } = useI18n();
  const runsQuery = useSuspenseRunsSample();
  const indexStatsQuery = useSuspenseDataIndexStats();
  const promotionCandidatesQuery = useSuspenseDataPromotionCandidates();
  const runs = runsQuery.data?.runs ?? [];
  const decisionQueue = getDecisionQueue(runs);
  const unavailable = t("common.unavailable");
  const docsAdded = indexStatsQuery.data?.stats.docs_added_last_run ?? 0;
  const promotions = promotionCandidatesQuery.data?.candidates?.length ?? 0;

  const items = [
    {
      body: t("pages.dashboard.narrativeAttentionBody", {
        blocked: unavailable,
        count: unavailable,
      }),
      label: t("pages.dashboard.narrativeAttention"),
      value: unavailable,
    },
    {
      body: t("pages.dashboard.narrativeThroughputBody", {
        success: unavailable,
        total: unavailable,
      }),
      label: t("pages.dashboard.narrativeThroughput"),
      value: unavailable,
    },
    {
      body: t("pages.dashboard.narrativeQueueBody", {
        count: formatNumber(decisionQueue.length),
      }),
      label: t("pages.dashboard.narrativeQueue"),
      value: formatNumber(decisionQueue.length),
    },
    {
      body: t("pages.dashboard.narrativeEvidenceBody", {
        docs: formatNumber(docsAdded),
        promotions: formatNumber(promotions),
      }),
      label: t("pages.dashboard.narrativeEvidence"),
      value: `${formatNumber(docsAdded)} / ${formatNumber(promotions)}`,
    },
  ];

  return (
    <div className="grid gap-4 lg:grid-cols-4">
      {items.map((item) => (
        <article
          key={item.label}
          className="bg-surface/75 border-line rounded-2xl border p-4"
        >
          <span className="text-muted text-xs tracking-wide uppercase">
            {item.label}
          </span>
          <strong className="mt-2 block text-2xl font-semibold">
            {item.value}
          </strong>
          <p className="text-muted mt-2 text-sm">{item.body}</p>
        </article>
      ))}
    </div>
  );
}

function DashboardStatusChartContent() {
  const { t } = useI18n();
  const prefersReducedMotion = useReducedMotion();
  const runsQuery = useSuspenseRunsSample();
  const statusBreakdown = groupRunsByStatus(runsQuery.data?.runs ?? []);

  if (statusBreakdown.length === 0) {
    return (
      <EmptyState
        title={t("pages.dashboard.statusChartEmptyTitle")}
        body={t("pages.dashboard.statusChartEmptyBody")}
      />
    );
  }

  return (
    <div className="h-[280px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={statusBreakdown}>
          <CartesianGrid stroke={chartTheme.grid} vertical={false} />
          <XAxis dataKey="status" stroke={chartTheme.axis} fontSize={12} />
          <YAxis allowDecimals={false} stroke={chartTheme.axis} fontSize={12} />
          <Tooltip
            formatter={(value) => [
              formatNumber(Number(value)),
              t("pages.dashboard.runsTooltipLabel"),
            ]}
            labelFormatter={(value) => String(value)}
          />
          <Bar
            dataKey="count"
            fill={chartTheme.primary}
            isAnimationActive={!prefersReducedMotion}
            radius={[10, 10, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function DashboardDurationTrendContent() {
  const { t } = useI18n();
  const prefersReducedMotion = useReducedMotion();
  const runsQuery = useSuspenseRunsSample();
  const durationTrend = (runsQuery.data?.runs ?? [])
    .filter(
      (run) =>
        typeof run.duration_ms === "number" && Number.isFinite(run.duration_ms),
    )
    .slice(0, 8)
    .map((run, index) => ({
      name: run.run_id.slice(-4) || `#${index + 1}`,
      durationMs: run.duration_ms ?? 0,
      artifacts: run.root_artifact_count ?? 0,
    }));

  if (durationTrend.length < 2) {
    return (
      <EmptyState
        title={t("pages.dashboard.trendEmptyTitle")}
        body={t("pages.dashboard.trendEmptyBody")}
      />
    );
  }

  return (
    <div className="h-[280px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={durationTrend}>
          <CartesianGrid stroke={chartTheme.grid} vertical={false} />
          <XAxis dataKey="name" stroke={chartTheme.axis} fontSize={12} />
          <YAxis
            stroke={chartTheme.axis}
            fontSize={12}
            tickFormatter={(value) => `${Math.round(Number(value) / 1000)}s`}
          />
          <Tooltip
            formatter={(value, name) => [
              name === "durationMs"
                ? formatDuration(Number(value))
                : formatNumber(Number(value)),
              name === "durationMs"
                ? t("pages.dashboard.trendDurationLabel")
                : t("pages.dashboard.trendArtifactsLabel"),
            ]}
          />
          <Line
            type="monotone"
            dataKey="durationMs"
            stroke={chartTheme.alert}
            strokeWidth={3}
            isAnimationActive={!prefersReducedMotion}
            dot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function DashboardCoverageContent() {
  const { t } = useI18n();
  const indexStatsQuery = useSuspenseDataIndexStats();
  const sourceCoverage = Object.entries(
    indexStatsQuery.data?.stats.source_coverage ?? {},
  )
    .map(([source, count]) => ({ source: source.replace(/_/g, " "), count }))
    .sort((left, right) => right.count - left.count)
    .slice(0, 6);

  if (sourceCoverage.length === 0) {
    return (
      <EmptyState
        title={t("pages.dashboard.coverageEmptyTitle")}
        body={t("pages.dashboard.coverageEmptyBody")}
      />
    );
  }

  return (
    <div className="space-y-3">
      {sourceCoverage.map((item) => (
        <div
          key={item.source}
          className="bg-surface/75 border-line rounded-2xl border p-4"
        >
          <div className="flex items-center justify-between gap-3">
            <strong className="capitalize">{item.source}</strong>
            <span className="text-muted text-sm font-semibold">
              {formatNumber(item.count)}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function DashboardPromotionsContent() {
  const { t } = useI18n();
  const promotionCandidatesQuery = useSuspenseDataPromotionCandidates();
  const promotionCandidates = promotionCandidatesQuery.data?.candidates ?? [];

  if (promotionCandidates.length === 0) {
    return (
      <EmptyState
        title={t("pages.dashboard.promotionsEmptyTitle")}
        body={t("pages.dashboard.promotionsEmptyBody")}
      />
    );
  }

  return (
    <div className="space-y-3">
      {promotionCandidates.slice(0, 4).map((candidate) => (
        <PrefetchLink
          key={candidate.promotion_id}
          prefetch="viewport"
          to={`/evidence?focus=promotion&promotionId=${candidate.promotion_id}`}
          className="bg-surface/75 hover:border-accent/35 border-line block rounded-2xl border p-4 transition"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold">{candidate.metric_id}</p>
              <p className="text-muted mt-1 text-sm">
                {candidate.connector_id} / {candidate.dataset_id}
              </p>
            </div>
            <Badge kind="warn">{candidate.status ?? t("common.pending")}</Badge>
          </div>
          <p className="text-muted mt-3 text-xs">
            {t("pages.dashboard.promotionMeta", {
              lane: candidate.source_lane,
              confidence: formatPercent(candidate.confidence ?? 0, {
                maximumFractionDigits: 1,
              }),
            })}
          </p>
        </PrefetchLink>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const { t } = useI18n();

  return (
    <div className="space-y-5" data-testid="dashboard-page">
      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.8fr)_minmax(320px,1fr)]">
        <Card>
          <FeatureAsyncBoundary
            feature="dashboard.hero"
            title={t("pages.dashboard.runsLoadError")}
            body={t("common.pageErrorBody")}
            loading={
              <PanelSkeleton rows={5} className="border-0 bg-transparent p-0" />
            }
          >
            <DashboardHeroContent />
          </FeatureAsyncBoundary>
        </Card>

        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.dashboard.actionQueueTitle")}</p>
              <h2>{t("pages.dashboard.actionQueueHeading")}</h2>
            </div>
          </div>
          <FeatureAsyncBoundary
            feature="dashboard.actionQueue"
            title={t("pages.dashboard.queueLoadError")}
            body={t("common.pageErrorBody")}
            loading={
              <PanelSkeleton rows={3} className="border-0 bg-transparent p-0" />
            }
          >
            <DashboardActionQueueContent />
          </FeatureAsyncBoundary>
        </Card>
      </section>

      <FeatureAsyncBoundary
        feature="dashboard.metrics"
        title={t("pages.dashboard.runsLoadError")}
        body={t("common.pageErrorBody")}
        loading={<MetricsSkeleton />}
      >
        <DashboardMetricsContent />
      </FeatureAsyncBoundary>

      <Card className="space-y-4">
        <div className="panel-header">
          <div>
            <p className="eyebrow">{t("pages.dashboard.narrativeTitle")}</p>
            <h2>{t("pages.dashboard.narrativeHeading")}</h2>
          </div>
        </div>
        <FeatureAsyncBoundary
          feature="dashboard.narrative"
          title={t("pages.dashboard.runsLoadError")}
          body={t("common.pageErrorBody")}
          loading={
            <PanelSkeleton rows={4} className="border-0 bg-transparent p-0" />
          }
        >
          <DashboardNarrativeContent />
        </FeatureAsyncBoundary>
      </Card>

      <section className="grid gap-5 xl:grid-cols-2">
        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.dashboard.statusChartTitle")}</p>
              <h2>{t("pages.dashboard.statusChartHeading")}</h2>
            </div>
          </div>
          <FeatureAsyncBoundary
            feature="dashboard.statusChart"
            title={t("pages.dashboard.runsLoadError")}
            body={t("common.pageErrorBody")}
            loading={
              <PanelSkeleton rows={5} className="border-0 bg-transparent p-0" />
            }
          >
            <DashboardStatusChartContent />
          </FeatureAsyncBoundary>
        </Card>

        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.dashboard.trendTitle")}</p>
              <h2>{t("pages.dashboard.trendHeading")}</h2>
            </div>
          </div>
          <FeatureAsyncBoundary
            feature="dashboard.durationTrend"
            title={t("pages.dashboard.runsLoadError")}
            body={t("common.pageErrorBody")}
            loading={
              <PanelSkeleton rows={5} className="border-0 bg-transparent p-0" />
            }
          >
            <DashboardDurationTrendContent />
          </FeatureAsyncBoundary>
        </Card>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.dashboard.coverageTitle")}</p>
              <h2>{t("pages.dashboard.coverageHeading")}</h2>
            </div>
          </div>
          <FeatureAsyncBoundary
            feature="dashboard.sourceCoverage"
            title={t("pages.dashboard.coverageLoadError")}
            body={t("common.pageErrorBody")}
            loading={
              <PanelSkeleton rows={4} className="border-0 bg-transparent p-0" />
            }
          >
            <DashboardCoverageContent />
          </FeatureAsyncBoundary>
        </Card>

        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.dashboard.promotionsTitle")}</p>
              <h2>{t("pages.dashboard.promotionsHeading")}</h2>
            </div>
          </div>
          <FeatureAsyncBoundary
            feature="dashboard.promotions"
            title={t("pages.dashboard.promotionsLoadError")}
            body={t("common.pageErrorBody")}
            loading={
              <PanelSkeleton rows={4} className="border-0 bg-transparent p-0" />
            }
          >
            <DashboardPromotionsContent />
          </FeatureAsyncBoundary>
        </Card>
      </section>
    </div>
  );
}
