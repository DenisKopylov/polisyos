import { useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import MetricValidationComparisonTable from "@/features/artifacts/components/MetricValidationComparisonTable";
import { Select, chartTheme } from "@/shared/ui";
import type { SimulationMetric, TimeSeries } from "@/lib/domain/simulation";
import type {
  MetricValidationComparisonRow,
  MetricValidationFamilyAdjustment,
} from "@/lib/domain/metricValidation";
import { clamp } from "@/lib/parsing";

type MetricsPanelProps = {
  metrics: SimulationMetric[];
  metricComparisons: MetricValidationComparisonRow[];
  metricValidationFamilyAdjustment: MetricValidationFamilyAdjustment | null;
  timeSeries: TimeSeries[];
  showUncertainty: boolean;
};

function barClass(severity: SimulationMetric["severity"]): string {
  if (severity === "high") {
    return "bg-danger";
  }
  if (severity === "medium") {
    return "bg-warning";
  }
  return "bg-success";
}

function normalizeMagnitude(value: number, max: number): number {
  if (max <= 0) {
    return 0.1;
  }
  return clamp(Math.abs(value) / max, 0.1, 1);
}

export default function MetricsPanel({
  metrics,
  metricComparisons,
  metricValidationFamilyAdjustment,
  timeSeries,
  showUncertainty,
}: MetricsPanelProps) {
  const [selectedSeriesId, setSelectedSeriesId] = useState<string>(
    () => timeSeries[0]?.id ?? "",
  );

  const selectedSeries = useMemo(() => {
    const fallback = timeSeries[0] ?? null;
    if (!selectedSeriesId) {
      return fallback;
    }
    return (
      timeSeries.find((series) => series.id === selectedSeriesId) ?? fallback
    );
  }, [selectedSeriesId, timeSeries]);

  const maxMetricMagnitude = useMemo(
    () => Math.max(...metrics.map((item) => Math.abs(item.value)), 0),
    [metrics],
  );

  return (
    <div className="space-y-4">
      <section>
        <h3 className="mb-2 text-lg font-semibold">Key Metrics</h3>
        {metrics.length === 0 ? (
          <p className="text-muted text-sm">
            {metricComparisons.length > 0
              ? "No summary metrics in this artifact; inspect the formal comparison table below."
              : "No numeric metrics in this artifact."}
          </p>
        ) : (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            {metrics.slice(0, 8).map((metric) => {
              const width = `${Math.round(normalizeMagnitude(metric.value, maxMetricMagnitude) * 100)}%`;
              return (
                <article
                  key={metric.key}
                  className="border-line bg-panel rounded-xl border p-3"
                >
                  <p className="text-muted text-xs uppercase">{metric.label}</p>
                  <p className="text-lg font-semibold">
                    {metric.formatted}
                    {metric.unit ? ` ${metric.unit}` : ""}
                  </p>
                  {metric.ciLower !== null && metric.ciUpper !== null ? (
                    <p className="text-muted text-xs">
                      CI: [{metric.ciLower.toFixed(3)},{" "}
                      {metric.ciUpper.toFixed(3)}]
                      {metric.ciLevel !== null
                        ? ` @ ${(metric.ciLevel * 100).toFixed(0)}%`
                        : ""}
                    </p>
                  ) : null}
                  {metric.testLabel || metric.pValue !== null || metric.pAdj !== null ? (
                    <p className="text-muted text-xs">
                      {metric.testLabel ?? "Stat test"}
                      {metric.pAdj !== null
                        ? `, p_adj=${metric.pAdj.toFixed(4)}`
                        : metric.pValue !== null
                          ? `, p=${metric.pValue.toFixed(4)}`
                          : ""}
                      {metric.significant !== null
                        ? metric.significant
                          ? ", significant"
                          : ", not significant"
                        : ""}
                    </p>
                  ) : null}
                  {metric.assumptionWarnings && metric.assumptionWarnings.length > 0 ? (
                    <p className="text-warning text-xs">
                      {metric.assumptionWarnings.join(", ")}
                    </p>
                  ) : null}
                  <div className="bg-line mt-2 h-1.5 rounded-full">
                    <div
                      className={`h-1.5 rounded-full ${barClass(metric.severity)}`}
                      style={{ width }}
                    />
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <MetricValidationComparisonTable
        comparisons={metricComparisons}
        familyAdjustment={metricValidationFamilyAdjustment}
      />

      <section>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-lg font-semibold">Time Series</h3>
          {timeSeries.length > 0 ? (
            <Select
              value={selectedSeries?.id ?? ""}
              onChange={(event) => setSelectedSeriesId(event.target.value)}
              className="w-auto rounded-lg px-2 py-1"
            >
              {timeSeries.map((series) => (
                <option key={series.id} value={series.id}>
                  {series.label}
                </option>
              ))}
            </Select>
          ) : null}
        </div>

        {selectedSeries ? (
          <div className="border-line bg-panel h-80 rounded-xl border p-2">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={selectedSeries.points}
                margin={{ top: 12, right: 16, left: 4, bottom: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
                <XAxis dataKey="step" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />

                {selectedSeries.mode === "single" ? (
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke={chartTheme.secondary}
                    strokeWidth={2}
                    dot={false}
                    name={selectedSeries.label}
                  />
                ) : null}

                {selectedSeries.mode === "observed_fitted" ? (
                  <>
                    <Line
                      type="monotone"
                      dataKey="observed"
                      stroke={chartTheme.tertiary}
                      strokeWidth={2}
                      dot={false}
                      name="Observed"
                    />
                    <Line
                      type="monotone"
                      dataKey="fitted"
                      stroke={chartTheme.success}
                      strokeWidth={2}
                      dot={false}
                      name="Fitted"
                    />
                  </>
                ) : null}

                {selectedSeries.mode === "baseline_policy" ? (
                  <>
                    {showUncertainty && selectedSeries.supportsUncertainty ? (
                      <>
                        <Area
                          type="monotone"
                          dataKey="upper2"
                          stroke="none"
                          fill={chartTheme.secondary}
                          fillOpacity={0.08}
                          name="+2σ"
                        />
                        <Area
                          type="monotone"
                          dataKey="upper1"
                          stroke="none"
                          fill={chartTheme.secondary}
                          fillOpacity={0.15}
                          name="+1σ"
                        />
                        <Area
                          type="monotone"
                          dataKey="lower1"
                          stroke="none"
                          fill={chartTheme.secondary}
                          fillOpacity={0.15}
                          name="-1σ"
                        />
                        <Area
                          type="monotone"
                          dataKey="lower2"
                          stroke="none"
                          fill={chartTheme.secondary}
                          fillOpacity={0.08}
                          name="-2σ"
                        />
                      </>
                    ) : null}
                    <Line
                      type="monotone"
                      dataKey="baseline"
                      stroke={chartTheme.tertiary}
                      strokeWidth={2}
                      dot={false}
                      name="Baseline"
                    />
                    <Line
                      type="monotone"
                      dataKey="policy"
                      stroke={chartTheme.success}
                      strokeWidth={2}
                      dot={false}
                      name="Policy"
                    />
                  </>
                ) : null}
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="text-muted text-sm">
            No time series data found for this artifact.
          </p>
        )}
      </section>
    </div>
  );
}
