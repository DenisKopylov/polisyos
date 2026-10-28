import { runN5InteractionEvidenceFixture } from "./runN5InteractionEvidence";

/** Synthetic parent-only candidate data shaped like the r8 fresh GET projection. */
export function c41JointParentObservation() {
  const atomIds = ["atom-a", "atom-b", "atom-c"];
  const parentAtomIds = [
    "atom_1111111111111111",
    "atom_2222222222222222",
    "atom_3333333333333333",
  ];
  const resultRef = {
    artifact_id: `sha256:${"7".repeat(64)}`,
    kind: "polisyos.runtime.joint_simulation_result",
    media_type: "application/json",
    manifest_profile_sha256: `sha256:${"8".repeat(64)}`,
  };
  const evidence = runN5InteractionEvidenceFixture();
  evidence.numeric_interaction = "non_additive";
  evidence.higher_order_residuals = { "outcome-a": { "0": 1 } };
  evidence.higher_order_residual_sampling = {
    "outcome-a": {
      "0": {
        status: "estimated",
        replicate_count: 2,
        seeds: [41, 42],
        samples: [
          { seed: 41, value: 1 },
          { seed: 42, value: 1 },
        ],
        mean: 1,
        standard_error: 0,
      },
    },
  };
  return {
    node_ref: `design-problem://${"d".repeat(64)}`,
    design_problem_ref: `sha256:${"d".repeat(64)}`,
    candidate_id: `joint-candidate:sha256:${"f".repeat(64)}`,
    atom_ids: atomIds,
    selected_outcomes: ["outcome-a"],
    executed_steps: [0],
    replication_seeds: [41, 42],
    status: "joint_simulated",
    simulation_ref: `sha256:${"9".repeat(64)}`,
    simulation_result_ref: resultRef,
    currentness_status: "not_established",
    world_model_record_content_hash: `sha256:${"e".repeat(64)}`,
    k_world_ref_before: `sha256:${"e".repeat(64)}`,
    k_world_ref_after: `sha256:${"e".repeat(64)}`,
    authority_blockers: ["n5_execution_request_provenance_not_established"],
    n5_interaction_evidence: evidence,
    n8_numeric_interaction: "non_additive",
    n8_numeric_interaction_basis: "finite_checked_model_point_estimate_only",
    n8_interaction_sampling_status: "estimated",
    n8_status: "value_conditional",
    n8_candidate_value_ref: resultRef.artifact_id,
    n8_candidate_decision_grade: "low",
    n8_authority_blockers: [
      "n5_execution_request_provenance_not_established",
      "n4_source_candidates_are_alternatives_not_authored_compound_design",
      "child_to_parent_refinement_rule_not_established",
      "parent_joint_coupling_evidence_not_established",
    ],
    n8_joint_scope_status: "not_established",
    n8_joint_scope_limitation_code:
      "parent_joint_coupling_evidence_not_established",
    n8_candidate_joint_selection_status: "resolved",
    n8_candidate_joint_selection_content_hash: `sha256:${"f".repeat(64)}`,
    n8_candidate_parent_atom_ids: parentAtomIds,
    n8_candidate_parent_atom_content_hashes: ["4", "5", "6"].map(
      (digit) => `sha256:${digit.repeat(64)}`,
    ),
    n8_candidate_parent_intervention_ids: atomIds,
    n8_candidate_parent_child_refs: ["child://a", "child://b", "child://c"],
    n8_candidate_member_basis: "hypothetical_all_unique_n4_source_members",
    n8_source_candidate_relationship: "alternatives",
    n8_policy_composition_status: "not_established",
    n8_policy_composition_limitation_code:
      "n4_source_candidates_are_alternatives_not_authored_compound_design",
    n8_child_to_parent_refinement_status: "not_established",
    n8_child_to_parent_refinement_limitation_code:
      "child_to_parent_refinement_rule_not_established",
  };
}
