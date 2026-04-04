import { startTransition, useDeferredValue, useEffect, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useRuns } from "@/api/hooks/useRuns";
import { PrefetchLink } from "@/app/routes/PrefetchLink";
import { useTelemetryReadyMark } from "@/app/providers/TelemetryProvider";
import { useI18n } from "@/i18n/LocaleProvider";
import { formatDate, formatDuration } from "@/lib/utils";
import {
  buildRunsListHref,
  parseRunsListSearchParams,
} from "@/features/runs/domain/searchParams";
import { useRunsListUiStore } from "@/features/runs/state/useRunsListUiStore";
import {
  AsyncSection,
  Badge,
  Button,
  Card,
  copyRow,
  copyShareLink,
  EmptyState,
  exportCsv,
  exportJson,
  FilterPanel,
  Input,
  PanelSkeleton,
  Select,
  VirtualTable,
  VIRTUALIZATION_THRESHOLD,
} from "@/shared/ui";

function statusKind(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === "completed" || normalized === "done") {
    return "ok" as const;
  }
  if (
    normalized === "failed" ||
    normalized === "fail" ||
    normalized === "rejected"
  ) {
    return "fail" as const;
  }
  if (normalized === "running" || normalized === "pending") {
    return "warn" as const;
  }
  return "unknown" as const;
}

function statusBadgeKind(status: string) {
  const kind = statusKind(status);
  return kind === "unknown" ? "neutral" : kind;
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

function isEditableTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return Boolean(
    target.closest("input, textarea, select, [contenteditable='true']") ||
    target.isContentEditable,
  );
}

export default function RunsList() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const parsedSearch = parseRunsListSearchParams(searchParams);
  const status = parsedSearch.status ?? "";
  const from = parsedSearch.from ?? "";
  const to = parsedSearch.to ?? "";
  const query = parsedSearch.q ?? "";
  const cursor = parsedSearch.cursor ?? "";
  const deferredQuery = useDeferredValue(query);

  const {
    activeRunId,
    cursorTrail,
    fromInput,
    pushCursor,
    queryInput,
    replaceDraftFilters,
    resetCursorTrail,
    setActiveRunId,
    setQueryInput,
    setStatusInput,
    setFromInput,
    setToInput,
    statusInput,
    setTableScrollTop,
    tableScrollTop,
    toInput,
  } = useRunsListUiStore();

  useTelemetryReadyMark("runs.list.page", { routeId: "runs.list" });

  useEffect(() => {
    replaceDraftFilters({
      fromInput: from,
      queryInput: query,
      statusInput: status,
      toInput: to,
    });
  }, [from, query, replaceDraftFilters, status, to]);

  useEffect(() => {
    pushCursor(cursor);
  }, [cursor, pushCursor]);

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
    if (!deferredQuery.trim()) {
      return rows;
    }
    const normalized = deferredQuery.trim().toLowerCase();
    return rows.filter(
      (row) =>
        row.run_id.toLowerCase().includes(normalized) ||
        row.status.toLowerCase().includes(normalized) ||
        row.source_kind.toLowerCase().includes(normalized),
    );
  }, [deferredQuery, runsQuery.data?.runs]);

  useEffect(() => {
    if (filteredRuns.length === 0) {
      setActiveRunId(null);
      return;
    }
    setActiveRunId((current) =>
      current && filteredRuns.some((run) => run.run_id === current)
        ? current
        : (filteredRuns[0]?.run_id ?? null),
    );
  }, [filteredRuns]);

  const currentCursorIndex = cursorTrail.lastIndexOf(cursor);
  const previousCursor =
    currentCursorIndex > 0 ? cursorTrail[currentCursorIndex - 1] : null;
  const activeRunIndex = activeRunId
    ? filteredRuns.findIndex((run) => run.run_id === activeRunId)
    : 0;
  const activeRun =
    activeRunId != null
      ? (filteredRuns.find((run) => run.run_id === activeRunId) ?? null)
      : null;

  const columns = useMemo(
    () => [
      {
        key: "runId",
        header: t("pages.runs.columns.runId"),
        exportValue: (run: (typeof filteredRuns)[number]) => run.run_id,
        render: (run: (typeof filteredRuns)[number]) => (
          <PrefetchLink
            className="decoration-line underline"
            prefetch="intent"
            to={`/runs/${run.run_id}/overview`}
          >
            {run.run_id}
          </PrefetchLink>
        ),
      },
      {
        key: "status",
        header: t("pages.runs.columns.status"),
        exportValue: (run: (typeof filteredRuns)[number]) => run.status,
        render: (run: (typeof filteredRuns)[number]) => (
          <Badge kind={statusBadgeKind(run.status)}>{run.status}</Badge>
        ),
      },
      {
        key: "started",
        header: t("pages.runs.columns.started"),
        exportValue: (run: (typeof filteredRuns)[number]) => run.started_at,
        render: (run: (typeof filteredRuns)[number]) =>
          formatDate(run.started_at),
      },
      {
        key: "duration",
        header: t("pages.runs.columns.duration"),
        exportValue: (run: (typeof filteredRuns)[number]) => run.duration_ms,
        render: (run: (typeof filteredRuns)[number]) =>
          formatDuration(run.duration_ms),
      },
      {
        key: "artifacts",
        header: t("pages.runs.columns.artifacts"),
        exportValue: (run: (typeof filteredRuns)[number]) =>
          run.root_artifact_count ?? 0,
        render: (run: (typeof filteredRuns)[number]) =>
          run.root_artifact_count ?? 0,
      },
      {
        key: "source",
        header: t("pages.runs.columns.source"),
        exportValue: (run: (typeof filteredRuns)[number]) => run.source_kind,
        render: (run: (typeof filteredRuns)[number]) => run.source_kind,
      },
    ],
    [t],
  );

  function exportRunsCsv() {
    exportCsv("runs-view.csv", filteredRuns, columns);
  }

  function exportRunsJson() {
    exportJson("runs-view.json", {
      filters: {
        cursor,
        from,
        q: query,
        status,
        to,
      },
      page: runsQuery.data?.page ?? null,
      runs: filteredRuns,
    });
  }

  function shareRunsView() {
    void copyShareLink(
      new URL(
        buildRunsListHref({
          cursor: cursor || undefined,
          from,
          q: query,
          status,
          to,
        }),
        window.location.origin,
      ),
    );
  }

  function copyActiveRun() {
    if (!activeRun) {
      return;
    }
    void copyRow(activeRun, columns);
  }

  useEffect(() => {
    function moveSelection(delta: number) {
      if (filteredRuns.length === 0) {
        return;
      }
      const currentIndex = activeRunId
        ? filteredRuns.findIndex((run) => run.run_id === activeRunId)
        : 0;
      const baseIndex = currentIndex >= 0 ? currentIndex : 0;
      const nextIndex = Math.max(
        0,
        Math.min(filteredRuns.length - 1, baseIndex + delta),
      );
      setActiveRunId(filteredRuns[nextIndex]?.run_id ?? null);
    }

    function onKeyDown(event: KeyboardEvent) {
      if (
        event.defaultPrevented ||
        event.metaKey ||
        event.ctrlKey ||
        event.altKey ||
        isEditableTarget(event.target)
      ) {
        return;
      }

      if (event.key === "j" || event.key === "ArrowDown") {
        event.preventDefault();
        moveSelection(1);
        return;
      }
      if (event.key === "k" || event.key === "ArrowUp") {
        event.preventDefault();
        moveSelection(-1);
        return;
      }
      if (event.key === "Enter" && activeRunId) {
        event.preventDefault();
        navigate(`/runs/${activeRunId}/overview`);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [activeRunId, filteredRuns, navigate]);

  function updateParams(next: {
    status?: string;
    from?: string;
    to?: string;
    q?: string;
    cursor?: string | null;
  }) {
    const href = buildRunsListHref({
      cursor: next.cursor ?? undefined,
      from: next.from,
      q: next.q,
      status: next.status,
      to: next.to,
    });
    startTransition(() => {
      setSearchParams(new URL(href, "http://localhost").searchParams);
    });
  }

  function applyFilters(event: React.SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    resetCursorTrail();
    updateParams({
      status: statusInput,
      from: fromInput,
      to: toInput,
      q: queryInput,
      cursor: null,
    });
  }

  function clearFilters() {
    resetCursorTrail();
    startTransition(() => setSearchParams(new URLSearchParams()));
  }

  function goNext() {
    const nextCursor = runsQuery.data?.page.next_cursor;
    if (!nextCursor) {
      return;
    }
    pushCursor(nextCursor);
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
    <div className="space-y-4" data-testid="runs-list-page">
      <Card>
        <p className="text-muted text-xs font-semibold tracking-[0.24em] uppercase">
          {t("pages.runs.title")}
        </p>
        <h2 className="mt-2 text-3xl font-semibold">
          {t("pages.runs.explorerTitle")}
        </h2>
        <p className="text-muted mt-2 text-sm">{t("pages.runs.subtitle")}</p>
      </Card>

      <FilterPanel
        title={t("pages.runs.searchLabel")}
        description={t("pages.runs.searchPlaceholder")}
      >
        <form className="grid gap-3 md:grid-cols-5" onSubmit={applyFilters}>
          <Input
            type="text"
            value={queryInput}
            onChange={(event) => setQueryInput(event.target.value)}
            aria-label={t("pages.runs.searchLabel")}
            placeholder={t("pages.runs.searchPlaceholder")}
          />

          <Select
            value={statusInput}
            onChange={(event) => setStatusInput(event.target.value)}
            aria-label={t("pages.runs.statusLabel")}
          >
            <option value="">{t("pages.runs.allStatuses")}</option>
            <option value="completed">
              {t("pages.runs.status.completed")}
            </option>
            <option value="fail">{t("pages.runs.status.fail")}</option>
            <option value="running">{t("pages.runs.status.running")}</option>
          </Select>

          <Input
            type="datetime-local"
            value={fromInput}
            onChange={(event) => setFromInput(event.target.value)}
            aria-label={t("pages.runs.fromLabel")}
          />

          <Input
            type="datetime-local"
            value={toInput}
            onChange={(event) => setToInput(event.target.value)}
            aria-label={t("pages.runs.toLabel")}
          />

          <div className="flex gap-2">
            <Button type="submit" fullWidth variant="primary">
              {t("pages.runs.apply")}
            </Button>
            <Button type="button" onClick={clearFilters} variant="ghost">
              {t("pages.runs.reset")}
            </Button>
          </div>
        </form>
      </FilterPanel>

      <AsyncSection
        query={runsQuery}
        loading={<PanelSkeleton rows={6} />}
        errorTitle={t("pages.runs.loadError")}
        empty={filteredRuns.length === 0}
        emptyState={
          <EmptyState
            title={t("pages.runs.emptyTitle")}
            body={t("pages.runs.emptyBody")}
          />
        }
      >
        <Card>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold">
                {t("pages.runs.explorerTitle")}
              </h2>
              <p className="text-muted mt-1 text-sm">
                {t("pages.runs.keyboardHint")}
              </p>
            </div>
            <div className="text-muted text-right text-sm">
              <p>
                {runsQuery.data?.page.total !== null &&
                runsQuery.data?.page.total !== undefined
                  ? t("pages.runs.pageCountWithTotal", {
                      count: runsQuery.data?.page.count ?? 0,
                      total: runsQuery.data.page.total,
                    })
                  : t("pages.runs.pageCount", {
                      count: runsQuery.data?.page.count ?? 0,
                    })}
              </p>
              {activeRunId ? (
                <p className="mt-1 font-mono text-xs">{activeRunId}</p>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" onClick={shareRunsView} variant="ghost">
                {t("common.shareView")}
              </Button>
              <Button
                type="button"
                onClick={copyActiveRun}
                disabled={!activeRun}
                variant="ghost"
              >
                {t("common.copy")}
              </Button>
              <Button type="button" onClick={exportRunsCsv} variant="ghost">
                {t("common.exportCsv")}
              </Button>
              <Button type="button" onClick={exportRunsJson} variant="ghost">
                {t("common.exportJson")}
              </Button>
            </div>
          </div>

          {filteredRuns.length < VIRTUALIZATION_THRESHOLD ? (
            <div className="border-line overflow-x-auto rounded-2xl border">
              <table
                aria-label={t("pages.runs.explorerTitle")}
                className="min-w-full border-collapse text-sm"
              >
                <thead>
                  <tr className="border-line text-muted border-b text-left text-xs tracking-wide uppercase">
                    {columns.map((column) => (
                      <th key={column.key} className="px-3 py-2">
                        {column.header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredRuns.map((run) => (
                    <tr
                      key={run.run_id}
                      aria-selected={activeRunId === run.run_id}
                      className={
                        activeRunId === run.run_id
                          ? "border-accent/20 bg-accent/5 border-b last:border-b-0"
                          : "border-line/70 border-b last:border-b-0"
                      }
                      onMouseEnter={() => setActiveRunId(run.run_id)}
                    >
                      {columns.map((column) => (
                        <td key={column.key} className="px-3 py-3 align-top">
                          {column.render(run)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <VirtualTable
              activeIndex={activeRunIndex >= 0 ? activeRunIndex : 0}
              ariaLabel={t("pages.runs.explorerTitle")}
              columns={columns}
              estimateRowHeight={56}
              initialScrollTop={tableScrollTop}
              maxHeight={560}
              onScrollPositionChange={setTableScrollTop}
              rowClassName={(run) =>
                activeRunId === run.run_id
                  ? "border-accent/20 bg-accent/5 border-b last:border-b-0"
                  : "border-line/70 border-b last:border-b-0"
              }
              rowKey={(run) => run.run_id}
              rowProps={(run) => ({
                "aria-selected": activeRunId === run.run_id,
                onMouseEnter: () => setActiveRunId(run.run_id),
              })}
              rows={filteredRuns}
            />
          )}

          <div className="mt-4 flex items-center justify-end gap-2">
            <Button
              type="button"
              onClick={goPrev}
              disabled={previousCursor === null}
              variant="ghost"
            >
              {t("pages.runs.prev")}
            </Button>
            <Button
              type="button"
              onClick={goNext}
              disabled={!runsQuery.data?.page.next_cursor}
              variant="ghost"
            >
              {t("pages.runs.next")}
            </Button>
          </div>
        </Card>
      </AsyncSection>
    </div>
  );
}
