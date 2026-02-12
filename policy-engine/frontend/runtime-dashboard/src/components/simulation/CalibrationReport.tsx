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

import type { CalibrationModel } from "../../lib/domain/simulation";

type CalibrationReportProps = {
  calibration: CalibrationModel | null;
};

export default function CalibrationReport({ calibration }: CalibrationReportProps) {
  const [selectedSeriesTarget, setSelectedSeriesTarget] = useState<string>(calibration?.series[0]?.target ?? "");

  const selectedSeries = useMemo(() => {
    if (!calibration) {
      return null;
    }
    if (!selectedSeriesTarget) {
      return calibration.series[0] ?? null;
    }
    return calibration.series.find((series) => series.target === selectedSeriesTarget) ?? calibration.series[0] ?? null;
  }, [calibration, selectedSeriesTarget]);

  if (!calibration) {
    return (
      <section className="rounded-xl border border-dashed border-line bg-canvas/40 p-4">
        <h3 className="mb-1 text-lg font-semibold">Calibration Report</h3>
        <p className="text-sm text-muted">Calibration report not detected for this artifact.</p>
      </section>
    );
  }

  const lossData = calibration.lossHistory.map((value, index) => ({ step: index, value }));

  return (
    <section className="space-y-3 rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">Calibration Report</h3>
        <p className="text-sm text-muted">Total loss: {calibration.totalLoss !== null ? calibration.totalLoss.toFixed(4) : "-"}</p>
      </div>

      <div className="grid gap-2 md:grid-cols-4">
        <div className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
          <p className="text-xs uppercase text-muted">Loss steps</p>
          <p className="font-semibold">{calibration.lossHistory.length}</p>
        </div>
        <div className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
          <p className="text-xs uppercase text-muted">Fit targets</p>
          <p className="font-semibold">{calibration.fitRows.length}</p>
        </div>
        <div className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
          <p className="text-xs uppercase text-muted">Calibrated params</p>
          <p className="font-semibold">{calibration.params.length}</p>
        </div>
        <div className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
          <p className="text-xs uppercase text-muted">Uncertainty</p>
          <p className="font-semibold">{calibration.uncertaintyMethod ?? "-"}</p>
        </div>
      </div>

      {lossData.length > 1 ? (
        <div className="h-64 rounded-xl border border-line bg-canvas/20 p-2">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={lossData} margin={{ top: 12, right: 16, left: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#dbe3ed" />
              <XAxis dataKey="step" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#2557a7"
                strokeWidth={2}
                dot={false}
                name="Loss"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="text-sm text-muted">Loss history is unavailable.</p>
      )}

      {calibration.fitRows.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="min-w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-3 py-2">Target</th>
                <th className="px-3 py-2">R²</th>
                <th className="px-3 py-2">RMSE</th>
                <th className="px-3 py-2">MAE</th>
                <th className="px-3 py-2">MSE</th>
                <th className="px-3 py-2">N</th>
              </tr>
            </thead>
            <tbody>
              {calibration.fitRows.map((row) => (
                <tr key={row.target} className="border-b border-line/70 align-top last:border-b-0">
                  <td className="px-3 py-2 font-mono text-xs">{row.target}</td>
                  <td className="px-3 py-2">{row.r2 !== null ? row.r2.toFixed(4) : "-"}</td>
                  <td className="px-3 py-2">{row.rmse !== null ? row.rmse.toFixed(4) : "-"}</td>
                  <td className="px-3 py-2">{row.mae !== null ? row.mae.toFixed(4) : "-"}</td>
                  <td className="px-3 py-2">{row.mse !== null ? row.mse.toFixed(4) : "-"}</td>
                  <td className="px-3 py-2">{row.n !== null ? Math.round(row.n) : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {calibration.params.length > 0 ? (
        <div className="rounded-xl border border-line bg-canvas/20 p-3">
          <p className="mb-2 text-xs font-semibold uppercase text-muted">Parameter Estimates</p>
          <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            {calibration.params.map((param) => (
              <div key={param.name} className="rounded-lg border border-line bg-panel p-2 text-sm">
                <p className="font-mono text-xs text-muted">{param.name}</p>
                <p className="font-semibold">{param.value.toFixed(6)}</p>
                {param.ciLower !== null && param.ciUpper !== null ? (
                  <p className="text-xs text-muted">[{param.ciLower.toFixed(6)}, {param.ciUpper.toFixed(6)}]</p>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {calibration.series.length > 0 ? (
        <div className="space-y-2 rounded-xl border border-line bg-canvas/20 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase text-muted">Observed vs Fitted</p>
            <select
              value={selectedSeries?.target ?? ""}
              onChange={(event) => setSelectedSeriesTarget(event.target.value)}
              className="rounded-lg border border-line bg-panel px-2 py-1 text-sm"
            >
              {calibration.series.map((series) => (
                <option key={series.target} value={series.target}>
                  {series.target}
                </option>
              ))}
            </select>
          </div>
          {selectedSeries ? (
            <div className="h-64 rounded-lg border border-line bg-panel p-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={selectedSeries.points}
                  margin={{ top: 12, right: 16, left: 8, bottom: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#dbe3ed" />
                  <XAxis dataKey="step" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="observed"
                    stroke="#0a2342"
                    strokeWidth={2}
                    dot={false}
                    name="Observed"
                  />
                  <Line
                    type="monotone"
                    dataKey="fitted"
                    stroke="#12805c"
                    strokeWidth={2}
                    dot={false}
                    name="Fitted"
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
