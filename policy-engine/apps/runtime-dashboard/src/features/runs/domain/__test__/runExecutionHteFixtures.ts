import {
  hteRef,
  intervalSummary,
  pointSummary,
  type HTEWire,
} from "@/features/artifacts/domain/__test__/decisionPacketHteFixtures";

export const RUN_HTE_LIMITATIONS = [
  "candidate_input_not_external_truth",
  "scientific_validity_not_established",
];

export function runHteSelectedProjection(summaryOverride?: HTEWire) {
  const summary = summaryOverride ?? pointSummary();
  if (summaryOverride === undefined) {
    summary.source_data_ref = hteRef("5", "ir.observation_method_input");
    const relation = summary.target_relation as Record<string, unknown>;
    relation.estimand_status = "not_established";
    relation.overall_disposition = "not_established";
  }
  const resource = summary.resource_evidence as Record<string, unknown>;
  const context: Record<string, unknown> = {
    request_estimand_status: summary.request_estimand_status,
    request_estimand: summary.request_estimand,
    request_target_scope_status: summary.request_target_scope_status,
    request_target_scope: summary.request_target_scope,
    outcome_variable_status: summary.outcome_variable_status,
    outcome_variable_id: summary.outcome_variable_id,
    treatment_variable_status: summary.treatment_variable_status,
    treatment_variable_id: summary.treatment_variable_id,
    contrast_status: summary.request_contrast_status,
    control_value: summary.control_value,
    treated_value: summary.treated_value,
    request_alpha_status: summary.request_alpha_status,
    requested_alpha: summary.requested_alpha,
    requested_guarantee_status: summary.requested_guarantee_status,
    requested_guarantee: summary.requested_guarantee,
  };
  if (summary.search_uncertainty_task_binding_ref != null) {
    context.search_uncertainty_task_binding_ref =
      summary.search_uncertainty_task_binding_ref;
  }
  if (summary.materialization_binding_ref != null) {
    context.materialization_binding_ref = summary.materialization_binding_ref;
  }
  const methodBuildDigest = "e".repeat(64);
  const selection = {
    selection_kind: "direct_method",
    job_id: "job-hte-fixture",
    run_id: "run-hte-fixture",
    attempt: 1,
    requested_source_ref: summary.source_data_ref,
    observational_run_intent_ref: hteRef(
      "8",
      "runtime.observational_run_intent",
    ),
    content_admitted_intent_ref: hteRef(
      "9",
      "runtime.content_admitted_observational_run_intent",
    ),
    resource_policy_ref: resource.owner_policy_ref,
    submitted_input_ref: summary.source_data_ref,
    effective_input_ref: summary.source_data_ref,
    method_result_ref: summary.method_result_ref,
    method_evidence_ref: summary.method_evidence_ref,
    owned_attempt_anchor_ref: summary.owned_attempt_anchor_ref,
    hte_outcome_ref: summary.hte_outcome_ref,
    point_result_ref: summary.point_result_ref,
    hte_result_ref: summary.hte_result_ref,
    inference_basis_ref: summary.inference_basis_ref,
    refusal_diagnostic_ref: summary.refusal_diagnostic_ref,
    invocation_basis_ref: null,
    hte: summary,
    contract_target_id: "foundry.causal.hte_observational_data.v1",
    contract_target:
      "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData",
    selection_digest: "f".repeat(64),
    source_access_revalidation_status: null,
    method_fqn: summary.method_fqn,
    method_version: "2.0.0",
    method_abi_digest: summary.method_abi_digest,
    method_build_digest: methodBuildDigest,
    method_build_digest_scope: "class_source_only",
    resource_policy_digest: resource.owner_policy_digest,
    source_protocol: "method_input_envelope_v1",
    normalization: "canonical_passthrough",
    limitations: RUN_HTE_LIMITATIONS,
    method_dispatch_binding_status: "recomputed",
    owned_hte_request_context: context,
    candidate_outcome: null,
    posterior_summary_refs: [],
  };
  const request = {
    requested_source_ref: summary.source_data_ref,
    requested_intent_ref: selection.observational_run_intent_ref,
    resource_policy_ref: resource.owner_policy_ref,
    source_protocol: selection.source_protocol,
    method_fqn: selection.method_fqn,
    method_version: selection.method_version,
    owned_hte_request_context: context,
    method_abi_digest: summary.method_abi_digest,
    method_build_digest: methodBuildDigest,
    method_build_digest_scope: "class_source_only",
    resource_policy_digest: resource.owner_policy_digest,
    resolved_params_sha256: summary.resolved_params_sha256,
    seed: 0,
    seed_policy_revision: "server_seed_zero_v1",
    required_estimator_n_jobs: 1,
    max_manifest_bytes: 1000000,
    max_bytes: 1000000,
    max_depth: 16,
    max_elements: 10000,
    requested_at: "2026-10-21T10:00:00Z",
  };
  return {
    status: "selected",
    candidate_only: true,
    limitations: RUN_HTE_LIMITATIONS,
    request,
    time_roles: {
      admitted_at: "2026-10-21T10:00:00Z",
      execution_started_at: "2026-10-21T10:01:00Z",
      execution_finished_at: "2026-10-21T10:02:00Z",
      source_observation_epoch: null,
      owner_verified_at: "2026-10-21T10:02:00Z",
      reader_at: "2026-10-21T10:03:00Z",
    },
    selection,
  };
}

export function r5RunHteSelectedProjection() {
  const projection = runHteSelectedProjection();
  const summary = projection.selection.hte;
  const evidence = summary.resource_evidence as Record<string, unknown>;
  evidence.owner_policy_schema_version =
    "polisyos.runtime.observational_input_resource_policy.v5";
  evidence.owner_policy_revision = "r5";
  evidence.owner_policy_execution_scope =
    "producer_scoped_joblib_parallelism_one";
  evidence.joblib_observation_status = "recomputed";
  evidence.joblib_profile_id = "joblib.parallel_config.current_thread@1.0";
  evidence.joblib_profile_revision = "1.0";
  evidence.joblib_implementation = "joblib.parallel_config";
  evidence.joblib_implementation_version = "1.5.2";
  evidence.joblib_scope = "current_thread_joblib";
  evidence.joblib_max_jobs = 1;
  evidence.joblib_started = true;
  evidence.joblib_finished = true;
  evidence.joblib_exit_status = "returned";
  evidence.joblib_entry_effective_jobs = 1;
  evidence.joblib_entry_backend_fqn = "joblib._parallel_backends.LokyBackend";
  evidence.joblib_entry_config_sha256 = "c".repeat(64);
  evidence.joblib_entry_implementation_version = "1.5.2";
  evidence.joblib_exit_effective_jobs = 1;
  evidence.joblib_exit_backend_fqn = "joblib._parallel_backends.LokyBackend";
  evidence.joblib_exit_config_sha256 = "c".repeat(64);
  evidence.joblib_exit_implementation_version = "1.5.2";
  summary.materialization_binding_ref = hteRef(
    "7",
    "foundry.hte.physical_source_materialization_binding",
  );
  const context = projection.selection.owned_hte_request_context as Record<
    string,
    unknown
  >;
  context.materialization_binding_ref = summary.materialization_binding_ref;
  return projection;
}

export function runHteIntervalSelectedProjection() {
  return runHteSelectedProjection(intervalSummary());
}
