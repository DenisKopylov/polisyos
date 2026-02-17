import { useMemo, useState } from "react";

import { useDataCatalogSearch } from "../../api/hooks/useDataCatalogSearch";
import { useDataIndexStats } from "../../api/hooks/useDataIndexStats";
import { useDataPromotionCandidates } from "../../api/hooks/useDataPromotionCandidates";
import { useDiscoverDataSources } from "../../api/hooks/useDiscoverDataSources";
import { usePreviewFetchPlan } from "../../api/hooks/usePreviewFetchPlan";
import {
  useApprovePromotionCandidate,
  useRejectPromotionCandidate,
} from "../../api/hooks/usePromotionDecision";
import { useResolveDataNeeds } from "../../api/hooks/useResolveDataNeeds";
import type { components } from "../../api/types";
import ApiErrorAlert from "../shared/ApiErrorAlert";
import { Card } from "../ui/card";

type RetrievalMode = "fastlane" | "hybrid" | "explorelane";
type FetchPlan = components["schemas"]["FetchPlan"];
type DataNeed = components["schemas"]["DataNeed"];

function formatPercent(value: number | null | undefined): string {
  if (value == null) {
    return "-";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(2)} MB`;
}

export default function DataIntelligencePanel() {
  const [metric, setMetric] = useState("");
  const [geography, setGeography] = useState("");
  const [timeStart, setTimeStart] = useState("");
  const [timeEnd, setTimeEnd] = useState("");
  const [granularity, setGranularity] = useState("annual");
  const [qualityMin, setQualityMin] = useState(0.6);
  const [mode, setMode] = useState<RetrievalMode>("hybrid");
  const [allowExploreFallback, setAllowExploreFallback] = useState(true);

  const [maxSourcesPerQuery, setMaxSourcesPerQuery] = useState(5);
  const [maxDiscoveryCallsPerSource, setMaxDiscoveryCallsPerSource] = useState(25);
  const [maxCandidatesTotal, setMaxCandidatesTotal] = useState(50);
  const [timeBudgetMs, setTimeBudgetMs] = useState(5000);

  const [lastPreviewPlanId, setLastPreviewPlanId] = useState<string | null>(null);
  const [promotionReason, setPromotionReason] = useState("");

  const indexStatsQuery = useDataIndexStats();
  const promotionCandidatesQuery = useDataPromotionCandidates();
  const resolveMutation = useResolveDataNeeds();
  const discoverMutation = useDiscoverDataSources();
  const previewMutation = usePreviewFetchPlan();
  const approveMutation = useApprovePromotionCandidate();
  const rejectMutation = useRejectPromotionCandidate();

  const catalogQuery = useDataCatalogSearch({
    metricQuery: metric,
    geography: geography || null,
    limit: 20,
    enabled: metric.trim().length >= 2,
  });

  const canRun = metric.trim().length > 0;
  const resolvedPlans = resolveMutation.data?.fetch_plans ?? [];
  const resolvedCandidates = resolveMutation.data?.candidates ?? [];
  const discoverCandidates = discoverMutation.data?.candidates ?? [];

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
      purpose: "data_intelligence_ui",
    };
  }, [canRun, geography, granularity, metric, qualityMin, timeEnd, timeStart]);

  function handleResolve() {
    if (!currentNeed) {
      return;
    }
    resolveMutation.mutate({
      data_needs: [currentNeed],
      mode,
      allow_explore_fallback: allowExploreFallback,
    });
  }

  function handleDiscover() {
    if (!currentNeed) {
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
    setLastPreviewPlanId(plan.plan_id);
    previewMutation.mutate({
      fetch_plan: plan,
      allow_fallback: true,
    });
  }

  const selectedPreview = previewMutation.data?.preview ?? null;

  return (
    <div className="space-y-4">
      <Card>
        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted">
            Data Intelligence Controls
          </h3>
          <span className="text-xs text-muted">FastLane / ExploreLane / PromotionLane</span>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs text-muted">Metric</label>
            <input
              type="text"
              value={metric}
              onChange={(event) => setMetric(event.target.value)}
              placeholder="us.macro.gdp_nominal"
              className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">Geography</label>
            <input
              type="text"
              value={geography}
              onChange={(event) => setGeography(event.target.value)}
              placeholder="USA / EU*"
              className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">Granularity</label>
            <select
              value={granularity}
              onChange={(event) => setGranularity(event.target.value)}
              className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
            >
              <option value="annual">annual</option>
              <option value="quarterly">quarterly</option>
              <option value="monthly">monthly</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">Time start</label>
            <input
              type="text"
              value={timeStart}
              onChange={(event) => setTimeStart(event.target.value)}
              placeholder="2015"
              className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">Time end</label>
            <input
              type="text"
              value={timeEnd}
              onChange={(event) => setTimeEnd(event.target.value)}
              placeholder="2024"
              className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">Quality min</label>
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={qualityMin}
              onChange={(event) => setQualityMin(Number(event.target.value))}
              className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
            />
          </div>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <div>
            <label className="mb-1 block text-xs text-muted">Retrieval mode</label>
            <select
              value={mode}
              onChange={(event) => setMode(event.target.value as RetrievalMode)}
              className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
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
                onChange={(event) => setAllowExploreFallback(event.target.checked)}
                className="accent-accent"
              />
              allow explore fallback
            </label>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!canRun || resolveMutation.isPending}
            onClick={handleResolve}
            className="rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
          >
            {resolveMutation.isPending ? "Resolving..." : "Resolve DataNeeds"}
          </button>
          <button
            type="button"
            disabled={!canRun || discoverMutation.isPending}
            onClick={handleDiscover}
            className="rounded-xl border border-line bg-panel px-4 py-2 text-xs font-semibold disabled:opacity-50"
          >
            {discoverMutation.isPending ? "Discovering..." : "Run Explore Discovery"}
          </button>
        </div>
        {resolveMutation.error && (
          <div className="mt-3">
            <ApiErrorAlert title="Resolve failed" error={resolveMutation.error} />
          </div>
        )}
        {discoverMutation.error && (
          <div className="mt-3">
            <ApiErrorAlert title="Discover failed" error={discoverMutation.error} />
          </div>
        )}
      </Card>

      <Card>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
          Local Index and Discovery Stats
        </h3>
        {indexStatsQuery.isLoading ? <p className="text-sm text-muted">Loading index stats...</p> : null}
        {indexStatsQuery.error ? <ApiErrorAlert error={indexStatsQuery.error} /> : null}
        {indexStatsQuery.data ? (
          <>
            <div className="grid gap-2 md:grid-cols-4">
              <div className="rounded-lg border border-line bg-surface/40 p-2 text-xs">
                <p className="text-muted">Index docs</p>
                <p className="text-sm font-semibold">
                  {indexStatsQuery.data.stats.index_docs_total.toLocaleString()}
                </p>
              </div>
              <div className="rounded-lg border border-line bg-surface/40 p-2 text-xs">
                <p className="text-muted">Index size</p>
                <p className="text-sm font-semibold">
                  {formatBytes(indexStatsQuery.data.stats.index_size_bytes)}
                </p>
              </div>
              <div className="rounded-lg border border-line bg-surface/40 p-2 text-xs">
                <p className="text-muted">Indexed sources</p>
                <p className="text-sm font-semibold">
                  {indexStatsQuery.data.stats.indexed_sources.toLocaleString()}
                </p>
              </div>
              <div className="rounded-lg border border-line bg-surface/40 p-2 text-xs">
                <p className="text-muted">Docs added last run</p>
                <p className="text-sm font-semibold">
                  {indexStatsQuery.data.stats.docs_added_last_run.toLocaleString()}
                </p>
              </div>
            </div>
            <div className="mt-3">
              <p className="mb-1 text-xs text-muted">Source coverage</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(indexStatsQuery.data.stats.source_coverage ?? {}).map(
                  ([source, count]) => (
                    <span
                      key={source}
                      className="rounded border border-line bg-canvas/50 px-2 py-1 font-mono text-[11px]"
                    >
                      {source}: {count}
                    </span>
                  ),
                )}
              </div>
            </div>
          </>
        ) : null}
        {discoverMutation.data ? (
          <p className="mt-3 text-xs text-muted">
            Last discover fetched {discoverMutation.data.docs_fetched_total} metadata docs and
            returned {(discoverMutation.data.candidates ?? []).length} candidates.
          </p>
        ) : null}
      </Card>

      <Card>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
          Catalog Search and Resolve Results
        </h3>
        {catalogQuery.isLoading ? <p className="text-sm text-muted">Searching catalog...</p> : null}
        {catalogQuery.error ? <ApiErrorAlert error={catalogQuery.error} /> : null}
        {catalogQuery.data ? (
          <p className="mb-2 text-xs text-muted">
            Catalog matches: {catalogQuery.data.total_matches} for query `{catalogQuery.data.query}`
          </p>
        ) : null}
        {(catalogQuery.data?.matches ?? []).slice(0, 5).map((candidate) => (
          <div
            key={candidate.candidate_id}
            className="mb-2 rounded-lg border border-line bg-surface/50 p-2 text-xs"
          >
            <p className="font-mono">
              {candidate.metric_id} {"->"} {candidate.connector_id} / {candidate.dataset_id}
            </p>
            <p className="text-muted">
              confidence {formatPercent(candidate.confidence)} | lane {candidate.source_lane}
            </p>
          </div>
        ))}
        {resolveMutation.data ? (
          <div className="mt-3 space-y-2">
            <p className="text-xs text-muted">
              Resolved {resolvedPlans.length} plans from {resolvedCandidates.length} candidates.
            </p>
            {(resolveMutation.data.warnings ?? []).length > 0 ? (
              <ul className="text-xs text-yellow-700">
                {(resolveMutation.data.warnings ?? []).map((warning, index) => (
                  <li key={`${warning}-${index}`}>{warning}</li>
                ))}
              </ul>
            ) : null}
            {resolvedPlans.map((plan) => (
              <div key={plan.plan_id} className="rounded-lg border border-line bg-surface/50 p-2 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-mono">
                    {plan.metric_id} {"->"} {plan.connector_id} / {plan.dataset_id}
                  </p>
                  <button
                    type="button"
                    onClick={() => handlePreview(plan)}
                    disabled={previewMutation.isPending}
                    className="rounded border border-line bg-panel px-2 py-1 text-[11px] font-semibold"
                  >
                    Preview
                  </button>
                </div>
                <p className="text-muted">
                  lane={plan.source_lane} quality_min={plan.quality_min} fallbacks=
                  {(plan.fallbacks ?? []).length}
                </p>
                {lastPreviewPlanId === plan.plan_id && selectedPreview ? (
                  <div className="mt-2 rounded border border-line bg-canvas/40 p-2">
                    <p>
                      status={selectedPreview.status}, rows={selectedPreview.row_count}, completeness=
                      {formatPercent(selectedPreview.completeness)}, coverage_ok=
                      {selectedPreview.coverage_ok ? "yes" : "no"}
                    </p>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
        {discoverCandidates.length > 0 ? (
          <div className="mt-3">
            <p className="mb-1 text-xs text-muted">Explore candidates ({discoverCandidates.length})</p>
            {discoverCandidates.slice(0, 5).map((candidate) => (
              <div
                key={candidate.candidate_id}
                className="mb-1 rounded border border-line bg-canvas/40 p-2 text-xs"
              >
                <p className="font-mono">
                  {candidate.metric_id} {"->"} {candidate.connector_id} / {candidate.dataset_id}
                </p>
                <p className="text-muted">confidence {formatPercent(candidate.confidence)}</p>
              </div>
            ))}
          </div>
        ) : null}
      </Card>

      <Card>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
          Promotion Queue
        </h3>
        {promotionCandidatesQuery.isLoading ? (
          <p className="text-sm text-muted">Loading promotion candidates...</p>
        ) : null}
        {promotionCandidatesQuery.error ? <ApiErrorAlert error={promotionCandidatesQuery.error} /> : null}
        <div className="mb-3">
          <label className="mb-1 block text-xs text-muted">Decision reason (optional)</label>
          <input
            type="text"
            value={promotionReason}
            onChange={(event) => setPromotionReason(event.target.value)}
            placeholder="Reason for approve/reject"
            className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
          />
        </div>
        {(promotionCandidatesQuery.data?.candidates ?? []).length === 0 ? (
          <p className="text-sm text-muted">No promotion candidates yet.</p>
        ) : null}
        {(promotionCandidatesQuery.data?.candidates ?? []).map((candidate) => (
          <div key={candidate.promotion_id} className="mb-2 rounded-lg border border-line bg-surface/50 p-2">
            <p className="font-mono text-xs">
              {candidate.metric_id} {"->"} {candidate.connector_id} / {candidate.dataset_id}
            </p>
            <p className="text-xs text-muted">
              status={candidate.status} confidence={formatPercent(candidate.confidence)}
            </p>
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                disabled={approveMutation.isPending}
                onClick={() =>
                  approveMutation.mutate({
                    promotionId: candidate.promotion_id,
                    reason: promotionReason.trim() || undefined,
                  })
                }
                className="rounded border border-green-600/40 bg-green-600/10 px-2 py-1 text-[11px] font-semibold text-green-700"
              >
                Approve
              </button>
              <button
                type="button"
                disabled={rejectMutation.isPending}
                onClick={() =>
                  rejectMutation.mutate({
                    promotionId: candidate.promotion_id,
                    reason: promotionReason.trim() || undefined,
                  })
                }
                className="rounded border border-red-600/40 bg-red-600/10 px-2 py-1 text-[11px] font-semibold text-red-700"
              >
                Reject
              </button>
            </div>
          </div>
        ))}
        {approveMutation.error ? (
          <div className="mt-2">
            <ApiErrorAlert title="Approve failed" error={approveMutation.error} />
          </div>
        ) : null}
        {rejectMutation.error ? (
          <div className="mt-2">
            <ApiErrorAlert title="Reject failed" error={rejectMutation.error} />
          </div>
        ) : null}
      </Card>

      <Card>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
          Explore Lane Budget
        </h3>
        <div className="grid gap-3 md:grid-cols-4">
          <div>
            <label className="mb-1 block text-xs text-muted">Max sources/query</label>
            <input
              type="number"
              min={1}
              max={50}
              value={maxSourcesPerQuery}
              onChange={(event) => setMaxSourcesPerQuery(Number(event.target.value))}
              className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">Max calls/source</label>
            <input
              type="number"
              min={1}
              max={500}
              value={maxDiscoveryCallsPerSource}
              onChange={(event) => setMaxDiscoveryCallsPerSource(Number(event.target.value))}
              className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">Max candidates total</label>
            <input
              type="number"
              min={1}
              max={500}
              value={maxCandidatesTotal}
              onChange={(event) => setMaxCandidatesTotal(Number(event.target.value))}
              className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">Time budget (ms)</label>
            <input
              type="number"
              min={100}
              max={120000}
              value={timeBudgetMs}
              onChange={(event) => setTimeBudgetMs(Number(event.target.value))}
              className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
            />
          </div>
        </div>
      </Card>
    </div>
  );
}
