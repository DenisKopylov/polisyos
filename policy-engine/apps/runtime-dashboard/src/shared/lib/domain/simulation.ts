import {
  asArray,
  asNumber,
  asRecord,
  asString,
  toDisplayLabel,
} from "../parsing";
import {
  type MetricValidationComparisonRow,
  type MetricValidationFamilyAdjustment,
  parseMetricValidationComparisonRows,
  parseMetricValidationFamilyAdjustment,
} from "./metricValidation";

export type SimulationMetric = {
  key: string;
  label: string;
  value: number;
  formatted: string;
  unit: string;
  severity: "low" | "medium" | "high";
  ciLower: number | null;
  ciUpper: number | null;
  ciLevel: number | null;
  pValue?: number | null;
  pAdj?: number | null;
  alpha?: number | null;
  significant?: boolean | null;
  testLabel?: string | null;
  effectSize?: number | null;
  assumptionWarnings?: string[];
};

export type TimeSeriesPoint = {
  step: number;
  value?: number;
  baseline?: number;
  policy?: number;
  observed?: number;
  fitted?: number;
  lower1?: number;
  upper1?: number;
  lower2?: number;
  upper2?: number;
};

export type TimeSeries = {
  id: string;
  label: string;
  mode: "single" | "baseline_policy" | "observed_fitted";
  points: TimeSeriesPoint[];
  supportsUncertainty: boolean;
};

export type DistributionalCohort = {
  cohortId: string;
  cohortLabel: string;
  populationShare: number;
  delta: number;
  impactDirection: string;
  isVulnerable: boolean;
};

export type DistributionalBreakdown = {
  dimensionLabel: string;
  primaryMetric: string;
  giniBefore: number | null;
  giniAfter: number | null;
  giniDelta: number | null;
  cohorts: DistributionalCohort[];
};

export type DistributionalModel = {
  overallGiniBefore: number | null;
  overallGiniAfter: number | null;
  overallGiniDelta: number | null;
  winnersCount: number | null;
  losersCount: number | null;
  winnersShare: number | null;
  losersShare: number | null;
  breakdowns: DistributionalBreakdown[];
};

export type CalibrationFitRow = {
  target: string;
  mse: number | null;
  rmse: number | null;
  mae: number | null;
  r2: number | null;
  n: number | null;
};

export type CalibrationParam = {
  name: string;
  value: number;
  ciLower: number | null;
  ciUpper: number | null;
};

export type CalibrationSeries = {
  target: string;
  points: Array<{
    step: number;
    observed: number | null;
    fitted: number | null;
  }>;
};

export type CalibrationModel = {
  totalLoss: number | null;
  lossHistory: number[];
  gradNormHistory: number[];
  fitRows: CalibrationFitRow[];
  params: CalibrationParam[];
  series: CalibrationSeries[];
  uncertaintyMethod: string | null;
  uncertaintyParams: string[];
};

export type UncertaintyEnvelopeModel = {
  pointEstimate: number | null;
  ciLower: number | null;
  ciUpper: number | null;
  ciLevel: number | null;
  source: string | null;
  propagationMethod: string | null;
  intervalSemantics: string | null;
};

export type MetricBound = {
  lower: number | null;
  upper: number | null;
  point: number | null;
  ciLevel: number | null;
};

export type MetricSignificance = {
  pValue: number | null;
  pAdj: number | null;
  alpha: number | null;
  significant: boolean | null;
  testLabel: string | null;
  effectSize: number | null;
  assumptionWarnings: string[];
};

export type SimulationViewModel = {
  sourceKind: string;
  metrics: SimulationMetric[];
  metricComparisons: MetricValidationComparisonRow[];
  metricValidationFamilyAdjustment: MetricValidationFamilyAdjustment | null;
  timeSeries: TimeSeries[];
  distributional: DistributionalModel | null;
  calibration: CalibrationModel | null;
  envelope: UncertaintyEnvelopeModel | null;
  boundsByMetric: Record<string, MetricBound>;
  notes: string[];
};

const KEY_TO_LABEL: Record<
  string,
  { label: string; unit: string; scale: number }
> = {
  gdp_change: { label: "GDP Change", unit: "%", scale: 100 },
  unemployment_change: { label: "Unemployment Change", unit: "%", scale: 100 },
  inflation_change: { label: "Inflation Change", unit: "%", scale: 100 },
  gini_coefficient: { label: "Gini Coefficient", unit: "", scale: 1 },
  applied_nodes: { label: "Applied Nodes", unit: "", scale: 1 },
  step_latency_ms: { label: "Step Latency", unit: "ms", scale: 1 },
  avg_income: { label: "Average Income", unit: "", scale: 1 },
  gov_balance: { label: "Government Balance", unit: "", scale: 1 },
  n_agents: { label: "Agents", unit: "", scale: 1 },
};

function toNumberArray(value: unknown): number[] {
  return asArray(value)
    .map((item) => asNumber(item))
    .filter((item): item is number => item !== null);
}

function toSeverity(value: number, maxAbs: number): "low" | "medium" | "high" {
  if (maxAbs <= 0) {
    return "low";
  }
  const ratio = Math.abs(value) / maxAbs;
  if (ratio >= 0.66) {
    return "high";
  }
  if (ratio >= 0.33) {
    return "medium";
  }
  return "low";
}

function formatMetric(
  key: string,
  value: number,
  bounds: MetricBound | null,
  significance: MetricSignificance | null,
): SimulationMetric {
  const spec = KEY_TO_LABEL[key] ?? {
    label: toDisplayLabel(key),
    unit: "",
    scale: 1,
  };
  const scaled = value * spec.scale;
  const maxFraction = Math.abs(scaled) >= 100 ? 1 : 2;

  const significanceFields = significance
    ? {
        pValue: significance.pValue,
        pAdj: significance.pAdj,
        alpha: significance.alpha,
        significant: significance.significant,
        testLabel: significance.testLabel,
        effectSize: significance.effectSize,
        assumptionWarnings: significance.assumptionWarnings,
      }
    : {};

  return {
    key,
    label: spec.label,
    value: scaled,
    formatted: `${scaled >= 0 ? "+" : ""}${scaled.toFixed(maxFraction)}`,
    unit: spec.unit,
    severity: "low",
    ciLower: bounds?.lower ?? null,
    ciUpper: bounds?.upper ?? null,
    ciLevel: bounds?.ciLevel ?? null,
    ...significanceFields,
  };
}

function parseBounds(
  record: Record<string, unknown> | null,
): Record<string, MetricBound> {
  if (!record) {
    return {};
  }

  const out: Record<string, MetricBound> = {};

  for (const [key, value] of Object.entries(record)) {
    const numeric = asNumber(value);
    if (numeric === null) {
      continue;
    }

    const match = key.match(
      /^(?<metricId>.*)_(?<suffix>lower|upper|point|ci_level)$/,
    );
    if (!match?.groups) {
      continue;
    }

    const { metricId, suffix } = match.groups;
    if (!metricId || !suffix) {
      continue;
    }
    const current = out[metricId] ?? {
      lower: null,
      upper: null,
      point: null,
      ciLevel: null,
    };

    if (suffix === "lower") {
      current.lower = numeric;
    }
    if (suffix === "upper") {
      current.upper = numeric;
    }
    if (suffix === "point") {
      current.point = numeric;
    }
    if (suffix === "ci_level") {
      current.ciLevel = numeric;
    }

    out[metricId] = current;
  }

  return out;
}

function collectNumericMetrics(
  record: Record<string, unknown>,
): Array<{ key: string; value: number }> {
  return Object.entries(record)
    .map(([key, value]) => ({ key, value: asNumber(value) }))
    .filter(
      (item): item is { key: string; value: number } => item.value !== null,
    );
}

function parseMetricSignificance(
  record: Record<string, unknown> | null,
): Record<string, MetricSignificance> {
  if (!record) {
    return {};
  }

  const out: Record<string, MetricSignificance> = {};
  for (const [metricId, value] of Object.entries(record)) {
    const entry = asRecord(value);
    if (!entry) {
      continue;
    }
    out[metricId] = {
      pValue: asNumber(entry.p_value),
      pAdj: asNumber(entry.p_adj),
      alpha: asNumber(entry.alpha),
      significant:
        typeof entry.significant === "boolean" ? entry.significant : null,
      testLabel: asString(entry.test_label),
      effectSize: extractEffectSizePoint(entry.effect_size),
      assumptionWarnings: asArray(entry.assumption_warnings)
        .map((item) => asString(item))
        .filter((item): item is string => Boolean(item)),
    };
  }
  return out;
}

function extractEffectSizePoint(value: unknown): number | null {
  const direct = asNumber(value);
  if (direct !== null) {
    return direct;
  }
  return asNumber(asRecord(value)?.point);
}

function parseMetrics(
  payload: Record<string, unknown>,
  artifactKind: string,
  boundsByMetric: Record<string, MetricBound>,
  significanceByMetric: Record<string, MetricSignificance>,
): SimulationMetric[] {
  const candidates: Array<{ key: string; value: number }> = [];

  const metricsValues = asRecord(payload.values);
  if (artifactKind === "foundry.metrics" && metricsValues) {
    candidates.push(...collectNumericMetrics(metricsValues));
  }

  const simulationResults = asRecord(payload.simulation_results);
  if (simulationResults) {
    candidates.push(...collectNumericMetrics(simulationResults));
  }

  if (artifactKind === "scientist.simulation_results") {
    candidates.push(...collectNumericMetrics(payload));
  }

  if (artifactKind === "foundry.calibration_report") {
    const totalLoss = asNumber(payload.total_loss);
    if (totalLoss !== null) {
      candidates.push({ key: "total_loss", value: totalLoss });
    }
  }

  if (candidates.length === 0) {
    const fallback = collectNumericMetrics(payload).filter(
      (entry) => !entry.key.endsWith("_id") && entry.key !== "schema_version",
    );
    candidates.push(...fallback);
  }

  const deduped = new Map<string, number>();
  for (const candidate of candidates) {
    deduped.set(candidate.key, candidate.value);
  }

  const metrics = Array.from(deduped.entries()).map(([key, value]) =>
    formatMetric(
      key,
      value,
      boundsByMetric[key] ?? null,
      significanceByMetric[key] ?? null,
    ),
  );

  const maxAbs = Math.max(
    ...metrics.map((metric) => Math.abs(metric.value)),
    0,
  );
  return metrics
    .map((metric) => ({
      ...metric,
      severity: toSeverity(metric.value, maxAbs),
    }))
    .sort((left, right) => Math.abs(right.value) - Math.abs(left.value));
}

function seriesFromSingleArray(
  id: string,
  label: string,
  values: number[],
): TimeSeries {
  return {
    id,
    label,
    mode: "single",
    supportsUncertainty: false,
    points: values.map((value, index) => ({
      step: index,
      value,
    })),
  };
}

function seriesFromComparison(
  id: string,
  label: string,
  observed: number[],
  fitted: number[],
  time: number[],
): TimeSeries {
  const count = Math.max(observed.length, fitted.length);
  const points: TimeSeriesPoint[] = [];
  for (let index = 0; index < count; index += 1) {
    points.push({
      step: time[index] ?? index,
      observed: observed[index],
      fitted: fitted[index],
    });
  }

  return {
    id,
    label,
    mode: "observed_fitted",
    supportsUncertainty: false,
    points,
  };
}

function seriesFromBaselinePolicy(
  id: string,
  label: string,
  baseline: number[],
  policy: number[],
  lower1: number[],
  upper1: number[],
  lower2: number[],
  upper2: number[],
): TimeSeries {
  const count = Math.max(baseline.length, policy.length);
  const points: TimeSeriesPoint[] = [];

  for (let index = 0; index < count; index += 1) {
    points.push({
      step: index,
      baseline: baseline[index],
      policy: policy[index],
      lower1: lower1[index],
      upper1: upper1[index],
      lower2: lower2[index],
      upper2: upper2[index],
    });
  }

  return {
    id,
    label,
    mode: "baseline_policy",
    supportsUncertainty:
      lower1.length > 0 ||
      upper1.length > 0 ||
      lower2.length > 0 ||
      upper2.length > 0,
    points,
  };
}

function parseTimeSeries(payload: Record<string, unknown>): TimeSeries[] {
  const series: TimeSeries[] = [];

  const lossHistory = toNumberArray(payload.loss_history);
  if (lossHistory.length > 1) {
    series.push(
      seriesFromSingleArray("loss_history", "Loss History", lossHistory),
    );
  }

  const gradNormHistory = toNumberArray(payload.grad_norm_history);
  if (gradNormHistory.length > 1) {
    series.push(
      seriesFromSingleArray(
        "grad_norm_history",
        "Gradient Norm",
        gradNormHistory,
      ),
    );
  }

  const timeSeriesRecord = asRecord(payload.time_series);
  if (timeSeriesRecord) {
    for (const [id, value] of Object.entries(timeSeriesRecord)) {
      const seriesRecord = asRecord(value);
      if (!seriesRecord) {
        continue;
      }
      const baseline = toNumberArray(seriesRecord.baseline);
      const policy = toNumberArray(seriesRecord.policy);
      if (baseline.length > 0 || policy.length > 0) {
        series.push(
          seriesFromBaselinePolicy(
            id,
            toDisplayLabel(id),
            baseline,
            policy,
            toNumberArray(seriesRecord.lower_1sigma),
            toNumberArray(seriesRecord.upper_1sigma),
            toNumberArray(seriesRecord.lower_2sigma),
            toNumberArray(seriesRecord.upper_2sigma),
          ),
        );
      }
    }
  }

  const seriesComparison = asRecord(payload.series_comparison);
  if (seriesComparison) {
    for (const [id, value] of Object.entries(seriesComparison)) {
      const comparison = asRecord(value);
      if (!comparison) {
        continue;
      }
      const observed = toNumberArray(comparison.real);
      const fitted = toNumberArray(comparison.model);
      if (observed.length === 0 && fitted.length === 0) {
        continue;
      }
      const time = toNumberArray(comparison.time);
      series.push(
        seriesFromComparison(id, toDisplayLabel(id), observed, fitted, time),
      );
    }
  }

  for (const [key, value] of Object.entries(payload)) {
    if (!key.endsWith("_history")) {
      continue;
    }
    const alreadyIncluded = series.some((item) => item.id === key);
    if (alreadyIncluded) {
      continue;
    }
    const values = toNumberArray(value);
    if (values.length > 1) {
      series.push(seriesFromSingleArray(key, toDisplayLabel(key), values));
    }
  }

  return series;
}

function parseDistributionalObject(
  record: Record<string, unknown>,
): DistributionalModel | null {
  const breakdownValues = asArray(record.breakdowns);
  const breakdowns: DistributionalBreakdown[] = [];

  for (const item of breakdownValues) {
    const breakdown = asRecord(item);
    if (!breakdown) {
      continue;
    }

    const cohorts: DistributionalCohort[] = [];
    const primaryMetric = asString(breakdown.primary_metric) ?? "delta";
    for (const cohortValue of asArray(breakdown.cohorts)) {
      const cohort = asRecord(cohortValue);
      if (!cohort) {
        continue;
      }

      let delta = asNumber(cohort.delta);
      if (delta === null) {
        const metricDeltas = asRecord(cohort.metric_deltas);
        delta = asNumber(metricDeltas?.[primaryMetric]);
      }
      if (delta === null) {
        continue;
      }

      cohorts.push({
        cohortId: asString(cohort.cohort_id) ?? "unknown",
        cohortLabel: asString(cohort.cohort_label) ?? "Unknown",
        populationShare: asNumber(cohort.population_share) ?? 0,
        delta,
        impactDirection: asString(cohort.impact_direction) ?? "neutral",
        isVulnerable: Boolean(cohort.is_vulnerable),
      });
    }

    if (cohorts.length === 0) {
      continue;
    }

    breakdowns.push({
      dimensionLabel:
        asString(breakdown.dimension_label) ??
        toDisplayLabel(asString(breakdown.dimension) ?? "dimension"),
      primaryMetric,
      giniBefore: asNumber(breakdown.gini_before),
      giniAfter: asNumber(breakdown.gini_after),
      giniDelta: asNumber(breakdown.gini_delta),
      cohorts,
    });
  }

  if (breakdowns.length === 0) {
    return null;
  }

  return {
    overallGiniBefore: asNumber(record.overall_gini_before),
    overallGiniAfter: asNumber(record.overall_gini_after),
    overallGiniDelta: asNumber(record.overall_gini_delta),
    winnersCount: asNumber(record.winners_count),
    losersCount: asNumber(record.losers_count),
    winnersShare: asNumber(record.winners_share),
    losersShare: asNumber(record.losers_share),
    breakdowns,
  };
}

function parseDistributional(
  payload: Record<string, unknown>,
  artifactKind: string,
): DistributionalModel | null {
  if (artifactKind === "ir.distributional_report") {
    return parseDistributionalObject(payload);
  }

  const distributionalSection = asRecord(payload.distributional);
  if (distributionalSection) {
    return parseDistributionalObject(distributionalSection);
  }

  return null;
}

function parseCalibration(
  payload: Record<string, unknown>,
  artifactKind: string,
): CalibrationModel | null {
  if (artifactKind !== "foundry.calibration_report") {
    return null;
  }

  const perTarget = asRecord(asRecord(payload.fit_quality)?.per_target);
  const fitRows: CalibrationFitRow[] = [];
  if (perTarget) {
    for (const [target, value] of Object.entries(perTarget)) {
      const metrics = asRecord(value);
      if (!metrics) {
        continue;
      }
      fitRows.push({
        target,
        mse: asNumber(metrics.mse),
        rmse: asNumber(metrics.rmse),
        mae: asNumber(metrics.mae),
        r2: asNumber(metrics.r2),
        n: asNumber(metrics.n),
      });
    }
  }

  const params: CalibrationParam[] = [];
  const calibratedParams = asRecord(payload.calibrated_params);
  const uncertaintyEnvelopes = asRecord(payload.uncertainty_envelopes);
  if (calibratedParams) {
    for (const [name, value] of Object.entries(calibratedParams)) {
      const numeric = asNumber(value);
      if (numeric === null) {
        continue;
      }
      const envelope = asRecord(uncertaintyEnvelopes?.[name]);
      const interval = asArray(envelope?.confidence_interval);
      params.push({
        name,
        value: numeric,
        ciLower: asNumber(interval[0]),
        ciUpper: asNumber(interval[1]),
      });
    }
  }

  const series: CalibrationSeries[] = [];
  const seriesComparison = asRecord(payload.series_comparison);
  if (seriesComparison) {
    for (const [target, value] of Object.entries(seriesComparison)) {
      const comparison = asRecord(value);
      if (!comparison) {
        continue;
      }
      const observed = toNumberArray(comparison.real);
      const fitted = toNumberArray(comparison.model);
      if (observed.length === 0 && fitted.length === 0) {
        continue;
      }
      const time = toNumberArray(comparison.time);
      const count = Math.max(observed.length, fitted.length);
      series.push({
        target,
        points: Array.from({ length: count }, (_, index) => ({
          step: time[index] ?? index,
          observed: observed[index] ?? null,
          fitted: fitted[index] ?? null,
        })),
      });
    }
  }

  const uncertainty = asRecord(payload.uncertainties);

  return {
    totalLoss: asNumber(payload.total_loss),
    lossHistory: toNumberArray(payload.loss_history),
    gradNormHistory: toNumberArray(payload.grad_norm_history),
    fitRows,
    params,
    series,
    uncertaintyMethod: asString(uncertainty?.method),
    uncertaintyParams: asArray(uncertainty?.params)
      .map((item) => asString(item))
      .filter((item): item is string => Boolean(item)),
  };
}

function parseEnvelope(
  payload: Record<string, unknown>,
  artifactKind: string,
): UncertaintyEnvelopeModel | null {
  if (artifactKind !== "ir.uncertainty_envelope") {
    return null;
  }

  const interval = asArray(payload.confidence_interval);

  return {
    pointEstimate: asNumber(payload.point_estimate),
    ciLower: asNumber(interval[0]),
    ciUpper: asNumber(interval[1]),
    ciLevel: asNumber(payload.confidence_level),
    source: asString(payload.source),
    propagationMethod: asString(payload.propagation_method),
    intervalSemantics: asString(payload.interval_semantics),
  };
}

function detectSourceKind(
  artifactKind: string,
  payload: Record<string, unknown>,
): string {
  if (artifactKind === "scientist.decision_packet") {
    return "decision_packet";
  }
  if (artifactKind === "foundry.metrics") {
    return "metrics";
  }
  if (artifactKind === "foundry.calibration_report") {
    return "calibration_report";
  }
  if (artifactKind === "ir.distributional_report") {
    return "distributional_report";
  }
  if (artifactKind === "ir.uncertainty_envelope") {
    return "uncertainty_envelope";
  }
  if (artifactKind === "scientist.metric_validation_report") {
    return "metric_validation_report";
  }
  if (asRecord(payload.simulation_results)) {
    return "simulation_bundle";
  }
  return artifactKind;
}

export function normalizeSimulationPayload(
  artifactKind: string,
  preview: unknown,
): SimulationViewModel | null {
  const payload = asRecord(preview);
  if (!payload) {
    return null;
  }

  const boundsByMetric = parseBounds(asRecord(payload.uncertainty_bounds));
  const significanceByMetric = parseMetricSignificance(
    asRecord(payload.metric_significance),
  );
  const metricComparisons = parseMetricValidationComparisonRows(
    payload.metric_validation_comparisons ?? payload.comparisons,
  );
  const metricValidationFamilyAdjustment =
    parseMetricValidationFamilyAdjustment(
      payload.metric_validation_family_adjustment ?? payload.family_adjustment,
    );
  const metrics = parseMetrics(
    payload,
    artifactKind,
    boundsByMetric,
    significanceByMetric,
  );
  const timeSeries = parseTimeSeries(payload);
  const distributional = parseDistributional(payload, artifactKind);
  const calibration = parseCalibration(payload, artifactKind);
  const envelope = parseEnvelope(payload, artifactKind);

  const notes: string[] = [];
  if (artifactKind === "foundry.simulation_result") {
    notes.push(
      "SimulationResult mostly stores refs; inspect linked artifacts for full metrics and charts.",
    );
  }
  if (artifactKind === "scientist.metric_validation_report") {
    notes.push(
      "Formal metric validation focuses on pairwise comparisons and multiplicity-adjusted significance.",
    );
  }
  if (metrics.length === 0 && metricComparisons.length === 0) {
    notes.push("No numeric metrics were detected in this payload.");
  }
  if (timeSeries.length === 0) {
    notes.push("No time series arrays were detected.");
  }

  return {
    sourceKind: detectSourceKind(artifactKind, payload),
    metrics,
    metricComparisons,
    metricValidationFamilyAdjustment,
    timeSeries,
    distributional,
    calibration,
    envelope,
    boundsByMetric,
    notes,
  };
}
