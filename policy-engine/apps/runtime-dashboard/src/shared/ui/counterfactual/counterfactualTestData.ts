import type {
  CounterfactualMetric,
  QuantityValueOutput,
  ScenarioManifest,
} from "@polisyos/runtime-api-client";

const baseLineage = {
  id: "lineage:employment",
  status: "verified",
  freshness: "current",
  summary: { source: "test" },
} as const;

export const scenario = {
  id: "scn_fixture",
  baseline_run_id: "run_actual",
  status: "computed",
  policy_question: "What if policy cost is capped?",
  author: "operator",
  lifecycle_status: "generated",
  manifest_hash: "sha256:scn_fixture",
  model_family: "runtime-counterfactual-linearized",
  model_lineage: {
    id: "scenario:scn_fixture:model",
    status: "pending",
    freshness: "current",
    summary: { source: "scenario" },
  },
  interventions: [],
  revision: 1,
  assumptions: [
    {
      id: "asm_1",
      label: "No external shock",
      status: "operator_assumption",
      lineage: {
        id: "scenario:scn_fixture:assumption",
        status: "pending",
        freshness: "current",
        summary: { source: "operator" },
      },
    },
  ],
} satisfies ScenarioManifest;

export const actual: QuantityValueOutput = {
  point: 0.2,
  unit: { code: "1", system: "ucum", display: "ratio" },
  metric_id: "employment_rate_delta",
  label: "Employment",
  lineage: baseLineage,
  uncertainty: {
    ci_95: [0.16, 0.24],
    method: "bootstrap",
    identifiability: "estimated",
    disputed: false,
  },
  time: { valid_at: "2026-04-15T12:00:00Z" },
  quantity_class: "decision",
};

export const scenarioQuantity: QuantityValueOutput = {
  ...actual,
  point: 0.24,
  lineage: {
    id: "scenario:scn_fixture:projection",
    status: "pending",
    freshness: "current",
    summary: { source: "scenario", assumptions: "asm_1" },
  },
  uncertainty: {
    ci_95: [0.19, 0.29],
    method: "simulation",
    identifiability: "assumed",
    disputed: false,
  },
  time: { ...actual.time, scenario_id: "scn_fixture" },
};

export const counterfactualMetric: CounterfactualMetric = {
  metric_id: "employment_rate_delta",
  label: "Employment",
  actual,
  counterfactual: scenarioQuantity,
  delta: {
    ...scenarioQuantity,
    point: 0.04,
    metric_id: "employment_rate_delta.counterfactual_delta",
    label: "Employment delta",
    uncertainty: {
      ci_95: [-0.01, 0.09],
      method: "simulation",
      identifiability: "assumed",
      disputed: false,
    },
  },
  scenario_ref: {
    id: "scn_fixture",
    status: "computed",
    baseline_run_id: "run_actual",
    lineage: scenarioQuantity.lineage,
    assumption_ids: ["asm_1"],
  },
  assumption_ids: ["asm_1"],
};
