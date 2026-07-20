import { useI18n } from "@/shared/i18n/LocaleProvider";
import type { InteractionState } from "@/shared/lib/domain/statusOwnership";
import { cn, formatDate, formatNumber } from "@/shared/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type DataSourceFreshness = {
  displayState: DataFreshnessDisplayState;
  sourceId: string;
  label: string;
  lastUpdated: string;
  recordCount?: number;
};

export type DataFreshnessDisplayState = InteractionState;

type DataFreshnessMatrixProps = {
  sources: DataSourceFreshness[];
  staleDays?: number;
  className?: string;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function hasTelemetryLabel(source: DataSourceFreshness, label: string) {
  return (
    source.displayState.authorityPurpose === "telemetry" &&
    source.displayState.label === label
  );
}

function freshnessColor(source: DataSourceFreshness) {
  if (hasTelemetryLabel(source, "fresh")) {
    return "var(--color-status-approved)";
  }
  if (hasTelemetryLabel(source, "stale")) {
    return "var(--color-status-rejected)";
  }
  return "var(--line)";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DataFreshnessMatrix({
  sources,
  className,
}: DataFreshnessMatrixProps) {
  const { t } = useI18n();
  if (sources.length === 0) {
    return (
      <p className="text-muted py-4 text-center text-xs">
        {t("features.dashboard.dataFreshness.empty")}
      </p>
    );
  }

  const freshCount = sources.filter((source) =>
    hasTelemetryLabel(source, "fresh"),
  ).length;
  const staleCount = sources.filter((source) =>
    hasTelemetryLabel(source, "stale"),
  ).length;

  return (
    <div className={cn("space-y-3", className)}>
      {/* Summary bar */}
      <div className="flex gap-3 text-xs">
        <span className="flex items-center gap-1">
          <span className="inline-block size-2 rounded-full bg-[var(--color-status-approved)]" />
          {t("features.dashboard.dataFreshness.freshCount", {
            count: freshCount,
          })}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block size-2 rounded-full bg-[var(--color-status-rejected)]" />
          {t("features.dashboard.dataFreshness.staleCount", {
            count: staleCount,
          })}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block size-2 rounded-full bg-[var(--line)]" />
          {t("features.dashboard.dataFreshness.unknownCount", {
            count: sources.length - freshCount - staleCount,
          })}
        </span>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
        {sources.map((source) => (
          <div
            key={source.sourceId}
            className="border-line rounded-xl border p-2 text-xs"
            data-authority-purpose={source.displayState.authorityPurpose}
            data-display-state={source.displayState.label}
            data-testid={`data-freshness-source-${source.sourceId}`}
            style={{
              borderLeftWidth: 3,
              borderLeftColor: freshnessColor(source),
            }}
          >
            <p className="truncate font-semibold">{source.label}</p>
            <p className="text-muted mt-0.5">
              {formatDate(source.lastUpdated)}
            </p>
            {source.recordCount != null && (
              <p className="text-muted">
                {t("features.dashboard.dataFreshness.records", {
                  count: formatNumber(source.recordCount),
                })}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
