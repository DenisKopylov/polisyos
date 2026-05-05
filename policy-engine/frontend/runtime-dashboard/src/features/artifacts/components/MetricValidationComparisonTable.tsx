import { useI18n } from "@/shared/i18n/LocaleProvider";
import type {
  MetricValidationComparisonRow,
  MetricValidationFamilyAdjustment,
} from "@/shared/lib/domain/metricValidation";

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
  title,
  comparisons,
  familyAdjustment,
}: MetricValidationComparisonTableProps) {
  const { t } = useI18n();
  if (comparisons.length === 0) {
    return null;
  }

  const resolvedTitle = title ?? t("pages.artifacts.metricValidation.title");

  return (
    <section className="border-line bg-panel rounded-xl border p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h4 className="text-base font-semibold">{resolvedTitle}</h4>
          <p className="text-muted text-xs">
            {familyAdjustment?.method
              ? t("pages.artifacts.metricValidation.correction", {
                  method: familyAdjustment.method,
                })
              : t("pages.artifacts.metricValidation.correctionUnavailable")}
            {familyAdjustment?.alpha !== null &&
            familyAdjustment?.alpha !== undefined
              ? ` · ${t("pages.artifacts.metricValidation.alpha", {
                  alpha: familyAdjustment.alpha.toFixed(2),
                })}`
              : ""}
            {familyAdjustment?.hypothesesTotal !== null &&
            familyAdjustment?.hypothesesTotal !== undefined
              ? ` · ${t("pages.artifacts.metricValidation.hypotheses", {
                  count: Math.round(familyAdjustment.hypothesesTotal),
                })}`
              : ""}
          </p>
        </div>
        <p className="text-muted text-xs">
          {t("pages.artifacts.metricValidation.comparisonCount", {
            count: comparisons.length,
          })}
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-muted border-line border-b text-left text-xs uppercase">
            <tr>
              <th className="px-2 py-2">
                {t("pages.artifacts.metricValidation.columns.metric")}
              </th>
              <th className="px-2 py-2">
                {t("pages.artifacts.metricValidation.columns.base")}
              </th>
              <th className="px-2 py-2">
                {t("pages.artifacts.metricValidation.columns.candidate")}
              </th>
              <th className="px-2 py-2">
                {t("pages.artifacts.metricValidation.columns.delta")}
              </th>
              <th className="px-2 py-2">CI</th>
              <th className="px-2 py-2">
                {t("pages.artifacts.metricValidation.columns.test")}
              </th>
              <th className="px-2 py-2">
                {t("pages.artifacts.metricValidation.columns.p")}
              </th>
              <th className="px-2 py-2">
                {t("pages.artifacts.metricValidation.columns.pAdjusted")}
              </th>
              <th className="px-2 py-2">
                {t("pages.artifacts.metricValidation.columns.significance")}
              </th>
              <th className="px-2 py-2">
                {t("pages.artifacts.metricValidation.columns.notes")}
              </th>
            </tr>
          </thead>
          <tbody>
            {comparisons.map((row) => (
              <tr key={row.id} className="border-line border-b last:border-b-0">
                <td className="px-2 py-2 align-top">
                  <div className="font-medium">{row.metricLabel}</div>
                  <div className="text-muted text-xs">
                    {row.baselineModelId ??
                      t(
                        "pages.artifacts.metricValidation.baselineFallback",
                      )}{" "}
                    {t("pages.artifacts.metricValidation.versus")}{" "}
                    {row.candidateModelId ??
                      t("pages.artifacts.metricValidation.candidateFallback")}
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
                      {t("pages.artifacts.metricValidation.stat", {
                        value: formatNumber(row.statistic),
                      })}
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
                      ? t("common.yes")
                      : t("common.no")}
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
