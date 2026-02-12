import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useHealth } from "../api/hooks/useHealth";
import { useRuns } from "../api/hooks/useRuns";
import ApiErrorAlert from "../components/shared/ApiErrorAlert";
import StatusBadge from "../components/shared/StatusBadge";
import { Card } from "../components/ui/card";
import { formatDate, formatDuration } from "../lib/utils";

function isSuccessStatus(status: string): boolean {
  const normalized = status.toLowerCase();
  return normalized === "completed" || normalized === "ok" || normalized === "success";
}

function isFailedStatus(status: string): boolean {
  const normalized = status.toLowerCase();
  return normalized === "fail" || normalized === "failed" || normalized === "error";
}

export default function Dashboard() {
  const runsQuery = useRuns({ limit: 80 });
  const healthQuery = useHealth();

  const stats = useMemo(() => {
    const runs = runsQuery.data?.runs ?? [];
    const total = runs.length;

    let success = 0;
    let failed = 0;
    let running = 0;

    let durationTotal = 0;
    let durationCount = 0;

    for (const run of runs) {
      if (isSuccessStatus(run.status)) {
        success += 1;
      } else if (isFailedStatus(run.status)) {
        failed += 1;
      } else {
        running += 1;
      }

      if (run.duration_ms !== null && run.duration_ms !== undefined) {
        durationTotal += run.duration_ms;
        durationCount += 1;
      }
    }

    const successRate = total > 0 ? (success / total) * 100 : 0;
    const avgDurationMs = durationCount > 0 ? durationTotal / durationCount : null;

    const trendData = [...runs]
      .reverse()
      .slice(-24)
      .map((run) => ({
        runId: run.run_id,
        timestamp: formatDate(run.started_at),
        success: isSuccessStatus(run.status) ? 1 : 0,
        failed: isFailedStatus(run.status) ? 1 : 0,
        durationSec: run.duration_ms ? run.duration_ms / 1000 : 0,
      }));

    const statusRatio = [
      { name: "success", count: success },
      { name: "failed", count: failed },
      { name: "other", count: running },
    ];

    const failedRuns = runs.filter((run) => isFailedStatus(run.status)).slice(0, 6);

    return {
      total,
      success,
      failed,
      running,
      successRate,
      avgDurationMs,
      trendData,
      statusRatio,
      failedRuns,
    };
  }, [runsQuery.data?.runs]);

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold">Runtime Overview</h2>
            <p className="text-sm text-muted">
              Phases 5-6: governance/debug panel and decision-centric dashboard views.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {healthQuery.isLoading ? <StatusBadge label="Health: checking" kind="unknown" /> : null}
            {healthQuery.isError ? <StatusBadge label="Health: unavailable" kind="fail" /> : null}
            {!healthQuery.isLoading && !healthQuery.isError ? (
              <StatusBadge
                label={`Health: ${healthQuery.data?.status ?? "unknown"}`}
                kind={healthQuery.data?.status === "ok" ? "ok" : "warn"}
              />
            ) : null}
          </div>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <p className="text-xs uppercase text-muted">Total runs</p>
          <p className="text-2xl font-semibold">{stats.total}</p>
          <p className="text-xs text-muted">sampled from latest page</p>
        </Card>
        <Card>
          <p className="text-xs uppercase text-muted">Success rate</p>
          <p className="text-2xl font-semibold text-success">{stats.successRate.toFixed(1)}%</p>
          <p className="text-xs text-muted">
            success {stats.success} / failed {stats.failed}
          </p>
        </Card>
        <Card>
          <p className="text-xs uppercase text-muted">Average duration</p>
          <p className="text-2xl font-semibold">{formatDuration(stats.avgDurationMs)}</p>
          <p className="text-xs text-muted">from runs with duration</p>
        </Card>
        <Card>
          <p className="text-xs uppercase text-muted">Running/other</p>
          <p className="text-2xl font-semibold">{stats.running}</p>
          <p className="text-xs text-muted">non-success and non-failure states</p>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <h3 className="mb-2 text-lg font-semibold">Run trend</h3>
          {runsQuery.isLoading ? <p className="text-sm text-muted">Loading trend...</p> : null}
          {runsQuery.isError ? <ApiErrorAlert title="Unable to load run trend" error={runsQuery.error} /> : null}
          {!runsQuery.isLoading && !runsQuery.isError ? (
            stats.trendData.length > 0 ? (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={stats.trendData} margin={{ top: 12, right: 16, left: 8, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#dbe3ed" />
                    <XAxis dataKey="runId" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Area
                      type="monotone"
                      dataKey="durationSec"
                      stroke="#2557a7"
                      fill="#2557a7"
                      fillOpacity={0.2}
                      name="Duration (s)"
                    />
                    <Area
                      type="stepAfter"
                      dataKey="failed"
                      stroke="#b5242f"
                      fill="#b5242f"
                      fillOpacity={0.25}
                      name="Failed flag"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted">No runs available for trend chart.</p>
            )
          ) : null}
        </Card>

        <Card>
          <h3 className="mb-2 text-lg font-semibold">Status ratio</h3>
          {stats.statusRatio.some((item) => item.count > 0) ? (
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stats.statusRatio} margin={{ top: 12, right: 16, left: 8, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#dbe3ed" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#2557a7" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-muted">No status data.</p>
          )}

          <div className="mt-3 flex flex-col gap-2 text-sm">
            <Link to="/runs" className="rounded-lg border border-line bg-panel px-3 py-2 font-semibold">
              Open Run Explorer
            </Link>
            <Link to="/health" className="rounded-lg border border-line bg-panel px-3 py-2 font-semibold">
              System Health
            </Link>
          </div>
        </Card>
      </div>

      <Card>
        <h3 className="mb-2 text-lg font-semibold">Latest failed runs</h3>
        {runsQuery.isLoading ? <p className="text-sm text-muted">Loading failed runs...</p> : null}
        {runsQuery.isError ? <ApiErrorAlert title="Unable to load failed runs" error={runsQuery.error} /> : null}

        {!runsQuery.isLoading && !runsQuery.isError ? (
          stats.failedRuns.length > 0 ? (
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {stats.failedRuns.map((run) => (
                <div key={run.run_id} className="rounded-xl border border-line bg-panel p-3 text-sm">
                  <p className="font-mono text-xs">{run.run_id}</p>
                  <p className="text-xs text-muted">{formatDate(run.started_at)}</p>
                  <p className="mt-1">duration: {formatDuration(run.duration_ms)}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Link to={`/runs/${run.run_id}?tab=governance`} className="text-xs underline">
                      governance
                    </Link>
                    <Link to={`/runs/${run.run_id}?tab=debug`} className="text-xs underline">
                      debug
                    </Link>
                    <Link to={`/runs/${run.run_id}?tab=decision`} className="text-xs underline">
                      decision
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">No failed runs in current sample.</p>
          )
        ) : null}
      </Card>
    </div>
  );
}
