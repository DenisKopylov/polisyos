"""Machine-readable Scientist remediation status report.

This module provides a repo-tracked Gate 0 baseline for
`SCIENTIST_AUDIT_REMEDIATION_PLAN.md`. The report is intentionally strict:
workstreams remain `partial` until their own Definition of Done is backed by
code, regression coverage, docs, observable evidence, and CI gates.
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

    The baseline is deliberately conservative. Existing partial implementations
    are marked `partial` until the remediation plan's own exit criteria are met.
    """

    workstreams = (
        ScientistWorkstreamStatus(
            workstream_id="WS-0A",
            phase="Phase 0",
            title="Async, locking and lifecycle correctness",
            status=RemediationStatusLevel.PARTIAL,
            summary=(
                "Critical async/lifecycle hardening landed across runners, pools, "
                "locks, verifier paths, and retry timeout workers. Lock "
                "liveness/stale probes plus heartbeat extension failures now "
                "emit typed degraded envelopes instead of broad swallowing, and "
                "the forked timeout worker no longer masks `SystemExit`/other "
                "non-runtime control flow. Local worker-pool execution now also "
                "surfaces typed worker runtime failures through its future "
                "contract instead of broad pool wrappers. The file-based fcntl "
                "lock backend and lock-metrics acquire wrapper also now avoid "
                "direct broad handlers. The remaining blocker is not lack of "
                "code, but incomplete full-matrix acceptance evidence."
            ),
            blocking_issues=(
                "phase0_acceptance_not_signed_off",
                "full_fault_injection_matrix_incomplete",
            ),
            evidence_refs=(
                "src/polisyos/scientist/engine/retry.py",
                "tests/scientist/engine/test_retry.py::test_timeout_worker_does_not_swallow_system_exit",
                "src/polisyos/scientist/engine/runner/local_pool.py",
                "tests/scientist/engine/runner/test_worker_pool.py::test_worker_runtime_error_surfaces_on_future",
                "src/polisyos/scientist/engine/locks/fcntl_lock.py",
                "tests/scientist/engine/locks/test_fcntl_lock.py",
                "src/polisyos/scientist/engine/locks/metrics.py",
                "tests/scientist/engine/locks/test_lock_metrics.py::test_measure_acquire_does_not_swallow_assertion_errors",
                "src/polisyos/scientist/engine/locks/dynamodb_lock.py",
                "tests/scientist/engine/locks/test_dynamodb_lock.py::test_detect_stale_runtime_probe_error_returns_false",
                "tests/scientist/engine/locks/test_dynamodb_lock.py::test_is_alive_runtime_probe_error_returns_false",
                "src/polisyos/scientist/engine/locks/redis_lock.py",
                "tests/scientist/engine/locks/test_redis_lock.py::test_is_alive_returns_false_on_runtime_probe_error",
                "tests/scientist/engine/locks/test_redis_lock.py::test_detect_stale_returns_false_on_runtime_probe_error",
                "tests/scientist/test_code_verifier.py",
            ),
            ci_gates=("pytest tests/scientist -q",),
            acceptance_signal=(
                "fault-injection, stress, and teardown tests prove no permit drift "
                "or orphan resources"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-0B",
            phase="Phase 0",
            title="Budget, request correctness, security and scientific hotfixes",
            status=RemediationStatusLevel.PARTIAL,
            summary=(
                "Idempotency, reservation accounting, masking, environment "
                "sanitization, and several statistical hotfixes landed. "
                "Fallback-router endpoint failure handling now emits structured "
                "degraded envelopes instead of broad swallowing, and provider "
                "verification artifact/check handling now uses typed load/parse "
                "errors. The remaining blocker is the incomplete statistical "
                "and Phase 0 acceptance ledger."
            ),
            blocking_issues=(
                "phase0_acceptance_not_signed_off",
                "full_statistical_regression_pack_incomplete",
            ),
            evidence_refs=(
                "src/polisyos/scientist/llm/gateway_client.py",
                "src/polisyos/scientist/llm/fallback_router.py",
                "tests/scientist/llm/test_fallback_router.py::test_failover_emits_degraded_path",
                "tests/scientist/llm/test_fallback_router.py::test_keyboard_interrupt_is_not_swallowed",
                "src/polisyos/scientist/llm/provider_verification.py",
                "tests/scientist/llm/test_provider_verification.py::test_load_provider_verification_invalid_json_returns_none",
                "tests/scientist/llm/test_provider_verification.py::test_run_named_check_does_not_swallow_assertion_errors",
                "src/polisyos/scientist/llm/budget_enforcer.py",
                "src/polisyos/scientist/backtesting/bootstrap.py",
                "src/polisyos/scientist/adapters/foundry_bridge.py",
            ),
            ci_gates=("pytest tests/scientist/test_idempotency.py -q",),
            acceptance_signal=(
                "retry/idempotency, budget, masking, and statistics regressions "
                "stay green"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-1A",
            phase="Phase 1",
            title="Error semantics and degraded-mode policy",
            status=RemediationStatusLevel.PARTIAL,
            summary=(
                "Governance pass failures now emit a structured degraded-path "
                "error envelope, and executor cache/provenance degradation paths "
                "use the shared helper. Tool-loop budget and memory degradation "
                "is carried in result artifacts, including malformed tool-call "
                "argument parsing. Corrupted local checkpoint metadata now raises "
                "typed checkpoint errors, model catalog parsing now degrades "
                "to an observable empty fallback, and decision-packet artifact "
                "load failures are now recorded as structured degraded paths, "
                "including deeper helper sections such as normative arbitration, "
                "sensitivity fallback parsing, decision-validity basis loading, "
                "and derived uncertainty-bound assembly. Sync executor cache "
                "write and provenance-recording degradation now also surface "
                "operator-visible warning events instead of log-only swallow, "
                "and sync/async node bind failures now surface typed "
                "`node.bind_failed` results instead of silently executing "
                "unbound nodes. "
                "Fan-out item bind failures now also fail the item without "
                "executing an inconsistently bound task node. "
                "CAS manifest identity checks now normalize cross-boundary "
                "ArtifactID wire values, restoring decision-packet artifact "
                "loads that previously degraded spuriously. Shared strategic "
                "runtime helpers now narrow live decision-runtime broad "
                "handlers to typed degraded paths, including invalid-input and "
                "persistence-failure summaries with structured envelopes. "
                "Optional policy-output artifact loads now also degrade into "
                "warning events instead of aborting the bundle build when "
                "distributional, uncertainty, stress, cross-graph, or "
                "calibration artifacts are unreadable, but broad exception "
                "swallowing still remains in other decision paths. Governance "
                "pass registry helpers also now use typed entrypoint/provider "
                "load errors instead of broad wrappers. Shared governance "
                "artifact resolution now normalizes CAS `ArtifactRef` payloads "
                "into typed IR refs, restoring integrated normative "
                "arbitration blocker/warning propagation, and "
                "`run_governance` helper loads now emit structured degraded "
                "envelopes for policy-summary, metrics-preview, transport, "
                "PII snapshot, and normative-result read failures. Strict human "
                "review graph resolution now emits a typed warning instead of "
                "silently dropping invalid causal-graph payloads, normative "
                "arbitration helper loads now emit structured degraded "
                "envelopes for invalid Trinity/metrics/simulation/distributional/"
                "legal artifacts, `legal_check` now degrades unreadable legal "
                "report grades into explicit warning events instead of helper-"
                "local swallowing while normalizing `simulation_result_ref` to "
                "its typed contract, `data_plane_gate` now emits structured "
                "warning events for broken quality-report loads instead of "
                "debug-only fallback, a remaining decision helper now "
                "narrows artifact-ref validation to typed errors, and "
                "distributed runtime helpers now replace their old broad "
                "worker/serialization/Temporal fallbacks with typed degraded "
                "paths for invalid registry refs, trace-context restore/read/"
                "inject failures, Temporal health/probe failures, Ray trace "
                "carrier/probe failures, fallback-runner primary-execution "
                "degradation, and checkpoint-hook runtime metadata validation. "
                "Core executor and fan-out slices now also replace their "
                "remaining broad runtime handlers with typed runtime-error "
                "groups, while builtin tracing and governance-pipeline "
                "helpers now narrow OTel access and validator-pass execution "
                "to typed failure envelopes instead of catch-all wrappers. "
                "Retry wrappers now narrow retry/dead-letter/runtime-worker "
                "handling to typed runtime groups without masking "
                "`SystemExit`, fallback-router endpoint failover now emits "
                "degraded envelopes instead of broad routing catches, provider "
                "verification no longer hides malformed artifacts or smoke-check "
                "runtime failures behind broad handlers, and lock backends now "
                "emit typed degraded probe/heartbeat failures instead of "
                "silently returning stale defaults. Async executor runtime "
                "fallback now also uses the shared typed runtime group instead "
                "of a direct broad catch, node-registry bootstrap now records "
                "typed provider creation failures while letting assertion-style "
                "programmer errors surface, telemetry span helpers now degrade "
                "through structured envelopes instead of silent catch-all "
                "wrappers, and local worker-pool execution now surfaces typed "
                "worker runtime failures through futures without a broad pool "
                "catch. The builtin data-snapshot helper now also degrades "
                "snapshot PII-summary read/validation failures through a "
                "structured envelope instead of a broad helper swallow. "
                "Planning/causal builtins like `run_preflight`, "
                "`run_evaluator`, `build_execution_plan`, "
                "`resolve_parameters`, `run_causal_queries`, "
                "`compile_cross_graph_evidence`, "
                "`run_discovery_blueprint_runtime`, "
                "`run_abm_consistency`, and `run_causal_ensemble` now also "
                "narrow helper/runtime validation to typed groups while "
                "surfacing degraded fallback warnings instead of silent "
                "defaults. `reconcile_causal_graph` and "
                "`resolve_transport` now also narrow graph/fragment/"
                "transport helper parsing and artifact-loading paths to typed "
                "validation/load groups without swallowing assertion-style "
                "failures, and simulate builtins like "
                "`propagate_uncertainty` and `run_distributional_analysis` now "
                "replace their remaining broad helper catches with typed "
                "degraded behavior while removing `deep=True` state clones "
                "from their artifact-write paths. The next causal/data/"
                "planning/simulate tranche now also narrows task/readiness/"
                "binding/search/simulation helper contracts in "
                "`run_causal_contract_execution`, `run_causal_readiness`, "
                "`bind_foundry_inputs`, `enrich_knowledge`, "
                "`run_hierarchical_policy_search`, `run_causal_evaluation`, "
                "and `run_simulation`, including invalid output payload "
                "handling for causal/simulation artifacts and explicit "
                "non-swallowing of assertion-style failures."
            ),
            blocking_issues=(
                "broad_exception_handlers_remain",
                "degraded_path_metrics_not_universal",
            ),
            evidence_refs=(
                "src/polisyos/scientist/governance/pipeline.py",
                "tests/scientist/governance/test_validation_pipeline.py::test_failing_pass_returns_structured_error_envelope",
                "src/polisyos/scientist/engine/retry.py",
                "tests/scientist/engine/test_retry.py::test_timeout_worker_does_not_swallow_system_exit",
                "src/polisyos/scientist/engine/locks/redis_lock.py",
                "tests/scientist/engine/locks/test_redis_lock.py::test_is_alive_returns_false_on_runtime_probe_error",
                "tests/scientist/engine/locks/test_redis_lock.py::test_detect_stale_returns_false_on_runtime_probe_error",
                "src/polisyos/scientist/engine/locks/dynamodb_lock.py",
                "tests/scientist/engine/locks/test_dynamodb_lock.py::test_detect_stale_runtime_probe_error_returns_false",
                "tests/scientist/engine/locks/test_dynamodb_lock.py::test_is_alive_runtime_probe_error_returns_false",
                "src/polisyos/scientist/engine/executor.py",
                "src/polisyos/scientist/engine/async_executor.py",
                "tests/scientist/engine/test_async_executor_hardening.py::test_runtime_lookup_failure_becomes_typed_node_error",
                "src/polisyos/scientist/engine/registry.py",
                "tests/scientist/test_node_registry_components_bootstrap.py::test_discover_nodes_records_typed_runtime_provider_error",
                "tests/scientist/test_node_registry_components_bootstrap.py::test_discover_nodes_does_not_swallow_assertion_errors",
                "src/polisyos/scientist/engine/telemetry.py",
                "tests/scientist/engine/test_telemetry.py::test_start_node_span_runtime_error_degrades",
                "tests/scientist/engine/test_telemetry.py::test_set_span_attribute_runtime_error_degrades",
                "tests/scientist/engine/test_telemetry.py::test_add_span_events_runtime_error_degrades",
                "src/polisyos/scientist/engine/runner/local_pool.py",
                "tests/scientist/engine/runner/test_worker_pool.py::test_worker_runtime_error_surfaces_on_future",
                "src/polisyos/scientist/nodes/builtins/data/build_data_snapshot.py",
                "tests/scientist/nodes/builtins/data/test_build_data_snapshot.py::test_snapshot_pii_summary_load_failure_degrades",
                "src/polisyos/scientist/nodes/builtins/planning/run_preflight.py",
                "tests/scientist/nodes/builtins/planning/test_run_preflight.py::test_preflight_invalid_input_load_returns_typed_fail",
                "src/polisyos/scientist/nodes/builtins/planning/run_evaluator.py",
                "tests/scientist/nodes/builtins/planning/test_run_evaluator.py::test_evaluator_invalid_governance_report_emits_warning",
                "tests/scientist/nodes/builtins/planning/test_run_evaluator.py::test_evaluator_transition_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/planning/build_execution_plan.py",
                "tests/scientist/nodes/builtins/planning/test_build_execution_plan.py::test_plan_from_raw_dict_fallback",
                "tests/scientist/nodes/builtins/planning/test_build_execution_plan.py::test_plan_invalid_data_needs_emit_warning",
                "src/polisyos/scientist/nodes/builtins/causal/resolve_parameters.py",
                "tests/scientist/nodes/builtins/causal/test_resolve_parameters.py::test_target_context_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/causal/run_causal_queries.py",
                "tests/scientist/nodes/builtins/causal/test_run_causal_queries.py::test_causal_query_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/planning/compile_cross_graph_evidence.py",
                "tests/scientist/nodes/builtins/planning/test_compile_cross_graph_evidence.py::test_compilation_target_context_assertion_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/planning/run_discovery_blueprint_runtime.py",
                "tests/scientist/nodes/builtins/planning/test_run_discovery_blueprint_runtime.py::test_resolve_causal_query_assertion_is_not_swallowed",
                "tests/scientist/nodes/builtins/planning/test_run_discovery_blueprint_runtime.py::test_measure_seed_reproducibility_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/causal/run_abm_consistency.py",
                "tests/scientist/nodes/builtins/causal/test_run_abm_consistency.py::test_abm_mapping_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/causal/run_causal_ensemble.py",
                "tests/scientist/nodes/builtins/causal/test_run_causal_ensemble.py::test_causal_ensemble_member_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/causal/reconcile_causal_graph.py",
                "tests/scientist/nodes/builtins/causal/test_reconcile_causal_graph.py::test_reconcile_fragment_load_assertion_is_not_swallowed",
                "tests/scientist/nodes/builtins/causal/test_reconcile_causal_graph.py::test_reconcile_literature_prior_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/causal/resolve_transport.py",
                "tests/scientist/nodes/builtins/causal/test_resolve_transport.py::test_run_transportability_report_assertion_is_not_swallowed",
                "tests/scientist/nodes/builtins/causal/test_resolve_transport.py::test_build_skg_query_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py",
                "tests/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py::test_collect_input_envelopes_snapshot_assertion_is_not_swallowed",
                "tests/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py::test_load_config_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/simulate/run_distributional_analysis.py",
                "tests/scientist/nodes/builtins/simulate/test_run_distributional_analysis.py::test_resolve_baseline_snapshot_ref_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/causal/run_causal_contract_execution.py",
                "tests/scientist/nodes/builtins/causal/test_run_causal_contract_execution.py::test_run_causal_contract_execution_task_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/causal/run_causal_readiness.py",
                "tests/scientist/nodes/builtins/causal/test_run_causal_readiness.py::test_run_causal_readiness_graph_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/data/bind_foundry_inputs.py",
                "tests/scientist/test_bind_foundry_inputs_node.py::test_bind_foundry_inputs_build_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/data/enrich_knowledge.py",
                "tests/scientist/test_enrich_knowledge_node_freshness.py::test_enrich_node_scholar_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py",
                "tests/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py::test_run_hierarchical_policy_search_adapter_assertion_is_not_swallowed",
                "src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py",
                "tests/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py::test_assertion_in_observational_data_load_is_not_swallowed",
                "tests/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py::test_fail_when_method_output_report_is_invalid",
                "src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py",
                "tests/scientist/nodes/builtins/simulate/test_run_simulation.py::test_run_simulation_result_assertion_is_not_swallowed",
                "src/polisyos/scientist/agent/tools/tool_loop.py",
                "tests/scientist/agent/tools/test_tool_loop.py::test_budget_probe_failure_is_reported_as_degraded_event",
                "tests/scientist/agent/tools/test_tool_loop.py::test_persistent_memory_recall_failure_is_reported_as_degraded_event",
                "tests/scientist/agent/tools/test_tool_loop.py::test_malformed_arguments_json",
                "src/polisyos/scientist/engine/checkpoint.py",
                "tests/scientist/test_checkpoint.py::test_checkpoint_head_invalid_json_raises_typed_error",
                "tests/scientist/test_checkpoint.py::test_checkpoint_history_invalid_json_raises_typed_error",
                "src/polisyos/scientist/llm/gateway_client.py",
                "tests/scientist/llm/test_gateway_client_retry.py::test_list_model_ids_invalid_json_degrades_to_empty_list",
                "tests/scientist/llm/test_gateway_client_retry.py::test_list_model_ids_invalid_shape_degrades_to_empty_list",
                "src/polisyos/scientist/llm/fallback_router.py",
                "tests/scientist/llm/test_fallback_router.py::test_failover_emits_degraded_path",
                "tests/scientist/llm/test_fallback_router.py::test_keyboard_interrupt_is_not_swallowed",
                "src/polisyos/scientist/llm/provider_verification.py",
                "tests/scientist/llm/test_provider_verification.py::test_load_provider_verification_invalid_json_returns_none",
                "tests/scientist/llm/test_provider_verification.py::test_run_named_check_does_not_swallow_assertion_errors",
                "tests/scientist/test_decision_packet_node_v3.py::test_build_decision_packet_records_degraded_paths_for_invalid_metrics_and_governance",
                "tests/scientist/test_decision_packet_node_v3.py::test_build_decision_packet_records_degraded_paths_for_invalid_decision_basis_quality_report",
                "tests/scientist/test_decision_packet_node_v3.py::test_build_decision_packet_records_degraded_paths_for_invalid_normative_arbitration",
                "tests/scientist/test_decision_packet_node_v3.py::test_build_decision_packet_records_degraded_paths_for_invalid_sensitivity_artifact",
                "tests/scientist/test_decision_packet_node_v3.py::test_build_decision_packet_records_degraded_paths_for_invalid_uncertainty_output_envelope",
                "tests/scientist/test_policy_verified_nodes.py::test_build_decision_packet_records_degraded_paths_for_invalid_policy_verification_artifacts",
                "tests/scientist/nodes/test_build_policy_output_bundle.py::test_decision_packet_records_degraded_path_for_invalid_policy_bundle",
                "tests/scientist/test_engine_executor_v0.py::test_executor_logs_cache_write_bypass_as_node_event",
                "tests/scientist/test_engine_executor_v0.py::test_executor_logs_provenance_recording_degraded_as_node_event",
                "tests/scientist/test_engine_executor_v0.py::test_executor_reports_bind_failure_as_typed_node_error",
                "tests/scientist/test_engine_executor_v0.py::test_executor_reports_lookup_runtime_failure_as_typed_node_error",
                "tests/scientist/engine/test_async_executor_hardening.py::test_bind_failure_becomes_typed_node_error",
                "tests/scientist/engine/test_fan_out.py::test_bind_failure_stops_without_executing_item_when_fail_fast",
                "tests/scientist/engine/test_fan_out.py::test_summary_persist_failure_emits_degraded_event",
                "tests/scientist/engine/test_fan_out_async.py::test_async_bind_failure_stops_without_executing_item_when_fail_fast",
                "tests/scientist/engine/test_fan_out_async.py::test_async_summary_persist_failure_emits_degraded_event",
                "tests/core/phase0/test_artifact_store.py::test_filesystem_cas_accepts_ir_artifact_id_roundtrip",
                "tests/scientist/search/test_policy_blueprint_runtime_guards.py::test_runtime_strategic_helper_invalid_input_records_degraded_path",
                "tests/scientist/search/test_policy_blueprint_runtime_guards.py::test_runtime_strategic_helper_persistence_failure_records_degraded_path",
                "tests/scientist/nodes/test_build_policy_output_bundle.py::test_build_policy_output_bundle_degrades_invalid_distributional_report",
                "tests/scientist/nodes/test_build_policy_output_bundle.py::test_build_policy_output_bundle_degrades_invalid_uncertainty_envelope",
                "tests/scientist/governance/test_pass_registry.py::test_load_governance_passes_wraps_entry_point_load_error",
                "tests/scientist/test_run_governance_normative.py::test_run_governance_rejects_on_explicit_normative_right_violation",
                "tests/scientist/test_run_governance_normative.py::test_run_governance_marks_needs_revision_when_policy_prefers_baseline",
                "tests/scientist/test_run_governance_normative.py::test_run_governance_keeps_warning_only_for_partial_model_when_proposal_selected",
                "tests/scientist/governance/test_normative_arbitration_pass.py::test_normative_arbitration_invalid_payload_emits_warning",
                "tests/scientist/governance/test_human_review_pass.py::test_human_review_invalid_graph_payload_emits_warning",
                "tests/scientist/test_normative_arbitration_node.py::test_normative_arbitration_invalid_trinity_bundle_skips_with_warning",
                "src/polisyos/scientist/nodes/builtins/governance/legal_check.py",
                "tests/scientist/test_legal_check_node.py::test_legal_check_records_degraded_event_when_report_grade_load_fails",
                "src/polisyos/scientist/nodes/builtins/governance/data_plane_gate.py",
                "tests/scientist/test_data_plane_gate_node.py::test_data_plane_gate_records_degraded_event_for_invalid_quality_report",
                "src/polisyos/scientist/governance/passes/_artifact_resolution.py",
                "tests/scientist/test_decision_packet_node_v3.py",
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
                "tests/scientist/engine/runner/test_activity_worker.py::test_build_worker_context_records_degraded_path_for_invalid_registry_bundle",
                "tests/scientist/engine/runner/test_activity_worker.py::test_restore_parent_trace_context_records_degraded_path_on_runtime_error",
                "src/polisyos/scientist/engine/runner/serialization.py",
                "tests/scientist/engine/runner/test_serialization.py::test_current_trace_ids_records_degraded_path_on_runtime_error",
                "src/polisyos/scientist/engine/runner/temporal_runner.py",
                "tests/scientist/engine/runner/test_temporal_runner.py::test_temporal_inject_trace_carrier_records_degraded_path_on_runtime_error",
                "tests/scientist/engine/runner/test_temporal_runner.py::test_temporal_health_check_returns_unhealthy_on_probe_error",
                "src/polisyos/scientist/engine/runner/ray_runner.py",
                "tests/scientist/engine/runner/test_ray_runner.py::test_ray_runner_inject_trace_carrier_records_degraded_path_on_runtime_error",
                "tests/scientist/engine/runner/test_ray_runner.py::test_ray_runner_health_check_returns_unhealthy_on_probe_error",
                "src/polisyos/scientist/engine/runner/fallback_runner.py",
                "tests/scientist/engine/runner/test_fallback_runner.py::test_primary_execution_error_emits_degraded_path_and_uses_fallback",
                "src/polisyos/scientist/nodes/builtins/tracing.py",
                "tests/scientist/nodes/builtins/test_tracing.py::test_runtime_trace_access_failure_returns_none_ids",
                "tests/scientist/test_checkpoint.py::test_restore_checkpoint_hook_from_runtime_metadata_rejects_invalid_store_config",
                "src/polisyos/core/artifacts/store.py",
            ),
            ci_gates=("pytest tests/scientist/governance -q",),
            acceptance_signal=(
                "every known swallow site resolves to typed error or explicit "
                "degraded result with metric/log"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-1B",
            phase="Phase 1",
            title="Atomic state mutation, merge semantics and deterministic execution",
            status=RemediationStatusLevel.PARTIAL,
            summary=(
                "The synchronous executor now branches node state with declared "
                "write-path copy-on-write isolation, but fan-out/checkpoint resume "
                "flows still need universal staged mutation and conflict policy. "
                "Fan-out now rejects invalid result write paths instead of "
                "silently drifting into params, and sub-workflows now apply "
                "output mappings atomically after child success while rejecting "
                "overlapping output targets. Checkpoint resume now reconciles "
                "local head/history metadata with an explicit policy: a missing "
                "latest history entry is repaired deterministically, while true "
                "head/history disagreement raises a typed conflict error. "
                "Checkpoint GC is now treated as post-commit hygiene, so a GC "
                "failure no longer rolls back hook bookkeeping after a "
                "checkpoint was already committed. Fan-out now also avoids "
                "committing partially merged result state when item failure "
                "terminates execution. Cached node outcomes now merge back into "
                "the current base state by declared write paths instead of "
                "replacing state wholesale, async checkpointing now seeds "
                "cache refs for resumed single-node and merged parallel tiers, "
                "resume now flows through the runner contract with an explicit "
                "fallback when distributed runners cannot be built, async "
                "cache-hit resume no longer trips retry metrics, checkpoint "
                "reconciliation now rejects divergent latest-history entries "
                "and head/artifact metadata mismatches instead of silently "
                "trusting one side, and available distributed runners can now "
                "resume through a pruned workflow contract instead of always "
                "falling back to local execution. CAS checkpoint hooks can now "
                "serialize runtime metadata for distributed execution, remote "
                "workers can reconstruct and continue checkpoint/cache state, "
                "distributed-runner serialization now normalizes list-encoded "
                "wire payloads back into bytes for real activity execution, "
                "and Temporal now wires tier merge/checkpoint through a remote "
                "merge activity when the hook is serializable instead of "
                "forcing a local in-process branch, with a local `temporalio` "
                "end-to-end workflow test proving the remote path runs. "
                "Distributed worker, serialization, and Temporal runner helper "
                "contracts now also have direct regression coverage for "
                "checkpoint metadata reconstruction, list-encoded wire payloads, "
                "and typed unhealthy probe behavior."
                " Ray now also wires tier merge/checkpoint through a remote "
                "merge task when the hook is serializable instead of keeping "
                "distributed execution on a local-only merge branch. Sync and "
                "async fan-out now also prove that summary-artifact persistence "
                "degrades after staged result-state merge without rolling back "
                "the merged state. `set_state`, `emit_artifact`, and "
                "`budget_ledger` now also switch their hot-path mutations from "
                "full-state deep copies to copy-on-write branching or narrow "
                "mutable-map clones, with direct regression coverage. The same "
                "copy-on-write/state-branching contract now also covers "
                "`run_causal_contract_execution`, `run_causal_readiness`, "
                "`bind_foundry_inputs`, `enrich_knowledge`, "
                "`run_hierarchical_policy_search`, and `run_simulation`, so "
                "these nodes no longer rely on local `deep=True` full-state "
                "snapshots for their declared write paths. Governance nodes "
                "`legal_check`, `data_plane_gate`, `run_governance`, and "
                "`run_normative_arbitration` now also branch only their "
                "declared input/params/report/artifact write paths instead of "
                "taking full-state deep copies on each execution. Compile "
                "nodes `compile_foundry`, `link_trinity`, and "
                "`formalize_verified_policy` now also use declared "
                "copy-on-write branching for report/artifact/input writes, "
                "and `formalize_verified_policy` now declares its generated "
                "policy marker in `state_writes` instead of mutating params "
                "off-contract. Planning nodes `run_preflight`, "
                "`run_evaluator`, and `build_execution_plan` now also branch "
                "only their declared params/input/artifact writes, and their "
                "top-level ref fields are now explicitly declared in "
                "`state_writes` instead of being silently mutated outside the "
                "spec contract. The policy-verified planning lane now also "
                "uses declared copy-on-write branching in "
                "`plan_policy_request`, `assemble_legal_candidate_pack`, "
                "`expand_legal_source_pack`, `run_source_verification`, "
                "`run_source_gap_review`, and `draft_policy_options` instead "
                "of taking full-state deep copies to materialize persisted ref "
                "artifacts and verification-cycle markers."
            ),
            blocking_issues=(
                "fanout_checkpoint_staged_mutation_not_universal",
                "parallel_conflict_policy_not_universal",
            ),
            evidence_refs=(
                "src/polisyos/scientist/engine/executor.py",
                "src/polisyos/scientist/engine/state_branching.py",
                "tests/scientist/test_engine_executor_v0.py::test_executor_branch_state_isolates_declared_nested_writes",
                "tests/scientist/engine/test_state_branching.py",
                "src/polisyos/scientist/engine/fan_out.py",
                "tests/scientist/engine/test_fan_out.py::test_invalid_result_path_fails_instead_of_silent_params_drift",
                "tests/scientist/engine/test_fan_out.py::test_summary_persist_failure_emits_degraded_event",
                "src/polisyos/scientist/engine/sub_workflow.py",
                "tests/scientist/engine/test_sub_workflow.py::test_child_failure_does_not_apply_output_mappings",
                "tests/scientist/engine/test_sub_workflow.py::test_overlapping_output_mappings_fail_atomically",
                "src/polisyos/scientist/engine/checkpoint.py",
                "tests/scientist/test_checkpoint.py::test_resolve_latest_checkpoint_repairs_history_when_head_is_newer",
                "tests/scientist/test_checkpoint.py::test_resolve_latest_checkpoint_rejects_head_history_conflict",
                "tests/scientist/test_checkpoint.py::test_checkpoint_hook_gc_failure_does_not_rollback_commit_bookkeeping",
                "tests/scientist/engine/test_fan_out.py::test_stop_on_failure_does_not_commit_partial_merged_state",
                "tests/scientist/engine/test_fan_out_async.py::test_async_stop_on_failure_does_not_commit_partial_merged_state",
                "tests/scientist/engine/test_fan_out_async.py::test_async_summary_persist_failure_emits_degraded_event",
                "tests/scientist/integration/test_checkpoint_resume.py::test_async_executor_resume_uses_checkpoint_cache_refs_when_trace_is_truncated",
                "tests/scientist/integration/test_checkpoint_resume.py::test_async_executor_parallel_tier_checkpoints_merged_state_for_resume",
                "tests/scientist/integration/test_checkpoint_resume.py::test_resume_falls_back_to_local_runner_when_distributed_backend_is_configured",
                "tests/scientist/integration/test_checkpoint_resume.py::test_resume_uses_configured_distributed_runner_with_pruned_workflow",
                "tests/scientist/test_checkpoint.py::test_resolve_latest_checkpoint_rejects_divergent_latest_history_entries",
                "tests/scientist/test_checkpoint.py::test_resolve_latest_checkpoint_rejects_head_artifact_metadata_mismatch",
                "tests/scientist/test_checkpoint.py::test_checkpoint_hook_runtime_metadata_roundtrip_preserves_sequence",
                "src/polisyos/scientist/engine/runner/serialization.py",
                "tests/scientist/engine/runner/test_serialization.py::test_deserialize_state_accepts_list_encoded_wire_payload",
                "tests/scientist/engine/runner/test_serialization.py::test_deserialize_outcome_accepts_list_encoded_wire_payload",
                "tests/scientist/engine/runner/test_activity_worker.py::test_run_merge_checkpoint_tier_in_worker_restores_checkpoint_contract",
                "tests/scientist/engine/runner/test_temporal_runner.py::test_temporal_runner_executes_remote_checkpoint_merge_activity",
                "tests/scientist/engine/runner/test_ray_runner.py::test_ray_runner_executes_remote_checkpoint_merge_task",
                "tests/scientist/engine/runner/test_ray_runner.py::test_ray_runner_health_check_returns_unhealthy_on_probe_error",
                "tests/scientist/engine/runner/test_fallback_runner.py::test_primary_execution_error_emits_degraded_path_and_uses_fallback",
                "tests/scientist/test_checkpoint.py::test_restore_checkpoint_hook_from_runtime_metadata_rejects_invalid_store_config",
                "src/polisyos/scientist/engine/builtins/set_state.py",
                "src/polisyos/scientist/engine/builtins/emit_artifact.py",
                "src/polisyos/scientist/engine/budget_ledger.py",
                "tests/scientist/nodes/builtins/test_state_builtins.py::test_set_state_uses_copy_on_write_for_params",
                "tests/scientist/nodes/builtins/test_state_builtins.py::test_emit_artifact_uses_copy_on_write_for_artifacts_index",
                "tests/scientist/engine/test_budget_middleware.py::test_ledger_mutation_uses_copy_on_write_budget_state",
                "src/polisyos/scientist/nodes/builtins/causal/run_causal_contract_execution.py",
                "src/polisyos/scientist/nodes/builtins/causal/run_causal_readiness.py",
                "src/polisyos/scientist/nodes/builtins/data/bind_foundry_inputs.py",
                "src/polisyos/scientist/nodes/builtins/data/enrich_knowledge.py",
                "src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py",
                "src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py",
                "tests/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py::test_run_hierarchical_policy_search_uses_branch_state_for_final_outputs",
                "src/polisyos/scientist/nodes/builtins/governance/legal_check.py",
                "tests/scientist/test_legal_check_node.py::test_legal_check_uses_branch_state_for_inputs_and_reports",
                "src/polisyos/scientist/nodes/builtins/governance/data_plane_gate.py",
                "tests/scientist/test_data_plane_gate_node.py::test_data_plane_gate_uses_branch_state_for_param_outputs",
                "src/polisyos/scientist/nodes/builtins/governance/run_governance.py",
                "tests/scientist/test_run_governance_normative.py::test_run_governance_uses_branch_state_for_params_and_report",
                "src/polisyos/scientist/nodes/builtins/governance/run_normative_arbitration.py",
                "tests/scientist/test_normative_arbitration_node.py::test_normative_arbitration_uses_branch_state_for_artifact_output",
                "src/polisyos/scientist/nodes/builtins/compile/compile_foundry.py",
                "tests/scientist/nodes/builtins/compile/test_compile_foundry.py::test_compile_foundry_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/compile/link_trinity.py",
                "tests/scientist/nodes/builtins/compile/test_link_trinity.py::test_link_trinity_uses_branch_state_for_report_output",
                "src/polisyos/scientist/nodes/builtins/compile/formalize_verified_policy.py",
                "tests/scientist/nodes/builtins/compile/test_formalize_verified_policy.py::test_formalize_verified_policy_uses_branch_state_for_inputs_and_params",
                "src/polisyos/scientist/nodes/builtins/planning/run_preflight.py",
                "tests/scientist/nodes/builtins/planning/test_run_preflight.py::test_preflight_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/run_evaluator.py",
                "tests/scientist/nodes/builtins/planning/test_run_evaluator.py::test_evaluator_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/build_execution_plan.py",
                "tests/scientist/nodes/builtins/planning/test_build_execution_plan.py::test_plan_builder_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/plan_policy_request.py",
                "tests/scientist/nodes/builtins/planning/test_plan_policy_request.py::test_plan_policy_request_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/assemble_legal_candidate_pack.py",
                "tests/scientist/nodes/builtins/planning/test_assemble_legal_candidate_pack.py::test_assemble_pack_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/expand_legal_source_pack.py",
                "tests/scientist/nodes/builtins/planning/test_expand_legal_source_pack.py::test_expand_source_pack_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/run_source_verification.py",
                "tests/scientist/nodes/builtins/planning/test_run_source_verification.py::test_source_verification_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/run_source_gap_review.py",
                "tests/scientist/nodes/builtins/planning/test_run_source_gap_review.py::test_gap_review_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/nodes/builtins/planning/draft_policy_options.py",
                "tests/scientist/nodes/builtins/planning/test_draft_policy_options.py::test_draft_policy_options_uses_branch_state_for_declared_outputs",
                "src/polisyos/scientist/engine/runner/local_runner.py",
                "src/polisyos/scientist/engine/runner/protocol.py",
                "src/polisyos/scientist/engine/runner/ray_runner.py",
                "src/polisyos/scientist/engine/runner/temporal_runner.py",
                "src/polisyos/scientist/engine/runner/_activity_worker.py",
            ),
            ci_gates=("pytest tests/scientist/test_iteration_state_machine.py -q",),
            acceptance_signal=(
                "partial failures never leave half-applied state and conflict "
                "artifacts remain visible"
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
                "tests/scientist/test_reliability_operational_evidence.py",
                "tools/ci/check_scientist_reliability.py",
            ),
            ci_gates=(
                "pytest tests/scientist/test_reliability_operational_evidence.py -q",
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
                "tests/scientist/integration/test_workflow_reliability_scenarios.py",
                "tests/performance/test_scientist_runtime_paths.py",
                "src/polisyos/scientist/reliability_scorecard.py",
                "tests/tools/test_scientist_reliability_gate.py",
                "tools/ci/check_scientist_reliability.py",
            ),
            ci_gates=(
                "pytest tests/scientist/integration/test_workflow_reliability_scenarios.py -q",
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
                "tests/scientist/engine/test_state_branching.py::test_branch_state_uses_copy_on_write_overlay_for_nested_pydantic_models",
                "src/polisyos/scientist/llm/prompt_cache.py",
                "tests/scientist/llm/test_prompt_cache.py",
                "tests/scientist/test_engine_executor_v0.py::test_executor_branch_state_isolates_declared_nested_writes",
                "src/polisyos/scientist/autotune/pareto.py",
                "tests/scientist/autotune/test_pareto.py",
                "src/polisyos/scientist/cross_graph/alignment.py",
                "src/polisyos/scientist/cross_graph/compiler.py",
                "tests/performance/test_scientist_runtime_paths.py::test_scientist_autotune_pareto_front_hot_path",
                "tests/performance/test_scientist_runtime_paths.py::test_scientist_prompt_cache_hit_hot_path",
            ),
            ci_gates=(
                "pytest tests/scientist/engine/test_state_branching.py -q",
                "pytest tests/scientist/llm/test_prompt_cache.py -q",
                "pytest tests/scientist/autotune/test_pareto.py -q",
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
                "tests/scientist/test_import_boundaries.py",
                "src/polisyos/scientist/cross_graph/alignment.py",
                "src/polisyos/scientist/cross_graph/compiler.py",
                "src/polisyos/scientist/feedback_utils.py",
                "src/polisyos/scientist/feedback.py",
                "src/polisyos/scientist/search/judge_thresholds.py",
                "src/polisyos/scientist/search/judge_stack.py",
                "tests/scientist/search/test_judge_thresholds.py",
                "tests/scientist/search/test_judge_stack_imports.py",
                "src/polisyos/scientist/nodes/builtins/decide/decision_packet_support.py",
                "src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py",
                "src/polisyos/scientist/nodes/builtins/decide/policy_runtime_state.py",
                "src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py",
                "tests/scientist/test_decision_packet_node_v3.py",
                "tools/ci/check_scientist_phase2_ratchet.py",
                "tools/ci/scientist_phase2_ratchet_baseline.toml",
                "tests/tools/test_scientist_phase2_ratchet.py",
                ".github/workflows/arch.yml",
            ),
            ci_gates=(
                "pytest tests/scientist/test_import_boundaries.py -q",
                "pytest tests/scientist/test_feedback_runtime.py -q",
                "pytest tests/scientist/search/test_policy_blueprint_runtime_guards.py -q",
                "pytest tests/tools/test_scientist_phase2_ratchet.py -q",
                "python tools/ci/check_scientist_phase2_ratchet.py",
            ),
            acceptance_signal=(
                "modular extractions hold and the Phase 2 debt counters never "
                "grow above the tracked baseline"
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
                "tests/scientist/test_causal_evaluation_node.py",
                "tests/scientist/test_decision_packet_node_v3.py",
                "tests/foundry/methods/catalog/causal/test_validity_eval_pack.py",
            ),
            ci_gates=(
                "pytest tests/scientist/test_causal_evaluation_node.py -q",
                "pytest tests/scientist/test_decision_packet_node_v3.py -q",
                "pytest tests/foundry/methods/catalog/causal/test_validity_eval_pack.py -q",
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
                "tests/scientist/governance/test_accountability.py",
                "tests/scientist/governance/test_calibration_validation.py",
                "tests/scientist/nodes/test_build_policy_output_bundle.py",
                "tests/ukraine_data/test_builders.py",
            ),
            ci_gates=(
                "pytest tests/scientist/governance/test_accountability.py -q",
                "pytest tests/scientist/governance/test_calibration_validation.py -q",
                "pytest tests/scientist/nodes/test_build_policy_output_bundle.py -q",
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
                "tests/scientist/agent/test_reasoning.py",
                "tests/scientist/agent/test_eval_harness.py",
                "tests/scientist/search/strategies/test_advanced_policy.py",
                "tests/scientist/test_frontier_runtime.py",
            ),
            ci_gates=(
                "pytest tests/scientist/agent/test_reasoning.py -q",
                "pytest tests/scientist/agent/test_eval_harness.py -q",
                "pytest tests/scientist/search/strategies/test_advanced_policy.py -q",
                "pytest tests/scientist/test_frontier_runtime.py -q",
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
            status=RemediationStatusLevel.PARTIAL,
            summary=(
                "Incremental checkpointing, priority scheduling, merge policy "
                "plumbing, and a file-backed budget ledger exist, but the full "
                "multi-host distributed safety contract is not closed. Corrupted "
                "local checkpoint head/history metadata now fails with typed "
                "checkpoint errors instead of raw JSON failures."
            ),
            blocking_issues=(
                "canonical_multi_host_ledger_missing",
                "distributed_failure_matrix_incomplete",
            ),
            evidence_refs=(
                "src/polisyos/scientist/engine/checkpoint.py",
                "tests/scientist/test_checkpoint.py::test_checkpoint_head_invalid_json_raises_typed_error",
                "tests/scientist/test_checkpoint.py::test_checkpoint_history_invalid_json_raises_typed_error",
                "src/polisyos/scientist/engine/budget_ledger.py",
                "src/polisyos/scientist/engine/runner/local_pool.py",
            ),
            ci_gates=("pytest tests/scientist/engine/runner -q",),
            acceptance_signal=(
                "distributed failure matrix proves replay-safe recovery across "
                "checkpoint, ledger, and multi-runner merge paths"
            ),
        ),
        ScientistWorkstreamStatus(
            workstream_id="WS-4B",
            phase="Phase 4",
            title="Frontier research backlog",
            status=RemediationStatusLevel.PARTIAL,
            summary=(
                "A frontier runtime registry and feature-flag contract exist, but "
                "the offline validation bundles and benchmark packs are incomplete "
                "for most frontier methods."
            ),
            blocking_issues=(
                "offline_validation_bundles_incomplete",
                "benchmark_pack_registry_incomplete",
            ),
            evidence_refs=(
                "src/polisyos/scientist/frontier_runtime.py",
                "tests/scientist/test_frontier_runtime.py",
            ),
            ci_gates=("pytest tests/scientist/test_frontier_runtime.py -q",),
            acceptance_signal=(
                "every frontier capability exposes status, flag, benchmark pack, "
                "offline validation ref, and baseline-replacement posture"
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
        assessment_id="gate0_baseline",
        strict_definition_of_done=True,
        overall_status=overall_status,
        phase_rollups=phase_rollups,
        workstreams=workstreams,
        notes=(
            "This report is a conservative Gate 0 baseline, not a declaration of closure.",
            "Partial implementations are reopened until their own exit criteria are evidenced.",
            "Phase 1 must be fully accepted before any new default-on frontier "
            "behavior is allowed.",
        ),
    )


def _build_phase_rollup(
    phase: str,
    workstreams: tuple[ScientistWorkstreamStatus, ...],
) -> ScientistPhaseStatus:
    return ScientistPhaseStatus(
        phase=phase,
        status=_rollup_status(item.status for item in workstreams),
        workstream_ids=tuple(item.workstream_id for item in workstreams),
        summary=(
            f"{phase} remains open under strict DoD accounting until every "
            "workstream in the phase has code, regression tests, docs, "
            "observable acceptance signals, and CI coverage."
        ),
    )


def _rollup_status(statuses: Iterable[RemediationStatusLevel]) -> RemediationStatusLevel:
    normalized = tuple(statuses)
    if normalized and all(item == RemediationStatusLevel.DONE for item in normalized):
        return RemediationStatusLevel.DONE
    if normalized and all(item == RemediationStatusLevel.MISSING for item in normalized):
        return RemediationStatusLevel.MISSING
    return RemediationStatusLevel.PARTIAL
