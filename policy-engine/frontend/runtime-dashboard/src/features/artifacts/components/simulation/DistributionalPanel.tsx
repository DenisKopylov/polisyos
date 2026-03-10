import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DistributionalModel } from "@/lib/domain/simulation";
import { Select, chartTheme } from "@/shared/ui";

type DistributionalPanelProps = {
  distributional: DistributionalModel | null;
};

export default function DistributionalPanel({
  distributional,
}: DistributionalPanelProps) {
  const [selectedDimension, setSelectedDimension] = useState<string>(
    distributional?.breakdowns[0]?.dimensionLabel ?? "",
  );

  const selectedBreakdown = useMemo(() => {
    if (!distributional) {
      return null;
    }
    if (!selectedDimension) {
      return distributional.breakdowns[0] ?? null;
    }
    return (
      distributional.breakdowns.find(
        (item) => item.dimensionLabel === selectedDimension,
      ) ??
      distributional.breakdowns[0] ??
      null
    );
  }, [distributional, selectedDimension]);

  if (!distributional) {
    return (
      <section className="bg-canvas/40 rounded-xl border border-dashed border-line p-4">
        <h3 className="mb-1 text-lg font-semibold">Distributional Panel</h3>
        <p className="text-sm text-muted">
          Distributional report not found in this artifact.
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-3 rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">Distributional Panel</h3>
        {distributional.breakdowns.length > 1 ? (
          <Select
            value={selectedBreakdown?.dimensionLabel ?? ""}
            onChange={(event) => setSelectedDimension(event.target.value)}
            className="w-auto rounded-lg px-2 py-1"
          >
            {distributional.breakdowns.map((breakdown) => (
              <option
                key={breakdown.dimensionLabel}
                value={breakdown.dimensionLabel}
              >
                {breakdown.dimensionLabel}
              </option>
            ))}
          </Select>
        ) : null}
      </div>

      <div className="grid gap-2 md:grid-cols-3">
        <div className="bg-canvas/30 rounded-lg border border-line p-3">
          <p className="text-xs uppercase text-muted">Gini (before to after)</p>
          <p className="text-sm font-semibold">
            {distributional.overallGiniBefore?.toFixed(4) ?? "-"} to{" "}
            {distributional.overallGiniAfter?.toFixed(4) ?? "-"}
          </p>
          <p className="text-xs text-muted">
            Δ{" "}
            {distributional.overallGiniDelta !== null
              ? distributional.overallGiniDelta.toFixed(4)
              : "-"}
          </p>
        </div>
        <div className="bg-canvas/30 rounded-lg border border-line p-3">
          <p className="text-xs uppercase text-muted">Winners / Losers</p>
          <p className="text-sm font-semibold">
            {distributional.winnersCount ?? 0} /{" "}
            {distributional.losersCount ?? 0}
          </p>
          <p className="text-xs text-muted">
            pop share: {((distributional.winnersShare ?? 0) * 100).toFixed(0)}%
            / {((distributional.losersShare ?? 0) * 100).toFixed(0)}%
          </p>
        </div>
        <div className="bg-canvas/30 rounded-lg border border-line p-3">
          <p className="text-xs uppercase text-muted">Breakdowns</p>
          <p className="text-sm font-semibold">
            {distributional.breakdowns.length}
          </p>
          <p className="text-xs text-muted">Primary metrics by cohort groups</p>
        </div>
      </div>

      {selectedBreakdown ? (
        <div className="bg-canvas/20 h-72 rounded-xl border border-line p-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={selectedBreakdown.cohorts}
              margin={{ top: 12, right: 16, left: 8, bottom: 8 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="cohortLabel" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Bar
                dataKey="delta"
                name={`Δ ${selectedBreakdown.primaryMetric}`}
              >
                {selectedBreakdown.cohorts.map((cohort) => (
                  <Cell
                    key={cohort.cohortId}
                    fill={
                      cohort.delta >= 0
                        ? cohort.isVulnerable
                          ? chartTheme.warning
                          : chartTheme.success
                        : chartTheme.alert
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="text-sm text-muted">
          No cohort data in distributional report.
        </p>
      )}
    </section>
  );
}
