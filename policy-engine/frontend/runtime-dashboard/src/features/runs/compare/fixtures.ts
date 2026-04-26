import type { CompareRunsPayload } from "@/api/validators";

export const policyDiffFixture: CompareRunsPayload = {
  meta: {
    request_id: "req-policy-diff",
    generated_at: "2026-04-24T12:00:00Z",
    source_kinds: ["core_run"],
  },
  status: "computed",
  temporal_scope: {
    valid_at: "2026-04-15T12:00:00Z",
    tx_at: "2026-04-16T09:20:00Z",
    branch: null,
    snapshot_id: null,
    scenario_id: null,
  },
  comparison_frame: {
    run_a: "run-a",
    run_b: "run-b",
    metric_set: ["employment_rate_delta", "policy_cost"],
    population: "national_workforce",
    unit_policy: "canonical",
    temporal_scope: {
      valid_at: "2026-04-15T12:00:00Z",
      tx_at: "2026-04-16T09:20:00Z",
      branch: null,
      snapshot_id: null,
      scenario_id: null,
    },
    scenario_scope: {},
    assumption_set: ["shared labor-market baseline"],
  },
  comparability: {
    status: "compatible",
    warnings: [],
    blocked_reasons: [],
  },
  deltas: [
    {
      metric_id: "employment_rate_delta",
      label: "Employment rate",
      a: quantity("employment_rate_delta", "Employment rate", 0.18, "run-a"),
      b: quantity("employment_rate_delta", "Employment rate", 0.23, "run-b"),
      delta_absolute: quantity(
        "employment_rate_delta.delta_absolute",
        "Employment rate absolute delta",
        0.05,
        "diff",
      ),
      delta_relative: quantity(
        "employment_rate_delta.delta_relative",
        "Employment rate relative delta",
        0.277,
        "diff",
      ),
      delta_distribution: {
        quantiles: { p50: 0.04 },
        mean_shift: 0.05,
        median_shift: 0.04,
        ci_overlap: false,
      },
      significance: "improved",
      dominance: "b",
      decision_salience: 0.82,
      lineage_delta: {
        source_changed: true,
        model_changed: false,
        hash_changed: true,
        freshness_changed: false,
        verification_changed: null,
        notes: ["source_changed"],
      },
    },
    {
      metric_id: "policy_cost",
      label: "Policy cost",
      a: quantity("policy_cost", "Policy cost", 100, "run-a", "USD"),
      b: quantity("policy_cost", "Policy cost", 92, "run-b", "USD"),
      delta_absolute: quantity(
        "policy_cost.delta_absolute",
        "Policy cost absolute delta",
        -8,
        "diff",
        "USD",
      ),
      delta_relative: quantity(
        "policy_cost.delta_relative",
        "Policy cost relative delta",
        -0.08,
        "diff",
      ),
      delta_distribution: {
        quantiles: {},
        mean_shift: -8,
        median_shift: null,
        ci_overlap: null,
      },
      significance: "improved",
      dominance: "b",
      decision_salience: 0.48,
      lineage_delta: {
        source_changed: false,
        model_changed: false,
        hash_changed: false,
        freshness_changed: false,
        verification_changed: null,
        notes: [],
      },
    },
  ],
};

function quantity(
  metricId: string,
  label: string,
  point: number,
  runId: string,
  unit = "ratio",
) {
  return {
    point,
    unit: {
      code: unit === "USD" ? "[USD]" : "1",
      system: "ucum",
      display: unit,
    },
    metric_id: metricId,
    lineage: {
      id: `artifact:${runId}:${metricId}`,
      hash: `sha256:${runId}-${metricId}`,
      status: "verified" as const,
      freshness: "current" as const,
      summary: { source: runId, method: "fixture" },
      compact_summary: [
        { kind: "source" as const, label: `${runId} packet` },
        { kind: "result" as const, label },
      ],
    },
    uncertainty: {
      ci_95: [point - 0.02, point + 0.02] as [number, number],
      method: "bootstrap",
      identifiability: "estimated" as const,
      disputed: false,
    },
    time: {
      valid_at: "2026-04-15T12:00:00Z",
      tx_at: "2026-04-16T09:20:00Z",
    },
    quantity_class: "decision" as const,
    label,
  };
}
