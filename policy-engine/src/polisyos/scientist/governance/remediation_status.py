"""Machine-readable Scientist remediation closure report.

This module is the repo-tracked source of truth for
`SCIENTIST_AUDIT_REMEDIATION_PLAN.md`. Workstreams are marked `done` only when
their Definition of Done is backed by code, regression coverage, docs,
observable evidence, and explicit CI gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "WORKSTREAM_IDS",
    "RemediationStatusLevel",
    "ScientistPhaseStatus",
    "ScientistRemediationStatusReport",
    "ScientistWorkstreamStatus",
    "build_scientist_remediation_status_report",
]


class RemediationStatusLevel(StrEnum):
    """Allowed status values for remediation tracking."""

    DONE = "done"
    PARTIAL = "partial"
    MISSING = "missing"


WORKSTREAM_IDS: tuple[str, ...] = (
    "WS-0A",
    "WS-0B",
    "WS-1A",
    "WS-1B",
    "WS-1C",
    "WS-1D",
    "WS-2A",
    "WS-2B",
    "WS-3A",
    "WS-3B",
    "WS-3C",
    "WS-4A",
    "WS-4B",
)


@dataclass(frozen=True)
class ScientistWorkstreamStatus:
    """One workstream entry in the Scientist remediation matrix."""

    workstream_id: str
    phase: str
    title: str
    status: RemediationStatusLevel
    summary: str
    blocking_issues: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    ci_gates: tuple[str, ...]
    acceptance_signal: str

    def to_dict(self) -> dict[str, object]:
        return {
            "workstream_id": self.workstream_id,
            "phase": self.phase,
            "title": self.title,
            "status": self.status.value,
            "summary": self.summary,
            "blocking_issues": list(self.blocking_issues),
            "evidence_refs": list(self.evidence_refs),
            "ci_gates": list(self.ci_gates),
            "acceptance_signal": self.acceptance_signal,
        }


@dataclass(frozen=True)
class ScientistPhaseStatus:
    """Aggregated phase-level remediation status."""

    phase: str
    status: RemediationStatusLevel
    workstream_ids: tuple[str, ...]
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "status": self.status.value,
            "workstream_ids": list(self.workstream_ids),
            "summary": self.summary,
        }


@dataclass(frozen=True)
class ScientistRemediationStatusReport:
    """Repo-tracked Gate 0 baseline for Scientist remediation closure."""

    schema_version: str
    assessment_id: str
    strict_definition_of_done: bool
    overall_status: RemediationStatusLevel
    phase_rollups: tuple[ScientistPhaseStatus, ...]
    workstreams: tuple[ScientistWorkstreamStatus, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "assessment_id": self.assessment_id,
            "strict_definition_of_done": self.strict_definition_of_done,
            "overall_status": self.overall_status.value,
            "phase_rollups": [item.to_dict() for item in self.phase_rollups],
            "workstreams": [item.to_dict() for item in self.workstreams],
            "notes": list(self.notes),
        }


def build_scientist_remediation_status_report() -> ScientistRemediationStatusReport:
    """Return the current repo-tracked Scientist remediation baseline.

    The report is deliberately strict. A workstream is marked `done` only when
    the remediation plan's exit criteria are all repo-tracked and gated.
    """

    workstreams = (
        ScientistWorkstreamStatus(
            workstream_id="WS-0A",
            phase="Phase 0",
            title="Async, locking and lifecycle correctness",
            status=RemediationStatusLevel.DONE,
            summary=(
                "Async, locking, and lifecycle containment is closed. Retry "
                "timeout workers, worker pools, lock probes, and lock metrics "
                "now surface typed failure semantics, and the dedicated "
                "Scientist Phase 0 gate keeps the teardown and containment "
                "regression pack green."
            ),
            blocking_issues=(),
            evidence_refs=(
                "src/polisyos/scientist/engine/retry.py",
                "tests/unit/scientist/engine/test_retry.py::test_timeout_worker_does_not_swallow_system_exit",
                "src/polisyos/scientist/engine/runner/local_pool.py",
                "tests/unit/scientist/engine/runner/test_worker_pool.py::test_worker_runtime_error_surfaces_on_future",
                "src/polisyos/scientist/engine/locks/fcntl_lock.py",
                "tests/unit/scientist/engine/locks/test_fcntl_lock.py",
                "src/polisyos/scientist/engine/locks/metrics.py",
                "tests/unit/scientist/engine/locks/test_lock_metrics.py::test_measure_acquire_does_not_swallow_assertion_errors",
                "src/polisyos/scientist/engine/locks/dynamodb_lock.py",
                "tests/unit/scientist/engine/locks/test_dynamodb_lock.py::test_detect_stale_runtime_probe_error_returns_false",
                "tests/unit/scientist/engine/locks/test_dynamodb_lock.py::test_is_alive_runtime_probe_error_returns_false",
                "src/polisyos/scientist/engine/locks/redis_lock.py",
                "tests/unit/scientist/engine/locks/test_redis_lock.py::test_is_alive_returns_false_on_runtime_probe_error",
                "tests/unit/scientist/engine/locks/test_redis_lock.py::test_detect_stale_returns_false_on_runtime_probe_error",
                "tests/unit/scientist/agent/test_code_verifier.py",
            ),
            ci_gates=(
                "pytest tests/unit/scientist/engine/test_retry.py tests/unit/scientist/engine/runner/test_worker_pool.py tests/unit/scientist/engine/locks/test_fcntl_lock.py tests/unit/scientist/engine/locks/test_lock_metrics.py tests/unit/scientist/engine/locks/test_dynamodb_lock.py tests/unit/scientist/engine/locks/test_redis_lock.py -q",
                "python tools/ci/check_scientist_phase0_gate.py --junit-xml _build/.tmp/test-reports/scientist-phase0.xml --output _build/.tmp/test-reports/scientist-phase0-gate.json --output-format json --require-passing",
            ),
            acceptance_signal=(
                "fault-injection, teardown, and lock regressions remain green "
                "under the dedicated Scientist Phase 0 barrier"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-0B",
            phase="Phase 0",
            title="Budget, request correctness, security and scientific hotfixes",
            status=RemediationStatusLevel.DONE,
            summary=(
                "Budget accounting, request idempotency, masking, env hardening, "
                "and default-path statistical hotfixes are closed. The "
                "dedicated Scientist Phase 0 gate now ties gateway "
                "idempotency, reservation reconciliation, masking fail-closed "
                "behavior, Foundry env sanitization, and the statistical "
                "regression pack into one repo-tracked barrier."
            ),
            blocking_issues=(),
            evidence_refs=(
                "src/polisyos/scientist/llm/gateway_client.py",
                "src/polisyos/scientist/llm/fallback_router.py",
                "tests/unit/scientist/llm/test_fallback_router.py::test_failover_emits_degraded_path",
                "tests/unit/scientist/llm/test_fallback_router.py::test_keyboard_interrupt_is_not_swallowed",
                "src/polisyos/scientist/llm/provider_verification.py",
                "tests/unit/scientist/llm/test_provider_verification.py::test_load_provider_verification_invalid_json_returns_none",
                "tests/unit/scientist/llm/test_provider_verification.py::test_run_named_check_does_not_swallow_assertion_errors",
                "src/polisyos/scientist/llm/budget_enforcer.py",
                "src/polisyos/scientist/backtesting/bootstrap.py",
                "src/polisyos/scientist/adapters/foundry_bridge.py",
            ),
            ci_gates=(
                "pytest tests/unit/scientist/llm/test_gateway_client_retry.py tests/unit/scientist/engine/test_idempotency.py tests/unit/scientist/llm/test_budget_enforcer.py tests/unit/scientist/backtesting/test_masking.py tests/unit/scientist/adapters/test_foundry_bridge.py tests/unit/scientist/backtesting/test_bootstrap.py tests/unit/scientist/backtesting/test_ipw.py tests/unit/scientist/backtesting/test_distributional.py tests/unit/scientist/search/test_cheap_stage_autotune.py -q",
                "python tools/ci/check_scientist_phase0_gate.py --junit-xml _build/.tmp/test-reports/scientist-phase0.xml --output _build/.tmp/test-reports/scientist-phase0-gate.json --output-format json --require-passing",
            ),
            acceptance_signal=(
                "idempotency, budget, masking, env hardening, and statistical "
                "regressions remain green under the dedicated Scientist Phase 0 gate"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-1A",
            phase="Phase 1",
            title="Error semantics and degraded-mode policy",
            status=RemediationStatusLevel.DONE,
            summary=(
                "Error semantics and degraded-mode policy are closed on the "
                "accepted Phase 1 slice. Critical governance, executor, agent, "
                "cross-graph, autotune, and funnel helpers now surface typed "
                "errors or structured degraded envelopes, and the dedicated "
                "Phase 1 gate ratchets the critical broad-handler targets."
            ),
            blocking_issues=(),
            evidence_refs=(
                "src/polisyos/scientist/governance/pipeline.py",
                "tests/unit/scientist/governance/test_validation_pipeline.py::test_failing_pass_returns_structured_error_envelope",
                "src/polisyos/scientist/engine/retry.py",
                "tests/unit/scientist/engine/test_retry.py::test_timeout_worker_does_not_swallow_system_exit",
                "src/polisyos/scientist/engine/locks/redis_lock.py",
                "tests/unit/scientist/engine/locks/test_redis_lock.py::test_is_alive_returns_false_on_runtime_probe_error",
                "tests/unit/scientist/engine/locks/test_redis_lock.py::test_detect_stale_returns_false_on_runtime_probe_error",
                "src/polisyos/scientist/engine/locks/dynamodb_lock.py",
                "tests/unit/scientist/engine/locks/test_dynamodb_lock.py::test_detect_stale_runtime_probe_error_returns_false",
                "tests/unit/scientist/engine/locks/test_dynamodb_lock.py::test_is_alive_runtime_probe_error_returns_false",
                "src/polisyos/scientist/engine/executor.py",
                "src/polisyos/scientist/engine/async_executor.py",
                "tests/unit/scientist/engine/test_async_executor_hardening.py::test_runtime_lookup_failure_becomes_typed_node_error",
                "src/polisyos/scientist/engine/registry.py",
                "tests/unit/scientist/engine/test_node_registry_components_bootstrap.py::test_discover_nodes_records_typed_runtime_provider_error",
                "tests/unit/scientist/engine/test_node_registry_components_bootstrap.py::test_discover_nodes_does_not_swallow_assertion_errors",
                "src/polisyos/scientist/engine/telemetry.py",
                "tests/unit/scientist/engine/test_telemetry.py::test_start_node_span_runtime_error_degrades",
                "tests/unit/scientist/engine/test_telemetry.py::test_set_span_attribute_runtime_error_degrades",
                "tests/unit/scientist/engine/test_telemetry.py::test_add_span_events_runtime_error_degrades",
                "src/polisyos/scientist/engine/runner/local_pool.py",
                "tests/unit/scientist/engine/runner/test_worker_pool.py::test_worker_runtime_error_surfaces_on_future",
                "src/polisyos/scientist/nodes/builtins/data/build_data_snapshot.py",
                "tests/unit/scientist/nodes/builtins/data/test_build_data_snapshot.py::test_snapshot_pii_summary_load_failure_degrades",
                "src/polisyos/scientist/nodes/builtins/planning/run_preflight.py",
                "tests/unit/scientist/nodes/builtins/planning/test_run_preflight.py::test_preflight_invalid_input_load_returns_typed_fail",
                "src/polisyos/scientist/nodes/builtins/planning/run_evaluator.py",
                "tests/unit/scientist/nodes/builtins/planning/test_run_evaluator.py::test_evaluator_invalid_governance_report_emits_warning",
                "tests/unit/scientist/nodes/builtins/planning/test_run_evaluator.py::test_evaluator_transition_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/planning/build_execution_plan.py",
                "tests/unit/scientist/nodes/builtins/planning/test_build_execution_plan.py::test_plan_from_raw_dict_fallback",
                "tests/unit/scientist/nodes/builtins/planning/test_build_execution_plan.py::test_plan_invalid_data_needs_emit_warning",
                "src/polisyos/scientist/nodes/builtins/causal/resolve_parameters.py",
                "tests/unit/scientist/nodes/builtins/causal/test_resolve_parameters.py::test_target_context_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/causal/run_causal_queries.py",
                "tests/unit/scientist/nodes/builtins/causal/test_run_causal_queries.py::test_causal_query_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/planning/compile_cross_graph_evidence.py",
                "tests/unit/scientist/nodes/builtins/planning/test_compile_cross_graph_evidence.py::test_compilation_target_context_assertion_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/planning/run_discovery_blueprint_runtime.py",
                "tests/unit/scientist/nodes/builtins/planning/test_run_discovery_blueprint_runtime.py::test_resolve_causal_query_assertion_is_not_swallowed",
                "tests/unit/scientist/nodes/builtins/planning/test_run_discovery_blueprint_runtime.py::test_measure_seed_reproducibility_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/causal/run_abm_consistency.py",
                "tests/unit/scientist/nodes/builtins/causal/test_run_abm_consistency.py::test_abm_mapping_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/causal/run_causal_ensemble.py",
                "tests/unit/scientist/nodes/builtins/causal/test_run_causal_ensemble.py::test_causal_ensemble_member_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/causal/reconcile_causal_graph.py",
                "tests/unit/scientist/nodes/builtins/causal/test_reconcile_causal_graph.py::test_reconcile_fragment_load_assertion_is_not_swallowed",
                "tests/unit/scientist/nodes/builtins/causal/test_reconcile_causal_graph.py::test_reconcile_literature_prior_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/causal/resolve_transport.py",
                "tests/unit/scientist/nodes/builtins/causal/test_resolve_transport.py::test_run_transportability_report_assertion_is_not_swallowed",
                "tests/unit/scientist/nodes/builtins/causal/test_resolve_transport.py::test_build_skg_query_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py",
                "tests/unit/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py::test_collect_input_envelopes_snapshot_assertion_is_not_swallowed",
                "tests/unit/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py::test_load_config_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/simulate/run_distributional_analysis.py",
                "tests/unit/scientist/nodes/builtins/simulate/test_run_distributional_analysis.py::test_resolve_baseline_snapshot_ref_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/causal/run_causal_contract_execution.py",
                "tests/unit/scientist/nodes/builtins/causal/test_run_causal_contract_execution.py::test_run_causal_contract_execution_task_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/causal/run_causal_readiness.py",
                "tests/unit/scientist/nodes/builtins/causal/test_run_causal_readiness.py::test_run_causal_readiness_graph_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/data/bind_foundry_inputs.py",
                "tests/unit/scientist/nodes/test_bind_foundry_inputs_node.py::test_bind_foundry_inputs_build_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/data/enrich_knowledge.py",
                "tests/unit/scientist/nodes/test_enrich_knowledge_node_freshness.py::test_enrich_node_scholar_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py",
                "tests/unit/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py::test_run_hierarchical_policy_search_adapter_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py",
                "tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py::test_assertion_in_observational_data_load_is_not_swallowed",
                "tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py::test_fail_when_method_output_report_is_invalid",
                "src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py",
                "tests/unit/scientist/nodes/builtins/simulate/test_run_simulation.py::test_run_simulation_result_assertion_is_not_swallowed",
                "src/polisyos/scientist/policy_verified/service.py",
                "tests/unit/scientist/policy_design/test_policy_verified_nodes.py::test_load_research_intent_assertion_is_not_swallowed",
                "tests/unit/scientist/policy_design/test_policy_verified_nodes.py::test_build_legal_toolkit_assertion_is_not_swallowed",
                "tests/unit/scientist/policy_design/test_policy_verified_nodes.py::test_load_cross_graph_profile_assertion_is_not_swallowed",
                "tests/unit/scientist/policy_design/test_policy_verified_nodes.py::test_parse_json_object_assertion_is_not_swallowed",
                "tests/unit/scientist/policy_design/test_policy_verified_nodes.py::test_maybe_verify_with_llm_assertion_is_not_swallowed",
                "src/polisyos/scientist/autotune/execution_plan.py",
                "tests/unit/scientist/autotune/test_execution_plan_autotune.py::test_with_topology_mutation_does_not_swallow_registry_assertion",
                "tests/unit/scientist/autotune/test_execution_plan_autotune.py::test_coerce_candidate_config_does_not_swallow_assertion",
                "tests/unit/scientist/autotune/test_execution_plan_autotune.py::test_backend_for_method_does_not_swallow_assertion",
                "src/polisyos/scientist/search/funnel/level2_causal.py",
                "tests/unit/scientist/search/funnel/test_level2_causal.py::test_coerce_context_data_does_not_swallow_assertion",
                "tests/unit/scientist/search/funnel/test_level2_causal.py::test_fast_propensity_check_does_not_swallow_assertion",
                "tests/unit/scientist/search/funnel/test_level2_causal.py::test_fast_proxy_estimate_does_not_swallow_assertion",
                "src/polisyos/scientist/agent/code_verifier.py",
                "tests/unit/scientist/agent/test_code_verifier.py::test_load_allowed_modules_assertion_is_not_swallowed",
                "tests/unit/scientist/agent/test_code_verifier.py::test_apply_resource_limits_import_assertion_is_not_swallowed",
                "tests/unit/scientist/agent/test_code_verifier.py::test_verification_worker_restrictedpython_import_assertion_is_not_swallowed",
                "src/polisyos/scientist/agent/supervisor.py",
                "tests/unit/scientist/agent/test_supervisor.py::test_supervisor_provenance_export_assertion_is_not_swallowed",
                "tests/unit/scientist/agent/test_supervisor.py::test_supervisor_worker_execution_assertion_is_not_swallowed",
                "tests/unit/scientist/agent/test_supervisor.py::test_supervisor_worker_result_assertion_is_not_swallowed",
                "src/polisyos/scientist/agent/rag.py",
                "tests/unit/scientist/agent/test_rag_index.py::test_rag_build_from_cas_manifest_assertion_is_not_swallowed",
                "tests/unit/scientist/agent/test_rag_index.py::test_rag_entry_trinity_assertion_is_not_swallowed",
                "tests/unit/scientist/agent/test_rag_index.py::test_build_or_load_rag_index_load_assertion_is_not_swallowed",
                "src/polisyos/scientist/cross_graph/compiler.py",
                "tests/unit/scientist/cross_graph/test_cross_graph_evidence.py::test_cross_graph_compiler_legal_assertion_is_not_swallowed",
                "tests/unit/scientist/cross_graph/test_cross_graph_evidence.py::test_build_academic_query_assertion_is_not_swallowed",
                "tests/unit/scientist/cross_graph/test_cross_graph_evidence.py::test_candidate_distance_assertion_is_not_swallowed",
                "tests/unit/scientist/cross_graph/test_cross_graph_evidence.py::test_fragment_alignment_ontology_assertion_is_not_swallowed",
                "src/polisyos/scientist/cross_graph/gatherers/academic.py",
                "tests/unit/scientist/cross_graph/test_gatherers.py::test_serialize_value_assertion_is_not_swallowed",
                "src/polisyos/scientist/agent/data_need_extractor.py",
                "tests/unit/scientist/agent/test_data_need_extractor.py::test_extract_data_needs_json_parse_assertion_is_not_swallowed",
                "tests/unit/scientist/agent/test_data_need_extractor.py::test_catalog_lookup_assertion_is_not_swallowed",
                "src/polisyos/scientist/agent/norm_loader.py",
                "tests/unit/scientist/agent/test_norm_loader.py::test_cas_norm_loader_assertion_is_not_swallowed",
                "src/polisyos/scientist/agent/drafter_factory.py",
                "tests/unit/scientist/agent/test_drafter_factory.py::test_create_drafter_agent_rag_assertion_is_not_swallowed",
                "src/polisyos/scientist/agent/_drafter_formatting.py",
                "tests/unit/scientist/agent/test_drafter_formatting.py::test_assertion_is_not_swallowed",
                "src/polisyos/scientist/agent/router.py",
                "tests/unit/scientist/agent/test_router.py::test_assertion_is_not_swallowed",
                "tests/unit/scientist/agent/test_router.py::test_parallel_assertion_is_not_swallowed",
                "src/polisyos/scientist/agent/tools/tool_loop.py",
                "tests/unit/scientist/agent/tools/test_tool_loop.py::test_budget_probe_failure_is_reported_as_degraded_event",
                "tests/unit/scientist/agent/tools/test_tool_loop.py::test_persistent_memory_recall_failure_is_reported_as_degraded_event",
                "tests/unit/scientist/agent/tools/test_tool_loop.py::test_malformed_arguments_json",
                "src/polisyos/scientist/engine/checkpoint.py",
                "tests/unit/scientist/engine/test_checkpoint.py::test_checkpoint_head_invalid_json_raises_typed_error",
                "tests/unit/scientist/engine/test_checkpoint.py::test_checkpoint_history_invalid_json_raises_typed_error",
                "src/polisyos/scientist/llm/gateway_client.py",
                "tests/unit/scientist/llm/test_gateway_client_retry.py::test_list_model_ids_invalid_json_degrades_to_empty_list",
                "tests/unit/scientist/llm/test_gateway_client_retry.py::test_list_model_ids_invalid_shape_degrades_to_empty_list",
                "src/polisyos/scientist/llm/fallback_router.py",
                "tests/unit/scientist/llm/test_fallback_router.py::test_failover_emits_degraded_path",
                "tests/unit/scientist/llm/test_fallback_router.py::test_keyboard_interrupt_is_not_swallowed",
                "src/polisyos/scientist/llm/provider_verification.py",
                "tests/unit/scientist/llm/test_provider_verification.py::test_load_provider_verification_invalid_json_returns_none",
                "tests/unit/scientist/llm/test_provider_verification.py::test_run_named_check_does_not_swallow_assertion_errors",
                "tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_build_decision_packet_records_degraded_paths_for_invalid_metrics_and_governance",
                "tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_build_decision_packet_records_degraded_paths_for_invalid_decision_basis_quality_report",
                "tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_build_decision_packet_records_degraded_paths_for_invalid_normative_arbitration",
                "tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_build_decision_packet_records_degraded_paths_for_invalid_sensitivity_artifact",
                "tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_build_decision_packet_records_degraded_paths_for_invalid_uncertainty_output_envelope",
                "tests/unit/scientist/policy_design/test_policy_verified_nodes.py::test_build_decision_packet_records_degraded_paths_for_invalid_policy_verification_artifacts",
                "tests/unit/scientist/nodes/test_build_policy_output_bundle.py::test_decision_packet_records_degraded_path_for_invalid_policy_bundle",
                "tests/unit/scientist/engine/test_engine_executor_v0.py::test_executor_logs_cache_write_bypass_as_node_event",
                "tests/unit/scientist/engine/test_engine_executor_v0.py::test_executor_logs_provenance_recording_degraded_as_node_event",
                "tests/unit/scientist/engine/test_engine_executor_v0.py::test_executor_reports_bind_failure_as_typed_node_error",
                "tests/unit/scientist/engine/test_engine_executor_v0.py::test_executor_reports_lookup_runtime_failure_as_typed_node_error",
                "tests/unit/scientist/engine/test_async_executor_hardening.py::test_bind_failure_becomes_typed_node_error",
                "tests/unit/scientist/engine/test_fan_out.py::test_bind_failure_stops_without_executing_item_when_fail_fast",
                "tests/unit/scientist/engine/test_fan_out.py::test_summary_persist_failure_emits_degraded_event",
                "tests/unit/scientist/engine/test_fan_out_async.py::test_async_bind_failure_stops_without_executing_item_when_fail_fast",
                "tests/unit/scientist/engine/test_fan_out_async.py::test_async_summary_persist_failure_emits_degraded_event",
                "tests/unit/core/phase0/test_artifact_store.py::test_filesystem_cas_accepts_ir_artifact_id_roundtrip",
                "tests/unit/scientist/search/test_policy_blueprint_runtime_guards.py::test_runtime_strategic_helper_invalid_input_records_degraded_path",
                "tests/unit/scientist/search/test_policy_blueprint_runtime_guards.py::test_runtime_strategic_helper_persistence_failure_records_degraded_path",
                "tests/unit/scientist/nodes/test_build_policy_output_bundle.py::test_build_policy_output_bundle_degrades_invalid_distributional_report",
                "tests/unit/scientist/nodes/test_build_policy_output_bundle.py::test_build_policy_output_bundle_degrades_invalid_uncertainty_envelope",
                "tests/unit/scientist/governance/test_pass_registry.py::test_load_governance_passes_wraps_entry_point_load_error",
                "tests/unit/scientist/nodes/test_run_governance_normative.py::test_run_governance_rejects_on_explicit_normative_right_violation",
                "tests/unit/scientist/nodes/test_run_governance_normative.py::test_run_governance_marks_needs_revision_when_policy_prefers_baseline",
                "tests/unit/scientist/nodes/test_run_governance_normative.py::test_run_governance_keeps_warning_only_for_partial_model_when_proposal_selected",
                "tests/unit/scientist/governance/test_normative_arbitration_pass.py::test_normative_arbitration_invalid_payload_emits_warning",
                "tests/unit/scientist/governance/test_human_review_pass.py::test_human_review_invalid_graph_payload_emits_warning",
                "tests/unit/scientist/nodes/test_normative_arbitration_node.py::test_normative_arbitration_invalid_trinity_bundle_skips_with_warning",
                "src/polisyos/scientist/nodes/builtins/governance/legal_check.py",
                "tests/unit/scientist/nodes/test_legal_check_node.py::test_legal_check_records_degraded_event_when_report_grade_load_fails",
                "src/polisyos/scientist/nodes/builtins/governance/data_plane_gate.py",
                "tests/unit/scientist/nodes/test_data_plane_gate_node.py::test_data_plane_gate_records_degraded_event_for_invalid_quality_report",
                "src/polisyos/scientist/governance/passes/_artifact_resolution.py",
                "tests/unit/scientist/nodes/test_decision_packet_node_v3.py",
                "src/polisyos/scientist/nodes/builtins/governance/run_governance.py",
                "src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py",
                "src/polisyos/scientist/nodes/builtins/decide/build_policy_output_bundle.py",
                "src/polisyos/scientist/nodes/builtins/c6c_runtime_support.py",
                "src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py",
                "src/polisyos/scientist/nodes/builtins/governance/run_normative_arbitration.py",
                "src/polisyos/scientist/governance/pass_registry.py",
                "src/polisyos/scientist/governance/passes/human_review_pass.py",
                "src/polisyos/scientist/governance/passes/pii_check_pass.py",
                "src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py",
                "src/polisyos/scientist/engine/executor.py",
                "src/polisyos/scientist/engine/async_executor.py",
                "src/polisyos/scientist/engine/runner/_activity_worker.py",
                "tests/unit/scientist/engine/runner/test_activity_worker.py::test_build_worker_context_records_degraded_path_for_invalid_registry_bundle",
                "tests/unit/scientist/engine/runner/test_activity_worker.py::test_restore_parent_trace_context_records_degraded_path_on_runtime_error",
                "src/polisyos/scientist/engine/runner/serialization.py",
                "tests/unit/scientist/engine/runner/test_serialization.py::test_current_trace_ids_records_degraded_path_on_runtime_error",
                "src/polisyos/scientist/engine/runner/temporal_runner.py",
                "tests/unit/scientist/engine/runner/test_temporal_runner.py::test_temporal_inject_trace_carrier_records_degraded_path_on_runtime_error",
                "tests/unit/scientist/engine/runner/test_temporal_runner.py::test_temporal_health_check_returns_unhealthy_on_probe_error",
                "src/polisyos/scientist/engine/runner/ray_runner.py",
                "tests/unit/scientist/engine/runner/test_ray_runner.py::test_ray_runner_inject_trace_carrier_records_degraded_path_on_runtime_error",
                "tests/unit/scientist/engine/runner/test_ray_runner.py::test_ray_runner_health_check_returns_unhealthy_on_probe_error",
                "src/polisyos/scientist/engine/runner/fallback_runner.py",
                "tests/unit/scientist/engine/runner/test_fallback_runner.py::test_primary_execution_error_emits_degraded_path_and_uses_fallback",
                "src/polisyos/scientist/nodes/builtins/tracing.py",
                "tests/unit/scientist/nodes/builtins/test_tracing.py::test_runtime_trace_access_failure_returns_none_ids",
                "tests/unit/scientist/engine/test_checkpoint.py::test_restore_checkpoint_hook_from_runtime_metadata_rejects_invalid_store_config",
                "src/polisyos/core/artifacts/store.py",
            ),
            ci_gates=(
                "pytest tests/unit/scientist/facade/test_remediation_status.py tests/unit/scientist/governance/test_reliability_scorecard.py tests/unit/scientist/engine/test_reliability_operational_evidence.py tests/integration/scientist/test_workflow_reliability_scenarios.py tests/unit/scientist/agent/test_data_need_extractor.py tests/unit/scientist/agent/test_norm_loader.py tests/unit/scientist/agent/test_drafter_factory.py tests/unit/scientist/agent/test_drafter_formatting.py tests/unit/scientist/agent/test_router.py tests/unit/scientist/agent/test_supervisor.py tests/unit/scientist/agent/test_rag_index.py tests/unit/scientist/cross_graph/test_cross_graph_evidence.py tests/unit/scientist/cross_graph/test_gatherers.py tests/unit/scientist/autotune/test_execution_plan_autotune.py tests/unit/scientist/autotune/test_calibration_autotune.py tests/unit/scientist/search/funnel/test_level2_causal.py tests/unit/scientist/agent/test_code_verifier.py tests/unit/scientist/nodes/builtins/decide/test_policy_translation.py tests/unit/scientist/engine/test_budget_middleware.py tests/unit/scientist/workflows/test_builder_pinning.py -q",
                "python tools/ci/check_scientist_phase1_gate.py --benchmark-json _build/.tmp/test-reports/scientist-phase1-benchmarks.json --junit-xml _build/.tmp/test-reports/scientist-phase1.xml --output _build/.tmp/test-reports/scientist-phase1-gate.json --output-format json --require-passing",
            ),
            acceptance_signal=(
                "critical error-semantics slices remain covered by direct "
                "regressions and the dedicated Scientist Phase 1 ratchet"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-1B",
            phase="Phase 1",
            title="Atomic state mutation, merge semantics and deterministic execution",
            status=RemediationStatusLevel.DONE,
            summary=(
                "Atomic mutation, merge semantics, and deterministic execution "
                "are closed on the accepted Phase 1 slice. Branch-local "
                "copy-on-write execution, staged fan-out merge behavior, "
                "checkpoint reconciliation, distributed resume, and translation/"
                "autotune mutation contracts are now regression-covered and "
                "ratcheted against new live deep-copy hot paths."
            ),
            blocking_issues=(),
            evidence_refs=(
                "src/polisyos/scientist/engine/executor.py",
                "src/polisyos/scientist/engine/state_branching.py",
                "tests/unit/scientist/engine/test_engine_executor_v0.py::test_executor_branch_state_isolates_declared_nested_writes",
                "tests/unit/scientist/engine/test_state_branching.py",
                "src/polisyos/scientist/engine/fan_out.py",
                "tests/unit/scientist/engine/test_fan_out.py::test_invalid_result_path_fails_instead_of_silent_params_drift",
                "tests/unit/scientist/engine/test_fan_out.py::test_summary_persist_failure_emits_degraded_event",
                "src/polisyos/scientist/engine/sub_workflow.py",
                "tests/unit/scientist/engine/test_sub_workflow.py::test_child_failure_does_not_apply_output_mappings",
                "tests/unit/scientist/engine/test_sub_workflow.py::test_overlapping_output_mappings_fail_atomically",
                "src/polisyos/scientist/engine/checkpoint.py",
                "tests/unit/scientist/engine/test_checkpoint.py::test_resolve_latest_checkpoint_repairs_history_when_head_is_newer",
                "tests/unit/scientist/engine/test_checkpoint.py::test_resolve_latest_checkpoint_rejects_head_history_conflict",
                "tests/unit/scientist/engine/test_checkpoint.py::test_checkpoint_hook_gc_failure_does_not_rollback_commit_bookkeeping",
                "tests/unit/scientist/engine/test_fan_out.py::test_stop_on_failure_does_not_commit_partial_merged_state",
                "tests/unit/scientist/engine/test_fan_out_async.py::test_async_stop_on_failure_does_not_commit_partial_merged_state",
                "tests/unit/scientist/engine/test_fan_out_async.py::test_async_summary_persist_failure_emits_degraded_event",
                "tests/integration/scientist/test_checkpoint_resume.py::test_async_executor_resume_uses_checkpoint_cache_refs_when_trace_is_truncated",
                "tests/integration/scientist/test_checkpoint_resume.py::test_async_executor_parallel_tier_checkpoints_merged_state_for_resume",
                "tests/integration/scientist/test_checkpoint_resume.py::test_resume_falls_back_to_local_runner_when_distributed_backend_is_configured",
                "tests/integration/scientist/test_checkpoint_resume.py::test_resume_uses_configured_distributed_runner_with_pruned_workflow",
                "tests/unit/scientist/engine/test_checkpoint.py::test_resolve_latest_checkpoint_rejects_divergent_latest_history_entries",
                "tests/unit/scientist/engine/test_checkpoint.py::test_resolve_latest_checkpoint_rejects_head_artifact_metadata_mismatch",
                "tests/unit/scientist/engine/test_checkpoint.py::test_checkpoint_hook_runtime_metadata_roundtrip_preserves_sequence",
                "src/polisyos/scientist/engine/runner/serialization.py",
                "tests/unit/scientist/engine/runner/test_serialization.py::test_deserialize_state_accepts_list_encoded_wire_payload",
                "tests/unit/scientist/engine/runner/test_serialization.py::test_deserialize_outcome_accepts_list_encoded_wire_payload",
                "tests/unit/scientist/engine/runner/test_activity_worker.py::test_run_merge_checkpoint_tier_in_worker_restores_checkpoint_contract",
                "tests/unit/scientist/engine/runner/test_temporal_runner.py::test_temporal_runner_executes_remote_checkpoint_merge_activity",
                "tests/unit/scientist/engine/runner/test_ray_runner.py::test_ray_runner_executes_remote_checkpoint_merge_task",
                "tests/unit/scientist/engine/runner/test_ray_runner.py::test_ray_runner_health_check_returns_unhealthy_on_probe_error",
                "tests/unit/scientist/engine/runner/test_fallback_runner.py::test_primary_execution_error_emits_degraded_path_and_uses_fallback",
                "tests/unit/scientist/engine/test_checkpoint.py::test_restore_checkpoint_hook_from_runtime_metadata_rejects_invalid_store_config",
                "src/polisyos/scientist/engine/builtins/set_state.py",
                "src/polisyos/scientist/engine/builtins/emit_artifact.py",
                "src/polisyos/scientist/engine/budget_ledger.py",
                "tests/unit/scientist/nodes/builtins/test_state_builtins.py::test_set_state_uses_copy_on_write_for_params",
                "tests/unit/scientist/nodes/builtins/test_state_builtins.py::test_emit_artifact_uses_copy_on_write_for_artifacts_index",
                "tests/unit/scientist/engine/test_budget_middleware.py::test_ledger_mutation_uses_copy_on_write_budget_state",
                "src/polisyos/scientist/nodes/builtins/causal/run_causal_contract_execution.py",
                "src/polisyos/scientist/nodes/builtins/causal/run_causal_readiness.py",
                "src/polisyos/scientist/nodes/builtins/data/bind_foundry_inputs.py",
                "src/polisyos/scientist/nodes/builtins/data/enrich_knowledge.py",
                "src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py",
                "src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py",
                "tests/unit/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py::test_run_hierarchical_policy_search_uses_branch_state_for_final_outputs",
                "src/polisyos/scientist/nodes/builtins/governance/legal_check.py",
                "tests/unit/scientist/nodes/test_legal_check_node.py::test_legal_check_uses_branch_state_for_inputs_and_reports",
                "src/polisyos/scientist/nodes/builtins/governance/data_plane_gate.py",
                "tests/unit/scientist/nodes/test_data_plane_gate_node.py::test_data_plane_gate_uses_branch_state_for_param_outputs",
                "src/polisyos/scientist/nodes/builtins/governance/run_governance.py",
                "tests/unit/scientist/nodes/test_run_governance_normative.py::test_run_governance_uses_branch_state_for_params_and_report",
                "src/polisyos/scientist/nodes/builtins/governance/run_normative_arbitration.py",
                "tests/unit/scientist/nodes/test_normative_arbitration_node.py::test_normative_arbitration_uses_branch_state_for_artifact_output",
                "src/polisyos/scientist/nodes/builtins/compile/compile_foundry.py",
                "tests/unit/scientist/nodes/builtins/compile/test_compile_foundry.py::test_compile_foundry_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/compile/link_trinity.py",
                "tests/unit/scientist/nodes/builtins/compile/test_link_trinity.py::test_link_trinity_uses_branch_state_for_report_output",
                "src/polisyos/scientist/nodes/builtins/compile/formalize_verified_policy.py",
                "tests/unit/scientist/nodes/builtins/compile/test_formalize_verified_policy.py::test_formalize_verified_policy_uses_branch_state_for_inputs_and_params",
                "src/polisyos/scientist/nodes/builtins/planning/run_preflight.py",
                "tests/unit/scientist/nodes/builtins/planning/test_run_preflight.py::test_preflight_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/run_evaluator.py",
                "tests/unit/scientist/nodes/builtins/planning/test_run_evaluator.py::test_evaluator_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/build_execution_plan.py",
                "tests/unit/scientist/nodes/builtins/planning/test_build_execution_plan.py::test_plan_builder_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/plan_policy_request.py",
                "tests/unit/scientist/nodes/builtins/planning/test_plan_policy_request.py::test_plan_policy_request_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/assemble_legal_candidate_pack.py",
                "tests/unit/scientist/nodes/builtins/planning/test_assemble_legal_candidate_pack.py::test_assemble_pack_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/expand_legal_source_pack.py",
                "tests/unit/scientist/nodes/builtins/planning/test_expand_legal_source_pack.py::test_expand_source_pack_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/run_source_verification.py",
                "tests/unit/scientist/nodes/builtins/planning/test_run_source_verification.py::test_source_verification_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/run_source_gap_review.py",
                "tests/unit/scientist/nodes/builtins/planning/test_run_source_gap_review.py::test_gap_review_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/draft_policy_options.py",
                "tests/unit/scientist/nodes/builtins/planning/test_draft_policy_options.py::test_draft_policy_options_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/data/build_data_snapshot.py",
                "tests/unit/scientist/nodes/builtins/data/test_build_data_snapshot.py::test_snapshot_builder_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/decide/build_verified_policy_report.py",
                "tests/unit/scientist/nodes/builtins/decide/test_build_verified_policy_report.py::test_verified_policy_report_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/decide/run_policy_translation.py",
                "tests/unit/scientist/nodes/builtins/decide/test_policy_translation.py::test_policy_translation_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/decide/run_translator_compliance.py",
                "tests/unit/scientist/nodes/builtins/decide/test_policy_translation.py::test_translator_compliance_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/build_method_catalog_snapshot.py",
                "tests/unit/scientist/nodes/builtins/planning/test_build_method_catalog_snapshot.py::test_method_catalog_snapshot_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/compile_cross_graph_evidence.py",
                "tests/unit/scientist/nodes/builtins/planning/test_compile_cross_graph_evidence.py::test_compilation_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/run_discovery_blueprint_runtime.py",
                "tests/unit/scientist/nodes/builtins/planning/test_run_discovery_blueprint_runtime.py::test_run_discovery_blueprint_runtime_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/decide/build_policy_output_bundle.py",
                "tests/unit/scientist/nodes/test_build_policy_output_bundle.py::test_build_policy_output_bundle_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/causal/resolve_parameters.py",
                "tests/unit/scientist/nodes/builtins/causal/test_resolve_parameters.py::test_resolve_parameters_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/causal/run_causal_queries.py",
                "tests/unit/scientist/nodes/builtins/causal/test_run_causal_queries.py::test_run_causal_queries_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/causal/run_abm_consistency.py",
                "tests/unit/scientist/nodes/builtins/causal/test_run_abm_consistency.py::test_run_abm_consistency_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/causal/resolve_transport.py",
                "tests/unit/scientist/nodes/builtins/causal/test_resolve_transport.py::test_run_transportability_uses_branch_state_for_skip_warning",
                "src/polisyos/scientist/nodes/builtins/causal/reconcile_causal_graph.py",
                "tests/unit/scientist/nodes/builtins/causal/test_reconcile_causal_graph.py::test_reconcile_causal_graph_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/causal/run_causal_ensemble.py",
                "tests/unit/scientist/nodes/builtins/causal/test_run_causal_ensemble.py::test_run_causal_ensemble_uses_branch_state_for_success_outputs",
                "src/polisyos/scientist/workflows/builder.py",
                "tests/unit/scientist/workflows/test_builder_pinning.py::test_workflow_runners_use_branch_local_snapshot_state",
                "tests/unit/scientist/workflows/test_builder_pinning.py::test_artifact_ref_or_none_assertion_is_not_swallowed",
                "src/polisyos/scientist/autotune/execution_plan.py",
                "tests/unit/scientist/autotune/test_execution_plan_autotune.py::test_with_topology_mutation_uses_branch_local_method_dag_clone",
                "src/polisyos/scientist/autotune/calibration.py",
                "tests/unit/scientist/autotune/test_calibration_autotune.py::test_apply_to_config_uses_branch_local_nested_model_clones",
                "src/polisyos/scientist/engine/runner/local_runner.py",
                "src/polisyos/scientist/engine/runner/protocol.py",
                "src/polisyos/scientist/engine/runner/ray_runner.py",
                "src/polisyos/scientist/engine/runner/temporal_runner.py",
                "src/polisyos/scientist/engine/runner/_activity_worker.py",
            ),
            ci_gates=(
                "pytest tests/unit/scientist/engine/test_fan_out.py tests/unit/scientist/engine/test_fan_out_async.py tests/unit/scientist/engine/test_checkpoint.py tests/integration/scientist/test_checkpoint_resume.py tests/unit/scientist/engine/runner/test_activity_worker.py tests/unit/scientist/engine/runner/test_serialization.py tests/unit/scientist/engine/runner/test_temporal_runner.py tests/unit/scientist/engine/runner/test_ray_runner.py tests/unit/scientist/engine/test_budget_middleware.py tests/unit/scientist/workflows/test_builder_pinning.py tests/unit/scientist/nodes/builtins/decide/test_policy_translation.py tests/unit/scientist/autotune/test_calibration_autotune.py -q",
                "python tools/ci/check_scientist_phase1_gate.py --benchmark-json _build/.tmp/test-reports/scientist-phase1-benchmarks.json --junit-xml _build/.tmp/test-reports/scientist-phase1.xml --output _build/.tmp/test-reports/scientist-phase1-gate.json --output-format json --require-passing",
            ),
            acceptance_signal=(
                "mutation, merge, resume, and deep-copy-removal regressions stay "
                "green under the dedicated Scientist Phase 1 barrier"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-1C",
            phase="Phase 1",
            title="Observability, metrics exporter and operational hygiene",
            status=RemediationStatusLevel.DONE,
            summary=(
                "OTel/Prometheus export, cross-runner trace correlation, DLQ "
                "replay, checkpoint GC retention, and runtime monitoring hooks "
                "now have direct operational evidence plus CI-generated scorecard "
                "artifacts."
            ),
            blocking_issues=(),
            evidence_refs=(
                "src/polisyos/scientist/engine/metrics.py",
                "src/polisyos/scientist/engine/metrics_otel.py",
                "src/polisyos/scientist/replay_backend.py",
                "src/polisyos/scientist/engine/operational_monitoring.py",
                "tests/unit/scientist/engine/test_reliability_operational_evidence.py",
                "tools/ci/check_scientist_reliability.py",
            ),
            ci_gates=(
                "pytest tests/unit/scientist/engine/test_reliability_operational_evidence.py -q",
                ".github/workflows/perf.yml",
            ),
            acceptance_signal=(
                "metrics export, trace correlation, replay, and bounded-retention "
                "checks pass in production-like runs"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-1D",
            phase="Phase 1",
            title="Test and benchmark program",
            status=RemediationStatusLevel.DONE,
            summary=(
                "Scientist now ships the required E2E scenario suite, benchmark "
                "coverage, CI benchmark artifacts, and a machine-readable "
                "reliability scorecard built from test evidence."
            ),
            blocking_issues=(),
            evidence_refs=(
                "tests/integration/scientist/test_workflow_reliability_scenarios.py",
                "tests/performance/test_scientist_runtime_paths.py",
                "src/polisyos/scientist/reliability_scorecard.py",
                "tests/tools/test_scientist_reliability_gate.py",
                "tools/ci/check_scientist_reliability.py",
            ),
            ci_gates=(
                "pytest tests/integration/scientist/test_workflow_reliability_scenarios.py -q",
                "pytest tests/performance/test_scientist_runtime_paths.py --benchmark-only -q",
                ".github/workflows/perf.yml",
            ),
            acceptance_signal=(
                "reliability scorecard passes with linked scenario, benchmark, "
                "and observability evidence"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-2A",
            phase="Phase 2",
            title="Hot-path memory, algorithmic complexity and cache efficiency",
            status=RemediationStatusLevel.DONE,
            summary=(
                "Hot-path state branching now stays copy-on-write across nested "
                "Pydantic payloads, prompt-cache entries are stored as stable "
                "serialized snapshots, Pareto/cross-graph discovery paths use "
                "lower-overhead cached primitives, and dedicated runtime-path "
                "benchmarks now cover the closure budget."
            ),
            blocking_issues=(),
            evidence_refs=(
                "src/polisyos/scientist/engine/state_branching.py",
                "tests/unit/scientist/engine/test_state_branching.py::test_branch_state_uses_copy_on_write_overlay_for_nested_pydantic_models",
                "src/polisyos/scientist/llm/prompt_cache.py",
                "tests/unit/scientist/llm/test_prompt_cache.py",
                "tests/unit/scientist/engine/test_engine_executor_v0.py::test_executor_branch_state_isolates_declared_nested_writes",
                "src/polisyos/scientist/autotune/pareto.py",
                "tests/unit/scientist/autotune/test_pareto.py",
                "src/polisyos/scientist/cross_graph/alignment.py",
                "src/polisyos/scientist/cross_graph/compiler.py",
                "tests/performance/test_scientist_runtime_paths.py::test_scientist_autotune_pareto_front_hot_path",
                "tests/performance/test_scientist_runtime_paths.py::test_scientist_prompt_cache_hit_hot_path",
            ),
            ci_gates=(
                "pytest tests/unit/scientist/engine/test_state_branching.py -q",
                "pytest tests/unit/scientist/llm/test_prompt_cache.py -q",
                "pytest tests/unit/scientist/autotune/test_pareto.py -q",
                "pytest tests/performance/test_scientist_runtime_paths.py -q",
            ),
            acceptance_signal=(
                "runtime-path benchmarks and copy-on-write regressions stay green "
                "without reintroducing deep-copy hot paths"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-2B",
            phase="Phase 2",
            title="API simplification, module decomposition and type safety",
            status=RemediationStatusLevel.DONE,
            summary=(
                "Phase 2 helper extractions now split cached alignment, feedback "
                "normalization, policy-runtime state handling, threshold "
                "registry logic, and decision-packet replay assembly out of the "
                "largest change-magnet modules, while a CI ratchet blocks new "
                "`Any`, unsafe `cast()`, and raw `dict[...]` growth on the "
                "targeted Scientist surfaces."
            ),
            blocking_issues=(),
            evidence_refs=(
                "src/polisyos/ir/analytics/__init__.py",
                "tests/unit/scientist/facade/test_import_boundaries.py",
                "src/polisyos/scientist/cross_graph/alignment.py",
                "src/polisyos/scientist/cross_graph/compiler.py",
                "src/polisyos/scientist/feedback_utils.py",
                "src/polisyos/scientist/feedback.py",
                "src/polisyos/scientist/search/judge_thresholds.py",
                "src/polisyos/scientist/search/judge_stack.py",
                "tests/unit/scientist/search/test_judge_thresholds.py",
                "tests/unit/scientist/search/test_judge_stack_imports.py",
                "src/polisyos/scientist/nodes/builtins/decide/decision_packet_support.py",
                "src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py",
                "src/polisyos/scientist/nodes/builtins/decide/policy_runtime_state.py",
                "src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py",
                "tests/unit/scientist/nodes/test_decision_packet_node_v3.py",
                "src/polisyos/foundry/validation/phase2_closure.py",
                "tools/quality/validation/foundry_phase2_manifest.json",
                "tools/quality/validation/validate_foundry_phase2_closure.py",
                "tools/quality/validation/generate_foundry_phase2_evidence.py",
                "tools/quality/validation/run_foundry_phase2_validation.sh",
                "docs/reference/foundry/phase2-acceptance.md",
                "tools/ci/check_scientist_phase2_ratchet.py",
                "tools/ci/check_scientist_phase2_gate.py",
                "tools/ci/scientist_phase2_ratchet_baseline.toml",
                "tests/unit/foundry/validation/test_phase2_closure.py",
                "tests/unit/foundry/validation/test_phase2_judge_stack.py",
                "tests/tools/test_scientist_phase2_gate.py",
                "tests/tools/test_scientist_phase2_ratchet.py",
                ".github/workflows/arch.yml",
                ".github/workflows/foundry-release-gate.yml",
            ),
            ci_gates=(
                "pytest tests/unit/scientist/facade/test_import_boundaries.py -q",
                "pytest tests/unit/scientist/engine/test_feedback_runtime.py -q",
                "pytest tests/unit/scientist/search/test_policy_blueprint_runtime_guards.py -q",
                "pytest tests/unit/foundry/validation/test_phase2_closure.py -q",
                "pytest tests/unit/foundry/validation/test_phase2_judge_stack.py -q",
                "pytest tests/tools/test_scientist_phase2_gate.py -q",
                "pytest tests/tools/test_scientist_phase2_ratchet.py -q",
                "bash tools/quality/validation/run_foundry_phase2_validation.sh",
                "python tools/ci/check_scientist_phase2_gate.py --junit-xml phase2.xml --benchmark-json phase2-benchmarks.json --evidence-json phase2-evidence.json",
                "python tools/ci/check_scientist_phase2_ratchet.py",
            ),
            acceptance_signal=(
                "modular extractions hold, the Phase 2 debt counters never "
                "grow above the tracked baseline, and the canonical Phase 2 "
                "closure validator plus compatibility gate block promotion "
                "until every enrolled frontier track has complete evidence"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-3A",
            phase="Phase 3",
            title="Causal inference and statistical validity",
            status=RemediationStatusLevel.DONE,
            summary=(
                "The default-path causal-validity bundle now ships shared "
                "confidence and sensitivity sections, synthetic/semi-synthetic "
                "eval-pack evidence, and explicit capability statuses so "
                "frontier causal methods stay honest and non-default."
            ),
            blocking_issues=(),
            evidence_refs=(
                "docs/reference/scientist/causal-validity.md",
                "docs/reference/scientist/causal-validity-acceptance.md",
                "docs/reference/scientist/phase3-acceptance.md",
                "src/polisyos/scientist/causal/validity.py",
                "tests/unit/scientist/causal/test_causal_evaluation_node.py",
                "tests/unit/scientist/nodes/test_decision_packet_node_v3.py",
                "tests/unit/foundry/methods/catalog/causal/test_validity_eval_pack.py",
            ),
            ci_gates=(
                "pytest tests/unit/scientist/causal/test_causal_evaluation_node.py -q",
                "pytest tests/unit/scientist/nodes/test_decision_packet_node_v3.py -q",
                "pytest tests/unit/foundry/methods/catalog/causal/test_validity_eval_pack.py -q",
            ),
            acceptance_signal=(
                "default-path validity bundle and offline benchmark pack agree "
                "on confidence, sensitivity, and explicit capability-status outputs"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-3B",
            phase="Phase 3",
            title="Governance, fairness, calibration and accountability",
            status=RemediationStatusLevel.DONE,
            summary=(
                "Calibration validation now emits a unified accountability "
                "artifact with fairness, calibration, adaptive thresholds, "
                "tail-risk, model-card, datasheet, and escalation evidence, "
                "plus explicit gaps when probabilistic support is incomplete."
            ),
            blocking_issues=(),
            evidence_refs=(
                "docs/reference/scientist/governance-accountability.md",
                "docs/reference/scientist/calibration-governance.md",
                "docs/reference/scientist/phase3-acceptance.md",
                "src/polisyos/scientist/governance/accountability.py",
                "src/polisyos/scientist/governance/calibration_validation.py",
                "tests/unit/scientist/governance/test_accountability.py",
                "tests/unit/scientist/governance/test_calibration_validation.py",
                "tests/unit/scientist/nodes/test_build_policy_output_bundle.py",
                "tests/ukraine_data/test_builders.py",
            ),
            ci_gates=(
                "pytest tests/unit/scientist/governance/test_accountability.py -q",
                "pytest tests/unit/scientist/governance/test_calibration_validation.py -q",
                "pytest tests/unit/scientist/nodes/test_build_policy_output_bundle.py -q",
                "pytest tests/ukraine_data/test_builders.py -q",
            ),
            acceptance_signal=(
                "governance artifact publishes calibration, fairness, threshold, "
                "escalation, and tail-risk evidence together"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-3C",
            phase="Phase 3",
            title="Search, optimization and agent reasoning",
            status=RemediationStatusLevel.DONE,
            summary=(
                "Supervisor DAG execution, ToT/LATS, advanced search policies, "
                "and candidate-vs-baseline evaluation now ship explicit "
                "offline-gate, release-gate, and default-enable rollout "
                "statuses before any non-default reasoning policy can be enabled."
            ),
            blocking_issues=(),
            evidence_refs=(
                "docs/reference/scientist/agent-search-reasoning.md",
                "docs/reference/scientist/phase3-acceptance.md",
                "src/polisyos/scientist/agent/reasoning.py",
                "src/polisyos/scientist/agent/eval_harness.py",
                "src/polisyos/scientist/search/strategies/advanced_policy.py",
                "src/polisyos/scientist/frontier_runtime.py",
                "tests/unit/scientist/agent/test_reasoning.py",
                "tests/unit/scientist/agent/test_eval_harness.py",
                "tests/unit/scientist/search/strategies/test_advanced_policy.py",
                "tests/unit/scientist/search/test_frontier_runtime.py",
            ),
            ci_gates=(
                "pytest tests/unit/scientist/agent/test_reasoning.py -q",
                "pytest tests/unit/scientist/agent/test_eval_harness.py -q",
                "pytest tests/unit/scientist/search/strategies/test_advanced_policy.py -q",
                "pytest tests/unit/scientist/search/test_frontier_runtime.py -q",
            ),
            acceptance_signal=(
                "offline evaluation harness proves advanced policies beat or "
                "safely complement the Reflexion baseline and every rollout "
                "decision stays machine-readable"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-4A",
            phase="Phase 4",
            title="Runtime scalability and distributed safety",
            status=RemediationStatusLevel.DONE,
            summary=(
                "Incremental checkpoints are now the canonical persisted path, "
                "fail-fast rollback emits saga compensation hooks, and the "
                "shared budget ledger publishes a canonical multi-host writer "
                "contract with bounded mutation retention and explicit writer "
                "provenance across resumed distributed execution."
            ),
            blocking_issues=(),
            evidence_refs=(
                "docs/reference/scientist/phase4-acceptance.md",
                "src/polisyos/scientist/engine/checkpoint.py",
                "src/polisyos/scientist/engine/budget_ledger.py",
                "src/polisyos/scientist/engine/compensation.py",
                "tests/unit/scientist/engine/test_checkpoint.py::test_incremental_checkpoint_materializes_full_state",
                "tests/unit/scientist/engine/test_checkpoint.py::test_checkpoint_hook_gc_failure_does_not_rollback_commit_bookkeeping",
                "tests/integration/scientist/test_checkpoint_resume.py",
                "tests/unit/scientist/engine/test_async_executor_hardening.py::TestTierSavepoints::test_rollback_compensation_hook_receives_fail_fast_event",
                "tests/unit/scientist/engine/test_budget_middleware.py",
                "tests/unit/scientist/engine/runner/test_temporal_runner.py",
                "tests/unit/scientist/engine/runner/test_ray_runner.py",
                "tests/unit/scientist/engine/runner/test_distributed_tier.py",
            ),
            ci_gates=(
                "pytest tests/unit/scientist/engine/test_budget_middleware.py -q",
                "pytest tests/unit/scientist/engine/test_checkpoint.py tests/integration/scientist/test_checkpoint_resume.py -q",
                "pytest tests/unit/scientist/engine/test_async_executor_hardening.py tests/unit/scientist/engine/runner/test_temporal_runner.py tests/unit/scientist/engine/runner/test_ray_runner.py tests/unit/scientist/engine/runner/test_distributed_tier.py -q",
            ),
            acceptance_signal=(
                "distributed failure matrix proves replay-safe recovery across "
                "incremental checkpointing, multi-host ledger mutations, saga "
                "rollback, and multi-runner resume paths"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-4B",
            phase="Phase 4",
            title="Frontier research backlog",
            status=RemediationStatusLevel.DONE,
            summary=(
                "Frontier capabilities now publish a machine-readable rollout "
                "matrix and resolve promotion evidence through the benchmark "
                "registry contract, so disabled, offline-gated, available-offline, "
                "and unwired methods stay explicit instead of leaking through "
                "ad hoc runtime params."
            ),
            blocking_issues=(),
            evidence_refs=(
                "docs/reference/scientist/phase4-acceptance.md",
                "docs/reference/scientist/frontier-runtime.md",
                "src/polisyos/scientist/frontier_runtime.py",
                "src/polisyos/scientist/search/benchmark_registry.py",
                "src/polisyos/scientist/search/registry_contracts.py",
                "src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py",
                "tests/unit/scientist/search/test_benchmark_registry.py",
                "tests/unit/scientist/search/test_frontier_runtime.py",
            ),
            ci_gates=(
                "pytest tests/unit/scientist/search/test_frontier_runtime.py -q",
                "pytest tests/unit/scientist/search/test_benchmark_registry.py -q",
            ),
            acceptance_signal=(
                "every frontier capability exposes status, flag, benchmark pack, "
                "offline validation ref, and baseline-replacement posture "
                "through the shared runtime and benchmark registry contracts"
            ),
        ),
    )

    phase_rollups = tuple(
        _build_phase_rollup(phase, phase_workstreams)
        for phase, phase_workstreams in (
            ("Phase 0", tuple(item for item in workstreams if item.phase == "Phase 0")),
            ("Phase 1", tuple(item for item in workstreams if item.phase == "Phase 1")),
            ("Phase 2", tuple(item for item in workstreams if item.phase == "Phase 2")),
            ("Phase 3", tuple(item for item in workstreams if item.phase == "Phase 3")),
            ("Phase 4", tuple(item for item in workstreams if item.phase == "Phase 4")),
        )
    )
    overall_status = _rollup_status(item.status for item in workstreams)

    return ScientistRemediationStatusReport(
        schema_version="1.0",
        assessment_id="gate0_closure",
        strict_definition_of_done=True,
        overall_status=overall_status,
        phase_rollups=phase_rollups,
        workstreams=workstreams,
        notes=(
            "This report is the repo-tracked closure view for the Scientist remediation plan.",
            "Phase 0 and Phase 1 are accepted only through the dedicated scientist-phase0-gate and scientist-phase1-gate CI barriers.",
            "Phase 2 now also requires the dedicated scientist-phase2-gate closure barrier; Phase 3 and Phase 4 remain subject to the same strict evidence and CI discipline.",
        ),
    )


def _build_phase_rollup(
    phase: str,
    workstreams: tuple[ScientistWorkstreamStatus, ...],
) -> ScientistPhaseStatus:
    status = _rollup_status(item.status for item in workstreams)
    if status == RemediationStatusLevel.DONE:
        summary = (
            f"{phase} is accepted under strict DoD accounting with repo-tracked "
            "code, regression tests, docs, observable acceptance signals, and "
            "CI coverage."
        )
    else:
        summary = (
            f"{phase} remains open under strict DoD accounting until every "
            "workstream in the phase has code, regression tests, docs, "
            "observable acceptance signals, and CI coverage."
        )
    return ScientistPhaseStatus(
        phase=phase,
        status=status,
        workstream_ids=tuple(item.workstream_id for item in workstreams),
        summary=summary,
    )


def _rollup_status(statuses: Iterable[RemediationStatusLevel]) -> RemediationStatusLevel:
    normalized = tuple(statuses)
    if normalized and all(item == RemediationStatusLevel.DONE for item in normalized):
        return RemediationStatusLevel.DONE
    if normalized and all(item == RemediationStatusLevel.MISSING for item in normalized):
        return RemediationStatusLevel.MISSING
    return RemediationStatusLevel.PARTIAL
