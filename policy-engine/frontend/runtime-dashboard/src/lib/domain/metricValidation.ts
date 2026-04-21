import {
  asArray,
  asNumber,
  asRecord,
  asString,
  toDisplayLabel,
} from "../parsing";

export type MetricValidationFamilyAdjustment = {
  method: string | null;
  alpha: number | null;
  hypothesesTotal: number | null;
  errorRateTarget: string | null;
  dependencyAssumption: string | null;
};

export type MetricValidationComparisonRow = {
  id: string;
  metricId: string;
  metricLabel: string;
  metricDirection: string | null;
  baselineModelId: string | null;
  candidateModelId: string | null;
  baselineValue: number | null;
  candidateValue: number | null;
  deltaValue: number | null;
  familyId: string | null;
  familyScope: string | null;
  sampleSizeEffective: number | null;
  resamplingMethod: string | null;
  testId: string | null;
  testLabel: string | null;
  statistic: number | null;
  effectSize: number | null;
  ciLow: number | null;
  ciHigh: number | null;
  ciLevel: number | null;
  pValue: number | null;
  pAdj: number | null;
  alpha: number | null;
  significant: boolean | null;
  assumptionWarnings: string[];
  calibrationWarnings: string[];
};

function toStringList(value: unknown): string[] {
  return asArray(value)
    .map((item) => asString(item))
    .filter((item): item is string => Boolean(item));
}

export function parseMetricValidationFamilyAdjustment(
  value: unknown,
): MetricValidationFamilyAdjustment | null {
  const record = asRecord(value);
  if (!record) {
    return null;
  }
  const method = asString(record.method);
  const alpha = asNumber(record.alpha);
  const hypothesesTotal = asNumber(record.hypotheses_total);
  const errorRateTarget = asString(record.error_rate_target);
  const dependencyAssumption = asString(record.dependency_assumption);
  if (
    method === null &&
    alpha === null &&
    hypothesesTotal === null &&
    errorRateTarget === null &&
    dependencyAssumption === null
  ) {
    return null;
  }
  return {
    method,
    alpha,
    hypothesesTotal,
    errorRateTarget,
    dependencyAssumption,
  };
}

export function parseMetricValidationComparisonRows(
  value: unknown,
): MetricValidationComparisonRow[] {
  return asArray(value)
    .map((item, index) => parseMetricValidationComparisonRow(item, index))
    .filter((item): item is MetricValidationComparisonRow => item !== null);
}

function parseMetricValidationComparisonRow(
  value: unknown,
  index: number,
): MetricValidationComparisonRow | null {
  const record = asRecord(value);
  if (!record) {
    return null;
  }

  const significance = asRecord(record.significance);
  const metricId = asString(record.metric_id);
  if (!metricId) {
    return null;
  }

  const assumptionWarnings = toStringList(
    significance?.assumption_flags ?? record.assumption_warnings,
  );
  const calibrationWarnings = toStringList(
    significance?.calibration_flags ?? record.calibration_warnings,
  );
  const testId = asString(significance?.test_id) ?? asString(record.test_id);
  const baselineModelId = asString(record.baseline_model_id);
  const candidateModelId = asString(record.candidate_model_id);

  return {
    id:
      `${baselineModelId ?? "baseline"}:${candidateModelId ?? "candidate"}:${metricId}:${index}`,
    metricId,
    metricLabel: toDisplayLabel(metricId),
    metricDirection: asString(record.metric_direction),
    baselineModelId,
    candidateModelId,
    baselineValue: asNumber(record.baseline_value),
    candidateValue: asNumber(record.candidate_value),
    deltaValue: asNumber(record.delta_value),
    familyId: asString(record.family_id),
    familyScope: asString(record.family_scope),
    sampleSizeEffective: asNumber(record.sample_size_effective),
    resamplingMethod: asString(record.resampling_method),
    testId,
    testLabel: asString(significance?.test_label) ?? asString(record.test_label),
    statistic: asNumber(significance?.statistic) ?? asNumber(record.statistic),
    effectSize: asNumber(significance?.effect_size) ?? asNumber(record.effect_size),
    ciLow: asNumber(significance?.ci_low) ?? asNumber(record.ci_low),
    ciHigh: asNumber(significance?.ci_high) ?? asNumber(record.ci_high),
    ciLevel: asNumber(significance?.ci_level) ?? asNumber(record.ci_level),
    pValue: asNumber(significance?.p_value_raw) ?? asNumber(record.p_value),
    pAdj: asNumber(significance?.p_value_adj) ?? asNumber(record.p_adj),
    alpha: asNumber(significance?.alpha) ?? asNumber(record.alpha),
    significant:
      typeof record.significant === "boolean"
        ? record.significant
        : typeof significance?.reject_null_adj === "boolean"
          ? significance.reject_null_adj
          : typeof significance?.reject_null_raw === "boolean"
            ? significance.reject_null_raw
            : null,
    assumptionWarnings,
    calibrationWarnings,
  };
}
