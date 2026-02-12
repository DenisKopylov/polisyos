import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useRuns } from "../api/hooks/useRuns";
import ApiErrorAlert from "../components/shared/ApiErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import StatusBadge from "../components/shared/StatusBadge";
import { Card } from "../components/ui/card";
import { formatDate, formatDuration } from "../lib/utils";

function statusKind(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === "completed" || normalized === "done") {
    return "ok" as const;
  }
  if (normalized === "failed" || normalized === "fail") {
    return "fail" as const;
  }
  if (normalized === "running") {
    return "warn" as const;
  }
  return "unknown" as const;
}

function localDateTimeToIso(value: string | null): string | undefined {
  if (!value) {
    return undefined;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return undefined;
  }
  return parsed.toISOString();
}

export default function RunsList() {
  const [searchParams, setSearchParams] = useSearchParams();

  const status = searchParams.get("status") ?? "";
  const from = searchParams.get("from") ?? "";
  const to = searchParams.get("to") ?? "";
  const query = searchParams.get("q") ?? "";
  const cursor = searchParams.get("cursor") ?? "";

  const [statusInput, setStatusInput] = useState(status);
  const [fromInput, setFromInput] = useState(from);
  const [toInput, setToInput] = useState(to);
  const [queryInput, setQueryInput] = useState(query);
  const [cursorTrail, setCursorTrail] = useState<string[]>([""]);

  useEffect(() => {
    setStatusInput(status);
    setFromInput(from);
    setToInput(to);
    setQueryInput(query);
  }, [status, from, to, query]);

  useEffect(() => {
    setCursorTrail((previous) => {
      if (previous.includes(cursor)) {
        return previous;
      }
      return [...previous, cursor];
    });
  }, [cursor]);

  const runsFilters = useMemo(
    () => ({
      limit: 50,
      cursor: cursor || undefined,
      status: status || undefined,
      from_ts: localDateTimeToIso(from),
      to_ts: localDateTimeToIso(to),
    }),
    [cursor, from, status, to],
  );

  const runsQuery = useRuns(runsFilters);

  const filteredRuns = useMemo(() => {
    const rows = runsQuery.data?.runs ?? [];
    if (!query.trim()) {
      return rows;
    }
    const normalized = query.trim().toLowerCase();
    return rows.filter((row) => row.run_id.toLowerCase().includes(normalized));
  }, [runsQuery.data?.runs, query]);

  const currentCursorIndex = cursorTrail.lastIndexOf(cursor);
  const previousCursor = currentCursorIndex > 0 ? cursorTrail[currentCursorIndex - 1] : null;

  function updateParams(next: {
    status?: string;
    from?: string;
    to?: string;
    q?: string;
    cursor?: string | null;
  }) {
    const params = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(next)) {
      if (!value) {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    }
    setSearchParams(params);
  }

  function applyFilters(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCursorTrail([""]);
    updateParams({
      status: statusInput,
      from: fromInput,
      to: toInput,
      q: queryInput,
      cursor: null,
    });
  }

  function clearFilters() {
    setCursorTrail([""]);
    setSearchParams(new URLSearchParams());
  }

  function goNext() {
    const nextCursor = runsQuery.data?.page.next_cursor;
    if (!nextCursor) {
      return;
    }
    setCursorTrail((previous) => (previous.includes(nextCursor) ? previous : [...previous, nextCursor]));
    updateParams({
      status,
      from,
      to,
      q: query,
      cursor: nextCursor,
    });
  }

  function goPrev() {
    if (previousCursor === null) {
      return;
    }
    updateParams({
      status,
      from,
      to,
      q: query,
      cursor: previousCursor || null,
    });
  }

  return (
    <div className="space-y-4">
      <Card>
        <form className="grid gap-3 md:grid-cols-5" onSubmit={applyFilters}>
          <input
            type="text"
            value={queryInput}
            onChange={(event) => setQueryInput(event.target.value)}
            placeholder="Search run_id"
            className="rounded-lg border border-line bg-panel px-3 py-2 text-sm"
          />

          <select
            value={statusInput}
            onChange={(event) => setStatusInput(event.target.value)}
            className="rounded-lg border border-line bg-panel px-3 py-2 text-sm"
          >
            <option value="">All statuses</option>
            <option value="completed">completed</option>
            <option value="fail">fail</option>
            <option value="running">running</option>
          </select>

          <input
            type="datetime-local"
            value={fromInput}
            onChange={(event) => setFromInput(event.target.value)}
            className="rounded-lg border border-line bg-panel px-3 py-2 text-sm"
          />

          <input
            type="datetime-local"
            value={toInput}
            onChange={(event) => setToInput(event.target.value)}
            className="rounded-lg border border-line bg-panel px-3 py-2 text-sm"
          />

          <div className="flex gap-2">
            <button
              type="submit"
              className="flex-1 rounded-lg border border-text/20 bg-text px-3 py-2 text-sm font-semibold text-white"
            >
              Apply
            </button>
            <button
              type="button"
              onClick={clearFilters}
              className="rounded-lg border border-line bg-panel px-3 py-2 text-sm font-semibold"
            >
              Reset
            </button>
          </div>
        </form>
      </Card>

      {runsQuery.isLoading ? <Card>Loading runs...</Card> : null}

      {runsQuery.isError ? <ApiErrorAlert title="Unable to load runs" error={runsQuery.error} /> : null}

      {!runsQuery.isLoading && !runsQuery.isError && filteredRuns.length === 0 ? (
        <EmptyState
          title="No runs matched"
          body="The API returned no records for current filters, or local search excluded all rows."
        />
      ) : null}

      {!runsQuery.isLoading && !runsQuery.isError && filteredRuns.length > 0 ? (
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xl font-semibold">Run Explorer</h2>
            <p className="text-sm text-muted">
              page count={runsQuery.data?.page.count ?? 0}
              {runsQuery.data?.page.total !== null && runsQuery.data?.page.total !== undefined
                ? ` of ${runsQuery.data.page.total}`
                : ""}
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                  <th className="px-3 py-2">Run ID</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Started</th>
                  <th className="px-3 py-2">Duration</th>
                  <th className="px-3 py-2">Artifacts</th>
                  <th className="px-3 py-2">Source</th>
                </tr>
              </thead>
              <tbody>
                {filteredRuns.map((run) => (
                  <tr key={run.run_id} className="border-b border-line/70 last:border-b-0">
                    <td className="px-3 py-3 font-mono text-xs">
                      <Link className="underline decoration-line" to={`/runs/${run.run_id}`}>
                        {run.run_id}
                      </Link>
                    </td>
                    <td className="px-3 py-3">
                      <StatusBadge label={run.status} kind={statusKind(run.status)} />
                    </td>
                    <td className="px-3 py-3">{formatDate(run.started_at)}</td>
                    <td className="px-3 py-3">{formatDuration(run.duration_ms)}</td>
                    <td className="px-3 py-3">{run.root_artifact_count ?? 0}</td>
                    <td className="px-3 py-3">{run.source_kind}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={goPrev}
              disabled={previousCursor === null}
              className="rounded-lg border border-line bg-panel px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            >
              Prev
            </button>
            <button
              type="button"
              onClick={goNext}
              disabled={!runsQuery.data?.page.next_cursor}
              className="rounded-lg border border-line bg-panel px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
