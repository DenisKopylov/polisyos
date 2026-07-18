import { useMemo } from "react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn, formatDate, formatDuration } from "@/shared/lib/utils";
import { Badge } from "@polisyos/atlas-ui";
import { PrefetchLink } from "@/app/routes/PrefetchLink";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type RecentRun = {
  runId: string;
  status: string;
  startedAt: string;
  durationMs?: number;
  topic?: string;
};

type RecentRunsTimelineProps = {
  runs: RecentRun[];
  maxItems?: number;
  className?: string;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_KIND: Record<string, "ok" | "fail" | "warn" | "neutral"> = {
  completed: "ok",
  failed: "fail",
  blocked: "fail",
  running: "warn",
  pending: "neutral",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RecentRunsTimeline({
  runs,
  maxItems = 10,
  className,
}: RecentRunsTimelineProps) {
  const { t } = useI18n();
  const displayed = useMemo(
    () =>
      [...runs]
        .sort(
          (a, b) =>
            new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime(),
        )
        .slice(0, maxItems),
    [runs, maxItems],
  );

  if (displayed.length === 0) {
    return (
      <p className="text-muted py-4 text-center text-xs">
        {t("pages.dashboard.recentRuns.empty")}
      </p>
    );
  }

  return (
    <div className={cn("relative space-y-0", className)}>
      {/* Timeline spine */}
      <div className="bg-line absolute top-0 bottom-0 left-3 w-px" />

      {displayed.map((run) => (
        <div key={run.runId} className="relative flex gap-3 py-2 pl-6">
          {/* Dot */}
          <span
            className="absolute top-3.5 left-1.5 size-3 rounded-full border-2 border-[var(--paper)]"
            style={{
              background:
                run.status === "completed"
                  ? "var(--color-status-approved)"
                  : run.status === "failed" || run.status === "blocked"
                    ? "var(--color-status-rejected)"
                    : "var(--line)",
            }}
          />

          <div className="flex flex-1 items-baseline justify-between gap-2">
            <div className="min-w-0">
              <PrefetchLink
                to={`/runs/${run.runId}`}
                prefetch="intent"
                className="text-accent truncate text-xs font-semibold underline"
              >
                {run.runId.slice(0, 8)}
              </PrefetchLink>
              {run.topic && (
                <p className="text-muted truncate text-[11px]">{run.topic}</p>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Badge kind={STATUS_KIND[run.status] ?? "neutral"}>
                {run.status}
              </Badge>
              <span className="text-muted text-[10px]">
                {formatDate(run.startedAt)}
              </span>
              {run.durationMs != null && (
                <span className="text-muted text-[10px]">
                  {formatDuration(run.durationMs)}
                </span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
