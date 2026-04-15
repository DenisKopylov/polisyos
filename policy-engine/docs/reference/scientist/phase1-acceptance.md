# Scientist Phase 1 Acceptance

Related reference: [Scientist Reliability Scorecard](reliability-scorecard.md).

> Acceptance contract for the Phase 1 reliability baseline. The goal is to move
> Scientist from “many improvements landed” to “production-like runtime posture
> is evidenced and gated.”

## Scope

- `WS-1A` error semantics and degraded-mode policy
- `WS-1B` atomic state mutation, merge semantics, deterministic execution
- `WS-1C` observability, metrics exporter, operational hygiene
- `WS-1D` test and benchmark program

## Exit Criteria

- Broad exception swallowing is removed from budget-critical and governance-critical paths.
- Every allowed degraded path emits a structured degraded result plus warning signal.
- Partial mutation failures do not leave half-written state.
- Merge conflicts become visible artifacts or terminate execution by policy.
- Key metrics export at runtime, traces correlate across runners, and DLQ replay is documented and testable.
- Reliability scorecard reaches `passes_all=true` with linked scenario, benchmark, and operational evidence.

## Required Evidence

| Evidence | Current posture |
|----------|-----------------|
| Closure list for broad exception handlers | Partial; governance pass failure, tool-loop budget/memory degradation, malformed tool parsing, corrupted local checkpoint metadata, invalid model-catalog parsing, fallback-router failover, provider-verification artifact/check parsing, retry dead-letter/runtime-worker handling, lock heartbeat/liveness/stale probes, async-executor runtime fallback, registry bootstrap provider creation, telemetry span helpers, local worker-pool execution wrappers, `build_data_snapshot` PII-summary loading, planning/causal helper paths in `run_preflight`, `run_evaluator`, `build_execution_plan`, `resolve_parameters`, `run_causal_queries`, `compile_cross_graph_evidence`, `run_discovery_blueprint_runtime`, `run_abm_consistency`, `run_causal_ensemble`, `reconcile_causal_graph`, `resolve_transport`, `run_causal_contract_execution`, `run_causal_readiness`, `bind_foundry_inputs`, `enrich_knowledge`, and `run_hierarchical_policy_search`, top-level decision-packet artifact-loading degradation, deeper helper-level normative/sensitivity degradation, decision-validity basis loading, derived uncertainty-bound loading, simulate helper paths in `propagate_uncertainty`, `run_distributional_analysis`, `run_causal_evaluation`, and `run_simulation`, sync executor cache/provenance degradation warning paths, sync/async bind failures, fan-out bind failures, shared strategic runtime invalid-input/persistence degradation, optional policy-output artifact loading degradation, governance pass registry helper wrapping, integrated normative-arbitration artifact-ref normalization for the full `run_governance` path, `run_governance` helper degraded envelopes for policy/metrics/transport/PII/normative loads, strict human-review graph invalidation, normative-arbitration Trinity/artifact helper degradation, `legal_check` compliance-grade degradation, `data_plane_gate` quality-report degradation, distributed runtime helper degradation for invalid registry refs plus trace-context restore/read/inject failures, Ray/fallback probe and execution degradation, checkpoint-hook runtime metadata validation, remaining executor/fan-out/tracing/governance-pipeline broad-handler slices, and the cross-boundary CAS identity false-negative that caused spurious decision-packet parse fallout now have typed/structured evidence |
| Mutation-plan and merge-conflict regression tests | Partial; sync executor declared-write branch isolation, fan-out invalid-path hard-fail, fan-out fail-fast no-partial-commit, fan-out staged state surviving summary-artifact persistence degradation, sub-workflow staged output application, cache-hit declared-write merge, async checkpoint cache seeding, parallel-tier merged-state resume, distributed-configured resume local fallback, distributed pruned-workflow resume, checkpoint head/history resume reconciliation, divergent latest-history conflict detection, head/artifact metadata mismatch detection, completed-node chain preservation across resumed checkpoints, post-commit checkpoint GC bookkeeping, Temporal wire-payload normalization, typed unhealthy Temporal probe behavior, real Temporal remote merge/checkpoint execution, and Ray remote merge/checkpoint execution are covered |
| Trace correlation and metrics exporter tests | Present via `tests/scientist/test_reliability_operational_evidence.py` and `tests/scientist/engine/test_metrics_slo.py` |
| Long-running bounded-retention tests | Present via `tests/scientist/test_reliability_operational_evidence.py::test_bounded_retention_operational_signal` |
| E2E reliability scenario suite | Present via `tests/scientist/integration/test_workflow_reliability_scenarios.py` |
| Benchmark JSON artifacts tied to CI/release review | Present via `.github/workflows/perf.yml` (`scientist-gate2-evidence`) |

## Current Blocking Themes

- Critical swallowing sites still remain in other decision/pipeline helpers; governance pass execution, tool-loop budget/memory degradation, malformed tool parsing, corrupted local checkpoint metadata, invalid model-catalog parsing, fallback-router failover, provider-verification artifact/check parsing, retry dead-letter/runtime-worker handling, lock heartbeat/liveness/stale probes, async-executor runtime fallback, registry bootstrap provider creation, telemetry span helpers, local worker-pool execution wrappers, `build_data_snapshot` PII-summary loading, the broader planning/causal helper slice (`run_preflight`, `run_evaluator`, `build_execution_plan`, `resolve_parameters`, `run_causal_queries`, `compile_cross_graph_evidence`, `run_discovery_blueprint_runtime`, `run_abm_consistency`, `run_causal_ensemble`, `reconcile_causal_graph`, `resolve_transport`, `run_causal_contract_execution`, `run_causal_readiness`, `bind_foundry_inputs`, `enrich_knowledge`, and `run_hierarchical_policy_search`) now emits typed failures/warnings instead of broad swallowing, sync executor cache/provenance degradation, sync/async bind failure handling, fan-out bind failure handling, shared strategic runtime invalid-input and persistence degradation, optional policy-output artifact loading degradation, governance pass registry helper wrapping, integrated normative-arbitration runtime artifact loading, `run_governance` helper degraded envelopes for policy/metrics/transport/PII/normative loads, `legal_check` compliance-grade degradation, `data_plane_gate` quality-report degradation, simulate helper degradation in `propagate_uncertainty`, `run_distributional_analysis`, `run_causal_evaluation`, and `run_simulation`, distributed runtime helper degradation for invalid registry refs, trace-context restore/read/inject, Ray/fallback probe and execution degradation, remaining executor/fan-out/tracing/governance-pipeline slices, and both top-level and deeper helper-level decision-packet artifact-loading failures now emit typed/structured failure surfaces, including decision-validity basis and uncertainty-bound helper paths.
- Staged mutation and merge semantics are not yet universal across fan-out and resume paths; sync executor node state now uses declared write-path branch isolation, cached outcomes now merge back by declared write paths, fan-out invalid write targets fail explicitly, fail-fast fan-out no longer commits partial merged state, fan-out summary persistence can now degrade after staged merge without rolling back merged state, sub-workflow output mappings now apply only after child success with overlap detection, async checkpointing now seeds cache refs for resumed single-node and merged parallel tiers, resume now runs through the runner contract with build-failure fallback only for distributed backend configs, distributed runners can now continue from a pruned remaining-node workflow, checkpoint resume now enforces repair-or-fail reconciliation for local head/history drift plus divergent latest-history and head/artifact metadata conflicts, checkpoint GC no longer rolls back already-committed hook state, serializable checkpoint-hook metadata now lets remote workers reconstruct tier merge/checkpoint state for Temporal-style and Ray-style distributed execution, distributed-runner serialization now normalizes list-encoded wire payloads, Temporal and Ray health checks now surface typed unhealthy probe results, real local/monkeypatched distributed runs now prove the remote merge/checkpoint path end-to-end for both backends, and `set_state`, `emit_artifact`, `budget_ledger`, `propagate_uncertainty`, `run_distributional_analysis`, `run_causal_contract_execution`, `run_causal_readiness`, `bind_foundry_inputs`, `enrich_knowledge`, `run_hierarchical_policy_search`, `run_simulation`, `legal_check`, `data_plane_gate`, `run_governance`, `run_normative_arbitration`, `compile_foundry`, `link_trinity`, `formalize_verified_policy`, `run_preflight`, `run_evaluator`, `build_execution_plan`, `plan_policy_request`, `assemble_legal_candidate_pack`, `expand_legal_source_pack`, `run_source_verification`, `run_source_gap_review`, and `draft_policy_options` now remove the targeted `deep=True` hot-path clones in favor of branch-local or narrow-map copy-on-write updates.
- Operational acceptance evidence exists in pieces, but not yet as a complete Phase 1 signoff packet.

## Latest Evidence

| Workstream | Regression |
|------------|------------|
| `WS-1A` | `tests/scientist/governance/test_validation_pipeline.py::test_failing_pass_returns_structured_error_envelope` |
| `WS-1A` | `tests/scientist/agent/tools/test_tool_loop.py::test_budget_probe_failure_is_reported_as_degraded_event` |
| `WS-1A` | `tests/scientist/agent/tools/test_tool_loop.py::test_persistent_memory_recall_failure_is_reported_as_degraded_event` |
| `WS-1A` | `tests/scientist/agent/tools/test_tool_loop.py::test_malformed_arguments_json` |
| `WS-1A` | `tests/scientist/test_checkpoint.py::test_checkpoint_head_invalid_json_raises_typed_error` |
| `WS-1A` | `tests/scientist/test_checkpoint.py::test_checkpoint_history_invalid_json_raises_typed_error` |
| `WS-1A` | `tests/scientist/llm/test_gateway_client_retry.py::test_list_model_ids_invalid_json_degrades_to_empty_list` |
| `WS-1A` | `tests/scientist/llm/test_gateway_client_retry.py::test_list_model_ids_invalid_shape_degrades_to_empty_list` |
| `WS-1A` | `tests/scientist/test_decision_packet_node_v3.py::test_build_decision_packet_records_degraded_paths_for_invalid_metrics_and_governance` |
| `WS-1A` | `tests/scientist/test_decision_packet_node_v3.py::test_build_decision_packet_records_degraded_paths_for_invalid_decision_basis_quality_report` |
| `WS-1A` | `tests/scientist/test_decision_packet_node_v3.py::test_build_decision_packet_records_degraded_paths_for_invalid_normative_arbitration` |
| `WS-1A` | `tests/scientist/test_decision_packet_node_v3.py::test_build_decision_packet_records_degraded_paths_for_invalid_sensitivity_artifact` |
| `WS-1A` | `tests/scientist/test_decision_packet_node_v3.py::test_build_decision_packet_records_degraded_paths_for_invalid_uncertainty_output_envelope` |
| `WS-1A` | `tests/scientist/test_policy_verified_nodes.py::test_build_decision_packet_records_degraded_paths_for_invalid_policy_verification_artifacts` |
| `WS-1A` | `tests/scientist/nodes/test_build_policy_output_bundle.py::test_decision_packet_records_degraded_path_for_invalid_policy_bundle` |
| `WS-1A` | `tests/scientist/test_engine_executor_v0.py::test_executor_logs_cache_write_bypass_as_node_event` |
| `WS-1A` | `tests/scientist/test_engine_executor_v0.py::test_executor_logs_provenance_recording_degraded_as_node_event` |
| `WS-1A` | `tests/scientist/test_engine_executor_v0.py::test_executor_reports_bind_failure_as_typed_node_error` |
| `WS-1A` | `tests/scientist/engine/test_async_executor_hardening.py::test_bind_failure_becomes_typed_node_error` |
| `WS-1A` | `tests/scientist/engine/test_fan_out.py::test_bind_failure_stops_without_executing_item_when_fail_fast` |
| `WS-1A` | `tests/scientist/engine/test_fan_out_async.py::test_async_bind_failure_stops_without_executing_item_when_fail_fast` |
| `WS-1A` | `tests/scientist/search/test_policy_blueprint_runtime_guards.py::test_runtime_strategic_helper_invalid_input_records_degraded_path` |
| `WS-1A` | `tests/scientist/search/test_policy_blueprint_runtime_guards.py::test_runtime_strategic_helper_persistence_failure_records_degraded_path` |
| `WS-1A` | `tests/scientist/nodes/test_build_policy_output_bundle.py::test_build_policy_output_bundle_degrades_invalid_distributional_report` |
| `WS-1A` | `tests/scientist/nodes/test_build_policy_output_bundle.py::test_build_policy_output_bundle_degrades_invalid_uncertainty_envelope` |
| `WS-1A` | `tests/scientist/governance/test_pass_registry.py::test_load_governance_passes_wraps_entry_point_load_error` |
| `WS-1A` | `tests/scientist/test_run_governance_normative.py::test_run_governance_rejects_on_explicit_normative_right_violation` |
| `WS-1A` | `tests/scientist/test_run_governance_normative.py::test_run_governance_marks_needs_revision_when_policy_prefers_baseline` |
| `WS-1A` | `tests/scientist/test_run_governance_normative.py::test_run_governance_keeps_warning_only_for_partial_model_when_proposal_selected` |
| `WS-1A support` | `tests/scientist/governance/test_normative_arbitration_pass.py::test_normative_arbitration_invalid_payload_emits_warning` |
| `WS-1A` | `tests/scientist/governance/test_human_review_pass.py::test_human_review_invalid_graph_payload_emits_warning` |
| `WS-1A` | `tests/scientist/test_normative_arbitration_node.py::test_normative_arbitration_invalid_trinity_bundle_skips_with_warning` |
| `WS-1A` | `tests/scientist/test_legal_check_node.py::test_legal_check_records_degraded_event_when_report_grade_load_fails` |
| `WS-1A` | `tests/scientist/test_data_plane_gate_node.py::test_data_plane_gate_records_degraded_event_for_invalid_quality_report` |
| `WS-1A` | `tests/scientist/engine/runner/test_activity_worker.py::test_build_worker_context_records_degraded_path_for_invalid_registry_bundle` |
| `WS-1A` | `tests/scientist/engine/runner/test_activity_worker.py::test_restore_parent_trace_context_records_degraded_path_on_runtime_error` |
| `WS-1A` | `tests/scientist/engine/runner/test_serialization.py::test_current_trace_ids_records_degraded_path_on_runtime_error` |
| `WS-1A` | `tests/scientist/engine/runner/test_temporal_runner.py::test_temporal_inject_trace_carrier_records_degraded_path_on_runtime_error` |
| `WS-1A` | `tests/scientist/engine/runner/test_temporal_runner.py::test_temporal_health_check_returns_unhealthy_on_probe_error` |
| `WS-1A` | `tests/scientist/engine/runner/test_ray_runner.py::test_ray_runner_inject_trace_carrier_records_degraded_path_on_runtime_error` |
| `WS-1A` | `tests/scientist/engine/runner/test_ray_runner.py::test_ray_runner_health_check_returns_unhealthy_on_probe_error` |
| `WS-1A` | `tests/scientist/engine/runner/test_fallback_runner.py::test_primary_execution_error_emits_degraded_path_and_uses_fallback` |
| `WS-1A` | `tests/scientist/test_checkpoint.py::test_restore_checkpoint_hook_from_runtime_metadata_rejects_invalid_store_config` |
| `WS-1A` | `tests/scientist/test_engine_executor_v0.py::test_executor_reports_lookup_runtime_failure_as_typed_node_error` |
| `WS-1A` | `tests/scientist/engine/test_fan_out.py::test_summary_persist_failure_emits_degraded_event` |
| `WS-1A` | `tests/scientist/engine/test_fan_out_async.py::test_async_summary_persist_failure_emits_degraded_event` |
| `WS-1A` | `tests/scientist/nodes/builtins/test_tracing.py::test_runtime_trace_access_failure_returns_none_ids` |
| `WS-1A` | `tests/scientist/engine/test_retry.py::test_timeout_worker_does_not_swallow_system_exit` |
| `WS-1A` | `tests/scientist/engine/locks/test_redis_lock.py::test_is_alive_returns_false_on_runtime_probe_error` |
| `WS-1A` | `tests/scientist/engine/locks/test_dynamodb_lock.py::test_is_alive_runtime_probe_error_returns_false` |
| `WS-1A` | `tests/scientist/llm/test_fallback_router.py::test_failover_emits_degraded_path` |
| `WS-1A` | `tests/scientist/llm/test_fallback_router.py::test_keyboard_interrupt_is_not_swallowed` |
| `WS-1A` | `tests/scientist/llm/test_provider_verification.py::test_load_provider_verification_invalid_json_returns_none` |
| `WS-1A` | `tests/scientist/llm/test_provider_verification.py::test_run_named_check_does_not_swallow_assertion_errors` |
| `WS-1A` | `tests/scientist/engine/test_async_executor_hardening.py::test_runtime_lookup_failure_becomes_typed_node_error` |
| `WS-1A` | `tests/scientist/test_node_registry_components_bootstrap.py::test_discover_nodes_records_typed_runtime_provider_error` |
| `WS-1A` | `tests/scientist/test_node_registry_components_bootstrap.py::test_discover_nodes_does_not_swallow_assertion_errors` |
| `WS-1A` | `tests/scientist/engine/test_telemetry.py::test_start_node_span_runtime_error_degrades` |
| `WS-1A` | `tests/scientist/engine/test_telemetry.py::test_set_span_attribute_runtime_error_degrades` |
| `WS-1A` | `tests/scientist/engine/test_telemetry.py::test_add_span_events_runtime_error_degrades` |
| `WS-1A` | `tests/scientist/engine/runner/test_worker_pool.py::test_worker_runtime_error_surfaces_on_future` |
| `WS-1A` | `tests/scientist/nodes/builtins/data/test_build_data_snapshot.py::test_snapshot_pii_summary_load_failure_degrades` |
| `WS-1A` | `tests/scientist/nodes/builtins/planning/test_run_preflight.py::test_preflight_invalid_input_load_returns_typed_fail` |
| `WS-1A` | `tests/scientist/nodes/builtins/planning/test_run_evaluator.py::test_evaluator_invalid_governance_report_emits_warning` |
| `WS-1A` | `tests/scientist/nodes/builtins/planning/test_run_evaluator.py::test_evaluator_transition_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/planning/test_build_execution_plan.py::test_plan_invalid_data_needs_emit_warning` |
| `WS-1A` | `tests/scientist/nodes/builtins/causal/test_resolve_parameters.py::test_target_context_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/causal/test_run_causal_queries.py::test_causal_query_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/planning/test_compile_cross_graph_evidence.py::test_compilation_target_context_assertion_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/planning/test_run_discovery_blueprint_runtime.py::test_measure_seed_reproducibility_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/causal/test_run_abm_consistency.py::test_abm_mapping_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/causal/test_run_causal_ensemble.py::test_causal_ensemble_member_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/causal/test_reconcile_causal_graph.py::test_reconcile_fragment_load_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/causal/test_reconcile_causal_graph.py::test_reconcile_literature_prior_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/causal/test_resolve_transport.py::test_run_transportability_report_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/causal/test_resolve_transport.py::test_build_skg_query_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py::test_collect_input_envelopes_snapshot_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py::test_load_config_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/simulate/test_run_distributional_analysis.py::test_resolve_baseline_snapshot_ref_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/causal/test_run_causal_contract_execution.py::test_run_causal_contract_execution_task_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/causal/test_run_causal_readiness.py::test_run_causal_readiness_graph_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/test_bind_foundry_inputs_node.py::test_bind_foundry_inputs_build_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/test_enrich_knowledge_node_freshness.py::test_enrich_node_scholar_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py::test_run_hierarchical_policy_search_adapter_assertion_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py::test_assertion_in_observational_data_load_is_not_swallowed` |
| `WS-1A` | `tests/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py::test_fail_when_method_output_report_is_invalid` |
| `WS-1A` | `tests/scientist/nodes/builtins/simulate/test_run_simulation.py::test_run_simulation_result_assertion_is_not_swallowed` |
| `WS-1A support` | `tests/core/phase0/test_artifact_store.py::test_filesystem_cas_accepts_ir_artifact_id_roundtrip` |
| `WS-1A support` | `pytest tests/scientist/test_decision_packet_node_v3.py tests/scientist/test_policy_verified_nodes.py tests/scientist/nodes/test_build_policy_output_bundle.py -q` |
| `WS-1B` | `tests/scientist/test_engine_executor_v0.py::test_executor_branch_state_isolates_declared_nested_writes` |
| `WS-1B` | `tests/scientist/engine/test_fan_out.py::test_invalid_result_path_fails_instead_of_silent_params_drift` |
| `WS-1B` | `tests/scientist/engine/test_fan_out.py::test_stop_on_failure_does_not_commit_partial_merged_state` |
| `WS-1B` | `tests/scientist/engine/test_fan_out.py::test_summary_persist_failure_emits_degraded_event` |
| `WS-1B` | `tests/scientist/engine/test_fan_out_async.py::test_async_stop_on_failure_does_not_commit_partial_merged_state` |
| `WS-1B` | `tests/scientist/engine/test_fan_out_async.py::test_async_summary_persist_failure_emits_degraded_event` |
| `WS-1B` | `tests/scientist/engine/test_sub_workflow.py::test_child_failure_does_not_apply_output_mappings` |
| `WS-1B` | `tests/scientist/engine/test_sub_workflow.py::test_overlapping_output_mappings_fail_atomically` |
| `WS-1B` | `tests/scientist/integration/test_checkpoint_resume.py::test_async_executor_resume_uses_checkpoint_cache_refs_when_trace_is_truncated` |
| `WS-1B` | `tests/scientist/integration/test_checkpoint_resume.py::test_async_executor_parallel_tier_checkpoints_merged_state_for_resume` |
| `WS-1B` | `tests/scientist/integration/test_checkpoint_resume.py::test_resume_falls_back_to_local_runner_when_distributed_backend_is_configured` |
| `WS-1B` | `tests/scientist/integration/test_checkpoint_resume.py::test_resume_uses_configured_distributed_runner_with_pruned_workflow` |
| `WS-1B` | `tests/scientist/test_checkpoint.py::test_resolve_latest_checkpoint_repairs_history_when_head_is_newer` |
| `WS-1B` | `tests/scientist/test_checkpoint.py::test_resolve_latest_checkpoint_rejects_head_history_conflict` |
| `WS-1B` | `tests/scientist/test_checkpoint.py::test_resolve_latest_checkpoint_rejects_divergent_latest_history_entries` |
| `WS-1B` | `tests/scientist/test_checkpoint.py::test_resolve_latest_checkpoint_rejects_head_artifact_metadata_mismatch` |
| `WS-1B` | `tests/scientist/test_checkpoint.py::test_checkpoint_hook_gc_failure_does_not_rollback_commit_bookkeeping` |
| `WS-1B` | `tests/scientist/test_checkpoint.py::test_checkpoint_hook_runtime_metadata_roundtrip_preserves_sequence` |
| `WS-1B` | `tests/scientist/engine/runner/test_activity_worker.py::test_run_merge_checkpoint_tier_in_worker_restores_checkpoint_contract` |
| `WS-1B` | `tests/scientist/engine/runner/test_serialization.py::test_deserialize_state_accepts_list_encoded_wire_payload` |
| `WS-1B` | `tests/scientist/engine/runner/test_serialization.py::test_deserialize_outcome_accepts_list_encoded_wire_payload` |
| `WS-1B` | `tests/scientist/engine/runner/test_temporal_runner.py::test_temporal_runner_executes_remote_checkpoint_merge_activity` |
| `WS-1B support` | `tests/scientist/engine/runner/test_temporal_runner.py::test_temporal_health_check_returns_unhealthy_on_probe_error` |
| `WS-1B` | `tests/scientist/engine/runner/test_ray_runner.py::test_ray_runner_executes_remote_checkpoint_merge_task` |
| `WS-1B support` | `tests/scientist/engine/runner/test_ray_runner.py::test_ray_runner_health_check_returns_unhealthy_on_probe_error` |
| `WS-1B` | `tests/scientist/nodes/builtins/test_state_builtins.py::test_set_state_uses_copy_on_write_for_params` |
| `WS-1B` | `tests/scientist/nodes/builtins/test_state_builtins.py::test_emit_artifact_uses_copy_on_write_for_artifacts_index` |
| `WS-1B` | `tests/scientist/engine/test_budget_middleware.py::test_ledger_mutation_uses_copy_on_write_budget_state` |
| `WS-1B` | `tests/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py::test_run_hierarchical_policy_search_uses_branch_state_for_final_outputs` |
| `WS-1B` | `tests/scientist/test_legal_check_node.py::test_legal_check_uses_branch_state_for_inputs_and_reports` |
| `WS-1B` | `tests/scientist/test_data_plane_gate_node.py::test_data_plane_gate_uses_branch_state_for_param_outputs` |
| `WS-1B` | `tests/scientist/test_run_governance_normative.py::test_run_governance_uses_branch_state_for_params_and_report` |
| `WS-1B` | `tests/scientist/test_normative_arbitration_node.py::test_normative_arbitration_uses_branch_state_for_artifact_output` |
| `WS-1B` | `tests/scientist/nodes/builtins/compile/test_compile_foundry.py::test_compile_foundry_uses_branch_state_for_declared_outputs` |
| `WS-1B` | `tests/scientist/nodes/builtins/compile/test_link_trinity.py::test_link_trinity_uses_branch_state_for_report_output` |
| `WS-1B` | `tests/scientist/nodes/builtins/compile/test_formalize_verified_policy.py::test_formalize_verified_policy_uses_branch_state_for_inputs_and_params` |
| `WS-1B` | `tests/scientist/nodes/builtins/planning/test_run_preflight.py::test_preflight_uses_branch_state_for_declared_outputs` |
| `WS-1B` | `tests/scientist/nodes/builtins/planning/test_run_evaluator.py::test_evaluator_uses_branch_state_for_declared_outputs` |
| `WS-1B` | `tests/scientist/nodes/builtins/planning/test_build_execution_plan.py::test_plan_builder_uses_branch_state_for_declared_outputs` |
| `WS-1B` | `tests/scientist/nodes/builtins/planning/test_plan_policy_request.py::test_plan_policy_request_uses_branch_state_for_declared_outputs` |
| `WS-1B` | `tests/scientist/nodes/builtins/planning/test_assemble_legal_candidate_pack.py::test_assemble_pack_uses_branch_state_for_declared_outputs` |
| `WS-1B` | `tests/scientist/nodes/builtins/planning/test_expand_legal_source_pack.py::test_expand_source_pack_uses_branch_state_for_declared_outputs` |
| `WS-1B` | `tests/scientist/nodes/builtins/planning/test_run_source_verification.py::test_source_verification_uses_branch_state_for_declared_outputs` |
| `WS-1B` | `tests/scientist/nodes/builtins/planning/test_run_source_gap_review.py::test_gap_review_uses_branch_state_for_declared_outputs` |
| `WS-1B` | `tests/scientist/nodes/builtins/planning/test_draft_policy_options.py::test_draft_policy_options_uses_branch_state_for_declared_outputs` |
| `WS-2B support` | `tests/scientist/test_import_boundaries.py::test_core_lex_import_does_not_eagerly_load_scientist_alignment_boundary` |

## Signoff Rule

Phase 1 is accepted only when the reliability scorecard and the direct workstream
tests agree that Scientist has:

1. Diagnostic failure surfaces.
2. Deterministic state mutation behavior.
3. Production-like observability.
4. Benchmarked and reproducible reliability evidence.
