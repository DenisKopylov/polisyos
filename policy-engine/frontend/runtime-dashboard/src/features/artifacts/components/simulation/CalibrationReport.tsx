import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { CalibrationModel } from "@/lib/domain/simulation";
import { useI18n } from "@/i18n/LocaleProvider";
import { Select, chartTheme } from "@/shared/ui";

type CalibrationReportProps = {
  calibration: CalibrationModel | null;
};

export default function CalibrationReport({
  calibration,
}: CalibrationReportProps) {
  const { t } = useI18n();
  const [selectedSeriesTarget, setSelectedSeriesTarget] = useState<string>(
    calibration?.series[0]?.target ?? "",
  );

  const selectedSeries = useMemo(() => {
    if (!calibration) {
      return null;
    }
    if (!selectedSeriesTarget) {
      return calibration.series[0] ?? null;
    }
    return (
      calibration.series.find(
        (series) => series.target === selectedSeriesTarget,
      ) ??
      calibration.series[0] ??
      null
    );
  }, [calibration, selectedSeriesTarget]);

  if (!calibration) {
    return (
      <section className="bg-canvas/40 border-line rounded-xl border border-dashed p-4">
        <h3 className="mb-1 text-lg font-semibold">
          {t("pages.artifacts.simulation.calibrationReport.title")}
        </h3>
        <p className="text-muted text-sm">
          {t("pages.artifacts.simulation.calibrationReport.unavailable")}
        </p>
      </section>
    );
  }

  const lossData = calibration.lossHistory.map((value, index) => ({
    step: index,
    value,
  }));

  return (
    <section className="border-line bg-panel space-y-3 rounded-xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">
          {t("pages.artifacts.simulation.calibrationReport.title")}
        </h3>
        <p className="text-muted text-sm">
          {t("pages.artifacts.simulation.calibrationReport.totalLoss", {
            value:
              calibration.totalLoss !== null
                ? calibration.totalLoss.toFixed(4)
                : "-",
          })}
        </p>
      </div>

      <div className="grid gap-2 md:grid-cols-4">
        <div className="bg-canvas/30 border-line rounded-lg border p-2 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("pages.artifacts.simulation.calibrationReport.lossSteps")}
          </p>
          <p className="font-semibold">{calibration.lossHistory.length}</p>
        </div>
        <div className="bg-canvas/30 border-line rounded-lg border p-2 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("pages.artifacts.simulation.calibrationReport.fitTargets")}
          </p>
          <p className="font-semibold">{calibration.fitRows.length}</p>
        </div>
        <div className="bg-canvas/30 border-line rounded-lg border p-2 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("pages.artifacts.simulation.calibrationReport.calibratedParams")}
          </p>
          <p className="font-semibold">{calibration.params.length}</p>
        </div>
        <div className="bg-canvas/30 border-line rounded-lg border p-2 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("pages.artifacts.simulation.calibrationReport.uncertainty")}
          </p>
          <p className="font-semibold">
            {calibration.uncertaintyMethod ?? "-"}
          </p>
        </div>
      </div>

      {lossData.length > 1 ? (
        <div className="bg-canvas/20 border-line h-64 rounded-xl border p-2">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={lossData}
              margin={{ top: 12, right: 16, left: 8, bottom: 8 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="step" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="value"
                stroke={chartTheme.secondary}
                strokeWidth={2}
                dot={false}
                name={t("pages.artifacts.simulation.calibrationReport.loss")}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="text-muted text-sm">
          {t(
            "pages.artifacts.simulation.calibrationReport.lossHistoryUnavailable",
          )}
        </p>
      )}

      {calibration.fitRows.length > 0 ? (
        <div className="border-line overflow-x-auto rounded-xl border">
          <table className="min-w-full border-collapse text-sm">
            <thead>
              <tr className="border-line text-muted border-b text-left text-xs tracking-wide uppercase">
                <th className="px-3 py-2">
                  {t(
                    "pages.artifacts.simulation.calibrationReport.columns.target",
                  )}
                </th>
                <th className="px-3 py-2">
                  {t(
                    "pages.artifacts.simulation.calibrationReport.columns.rSquared",
                  )}
                </th>
                <th className="px-3 py-2">RMSE</th>
                <th className="px-3 py-2">MAE</th>
                <th className="px-3 py-2">MSE</th>
                <th className="px-3 py-2">N</th>
              </tr>
            </thead>
            <tbody>
              {calibration.fitRows.map((row) => (
                <tr
                  key={row.target}
                  className="border-line/70 border-b align-top last:border-b-0"
                >
                  <td className="px-3 py-2 font-mono text-xs">{row.target}</td>
                  <td className="px-3 py-2">
                    {row.r2 !== null ? row.r2.toFixed(4) : "-"}
                  </td>
                  <td className="px-3 py-2">
                    {row.rmse !== null ? row.rmse.toFixed(4) : "-"}
                  </td>
                  <td className="px-3 py-2">
                    {row.mae !== null ? row.mae.toFixed(4) : "-"}
                  </td>
                  <td className="px-3 py-2">
                    {row.mse !== null ? row.mse.toFixed(4) : "-"}
                  </td>
                  <td className="px-3 py-2">
                    {row.n !== null ? Math.round(row.n) : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {calibration.params.length > 0 ? (
        <div className="bg-canvas/20 border-line rounded-xl border p-3">
          <p className="text-muted mb-2 text-xs font-semibold uppercase">
            {t(
              "pages.artifacts.simulation.calibrationReport.parameterEstimates",
            )}
          </p>
          <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            {calibration.params.map((param) => (
              <div
                key={param.name}
                className="border-line bg-panel rounded-lg border p-2 text-sm"
              >
                <p className="text-muted font-mono text-xs">{param.name}</p>
                <p className="font-semibold">{param.value.toFixed(6)}</p>
                {param.ciLower !== null && param.ciUpper !== null ? (
                  <p className="text-muted text-xs">
                    [{param.ciLower.toFixed(6)}, {param.ciUpper.toFixed(6)}]
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {calibration.series.length > 0 ? (
        <div className="bg-canvas/20 border-line space-y-2 rounded-xl border p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-muted text-xs font-semibold uppercase">
              {t(
                "pages.artifacts.simulation.calibrationReport.observedVsFitted",
              )}
            </p>
            <Select
              value={selectedSeries?.target ?? ""}
              onChange={(event) => setSelectedSeriesTarget(event.target.value)}
              className="w-auto rounded-lg px-2 py-1"
            >
              {calibration.series.map((series) => (
                <option key={series.target} value={series.target}>
                  {series.target}
                </option>
              ))}
            </Select>
          </div>
          {selectedSeries ? (
            <div className="border-line bg-panel h-64 rounded-lg border p-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={selectedSeries.points}
                  margin={{ top: 12, right: 16, left: 8, bottom: 8 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke={chartTheme.grid}
                  />
                  <XAxis dataKey="step" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="observed"
                    stroke={chartTheme.tertiary}
                    strokeWidth={2}
                    dot={false}
                    name={t(
                      "pages.artifacts.simulation.calibrationReport.observed",
                    )}
                  />
                  <Line
                    type="monotone"
                    dataKey="fitted"
                    stroke={chartTheme.success}
                    strokeWidth={2}
                    dot={false}
                    name={t(
                      "pages.artifacts.simulation.calibrationReport.fitted",
                    )}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
