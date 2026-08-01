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

import type { DistributionalModel } from "@/shared/lib/domain/simulation";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Select } from "@polisyos/atlas-ui";
import { chartTheme } from "@/shared/ui";

type DistributionalPanelProps = {
  distributional: DistributionalModel | null;
};

export default function DistributionalPanel({
  distributional,
}: DistributionalPanelProps) {
  const { t } = useI18n();
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
      <section className="bg-canvas/40 border-line rounded-xl border border-dashed p-4">
        <h3 className="mb-1 text-lg font-semibold">
          {t("pages.artifacts.simulation.distributionalPanel.title")}
        </h3>
        <p className="text-muted text-sm">
          {t("pages.artifacts.simulation.distributionalPanel.unavailable")}
        </p>
      </section>
    );
  }

  return (
    <section className="border-line bg-panel space-y-3 rounded-xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">
          {t("pages.artifacts.simulation.distributionalPanel.title")}
        </h3>
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
        <div className="bg-canvas/30 border-line rounded-lg border p-3">
          <p className="text-muted text-xs uppercase">
            {t("pages.artifacts.simulation.distributionalPanel.gini")}
          </p>
          <p className="text-sm font-semibold">
            {t("pages.artifacts.simulation.distributionalPanel.giniRange", {
              after: distributional.overallGiniAfter?.toFixed(4) ?? "-",
              before: distributional.overallGiniBefore?.toFixed(4) ?? "-",
            })}
          </p>
          <p className="text-muted text-xs">
            {t("pages.artifacts.simulation.distributionalPanel.delta", {
              value:
                distributional.overallGiniDelta !== null
                  ? distributional.overallGiniDelta.toFixed(4)
                  : "-",
            })}
          </p>
        </div>
        <div className="bg-canvas/30 border-line rounded-lg border p-3">
          <p className="text-muted text-xs uppercase">
            {t("pages.artifacts.simulation.distributionalPanel.winnersLosers")}
          </p>
          <p className="text-sm font-semibold">
            {distributional.winnersCount ?? 0} /{" "}
            {distributional.losersCount ?? 0}
          </p>
          <p className="text-muted text-xs">
            {t(
              "pages.artifacts.simulation.distributionalPanel.populationShare",
              {
                losers: `${((distributional.losersShare ?? 0) * 100).toFixed(0)}%`,
                winners: `${((distributional.winnersShare ?? 0) * 100).toFixed(0)}%`,
              },
            )}
          </p>
        </div>
        <div className="bg-canvas/30 border-line rounded-lg border p-3">
          <p className="text-muted text-xs uppercase">
            {t("pages.artifacts.simulation.distributionalPanel.breakdowns")}
          </p>
          <p className="text-sm font-semibold">
            {distributional.breakdowns.length}
          </p>
          <p className="text-muted text-xs">
            {t(
              "pages.artifacts.simulation.distributionalPanel.primaryMetricsByCohort",
            )}
          </p>
        </div>
      </div>

      {selectedBreakdown ? (
        <div className="bg-canvas/20 border-line h-72 rounded-xl border p-2">
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
                name={t(
                  "pages.artifacts.simulation.distributionalPanel.deltaMetric",
                  {
                    metric: selectedBreakdown.primaryMetric,
                  },
                )}
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
        <p className="text-muted text-sm">
          {t("pages.artifacts.simulation.distributionalPanel.noCohortData")}
        </p>
      )}
    </section>
  );
}
