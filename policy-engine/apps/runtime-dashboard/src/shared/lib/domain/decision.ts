import type { QuantityUncertainty } from "@polisyos/runtime-api-client";

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

const METRIC_IDENTIFIABILITY_MEMBERS = {
  assumed: true,
  estimated: true,
  identified: true,
  unknown: true,
} as const satisfies Record<QuantityUncertainty["identifiability"], true>;

export type DecisionMetric = {
  name: string;
  value: number;
  formatted: string;
  unit: string;
  ciLower: number | null;
  ciUpper: number | null;
  ciLevel: number | null;
  pValue?: number | null;
  pAdj?: number | null;
  alpha?: number | null;
  significant?: boolean | null;
  testLabel?: string | null;
  effectSize?: number | null;
  identifiability?: QuantityUncertainty["identifiability"];
  uncertaintyMethod?: QuantityUncertainty["method"];
  assumptionWarnings?: string[];
};

export type DecisionDiagnosticBadge = {
  label: string;
  ownerKind: string | null;
};

export type DecisionIssues = {
  blockerCount: number | null;
  warningCount: number | null;
  infoCount: number | null;
  blockedPasses: string[];
};

export type DecisionDistributionalRow = {
  cohortLabel: string;
  populationShare: number;
  primaryDelta: number;
  direction: string;
  isVulnerable: boolean;
};

export type DecisionDistributionalBreakdown = {
  dimensionLabel: string;
  rows: DecisionDistributionalRow[];
};

export type DecisionDistributional = {
  giniBefore: number | null;
  giniAfter: number | null;
  giniDelta: number | null;
  winnersCount: number;
  losersCount: number;
  winnersShare: number;
  losersShare: number;
  vulnerableLosersCount: number;
  breakdowns: DecisionDistributionalBreakdown[];
};

export type DecisionCardViewModel = {
  runId: string;
  generatedAt: string | null;
  /** Opaque producer verdict; presentation must go through the DS5 swap point. */
  verdict: string | null;
  confidence: string | null;
  policySummary: string;
  interventionCount: number;
  keyMetrics: DecisionMetric[];
  metricComparisons: MetricValidationComparisonRow[];
  metricValidationFamilyAdjustment: MetricValidationFamilyAdjustment | null;
  diagnosticsBadges: DecisionDiagnosticBadge[];
  issues: DecisionIssues;
  distributional: DecisionDistributional | null;
  totalDurationMs: number;
  sourceKind: "decision_card" | "decision_packet";
};

export function metricIdentifiability(
  metric: Pick<DecisionMetric, "identifiability">,
): QuantityUncertainty["identifiability"] {
  return metric.identifiability ?? "unknown";
}

function normalizeConfidence(value: string | null): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

function buildIssues(value: unknown): {
  diagnostics: DecisionDiagnosticBadge[];
  summary: DecisionIssues;
} {
  const diagnostics = asArray(value)
    .map((issueValue, index) => {
      const ownerLabel = asString(issueValue);
      if (ownerLabel) {
        return {
          label: ownerLabel,
          ownerKind: null,
        } satisfies DecisionDiagnosticBadge;
      }

      const issue = asRecord(issueValue);
      if (!issue) {
        return null;
      }
      const passId = asString(issue.pass_id);
      const message = asString(issue.message);
      const ownerKind = asString(issue.severity);
      if (!passId && !message && !ownerKind) {
        return null;
      }

      return {
        label:
          passId && message
            ? `${passId}: ${message}`
            : (passId ?? message ?? `Owner issue ${index + 1}`),
        ownerKind,
      } satisfies DecisionDiagnosticBadge;
    })
    .filter((item): item is DecisionDiagnosticBadge => item !== null);

  return {
    diagnostics,
    summary: {
      blockerCount: null,
      warningCount: null,
      infoCount: null,
      blockedPasses: [],
    },
  };
}

function metricSignificanceFields(
  value: Record<string, unknown> | null,
): Partial<DecisionMetric> {
  if (!value) {
    return {};
  }
  const warnings = asArray(value.assumption_warnings)
    .map((item) => asString(item))
    .filter((item): item is string => Boolean(item));
  const hasAnyField =
    "p_value" in value ||
    "p_adj" in value ||
    "alpha" in value ||
    typeof value.significant === "boolean" ||
    "test_label" in value ||
    "effect_size" in value ||
    warnings.length > 0;
  if (!hasAnyField) {
    return {};
  }
  const pValue = asNumber(value.p_value);
  const pAdj = asNumber(value.p_adj);
  const alpha = asNumber(value.alpha);
  const significant =
    typeof value.significant === "boolean" ? value.significant : undefined;
  const testLabel = asString(value.test_label) ?? undefined;
  const effectSize = extractEffectSizePoint(value.effect_size);
  const effectSizeEnvelope = asRecord(value.effect_size);
  const identifiability = extractMetricIdentifiability(
    effectSizeEnvelope?.identifiability,
  );
  const uncertaintyMethod = asString(effectSizeEnvelope?.method);
  return {
    ...(pValue !== null ? { pValue } : {}),
    ...(pAdj !== null ? { pAdj } : {}),
    ...(alpha !== null ? { alpha } : {}),
    ...(significant !== undefined ? { significant } : {}),
    ...(testLabel ? { testLabel } : {}),
    ...(effectSize !== null ? { effectSize } : {}),
    ...(identifiability ? { identifiability } : {}),
    ...(uncertaintyMethod ? { uncertaintyMethod } : {}),
    ...(warnings.length > 0 ? { assumptionWarnings: warnings } : {}),
  };
}

function extractMetricIdentifiability(
  value: unknown,
): QuantityUncertainty["identifiability"] | undefined {
  const candidate = asString(value);
  if (candidate && Object.hasOwn(METRIC_IDENTIFIABILITY_MEMBERS, candidate)) {
    return candidate as QuantityUncertainty["identifiability"];
  }
  return undefined;
}

function extractEffectSizePoint(value: unknown): number | null {
  const direct = asNumber(value);
  if (direct !== null) {
    return direct;
  }
  return asNumber(asRecord(value)?.point);
}

function extractMetrics(
  simulationResults: Record<string, unknown> | null,
  uncertaintyBounds: Record<string, unknown> | null,
  significanceByMetric: Record<string, unknown> | null,
): DecisionMetric[] {
  if (!simulationResults) {
    return [];
  }

  const bounds = uncertaintyBounds ?? {};
  const significance = significanceByMetric ?? {};

  const specs: Array<{
    key: string;
    name: string;
    scale: number;
    unit: string;
  }> = [
    { key: "gdp_change", name: "GDP Change", scale: 100, unit: "%" },
    {
      key: "unemployment_change",
      name: "Unemployment Change",
      scale: 100,
      unit: "%",
    },
    {
      key: "inflation_change",
      name: "Inflation Change",
      scale: 100,
      unit: "%",
    },
    { key: "gini_coefficient", name: "Gini Coefficient", scale: 1, unit: "" },
  ];

  const primary: DecisionMetric[] = [];
  for (const spec of specs) {
    const raw = asNumber(simulationResults[spec.key]);
    if (raw === null) {
      continue;
    }
    const value = raw * spec.scale;
    const significanceEntry = asRecord(significance[spec.key]);
    primary.push({
      name: spec.name,
      value,
      formatted: `${value >= 0 ? "+" : ""}${value.toFixed(2)}`,
      unit: spec.unit,
      ciLower: asNumber(bounds[`${spec.key}_lower`]),
      ciUpper: asNumber(bounds[`${spec.key}_upper`]),
      ciLevel: asNumber(bounds[`${spec.key}_ci_level`]),
      ...metricSignificanceFields(significanceEntry),
    });
  }

  if (primary.length > 0) {
    return primary;
  }

  return Object.entries(simulationResults)
    .map(([key, value]) => {
      const numeric = asNumber(value);
      if (numeric === null) {
        return null;
      }
      const significanceEntry = asRecord(significance[key]);
      return {
        name: toDisplayLabel(key),
        value: numeric,
        formatted: `${numeric >= 0 ? "+" : ""}${numeric.toFixed(2)}`,
        unit: "",
        ciLower: asNumber(bounds[`${key}_lower`]),
        ciUpper: asNumber(bounds[`${key}_upper`]),
        ciLevel: asNumber(bounds[`${key}_ci_level`]),
        ...metricSignificanceFields(significanceEntry),
      };
    })
    .filter((item): item is DecisionMetric => item !== null)
    .slice(0, 8);
}

function extractDistributionalFromCard(
  value: Record<string, unknown>,
): DecisionDistributional | null {
  const breakdownEntries = asArray(value.breakdowns);
  const breakdowns: DecisionDistributionalBreakdown[] = [];
  let vulnerableLosersCount = 0;

  for (const entry of breakdownEntries) {
    const tuple = asArray(entry);
    const dimensionLabel = asString(tuple[0]) ?? "Breakdown";
    const rowsRaw = asArray(tuple[1]);
    const rows: DecisionDistributionalRow[] = [];
    for (const rowValue of rowsRaw) {
      const row = asRecord(rowValue);
      if (!row) {
        continue;
      }
      const delta = asNumber(row.primary_delta);
      if (delta === null) {
        continue;
      }
      const isVulnerable = Boolean(row.is_vulnerable);
      if (isVulnerable && delta < -0.5) {
        vulnerableLosersCount += 1;
      }
      rows.push({
        cohortLabel: asString(row.cohort_label) ?? "Unknown",
        populationShare: asNumber(row.population_share) ?? 0,
        primaryDelta: delta,
        direction: asString(row.direction) ?? "~",
        isVulnerable,
      });
    }
    if (rows.length > 0) {
      breakdowns.push({
        dimensionLabel,
        rows,
      });
    }
  }

  if (breakdowns.length === 0) {
    return null;
  }

  return {
    giniBefore: asNumber(value.gini_before),
    giniAfter: asNumber(value.gini_after),
    giniDelta: asNumber(value.gini_delta),
    winnersCount: Math.max(0, Math.round(asNumber(value.winners_count) ?? 0)),
    losersCount: Math.max(0, Math.round(asNumber(value.losers_count) ?? 0)),
    winnersShare: asNumber(value.winners_share) ?? 0,
    losersShare: asNumber(value.losers_share) ?? 0,
    vulnerableLosersCount,
    breakdowns,
  };
}

function extractDistributionalFromPacket(
  value: Record<string, unknown>,
): DecisionDistributional | null {
  const breakdownsRaw = asArray(value.breakdowns);
  const breakdowns: DecisionDistributionalBreakdown[] = [];
  let vulnerableLosersCount = 0;

  for (const breakdownValue of breakdownsRaw) {
    const breakdown = asRecord(breakdownValue);
    if (!breakdown) {
      continue;
    }

    const rows: DecisionDistributionalRow[] = [];
    for (const cohortValue of asArray(breakdown.cohorts)) {
      const cohort = asRecord(cohortValue);
      if (!cohort) {
        continue;
      }
      const delta = asNumber(cohort.delta);
      if (delta === null) {
        continue;
      }
      const isVulnerable = Boolean(cohort.is_vulnerable);
      if (isVulnerable && delta < -0.5) {
        vulnerableLosersCount += 1;
      }
      rows.push({
        cohortLabel: asString(cohort.cohort_label) ?? "Unknown",
        populationShare: asNumber(cohort.population_share) ?? 0,
        primaryDelta: delta,
        direction: asString(cohort.impact_direction) ?? "~",
        isVulnerable,
      });
    }

    if (rows.length > 0) {
      breakdowns.push({
        dimensionLabel: asString(breakdown.dimension_label) ?? "Breakdown",
        rows,
      });
    }
  }

  if (breakdowns.length === 0) {
    return null;
  }

  return {
    giniBefore: asNumber(value.overall_gini_before),
    giniAfter: asNumber(value.overall_gini_after),
    giniDelta: asNumber(value.overall_gini_delta),
    winnersCount: Math.max(0, Math.round(asNumber(value.winners_count) ?? 0)),
    losersCount: Math.max(0, Math.round(asNumber(value.losers_count) ?? 0)),
    winnersShare: asNumber(value.winners_share) ?? 0,
    losersShare: asNumber(value.losers_share) ?? 0,
    vulnerableLosersCount,
    breakdowns,
  };
}

function derivePolicySummary(payload: Record<string, unknown>): {
  summary: string;
  interventionCount: number;
} {
  const explicitSummary = asString(payload.policy_summary);
  if (explicitSummary) {
    return {
      summary: explicitSummary,
      interventionCount: Math.max(
        0,
        Math.round(asNumber(payload.intervention_count) ?? 0),
      ),
    };
  }

  const policyIr = asRecord(payload.policy_ir);
  const policySpec = asRecord(policyIr?.policy_spec);
  const interventions = asArray(policySpec?.interventions);
  if (interventions.length > 0) {
    return {
      summary: `Policy with ${interventions.length} intervention(s)`,
      interventionCount: interventions.length,
    };
  }

  if (policyIr) {
    return {
      summary: "Policy data attached",
      interventionCount: 0,
    };
  }

  return {
    summary: "N/A",
    interventionCount: 0,
  };
}

function deriveDiagnosticBadges(
  record: Record<string, unknown>,
): DecisionDiagnosticBadge[] {
  const explicitBadges = asArray(record.diagnostic_badges)
    .map((value) => {
      const badge = asRecord(value);
      const label = asString(badge?.label);
      if (!label) {
        return null;
      }
      return {
        label,
        ownerKind: asString(badge?.kind),
      } satisfies DecisionDiagnosticBadge;
    })
    .filter((item): item is DecisionDiagnosticBadge => item !== null);
  if (explicitBadges.length > 0) {
    return explicitBadges.slice(0, 5);
  }

  const summary = asRecord(record.diagnostics_summary);
  if (!summary) {
    return [];
  }

  return [
    {
      label: `transport:${asString(summary.transport_status) ?? "not_available"}`,
      ownerKind: null,
    },
    {
      label: Boolean(summary.legal_executed)
        ? "legal:checked"
        : "legal:not_run",
      ownerKind: null,
    },
    {
      label: `replay:${asString(summary.replay_readiness) ?? "not_available"}`,
      ownerKind: null,
    },
    {
      label: Boolean(summary.human_review_needed)
        ? "human-review:required"
        : "human-review:not_required",
      ownerKind: null,
    },
    {
      label: Boolean(summary.uncertainty_available)
        ? "uncertainty:available"
        : "uncertainty:not_available",
      ownerKind: null,
    },
  ];
}

function parseDecisionCardRecord(
  record: Record<string, unknown>,
): DecisionCardViewModel {
  const distributional = asRecord(record.distributional);
  const issuesRecord = asRecord(record.issues);
  const policy = derivePolicySummary(record);

  const blockerCount = asNumber(issuesRecord?.blocker_count);
  const warningCount = asNumber(issuesRecord?.warning_count);
  const infoCount = asNumber(issuesRecord?.info_count);
  const issues: DecisionIssues = {
    blockerCount:
      blockerCount === null ? null : Math.max(0, Math.round(blockerCount)),
    warningCount:
      warningCount === null ? null : Math.max(0, Math.round(warningCount)),
    infoCount: infoCount === null ? null : Math.max(0, Math.round(infoCount)),
    blockedPasses: asArray(issuesRecord?.blocked_passes)
      .map((item) => asString(item))
      .filter((item): item is string => Boolean(item)),
  };

  return {
    runId: asString(record.run_id) ?? "unknown",
    generatedAt: asString(record.generated_at),
    verdict: asString(record.verdict),
    confidence: normalizeConfidence(asString(record.confidence)),
    policySummary: policy.summary,
    interventionCount: policy.interventionCount,
    keyMetrics: asArray(record.key_metrics)
      .map((value) => {
        const metric = asRecord(value);
        if (!metric) {
          return null;
        }
        const numeric = asNumber(metric.value);
        if (numeric === null) {
          return null;
        }
        const metricRecord = asRecord(value);
        return {
          name: asString(metricRecord?.name) ?? "Metric",
          value: numeric,
          formatted:
            asString(metricRecord?.formatted) ??
            `${numeric >= 0 ? "+" : ""}${numeric.toFixed(2)}`,
          unit: asString(metricRecord?.unit) ?? "",
          ciLower: asNumber(metricRecord?.ci_lower),
          ciUpper: asNumber(metricRecord?.ci_upper),
          ciLevel: asNumber(metricRecord?.ci_level),
          ...metricSignificanceFields(metricRecord),
        };
      })
      .filter((item): item is DecisionMetric => item !== null),
    metricComparisons: [],
    metricValidationFamilyAdjustment: null,
    diagnosticsBadges: deriveDiagnosticBadges(record),
    issues,
    distributional: distributional
      ? extractDistributionalFromCard(distributional)
      : null,
    totalDurationMs: Math.max(
      0,
      Math.round(asNumber(record.total_duration_ms) ?? 0),
    ),
    sourceKind: "decision_card",
  };
}

function parseDecisionPacketRecord(
  record: Record<string, unknown>,
): DecisionCardViewModel {
  const governance = asRecord(record.governance) ?? asRecord(record.feedback);
  const issuePresentation = buildIssues(governance?.issues);
  const policy = derivePolicySummary(record);

  const simulationResults = asRecord(record.simulation_results);
  const uncertaintyBounds = asRecord(record.uncertainty_bounds);
  const significanceByMetric = asRecord(record.metric_significance);

  let duration = 0;
  const runTimeline = asRecord(record.run_timeline);
  const summary = asRecord(runTimeline?.summary);
  const durationMaybe = asNumber(summary?.duration_ms);
  if (durationMaybe !== null) {
    duration = Math.max(0, Math.round(durationMaybe));
  }

  const distributional = extractDistributionalFromPacket(
    asRecord(record.distributional) ?? {},
  );

  return {
    runId: asString(record.run_id) ?? "unknown",
    generatedAt: asString(record.generated_at),
    verdict: asString(governance?.verdict),
    confidence: null,
    policySummary: policy.summary,
    interventionCount: policy.interventionCount,
    keyMetrics: extractMetrics(
      simulationResults,
      uncertaintyBounds,
      significanceByMetric,
    ),
    metricComparisons: parseMetricValidationComparisonRows(
      record.metric_validation_comparisons,
    ),
    metricValidationFamilyAdjustment: parseMetricValidationFamilyAdjustment(
      record.metric_validation_family_adjustment,
    ),
    diagnosticsBadges: [
      ...deriveDiagnosticBadges(record),
      ...issuePresentation.diagnostics,
    ],
    issues: issuePresentation.summary,
    distributional,
    totalDurationMs: duration,
    sourceKind: "decision_packet",
  };
}

export function parseDecisionCardPayload(
  payload: unknown,
): DecisionCardViewModel | null {
  const record = asRecord(payload);
  if (!record) {
    return null;
  }

  const hasCardShape =
    asString(record.verdict) !== null &&
    asString(record.confidence) !== null &&
    "key_metrics" in record &&
    ("policy_summary" in record || "issues" in record);

  if (hasCardShape) {
    return parseDecisionCardRecord(record);
  }

  const hasPacketShape =
    "simulation_results" in record ||
    "governance" in record ||
    "feedback" in record;
  if (hasPacketShape) {
    return parseDecisionPacketRecord(record);
  }

  return null;
}
