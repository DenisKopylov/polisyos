import type {
  MetricValidationComparisonRow,
  MetricValidationFamilyAdjustment,
} from "@/lib/domain/metricValidation";

type MetricValidationComparisonTableProps = {
  title?: string;
  comparisons: MetricValidationComparisonRow[];
  familyAdjustment?: MetricValidationFamilyAdjustment | null;
};

function formatNumber(value: number | null, digits = 4): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }
  return value.toFixed(digits);
}

function formatSigned(value: number | null, digits = 4): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

function formatInterval(row: MetricValidationComparisonRow): string {
  if (row.ciLow === null || row.ciHigh === null) {
    return "-";
  }
  const level =
    row.ciLevel !== null ? ` @ ${(row.ciLevel * 100).toFixed(0)}%` : "";
  return `[${formatNumber(row.ciLow)}, ${formatNumber(row.ciHigh)}]${level}`;
}

function buildNotes(row: MetricValidationComparisonRow): string {
  const notes: string[] = [];
  if (row.resamplingMethod) {
    notes.push(row.resamplingMethod);
  }
  notes.push(...row.assumptionWarnings);
  notes.push(...row.calibrationWarnings);
  return notes.join(", ");
}

export default function MetricValidationComparisonTable({
  title = "Metric Validation",
  comparisons,
  familyAdjustment,
}: MetricValidationComparisonTableProps) {
  if (comparisons.length === 0) {
    return null;
  }

  return (
    <section className="border-line bg-panel rounded-xl border p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h4 className="text-base font-semibold">{title}</h4>
          <p className="text-muted text-xs">
            {familyAdjustment?.method
              ? `Correction: ${familyAdjustment.method}`
              : "Correction: -"}
            {familyAdjustment?.alpha !== null &&
            familyAdjustment?.alpha !== undefined
              ? ` · alpha=${familyAdjustment.alpha.toFixed(2)}`
              : ""}
            {familyAdjustment?.hypothesesTotal !== null &&
            familyAdjustment?.hypothesesTotal !== undefined
              ? ` · hypotheses=${Math.round(familyAdjustment.hypothesesTotal)}`
              : ""}
          </p>
        </div>
        <p className="text-muted text-xs">
          {comparisons.length} comparison{comparisons.length === 1 ? "" : "s"}
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-muted border-line border-b text-left text-xs uppercase">
            <tr>
              <th className="px-2 py-2">Metric</th>
              <th className="px-2 py-2">Base</th>
              <th className="px-2 py-2">Candidate</th>
              <th className="px-2 py-2">Delta</th>
              <th className="px-2 py-2">CI</th>
              <th className="px-2 py-2">Test</th>
              <th className="px-2 py-2">p</th>
              <th className="px-2 py-2">p_adj</th>
              <th className="px-2 py-2">Sig</th>
              <th className="px-2 py-2">Notes</th>
            </tr>
          </thead>
          <tbody>
            {comparisons.map((row) => (
              <tr key={row.id} className="border-line border-b last:border-b-0">
                <td className="px-2 py-2 align-top">
                  <div className="font-medium">{row.metricLabel}</div>
                  <div className="text-muted text-xs">
                    {row.baselineModelId ?? "baseline"} vs{" "}
                    {row.candidateModelId ?? "candidate"}
                  </div>
                </td>
                <td className="px-2 py-2 align-top">
                  {formatNumber(row.baselineValue)}
                </td>
                <td className="px-2 py-2 align-top">
                  {formatNumber(row.candidateValue)}
                </td>
                <td className="px-2 py-2 align-top">
                  {formatSigned(row.deltaValue)}
                </td>
                <td className="px-2 py-2 align-top">{formatInterval(row)}</td>
                <td className="px-2 py-2 align-top">
                  <div>{row.testLabel ?? row.testId ?? "-"}</div>
                  {row.statistic !== null ? (
                    <div className="text-muted text-xs">
                      stat={formatNumber(row.statistic)}
                    </div>
                  ) : null}
                </td>
                <td className="px-2 py-2 align-top">
                  {formatNumber(row.pValue)}
                </td>
                <td className="px-2 py-2 align-top">
                  {formatNumber(row.pAdj)}
                </td>
                <td className="px-2 py-2 align-top">
                  {row.significant === null
                    ? "-"
                    : row.significant
                      ? "Yes"
                      : "No"}
                </td>
                <td className="px-2 py-2 align-top text-xs">
                  {buildNotes(row) || "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
