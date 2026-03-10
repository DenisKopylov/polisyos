import {
  asArray,
  asNumber,
  asRecord,
  asString,
  toDisplayLabel,
} from "../parsing";

export type DecisionVerdict = "APPROVE" | "REJECT" | "REVIEW";
export type DecisionConfidence = "HIGH" | "MEDIUM" | "LOW";

export type DecisionMetric = {
  name: string;
  value: number;
  formatted: string;
  unit: string;
  ciLower: number | null;
  ciUpper: number | null;
  ciLevel: number | null;
};

export type DecisionDiagnosticBadge = {
  label: string;
  kind: "ok" | "warn" | "fail" | "unknown";
};

export type DecisionIssues = {
  blockerCount: number;
  warningCount: number;
  infoCount: number;
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
  verdict: DecisionVerdict;
  confidence: DecisionConfidence;
  policySummary: string;
  interventionCount: number;
  keyMetrics: DecisionMetric[];
  diagnosticsBadges: DecisionDiagnosticBadge[];
  issues: DecisionIssues;
  distributional: DecisionDistributional | null;
  totalDurationMs: number;
  sourceKind: "decision_card" | "decision_packet";
};

function normalizeVerdict(value: string | null): DecisionVerdict {
  const normalized = (value ?? "").trim().toUpperCase();
  if (
    normalized === "APPROVE" ||
    normalized === "APPROVED" ||
    normalized === "PASS"
  ) {
    return "APPROVE";
  }
  if (
    normalized === "REJECT" ||
    normalized === "REJECTED" ||
    normalized === "FAIL"
  ) {
    return "REJECT";
  }
  return "REVIEW";
}

function normalizeConfidence(
  value: string | null,
  issues: DecisionIssues,
): DecisionConfidence {
  const normalized = (value ?? "").trim().toUpperCase();
  if (
    normalized === "HIGH" ||
    normalized === "MEDIUM" ||
    normalized === "LOW"
  ) {
    return normalized as DecisionConfidence;
  }
  if (issues.blockerCount > 0) {
    return "LOW";
  }
  if (issues.warningCount > 0) {
    return "MEDIUM";
  }
  return "HIGH";
}

function buildIssues(value: unknown): DecisionIssues {
  const issues = asArray(value);
  let blockerCount = 0;
  let warningCount = 0;
  let infoCount = 0;
  const blockedPasses = new Set<string>();

  for (const issueValue of issues) {
    const issue = asRecord(issueValue);
    if (!issue) {
      continue;
    }
    const severity = (asString(issue.severity) ?? "").toLowerCase();
    if (severity === "blocker") {
      blockerCount += 1;
      const passId = asString(issue.pass_id);
      if (passId) {
        blockedPasses.add(passId);
      }
      continue;
    }
    if (severity === "warning") {
      warningCount += 1;
      continue;
    }
    infoCount += 1;
  }

  return {
    blockerCount,
    warningCount,
    infoCount,
    blockedPasses: Array.from(blockedPasses).sort(),
  };
}

function extractMetrics(
  simulationResults: Record<string, unknown> | null,
  uncertaintyBounds: Record<string, unknown> | null,
): DecisionMetric[] {
  if (!simulationResults) {
    return [];
  }

  const bounds = uncertaintyBounds ?? {};

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
    primary.push({
      name: spec.name,
      value,
      formatted: `${value >= 0 ? "+" : ""}${value.toFixed(2)}`,
      unit: spec.unit,
      ciLower: asNumber(bounds[`${spec.key}_lower`]),
      ciUpper: asNumber(bounds[`${spec.key}_upper`]),
      ciLevel: asNumber(bounds[`${spec.key}_ci_level`]),
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
      return {
        name: toDisplayLabel(key),
        value: numeric,
        formatted: `${numeric >= 0 ? "+" : ""}${numeric.toFixed(2)}`,
        unit: "",
        ciLower: asNumber(bounds[`${key}_lower`]),
        ciUpper: asNumber(bounds[`${key}_upper`]),
        ciLevel: asNumber(bounds[`${key}_ci_level`]),
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

function badgeKindForTransport(
  value: string | null,
): DecisionDiagnosticBadge["kind"] {
  const normalized = (value ?? "").toLowerCase();
  if (normalized === "direct" || normalized === "transportable") {
    return "ok";
  }
  if (normalized === "non_transportable") {
    return "fail";
  }
  return "warn";
}

function badgeKindForReplay(
  value: string | null,
): DecisionDiagnosticBadge["kind"] {
  const normalized = (value ?? "").toLowerCase();
  if (normalized === "complete") {
    return "ok";
  }
  if (normalized === "incomplete") {
    return "fail";
  }
  return "warn";
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
      const kind = asString(badge?.kind);
      return {
        label,
        kind:
          kind === "ok" ||
          kind === "warn" ||
          kind === "fail" ||
          kind === "unknown"
            ? kind
            : "unknown",
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
      kind: badgeKindForTransport(asString(summary.transport_status)),
    },
    {
      label: Boolean(summary.legal_executed)
        ? "legal:checked"
        : "legal:not_run",
      kind: Boolean(summary.legal_executed) ? "ok" : "warn",
    },
    {
      label: `replay:${asString(summary.replay_readiness) ?? "not_available"}`,
      kind: badgeKindForReplay(asString(summary.replay_readiness)),
    },
    {
      label: Boolean(summary.human_review_needed)
        ? "human-review:required"
        : "human-review:not_required",
      kind: Boolean(summary.human_review_needed) ? "warn" : "ok",
    },
    {
      label: Boolean(summary.uncertainty_available)
        ? "uncertainty:available"
        : "uncertainty:not_available",
      kind: Boolean(summary.uncertainty_available) ? "ok" : "warn",
    },
  ];
}

function parseDecisionCardRecord(
  record: Record<string, unknown>,
): DecisionCardViewModel {
  const distributional = asRecord(record.distributional);
  const issuesRecord = asRecord(record.issues);
  const policy = derivePolicySummary(record);

  const issues: DecisionIssues = {
    blockerCount: Math.max(
      0,
      Math.round(asNumber(issuesRecord?.blocker_count) ?? 0),
    ),
    warningCount: Math.max(
      0,
      Math.round(asNumber(issuesRecord?.warning_count) ?? 0),
    ),
    infoCount: Math.max(0, Math.round(asNumber(issuesRecord?.info_count) ?? 0)),
    blockedPasses: asArray(issuesRecord?.blocked_passes)
      .map((item) => asString(item))
      .filter((item): item is string => Boolean(item)),
  };

  return {
    runId: asString(record.run_id) ?? "unknown",
    generatedAt: asString(record.generated_at),
    verdict: normalizeVerdict(asString(record.verdict)),
    confidence: normalizeConfidence(asString(record.confidence), issues),
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
        return {
          name: asString(metric.name) ?? "Metric",
          value: numeric,
          formatted:
            asString(metric.formatted) ??
            `${numeric >= 0 ? "+" : ""}${numeric.toFixed(2)}`,
          unit: asString(metric.unit) ?? "",
          ciLower: asNumber(metric.ci_lower),
          ciUpper: asNumber(metric.ci_upper),
          ciLevel: asNumber(metric.ci_level),
        };
      })
      .filter((item): item is DecisionMetric => item !== null),
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
  const issues = buildIssues(governance?.issues);
  const policy = derivePolicySummary(record);

  const simulationResults = asRecord(record.simulation_results);
  const uncertaintyBounds = asRecord(record.uncertainty_bounds);

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
    verdict: normalizeVerdict(asString(governance?.verdict)),
    confidence: normalizeConfidence(null, issues),
    policySummary: policy.summary,
    interventionCount: policy.interventionCount,
    keyMetrics: extractMetrics(simulationResults, uncertaintyBounds),
    diagnosticsBadges: deriveDiagnosticBadges(record),
    issues,
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
