import { cn, formatDate, formatNumber } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type DataSourceFreshness = {
  sourceId: string;
  label: string;
  lastUpdated: string;
  recordCount?: number;
  status: "fresh" | "stale" | "unknown";
};

type DataFreshnessMatrixProps = {
  sources: DataSourceFreshness[];
  staleDays?: number;
  className?: string;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_COLOR: Record<DataSourceFreshness["status"], string> = {
  fresh: "var(--color-status-approved)",
  stale: "var(--color-status-rejected)",
  unknown: "var(--line)",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DataFreshnessMatrix({
  sources,
  className,
}: DataFreshnessMatrixProps) {
  if (sources.length === 0) {
    return (
      <p className="text-muted py-4 text-center text-xs">
        No data source freshness information available.
      </p>
    );
  }

  const freshCount = sources.filter((s) => s.status === "fresh").length;
  const staleCount = sources.filter((s) => s.status === "stale").length;

  return (
    <div className={cn("space-y-3", className)}>
      {/* Summary bar */}
      <div className="flex gap-3 text-xs">
        <span className="flex items-center gap-1">
          <span className="inline-block size-2 rounded-full bg-[var(--color-status-approved)]" />
          {freshCount} fresh
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block size-2 rounded-full bg-[var(--color-status-rejected)]" />
          {staleCount} stale
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block size-2 rounded-full bg-[var(--line)]" />
          {sources.length - freshCount - staleCount} unknown
        </span>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
        {sources.map((source) => (
          <div
            key={source.sourceId}
            className="border-line rounded-xl border p-2 text-xs"
            style={{ borderLeftWidth: 3, borderLeftColor: STATUS_COLOR[source.status] }}
          >
            <p className="truncate font-semibold">{source.label}</p>
            <p className="text-muted mt-0.5">
              {formatDate(source.lastUpdated)}
            </p>
            {source.recordCount != null && (
              <p className="text-muted">
                {formatNumber(source.recordCount)} records
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
