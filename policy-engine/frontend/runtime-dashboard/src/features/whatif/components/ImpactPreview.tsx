import { cn } from "@/lib/utils";
import { Card } from "@/shared/ui/primitives";
import { AnimatedNumber, BarChart } from "@/shared/charts";

import type { ImpactMetric } from "../types";

type ImpactPreviewProps = {
  metrics: ImpactMetric[];
  loading?: boolean;
  className?: string;
};

export function ImpactPreview({
  metrics,
  loading = false,
  className,
}: ImpactPreviewProps) {
  if (metrics.length === 0 && !loading) {
    return (
      <Card className={cn("space-y-3", className)}>
        <h4 className="text-sm font-semibold">Impact Preview</h4>
        <p className="text-muted text-sm">
          Adjust parameters to see projected impact.
        </p>
      </Card>
    );
  }

  const hasChanges = metrics.some((m) => m.projectedValue !== m.baseValue);

  return (
    <Card className={cn("space-y-4", className)}>
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold">Impact Preview</h4>
        {loading && (
          <span className="text-muted animate-pulse text-xs">
            Computing...
          </span>
        )}
        {!loading && hasChanges && (
          <span className="text-xs font-medium text-[var(--chart-warning)]">
            Projected changes
          </span>
        )}
      </div>

      {/* Metric cards */}
      <div className="grid gap-3 sm:grid-cols-2">
        {metrics.map((m) => {
          const delta = m.projectedValue - m.baseValue;
          const pctChange =
            m.baseValue !== 0
              ? ((delta / Math.abs(m.baseValue)) * 100).toFixed(1)
              : "n/a";
          const improved = m.higherIsBetter ? delta > 0 : delta < 0;
          const changed = delta !== 0;

          return (
            <div
              key={m.key}
              className={cn(
                "border-line rounded-xl border p-3 transition-colors",
                changed &&
                  (improved
                    ? "border-[var(--chart-success)]/30"
                    : "border-[var(--chart-alert)]/30"),
              )}
            >
              <p className="text-muted truncate text-xs">{m.label}</p>

              <div className="mt-1 flex items-baseline gap-2">
                <span className="font-mono text-lg font-bold">
                  <AnimatedNumber
                    value={m.projectedValue}
                    formatOptions={{
                      maximumFractionDigits: 3,
                      minimumFractionDigits: 3,
                    }}
                  />
                  {m.unit && (
                    <span className="text-muted text-xs">{m.unit}</span>
                  )}
                </span>
              </div>

              {changed && (
                <div className="mt-1 flex items-center gap-2 text-xs">
                  <span
                    className="font-mono font-semibold"
                    style={{
                      color: improved
                        ? "var(--chart-success)"
                        : "var(--chart-alert)",
                    }}
                  >
                    {delta >= 0 ? "+" : ""}
                    {delta.toFixed(4)}
                  </span>
                  <span className="text-muted">
                    ({pctChange}%)
                  </span>
                  <span className="text-muted">
                    was {m.baseValue.toFixed(3)}
                  </span>
                </div>
              )}

              {m.ci && changed && (
                <p className="text-muted mt-0.5 text-[10px]">
                  CI: [{m.ci.lower.toFixed(3)}, {m.ci.upper.toFixed(3)}]
                </p>
              )}
            </div>
          );
        })}
      </div>

      {/* Delta bar chart */}
      {hasChanges && metrics.length >= 2 && (
        <div>
          <p className="text-muted mb-1 text-xs font-semibold uppercase">
            Delta overview
          </p>
          <BarChart
            data={metrics.map((m) => ({
              label: m.label,
              value: m.projectedValue - m.baseValue,
            }))}
            colorByValue
            height={160}
          />
        </div>
      )}
    </Card>
  );
}
