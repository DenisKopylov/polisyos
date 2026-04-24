import { startTransition, useEffect, useMemo, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useRuns } from "@/api/hooks/useRuns";
import { PrefetchLink } from "@/app/routes/PrefetchLink";
import { useTelemetryReadyMark } from "@/app/providers/TelemetryProvider";
import { buildEvidenceHref } from "@/features/evidence";
import { useI18n } from "@/i18n/LocaleProvider";
import { formatDate, formatDuration } from "@/lib/utils";
import {
  buildRunDeckHref,
  buildRunDetailHref,
  buildRunReportHref,
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

function isBlockedStatus(status: string) {
  const normalized = status.toLowerCase();
  return (
    normalized.includes("blocked") ||
    normalized === "failed" ||
    normalized === "fail" ||
    normalized === "rejected"
  );
}

function isRunningStatus(status: string) {
  const normalized = status.toLowerCase();
  return normalized === "running" || normalized === "pending";
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
  const { label, locale, t } = useI18n();
  const navigate = useNavigate();
  const explorerRef = useRef<HTMLDivElement | null>(null);
  const pendingFocusRunIdRef = useRef<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const parsedSearch = parseRunsListSearchParams(searchParams);
  const status = parsedSearch.status ?? "";
  const from = parsedSearch.from ?? "";
  const to = parsedSearch.to ?? "";
  const query = parsedSearch.q ?? "";
  const cursor = parsedSearch.cursor ?? "";

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
      q: query.trim() || undefined,
      status: status || undefined,
      from_ts: localDateTimeToIso(from),
      to_ts: localDateTimeToIso(to),
    }),
    [cursor, from, query, status, to],
  );

  const runsQuery = useRuns(runsFilters);
  const displayedRuns = runsQuery.data?.runs ?? [];
  const firstDisplayedRunId = displayedRuns[0]?.run_id ?? null;
  const activeRunIsVisible = activeRunId
    ? displayedRuns.some((run) => run.run_id === activeRunId)
    : false;

  useEffect(() => {
    if (!firstDisplayedRunId) {
      if (activeRunId !== null) {
        setActiveRunId(null);
      }
      return;
    }
    if (!activeRunIsVisible) {
      setActiveRunId(firstDisplayedRunId);
    }
  }, [activeRunId, activeRunIsVisible, firstDisplayedRunId, setActiveRunId]);

  const currentCursorIndex = cursorTrail.lastIndexOf(cursor);
  const previousCursor =
    currentCursorIndex > 0 ? cursorTrail[currentCursorIndex - 1] : null;
  const activeRunIndex = activeRunId
    ? displayedRuns.findIndex((run) => run.run_id === activeRunId)
    : 0;
  const activeRun =
    activeRunId != null
      ? (displayedRuns.find((run) => run.run_id === activeRunId) ?? null)
      : null;
  const visibleRuns = displayedRuns.length;
  const runningRuns = displayedRuns.filter((run) =>
    isRunningStatus(run.status),
  );
  const blockedRuns = displayedRuns.filter((run) =>
    isBlockedStatus(run.status),
  );
  const activeRunAnnouncement = activeRun
    ? t("pages.runs.activeRunAnnouncement", {
        count: displayedRuns.length,
        position: activeRunIndex + 1,
        runId: activeRun.run_id,
        status: label("runStatuses", activeRun.status, activeRun.status),
      })
    : "";

  const columns = useMemo(
    () => [
      {
        key: "runId",
        header: t("pages.runs.columns.runId"),
        exportValue: (run: (typeof displayedRuns)[number]) => run.run_id,
        render: (run: (typeof displayedRuns)[number]) => (
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
        exportValue: (run: (typeof displayedRuns)[number]) => run.status,
        render: (run: (typeof displayedRuns)[number]) => (
          <Badge kind={statusBadgeKind(run.status)}>
            {label("runStatuses", run.status, run.status)}
          </Badge>
        ),
      },
      {
        key: "started",
        header: t("pages.runs.columns.started"),
        exportValue: (run: (typeof displayedRuns)[number]) => run.started_at,
        render: (run: (typeof displayedRuns)[number]) =>
          formatDate(run.started_at, locale),
      },
      {
        key: "duration",
        header: t("pages.runs.columns.duration"),
        exportValue: (run: (typeof displayedRuns)[number]) => run.duration_ms,
        render: (run: (typeof displayedRuns)[number]) =>
          formatDuration(run.duration_ms, locale),
      },
      {
        key: "artifacts",
        header: t("pages.runs.columns.artifacts"),
        exportValue: (run: (typeof displayedRuns)[number]) =>
          run.root_artifact_count ?? 0,
        render: (run: (typeof displayedRuns)[number]) =>
          run.root_artifact_count ?? 0,
      },
      {
        key: "source",
        header: t("pages.runs.columns.source"),
        exportValue: (run: (typeof displayedRuns)[number]) => run.source_kind,
        render: (run: (typeof displayedRuns)[number]) =>
          label("runSourceKinds", run.source_kind, run.source_kind),
      },
    ],
    [label, locale, t],
  );

  function exportRunsCsv() {
    exportCsv("runs-view.csv", displayedRuns, columns);
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
      runs: displayedRuns,
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
    if (!pendingFocusRunIdRef.current || !activeRunId) {
      return;
    }
    if (pendingFocusRunIdRef.current !== activeRunId) {
      return;
    }

    const focusActiveRow = () => {
      const rows =
        explorerRef.current?.querySelectorAll<HTMLElement>("[data-run-row-id]");
      if (!rows) {
        return false;
      }
      for (const row of rows) {
        if (row.dataset.runRowId === activeRunId) {
          row.focus();
          pendingFocusRunIdRef.current = null;
          return true;
        }
      }
      return false;
    };

    if (focusActiveRow()) {
      return;
    }

    const frameId = window.requestAnimationFrame(() => {
      focusActiveRow();
    });
    return () => window.cancelAnimationFrame(frameId);
  }, [activeRunId]);

  function moveSelection(delta: number) {
    if (displayedRuns.length === 0) {
      return;
    }
    const currentIndex = activeRunId
      ? displayedRuns.findIndex((run) => run.run_id === activeRunId)
      : 0;
    const baseIndex = currentIndex >= 0 ? currentIndex : 0;
    const nextIndex = Math.max(
      0,
      Math.min(displayedRuns.length - 1, baseIndex + delta),
    );
    const nextRunId = displayedRuns[nextIndex]?.run_id ?? null;
    pendingFocusRunIdRef.current = nextRunId;
    setActiveRunId(nextRunId);
  }

  function handleExplorerKeyDown(event: KeyboardEvent) {
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
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        target.closest("a, button, summary, input, select, textarea")
      ) {
        return;
      }
      event.preventDefault();
      navigate(`/runs/${activeRunId}/overview`);
    }
  }

  function buildRowProps(run: (typeof displayedRuns)[number]) {
    return {
      "data-run-row-id": run.run_id,
      onFocus: () => setActiveRunId(run.run_id),
      onMouseEnter: () => setActiveRunId(run.run_id),
      tabIndex: activeRunId === run.run_id ? 0 : -1,
    };
  }

  function focusActiveExplorerRow() {
    const activeRow =
      explorerRef.current?.querySelector<HTMLElement>(
        "[data-run-row-id][tabindex='0']",
      ) ?? null;

    if (activeRow) {
      activeRow.focus();
      return;
    }

    explorerRef.current?.focus();
  }

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

  useEffect(() => {
    const explorer = explorerRef.current;
    if (!explorer) {
      return;
    }

    explorer.addEventListener("keydown", handleExplorerKeyDown);
    return () => {
      explorer.removeEventListener("keydown", handleExplorerKeyDown);
    };
  }, [handleExplorerKeyDown]);

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
      <button
        type="button"
        className="border-line bg-panel text-text sr-only top-4 left-4 z-50 rounded-full border px-4 py-2 text-sm font-semibold focus:not-sr-only focus:absolute"
        onClick={focusActiveExplorerRow}
      >
        {t("pages.runs.skipToExplorer")}
      </button>
      <Card>
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)]">
          <div>
            <p className="eyebrow">{t("pages.runs.fleetEyebrow")}</p>
            <h2>{t("pages.runs.fleetHeading")}</h2>
            <p className="topbar-subtitle">{t("pages.runs.subtitle")}</p>
            <p className="text-muted mt-2 max-w-3xl text-sm">
              {t("pages.runs.fleetBody")}
            </p>

            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <div className="bg-surface/75 border-line rounded-2xl border p-4">
                <span className="text-muted text-xs tracking-wide uppercase">
                  {t("pages.runs.visibleRuns")}
                </span>
                <strong className="mt-2 block text-2xl font-semibold">
                  {visibleRuns}
                </strong>
              </div>
              <div className="bg-surface/75 border-line rounded-2xl border p-4">
                <span className="text-muted text-xs tracking-wide uppercase">
                  {t("pages.runs.runningNow")}
                </span>
                <strong className="mt-2 block text-2xl font-semibold">
                  {runningRuns.length}
                </strong>
              </div>
              <div className="bg-surface/75 border-line rounded-2xl border p-4">
                <span className="text-muted text-xs tracking-wide uppercase">
                  {t("pages.runs.blockedNow")}
                </span>
                <strong className="mt-2 block text-2xl font-semibold">
                  {blockedRuns.length}
                </strong>
              </div>
            </div>
          </div>

          <div className="bg-surface/70 border-line rounded-2xl border p-4">
            <p className="eyebrow">{t("pages.runs.selectedRunTitle")}</p>
            {activeRun ? (
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold">
                      {activeRun.run_id}
                    </h3>
                    <p className="text-muted mt-2 text-sm">
                      {t("pages.runs.selectedRunBody")}
                    </p>
                  </div>
                  <Badge kind={statusBadgeKind(activeRun.status)}>
                    {label("runStatuses", activeRun.status, activeRun.status)}
                  </Badge>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="compact-metric">
                    <p className="text-muted text-xs uppercase">
                      {t("pages.runs.duration")}
                    </p>
                    <p className="mt-1 font-semibold">
                      {formatDuration(activeRun.duration_ms, locale)}
                    </p>
                  </div>
                  <div className="compact-metric">
                    <p className="text-muted text-xs uppercase">
                      {t("pages.runs.columns.artifacts")}
                    </p>
                    <p className="mt-1 font-semibold">
                      {activeRun.root_artifact_count ?? 0}
                    </p>
                  </div>
                  <div className="compact-metric">
                    <p className="text-muted text-xs uppercase">
                      {t("pages.runs.columns.source")}
                    </p>
                    <p className="mt-1 font-semibold">
                      {label(
                        "runSourceKinds",
                        activeRun.source_kind,
                        activeRun.source_kind,
                      )}
                    </p>
                  </div>
                  <div className="compact-metric">
                    <p className="text-muted text-xs uppercase">
                      {t("pages.runs.columns.started")}
                    </p>
                    <p className="mt-1 font-semibold">
                      {formatDate(activeRun.started_at, locale)}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button
                    to={buildRunDetailHref(activeRun.run_id)}
                    variant="primary"
                  >
                    {t("pages.runs.openRun")}
                  </Button>
                  <Button
                    to={buildEvidenceHref({
                      focus: "overview",
                      runId: activeRun.run_id,
                    })}
                    variant="ghost"
                  >
                    {t("pages.runs.openEvidence")}
                  </Button>
                  <Button
                    to={buildRunReportHref(activeRun.run_id)}
                    variant="ghost"
                  >
                    {t("pages.runs.auditReport")}
                  </Button>
                  <Button
                    to={buildRunDeckHref(activeRun.run_id)}
                    variant="ghost"
                  >
                    {t("pages.runs.openDeck")}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <h3 className="text-lg font-semibold">
                  {t("pages.runs.noActiveRunTitle")}
                </h3>
                <p className="text-muted text-sm">
                  {t("pages.runs.noActiveRunBody")}
                </p>
              </div>
            )}
          </div>
        </div>
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
        empty={displayedRuns.length === 0}
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

          <div ref={explorerRef} data-testid="runs-explorer" tabIndex={-1}>
            <div aria-atomic="true" aria-live="polite" className="sr-only">
              {activeRunAnnouncement}
            </div>
            {displayedRuns.length < VIRTUALIZATION_THRESHOLD ? (
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
                    {displayedRuns.map((run) => (
                      <tr
                        key={run.run_id}
                        className={
                          activeRunId === run.run_id
                            ? "border-accent/20 bg-accent/5 outline-accent/35 border-b last:border-b-0 focus-visible:outline-2 focus-visible:outline-offset-[-2px]"
                            : "border-line/70 outline-accent/35 border-b last:border-b-0 focus-visible:outline-2 focus-visible:outline-offset-[-2px]"
                        }
                        {...buildRowProps(run)}
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
                    ? "border-accent/20 bg-accent/5 outline-accent/35 border-b last:border-b-0 focus-visible:outline-2 focus-visible:outline-offset-[-2px]"
                    : "border-line/70 outline-accent/35 border-b last:border-b-0 focus-visible:outline-2 focus-visible:outline-offset-[-2px]"
                }
                rowKey={(run) => run.run_id}
                rowProps={(run) => buildRowProps(run)}
                rows={displayedRuns}
              />
            )}
          </div>

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
