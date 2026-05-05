import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import { Card } from "@/shared/ui/primitives";
import { BarChart } from "@/shared/charts";
import { Quantity, untracedDecisionQuantity } from "@/shared/ui/quantity";

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
  const { t } = useI18n();
  if (metrics.length === 0 && !loading) {
    return (
      <Card className={cn("space-y-3", className)}>
        <h4 className="text-sm font-semibold">{t("whatIf.impact.title")}</h4>
        <p className="text-muted text-sm">{t("whatIf.impact.noData")}</p>
      </Card>
    );
  }

  const hasChanges = metrics.some((m) => m.projectedValue !== m.baseValue);

  return (
    <Card className={cn("space-y-4", className)}>
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold">{t("whatIf.impact.title")}</h4>
        {loading && (
          <span className="text-muted animate-pulse text-xs">
            {t("whatIf.impact.computing")}
          </span>
        )}
        {!loading && hasChanges && (
          <span className="text-xs font-medium text-[var(--chart-warning)]">
            {t("whatIf.impact.projectedChanges")}
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
          const unit = {
            code: m.unit || "1",
            system: "ucum",
            display: m.unit || "value",
          };
          const projectedQuantity = untracedDecisionQuantity({
            point: m.projectedValue,
            metricId: `whatif_projected_${m.key}`,
            label: m.label,
            unit,
            uncertainty: m.ci
              ? {
                  ci_95: [m.ci.lower, m.ci.upper],
                  identifiability: "estimated",
                }
              : null,
            reasonCode: "whatif_projection_without_runtime_lineage",
          });
          const deltaQuantity = untracedDecisionQuantity({
            point: delta,
            metricId: `whatif_delta_${m.key}`,
            label: `${m.label} delta`,
            unit,
            reasonCode: "whatif_projection_without_runtime_lineage",
          });

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
                  <Quantity
                    value={projectedQuantity}
                    precision={3}
                    variant="inline"
                  />
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
                    <Quantity
                      value={deltaQuantity}
                      precision={4}
                      variant="dense"
                    />
                  </span>
                  <span className="text-muted">({pctChange}%)</span>
                  <span className="text-muted">
                    {t("whatIf.impact.wasValue", {
                      value: m.baseValue.toFixed(3),
                    })}
                  </span>
                </div>
              )}

              {m.ci && changed && (
                <p className="text-muted mt-0.5 text-[10px]">
                  {t("whatIf.impact.confidenceInterval", {
                    lower: m.ci.lower.toFixed(3),
                    upper: m.ci.upper.toFixed(3),
                  })}
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
            {t("whatIf.impact.deltaOverview")}
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
