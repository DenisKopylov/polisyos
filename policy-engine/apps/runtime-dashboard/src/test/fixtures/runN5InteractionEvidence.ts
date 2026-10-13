import type { components } from "@/api/types";

export function runN5InteractionEvidenceFixture(): components["schemas"]["RunN5InteractionEvidence"] {
  const pairSummary = {
    status: "estimated" as const,
    replicate_count: 2,
    seeds: [41, 42],
    samples: [
      { seed: 41, value: 0 },
      { seed: 42, value: 0 },
    ],
    mean: 0,
    standard_error: 0,
  };
  const residualSummary = {
    status: "estimated" as const,
    replicate_count: 2,
    seeds: [41, 42],
    samples: [
      { seed: 41, value: 1 },
      { seed: 42, value: -1 },
    ],
    mean: 0,
    standard_error: 1,
  };
  const interactionPairs: [string, string][] = [
    ["atom-a", "atom-b"],
    ["atom-a", "atom-c"],
    ["atom-b", "atom-c"],
  ];
  return {
    schema_version: "policyos.runtime.joint_simulation_horizon.v4",
    numeric_interaction: "unsupported",
    numeric_interaction_basis: "finite_checked_model_point_estimate_only",
    interaction_sampling_status: "estimated",
    interaction_terms: interactionPairs.map((atom_ids) => ({
      atom_ids,
      outcome: "outcome-a",
      by_step: { "0": 0 },
      replication_sampling_by_step: { "0": pairSummary },
    })),
    higher_order_residuals: { "outcome-a": { "0": 0 } },
    higher_order_residual_sampling: {
      "outcome-a": { "0": residualSummary },
    },
    checked_interaction_orders: [1, 2, 3],
    authority_purpose: "candidate_checked_model_only",
    publication_authority: false,
  };
}
