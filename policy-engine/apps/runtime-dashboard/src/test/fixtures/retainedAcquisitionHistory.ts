import type { components } from "@/api/types";

/** Display-only wire fixture; it is not a Runtime verifier success witness. */
export function retainedAcquisitionHistoryFixture(): components["schemas"]["RunCandidateSimulationAcquisitionHistoryEntryV3"] {
  const ref = (kind: string, digit: string) => ({
    artifact_id: `sha256:${digit.repeat(64)}`,
    manifest_profile_sha256: `sha256:${"f".repeat(64)}`,
    kind,
    media_type: "application/json",
  });
  return {
    schema_version:
      "policyos.runtime.run_candidate_simulation_acquisition_history.v3",
    route_receipt_ref: ref(
      "runtime_quality.acquisition_route_loop_receipt",
      "1",
    ),
    route_id: `sha256:${"2".repeat(64)}`,
    action_generation: 3,
    terminal_outcome: "source_admitted_evaluation_retained",
    admitted_source_ref: ref("data.snapshot", "3"),
    growth_receipt_ref: ref(
      "runtime_quality.acquisition_world_growth_receipt",
      "4",
    ),
    evaluation_decision_ref: ref(
      "runtime_quality.acquisition_evaluation_decision",
      "5",
    ),
    current_continuation_ref: ref(
      "runtime_quality.acquisition_retained_continuation",
      "0",
    ),
    retained_evaluation: {
      candidate_id: "candidate-prior",
      candidate_content_hash: `sha256:${"6".repeat(64)}`,
      design_problem_ref: `sha256:${"7".repeat(64)}`,
      world_model_record_hash: `sha256:${"8".repeat(64)}`,
      evaluation_job_id: "job-original",
      evaluation_run_id: "run-original",
      generation_run_id: "generation-original",
      cycle_index: 1,
      n4_source_ref: ref("runtime.quality.n4_candidate_scenario_source", "9"),
      context_job_ref: ref("runtime.quality.cycle_substrate_context_job", "a"),
      n5_input_ref: ref("runtime.quality.candidate_simulation_n5_input", "b"),
      n5_execution_ref: ref(
        "runtime.quality.candidate_simulation_execution",
        "c",
      ),
      n5_result_ref: ref("polisyos.runtime.joint_simulation_result", "d"),
      basis_ref: ref("runtime_quality.acquisition_evaluation_basis", "e"),
    },
    source_admission_status: "admitted",
    evaluation_disposition: "retained_prior",
    currentness_status: "not_established",
    authority_purpose: "candidate_observation_only",
    publication_authority: false,
  };
}
