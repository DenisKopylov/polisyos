import { useMemo } from "react";

import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/LocaleProvider";
import { Card } from "@/shared/ui/primitives";
import {
  BarChart,
  ParallelCoordinatesChart,
  type ParallelAxis,
  type ParallelRow,
} from "@/shared/charts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RunComparisonMetric = {
  key: string;
  label: string;
  base: number;
  target: number;
  unit?: string;
  higherIsBetter?: boolean;
};

type RunComparisonVisualProps = {
  baseRunId: string;
  targetRunId: string;
  metrics: RunComparisonMetric[];
  className?: string;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RunComparisonVisual({
  baseRunId,
  targetRunId,
  metrics,
  className,
}: RunComparisonVisualProps) {
  const { t } = useI18n();

  // Bar chart data
  const barData = useMemo(
    () =>
      metrics.map((m) => ({
        label: m.label,
        base: m.base,
        target: m.target,
      })),
    [metrics],
  );

  // Parallel coordinates
  const parallelAxes: ParallelAxis[] = useMemo(
    () =>
      metrics.map((m) => ({
        key: m.key,
        label: m.label,
      })),
    [metrics],
  );

  const parallelData: ParallelRow[] = useMemo(() => {
    const baseRow: ParallelRow = { id: baseRunId };
    const targetRow: ParallelRow = { id: targetRunId };
    for (const m of metrics) {
      baseRow[m.key] = m.base;
      targetRow[m.key] = m.target;
    }
    return [baseRow, targetRow];
  }, [baseRunId, targetRunId, metrics]);

  return (
    <div className={cn("space-y-6", className)}>
      {/* Side-by-side metric cards */}
      <div className="grid gap-4 sm:grid-cols-2">
        {/* Base run summary */}
        <Card className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="size-3 rounded-full bg-[var(--chart-primary)]" />
            <h4 className="text-sm font-semibold">
              {t("pages.runs.compare.visual.baseRun", { runId: baseRunId })}
            </h4>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {metrics.slice(0, 6).map((m) => (
              <div key={m.key} className="border-line rounded-xl border p-2">
                <p className="text-muted truncate text-xs">{m.label}</p>
                <p className="font-mono text-lg font-bold">
                  {typeof m.base === "number" ? m.base.toFixed(2) : m.base}
                  {m.unit && (
                    <span className="text-muted text-xs">{m.unit}</span>
                  )}
                </p>
              </div>
            ))}
          </div>
        </Card>

        {/* Target run summary */}
        <Card className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="size-3 rounded-full bg-[var(--chart-secondary)]" />
            <h4 className="text-sm font-semibold">
              {t("pages.runs.compare.visual.targetRun", {
                runId: targetRunId,
              })}
            </h4>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {metrics.slice(0, 6).map((m) => {
              const delta = m.target - m.base;
              const improved = m.higherIsBetter ? delta > 0 : delta < 0;
              return (
                <div key={m.key} className="border-line rounded-xl border p-2">
                  <p className="text-muted truncate text-xs">{m.label}</p>
                  <p className="font-mono text-lg font-bold">
                    {typeof m.target === "number"
                      ? m.target.toFixed(2)
                      : m.target}
                    {m.unit && (
                      <span className="text-muted text-xs">{m.unit}</span>
                    )}
                  </p>
                  <p
                    className="text-xs font-semibold"
                    style={{
                      color:
                        delta === 0
                          ? "var(--chart-neutral)"
                          : improved
                            ? "var(--chart-success)"
                            : "var(--chart-alert)",
                    }}
                  >
                    {delta >= 0 ? "+" : ""}
                    {delta.toFixed(2)}
                  </p>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Parallel coordinates view */}
      {metrics.length >= 3 && (
        <Card className="space-y-3">
          <h4 className="text-sm font-semibold">
            {t("pages.runs.compare.visual.multiMetricComparison")}
          </h4>
          <ParallelCoordinatesChart
            axes={parallelAxes}
            data={parallelData}
            highlightedIds={new Set([targetRunId])}
            height={280}
          />
          <div className="flex gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 bg-[var(--chart-primary)] opacity-40" />
              <span className="text-muted">
                {t("pages.runs.compare.columns.base")}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 bg-[var(--chart-primary)]" />
              <span>{t("pages.runs.compare.columns.target")}</span>
            </div>
          </div>
        </Card>
      )}

      {/* Delta bar chart */}
      <Card className="space-y-3">
        <h4 className="text-sm font-semibold">
          {t("pages.runs.compare.visual.deltaOverview")}
        </h4>
        <BarChart
          data={metrics.map((m) => ({
            label: m.label,
            value: m.target - m.base,
          }))}
          colorByValue
          height={220}
        />
      </Card>
    </div>
  );
}
