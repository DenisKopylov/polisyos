/** Finite display fixture only; this is not a persisted Runtime/N5 witness. */
export function failedCandidateSimulationFixture(runId = "run-1") {
  const digest = (value: string) => "sha256:" + value.repeat(64);
  const ref = (kind: string, value: string) => ({
    artifact_id: digest(value),
    kind,
    media_type: "application/json",
    manifest_profile_sha256: digest("b"),
  });
  const execution = ref("runtime.quality.candidate_simulation_execution", "1");
  const result = ref("polisyos.runtime.joint_simulation_result", "2");
  return {
    schema_version:
      "policyos.runtime.run_failed_candidate_simulation_projection.v1",
    run_id: runId,
    artifact_status: "resolved",
    authority_purpose: "candidate_observation_only",
    publication_authority: false,
    source_ref: execution,
    source_content_hash: digest("3"),
    cycle_index: 0,
    cycle_completed: false,
    failed_stage: "value_projection",
    failure_source: "same_control_job",
    n5_observations: [
      {
        node_ref: "control-job://fixture-job",
        design_problem_ref: digest("4"),
        cycle_index: 0,
        candidate_id: "retained-tax-candidate",
        atom_ids: ["tax-atom"],
        selected_outcomes: ["government.balance"],
        executed_steps: [0, 1],
        replication_seeds: [17],
        status: "joint_simulated",
        simulation_ref: digest("5"),
        simulation_result_ref: result,
        n5_execution_ref: execution,
        result_body_status: "resolved",
        n4_source_ref: ref("runtime.quality.n4_candidate_scenario_source", "6"),
        context_job_ref: ref(
          "runtime.quality.cycle_substrate_context_job",
          "7",
        ),
        n5_input_ref: ref("runtime.quality.candidate_simulation_n5_input", "8"),
        profile_config_ref: "fixture-profile",
        profile_selection_ref: digest("9"),
        lineage_status: "resolved",
        currentness_status: "not_established",
        world_model_record_content_hash: digest("a"),
        authority_blockers: [
          "simulation_only_k_sim_not_world_evidence",
          "simulation_effect_basis_not_established",
        ],
        result_body: {
          schema_version:
            "policyos.runtime.run_candidate_simulation_n5_result_body.v1",
          artifact_ref: result,
          artifact_schema_name: "policyos.runtime.n5.joint_simulation_result",
          artifact_schema_version: "4.0.0",
          result_schema_version: "policyos.runtime.joint_simulation_horizon.v4",
          selected_manifest_profile_sha256: digest("b"),
          world_model_record_ref: "fixture-world-model",
          world_model_record_content_hash: digest("a"),
          atom_ids: ["tax-atom"],
          selected_outcomes: ["government.balance"],
          horizon: {
            start: 0,
            end: 1,
            step: 1,
            valid_time_role: "forecast",
            transaction_time_role: "recorded",
            scenario_branch_policy: "declared",
          },
          trajectories: [
            {
              run_level: "individual",
              atom_ids: ["tax-atom"],
              points: [
                {
                  step: 0,
                  outcomes: { "government.balance": 2.5 },
                  effects: { "government.balance": 0 },
                },
                {
                  step: 1,
                  outcomes: { "government.balance": 3.25 },
                  effects: { "government.balance": 0.75 },
                },
              ],
            },
          ],
          uncertainty_kind: "K_sim",
          authority_purpose: "candidate_scenario_n5_only",
          candidate_status: "candidate_unverified",
          currentness_status: "not_established",
          publication_authority: false,
        },
      },
    ],
  };
}
