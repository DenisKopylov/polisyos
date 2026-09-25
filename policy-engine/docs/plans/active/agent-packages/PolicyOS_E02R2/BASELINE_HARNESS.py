#!/usr/bin/env python3
"""Run the fixed four-checkout E02-R2 JUnit baseline matrices.

The harness inspects only tracked test sources and existing local checkouts. It
does not edit a checkout while pytest is running. JUnit, caches, temporary
files, and complete stdout/stderr logs are written to external scratch. After
all jobs finish, deciding JUnit/log receipts are moved under this package's
ignored ``raw/`` directory; completed bulky pytest byproducts are moved to
macOS Trash with a path/size manifest under ``raw/``.

The initial census is exact to 32 named test modules; the separate touched
scope covers 68 additional paths, for a combined 100-path pre-repair scope. For every revision, the harness walks all tracked
Python test paths, records the complete path denominator, and records a Git
blob SHA or ``MISSING`` for every named module. An inspection failure is
``UNRUN``. A missing path is never treated as a passing test.

Predicate notes (P35/P37/P38/P41): checkout identity, file presence, and source
SHA are recomputed from Git; per-case outcomes are recomputed from JUnit XML.
JUnit status is the behavioral outcome, while the process exit code is only a
runner-integrity signal. Native-resource serialization is detected from
explicit imports/direct use in the test module; transitive or dynamic native
use is unresolved by construction and is listed as a bounded limitation.
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import hashlib
import json
import math
import os
import re
import shutil
import signal
import stat
import subprocess
import threading
import time
import traceback
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

PRODUCT_ROOT = Path("/Users/deniskopylov/polisyos")
DATA_ROOT = PRODUCT_ROOT / "policy-engine/production_data"
RUNNER_PYTHON = PRODUCT_ROOT / "policy-engine/.venv/bin/python"
SCRATCH_ROOT = Path("/Users/deniskopylov/.codex/scratch/e02-r2-baselines")
INTEGRATION_CHECKOUT = Path(__file__).resolve().parent.parents[5]
MAX_PROCESS_GROUPS = 5
DEFAULT_PROCESS_GROUPS = 5
RESOURCE_SAMPLE_SECONDS = 5.0
MIN_DISK_FREE_BYTES = 10 * 1024**3
MIN_MEMORY_FREE_PERCENT = 30
MAX_PROCESS_GROUP_RSS_KIB = 8 * 1024**2
MAX_SWAP_GROWTH_BYTES = 256 * 1024**2
ADAPTIVE_MAX_GROUP_RSS_KIB = 1280 * 1024
ADAPTIVE_MIN_GROUP_RSS_KIB = 64 * 1024
ADAPTIVE_MIN_MEMORY_FREE_PERCENT = 35
ADAPTIVE_MAX_GROUP_CPU_PERCENT = 100.0
ADAPTIVE_MAX_BATCH_RSS_KIB = 8 * 1024**2
ADAPTIVE_MAX_BATCH_CPU_PERCENT = 500.0
MAX_RUNNING_BATCH_CPU_PERCENT = 600.0
ADAPTIVE_RSS_PROJECTION_MULTIPLIER = 1.25
PROCESS_GROUP_LAUNCH_STAGGER_SECONDS = 0.5
PROCESS_GROUP_STARTUP_SECONDS = 60.0
HARD_MEMORY_RESERVE_PERCENT = 30
RESOURCE_HARD_LIMIT_CODES = frozenset({
    "process_group_rss_limit_exceeded",
    "minimum_memory_free_percent_breached",
    "aggregate_cpu_hard_limit_exceeded",
    "process_group_count_limit_exceeded",
    "maximum_swap_growth_exceeded",
    "minimum_scratch_free_space_breached",
})
LEGACY_CHECKPOINT_HARNESS_SHA256 = (
    "dc9fc32c6e4f20a1c2976c9eac8fb3f285869f02531e5ecca943ecd76dc08c9e"
)
LEGACY_CHECKPOINT_RUN_ID = "p41-pre-repair-20260924T144020Z-80143"
BOOTSTRAP_ALARM_SECONDS = 1800
TIMEOUT_MULTIPLIER = 3.0
MIN_MEASURED_ALARM_SECONDS = 120
EXPECTED_DATA_MANIFEST_SHA256 = (
    "9e0e0aa0acd3c91f0120a80a2570be358ff16a63218abcd998f4d6f0212b6105"
)
INTEGRATION_PACKAGE_RELATIVE = (
    "policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2"
)

_PROCESS_GROUPS_LOCK = threading.Lock()
_LIVE_PROCESS_GROUPS: dict[int, dict[str, Any]] = {}
_SCHEDULER_HALT_REASON: str | None = None
_STOP_REQUESTED = threading.Event()
_STOP_SIGNAL_NUMBER: int | None = None


def _stop_requested_reason() -> str | None:
    if not _STOP_REQUESTED.is_set():
        return None
    try:
        signal_name = signal.Signals(_STOP_SIGNAL_NUMBER).name if _STOP_SIGNAL_NUMBER else "STOP"
    except ValueError:
        signal_name = "STOP"
    return f"parent received {signal_name}; active cells were stopped and remaining cells are UNRUN"


def _record_stop_signal(signum: int, _frame: object) -> None:
    """Record a stop request; worker and scheduler threads perform cleanup safely."""
    global _STOP_SIGNAL_NUMBER
    _STOP_SIGNAL_NUMBER = signum
    _STOP_REQUESTED.set()


def _run_with_stop_handlers(action: Callable[[], int]) -> int:
    """Install cooperative SIGINT/SIGTERM handling for one harness invocation."""
    global _STOP_SIGNAL_NUMBER, _SCHEDULER_HALT_REASON
    _STOP_REQUESTED.clear()
    _STOP_SIGNAL_NUMBER = None
    _SCHEDULER_HALT_REASON = None
    prior_handlers = {
        signum: signal.signal(signum, _record_stop_signal)
        for signum in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        return action()
    finally:
        for signum, handler in prior_handlers.items():
            signal.signal(signum, handler)

REVISIONS: tuple[dict[str, str], ...] = (
    {
        "key": "e02_execution_base",
        "label": "78187878e",
        "commit": "78187878ee188ff6d27442ba1498bd094da9785b",
        "checkout": "/Users/deniskopylov/polisyos",
    },
    {
        "key": "e02_head",
        "label": "00d946c2b",
        "commit": "00d946c2b7d052522be092f9c70eb9902f6521c2",
        "checkout": "/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos",
    },
    {
        "key": "main",
        "label": "5fd3ebcc1",
        "commit": "5fd3ebcc15637e98bbd4938de5d62ee5004504a8",
        "checkout": "/Users/deniskopylov/polisyos/.worktrees/integration",
    },
    {
        "key": "phase0_merge",
        "label": "73c656744",
        "commit": "73c656744f051d9f40667da7f8bc91c61d8b4ebf",
        "checkout": "/Users/deniskopylov/.codex/worktrees/e02-r2-baseline/polisyos",
    },
)

# Appendix A/B, plus the three merge-review files that may be touched under R14
# and the two new test files needed to measure the Phase 0 composition.
INITIAL_TEST_PATHS: tuple[str, ...] = (
    "policy-engine/tests/integration/core_runtime/test_acquisition_authority_provider.py",
    "policy-engine/tests/integration/core_runtime/test_acquisition_authority_served.py",
    "policy-engine/tests/integration/core_runtime/test_acquisition_tenant_custody.py",
    "policy-engine/tests/integration/core_runtime/test_acquisition_world_growth_chain.py",
    "policy-engine/tests/integration/runtime_quality/test_evaluation_safety_promotion_bridge.py",
    "policy-engine/tests/integration/runtime_frontend/test_ds15_acquisition_route_contract_bridge.py",
    "policy-engine/tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py",
    "policy-engine/tests/repo_quality/architecture/test_repository_sota_phase4_discipline.py",
    "policy-engine/tests/repo_quality/tools/test_core_runtime_closeout.py",
    "policy-engine/tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py",
    "policy-engine/tests/unit/runtime/http/test_control_service_di.py",
    "policy-engine/tests/unit/runtime/http/test_human_decision_guarded_custody.py",
    "policy-engine/tests/unit/runtime/http/test_human_decision_service.py",
    "policy-engine/tests/unit/runtime/http/test_nl_pipeline_materialization.py",
    "policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py",
    "policy-engine/tests/unit/runtime/http/test_resilience_guards.py",
    "policy-engine/tests/unit/runtime/http/test_runtime_api_contract_hardening.py",
    "policy-engine/tests/unit/runtime/http/test_runtime_deployment_security.py",
    "policy-engine/tests/unit/runtime/quality/test_acquisition_movement_positive.py",
    "policy-engine/tests/unit/runtime/quality/test_acquisition_planner.py",
    "policy-engine/tests/unit/runtime/quality/test_epoch_deployment.py",
    "policy-engine/tests/unit/runtime/quality/test_generation_cycle.py",
    "policy-engine/tests/unit/runtime/quality/test_joint_simulation_horizon.py",
    "policy-engine/tests/unit/runtime/quality/test_live_acquisition_executor.py",
    "policy-engine/tests/unit/runtime/quality/test_promotion_epoch_deployment.py",
    "policy-engine/tests/unit/runtime/quality/test_promotion_safety.py",
    "policy-engine/tests/unit/runtime/quality/test_promotion_sequence.py",
    "policy-engine/tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py",
    "policy-engine/tests/unit/remediation/test_dur_02.py",
    "policy-engine/tests/unit/remediation/test_cas_01.py",
    "policy-engine/tests/unit/remediation/test_cas_02.py",
    "policy-engine/tests/unit/core/phase0/test_store_signing.py",
)

# The second pre-repair wave covers each additional known existing write-set
# test path. `test_acquisition_planner.py` already belongs to the initial wave.
ADDON_TEST_PATHS: tuple[str, ...] = (
    "policy-engine/tests/unit/remediation/test_sim_03.py",
    "policy-engine/tests/unit/remediation/test_cyc_05.py",
    "policy-engine/tests/unit/scientist/methods/search/test_objective.py",
    "policy-engine/tests/unit/scientist/methods/autotune/test_pareto.py",
    "policy-engine/tests/unit/scientist/methods/autotune/test_registry_and_runner.py",
    "policy-engine/tests/unit/foundry/methods/catalog/simulation/test_coupled_policy.py",
    "policy-engine/tests/unit/scientist/orchestration/engine/test_engine_executor_idempotency.py",
    "policy-engine/tests/unit/scientist/orchestration/engine/test_state_merge.py",
    "policy-engine/tests/unit/scientist/orchestration/engine/test_state_branching.py",
    "policy-engine/tests/unit/scientist/orchestration/engine/test_async_executor_hardening.py",
    "policy-engine/tests/unit/scientist/orchestration/engine/test_checkpoint.py",
    "policy-engine/tests/unit/remediation/test_res_02.py",
    "policy-engine/tests/unit/fabric/data_plane/test_modes.py",
    "policy-engine/tests/unit/remediation/test_can_01.py",
    "policy-engine/tests/repo_quality/tools/test_layer3_gy_promotion_contract.py",
    "policy-engine/tests/unit/scientist/search/test_search_loop.py",
    "policy-engine/tests/unit/remediation/test_acq_01.py",
    "policy-engine/tests/unit/runtime/quality/test_acquisition_movement.py",
    "policy-engine/tests/unit/runtime/quality/test_epoch_validity_cascade.py",
    "policy-engine/tests/unit/runtime/quality/test_generation_source.py",
    "policy-engine/tests/unit/runtime/quality/test_open_world_risk.py",
    "policy-engine/tests/unit/remediation/test_cyc_02.py",
    "policy-engine/tests/unit/remediation/test_plg_03.py",
    "policy-engine/tests/unit/runtime/quality/test_confidence_ledger.py",
    "policy-engine/tests/unit/runtime/quality/test_public_export.py",
    "policy-engine/tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py",
    "policy-engine/tests/repo_quality/tools/test_layer3_gy_generation_cycle_contract.py",
    "policy-engine/tests/unit/fabric/test_retrieval_fetch_custody.py",
    "policy-engine/tests/unit/fabric/test_retrieval_service_catalog.py",
    "policy-engine/tests/integration/scientist/test_checkpoint_resume.py",
    "policy-engine/tests/unit/scientist/orchestration/engine/test_async_executor.py",
    "policy-engine/tests/unit/core/artifacts/backends/test_s3_store.py",
    "policy-engine/tests/unit/core/artifacts/backends/test_gcs_store.py",
    "policy-engine/tests/unit/core/artifacts/backends/test_caching_store.py",
    "policy-engine/tests/unit/core/artifacts/test_async_store.py",
    "policy-engine/tests/unit/core/artifacts/test_artifact_store_protocol.py",
    "policy-engine/tests/unit/core/artifacts/test_storage_protocol_boundaries.py",
    "policy-engine/tests/unit/core/artifacts/test_signed_evidence.py",
    "policy-engine/tests/unit/core/phase0/test_artifact_export_import.py",
    "policy-engine/tests/unit/runtime/quality/test_multi_tenant_shared_cas.py",
    "policy-engine/tests/unit/fabric/connectors/test_registry.py",
    "policy-engine/tests/unit/fabric/ingestion/test_raw_result_sink.py",
    "policy-engine/tests/unit/fabric/data_plane/test_orchestrator.py",
    "policy-engine/tests/unit/runtime/quality/test_cycle_substrate.py",
    "policy-engine/tests/unit/runtime/quality/test_acquisition_world_growth.py",
    "policy-engine/tests/integration/runtime_quality/test_data_state_substrate.py",
    "policy-engine/tests/unit/runtime/quality/test_intervention_substrate.py",
    "policy-engine/tests/unit/runtime/quality/test_acquisition_source_replay.py",
    "policy-engine/tests/unit/runtime/quality/test_production_grounding_calibration.py",
    "policy-engine/tests/repo_quality/tools/test_gy_d1_catalog_wiring.py",
    "policy-engine/tests/unit/runtime/quality/test_credal_reference.py",
    "policy-engine/tests/unit/runtime/quality/test_design_generation.py",
    "policy-engine/tests/unit/remediation/test_cas_03.py",
    "policy-engine/tests/unit/runtime/http/test_runtime_authorization_access_audit.py",
    "policy-engine/tests/unit/runtime/quality/test_agent_action_authority.py",
    "policy-engine/tests/unit/core/phase0/test_artifact_store.py",
    "policy-engine/tests/unit/core/phase0/test_artifact_graph.py",
    "policy-engine/tests/unit/core/artifacts/test_artifact_id_serialization_contract.py",
    "policy-engine/tests/unit/core/artifacts/test_ir_adapter.py",
    "policy-engine/tests/unit/foundry/compile/test_program_graph_ops.py",
    "policy-engine/tests/unit/foundry/runtime/test_executor_snapshots.py",
    "policy-engine/tests/unit/runtime/quality/test_epoch_custody_audit.py",
    "policy-engine/tests/unit/runtime/quality/test_epoch_transition_inputs.py",
    "policy-engine/tests/unit/runtime/quality/test_epoch_transition_origin.py",
    "policy-engine/tests/unit/runtime/quality/test_epoch_transition_verification.py",
    "policy-engine/tests/unit/runtime/quality/test_epoch_transition_verification_properties.py",
    "policy-engine/tests/unit/runtime/http/test_acquisition_control_worker.py",
    "policy-engine/tests/unit/runtime/http/test_normative_evidence_intake.py",
)

PRE_REPAIR_TEST_PATHS: tuple[str, ...] = INITIAL_TEST_PATHS + ADDON_TEST_PATHS
if (len(INITIAL_TEST_PATHS), len(ADDON_TEST_PATHS), len(PRE_REPAIR_TEST_PATHS)) != (32, 68, 100):
    raise RuntimeError("P41 pre-repair path denominator must be 32 + 68 = 100")
if len(PRE_REPAIR_TEST_PATHS) != len(set(PRE_REPAIR_TEST_PATHS)):
    raise RuntimeError("P41 pre-repair test path union contains duplicates")

# This integration test copies a fixture directory that is part of the
# read-only production_data tree before mutating a JSON file. The copy itself
# is forbidden by the P41 data-custody instructions, so preserve the selected
# matrix cell as a declared UNRUN rather than executing it.
DECLARED_SAFETY_SKIPS: dict[str, dict[str, str]] = {
    "policy-engine/tests/integration/runtime_quality/test_data_state_substrate.py": {
        "code": "forbidden_production_data_copy",
        "policy": "production_data_must_not_be_copied",
        "reason": (
            "test helper calls shutil.copytree on the production_data fixture tree; "
            "the harness must not copy production_data, even to a temporary test checkout"
        ),
    },
}

REQUESTED_TEST_PATHS: tuple[str, ...] = INITIAL_TEST_PATHS

COMPARISON_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("e02_execution_base", "e02_head", "E02 base → E02 head"),
    ("main", "phase0_merge", "main → Phase 0 merge"),
    ("e02_head", "phase0_merge", "E02 head → Phase 0 merge"),
    ("e02_execution_base", "phase0_merge", "E02 base → Phase 0 merge"),
)
R6_DISCRIMINATING_CASE = (
    "policy-engine/tests/unit/runtime/quality/test_generation_cycle.py",
    "tests.unit.runtime.quality.test_generation_cycle::test_joint_port_rejects_candidate_unbound_resolution_from_another_context",
)
APPENDIX_IDENTITY_SOURCE = "policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-20260924T084614Z-77175/results.json"
APPENDIX_IDENTITY_SOURCE_SHA256 = "7df2cf49eba69875882f5dd91916ce3c3fce582a75e168adf9e52e7da0b260e5"
# Exact identities supplied by the Appendix A/B census. Its old result rows
# supply names only; no old outcome is reused because source import origin was
# not recorded. Every new matrix run must collect the named JUnit key at both
# ends of its required pair or report that case as UNRUN.
APPENDIX_REQUIRED_CASE_GROUPS: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    (
        "A", "e02_execution_base", "e02_head",
        "policy-engine/tests/unit/runtime/http/test_control_service_di.py",
        (
            "tests.unit.runtime.http.test_control_service_di::test_process_nl_job_enters_persisted_tenant_scope[authorized]",
            "tests.unit.runtime.http.test_control_service_di::test_process_nl_job_enters_persisted_tenant_scope[missing]",
            "tests.unit.runtime.http.test_control_service_di::test_process_nl_job_enters_persisted_tenant_scope[wrong_role]",
            "tests.unit.runtime.http.test_control_service_di::test_process_nl_job_enters_persisted_tenant_scope[wrong_source]",
        ),
    ),
    (
        "A", "e02_execution_base", "e02_head",
        "policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py",
        (
            "tests.unit.runtime.http.test_normative_generation_bridge::test_compiled_owner_rejects_leaf_graft_even_when_s8_leaf_is_valid",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_complete_composition_identity_and_projection_are_recomputed[disposition_node]",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_complete_composition_identity_and_projection_are_recomputed[front]",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_complete_composition_identity_and_projection_are_recomputed[source_node]",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_complete_composition_identity_and_projection_are_recomputed[status]",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_current_permission_expiry_overrides_persisted_green",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_current_signature_corruption_revokes_recommendation",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_data_only_leaf_growth_preserves_complete_source_identity_sets",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_every_current_job_reader_replays_persisted_authority[get_job_status]",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_every_current_job_reader_replays_persisted_authority[get_latest_job_for_run]",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_malformed_evidence_is_persisted_refusal_not_ignored[invalid]",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_malformed_evidence_is_persisted_refusal_not_ignored[raw0]",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_malformed_evidence_is_persisted_refusal_not_ignored[raw2]",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_missing_or_unresolved_sidecar_preserves_current_source_fronts[None]",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_missing_or_unresolved_sidecar_preserves_current_source_fronts[sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff]",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_same_display_ids_do_not_bind_another_current_compiled_source",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_signed_frontier_must_bind_actual_source_not_same_candidate_names",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_silent_default_cannot_cross_leaf_and_composition_emission[historical_prior]",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_silent_default_cannot_cross_leaf_and_composition_emission[proxy_as_priority]",
            "tests.unit.runtime.http.test_normative_generation_bridge::test_silent_default_cannot_cross_leaf_and_composition_emission[silent_equal_weight]",
        ),
    ),
    (
        "A", "e02_execution_base", "e02_head",
        "policy-engine/tests/unit/runtime/quality/test_acquisition_planner.py",
        ("tests.unit.runtime.quality.test_acquisition_planner::test_generation_cycle_bootstrap_authority_is_strangled",),
    ),
    (
        "A", "e02_execution_base", "e02_head",
        "policy-engine/tests/unit/runtime/quality/test_generation_cycle.py",
        (
            "tests.unit.runtime.quality.test_generation_cycle::test_acquisition_required_invokes_n7_and_records_same_cycle_reentry",
            "tests.unit.runtime.quality.test_generation_cycle::test_controller_runs_counterexample_driven_revision_over_two_real_cycles",
            "tests.unit.runtime.quality.test_generation_cycle::test_generation_cycle_contract_mutations_turn_red",
            "tests.unit.runtime.quality.test_generation_cycle::test_generation_cycle_contract_write_refuses_stale_comparison_admission",
            "tests.unit.runtime.quality.test_generation_cycle::test_joint_port_rejects_candidate_unbound_resolution_from_another_context",
        ),
    ),
    (
        "A", "e02_execution_base", "e02_head",
        "policy-engine/tests/unit/runtime/quality/test_joint_simulation_horizon.py",
        ("tests.unit.runtime.quality.test_joint_simulation_horizon::test_program_graph_plan_loops_real_shared_state_executor",),
    ),
    (
        "A", "e02_execution_base", "e02_head",
        "policy-engine/tests/unit/runtime/quality/test_promotion_sequence.py",
        (
            "tests.unit.runtime.quality.test_promotion_sequence::test_frozen_v6_capture_preserves_history_and_refuses_current_admission",
            "tests.unit.runtime.quality.test_promotion_sequence::test_round1_v5_authority_receipt_cannot_enter_historical_comparison",
            "tests.unit.runtime.quality.test_promotion_sequence::test_round1_v5_v2_receipt_round_trips_but_cannot_regain_current_authority",
        ),
    ),
    (
        "A", "e02_execution_base", "e02_head",
        "policy-engine/tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py",
        (
            "tests.unit.runtime.quality.test_recursive_generation_cycle_epoch_gate::test_http_and_direct_recursive_paths_share_the_pre_n9_subject_strangle",
            "tests.unit.runtime.quality.test_recursive_generation_cycle_epoch_gate::test_non_simulation_leaf_requires_current_eval_safety_head",
        ),
    ),
    (
        "A", "e02_execution_base", "e02_head",
        "policy-engine/tests/unit/runtime/quality/test_live_acquisition_executor.py",
        ("tests.unit.runtime.quality.test_live_acquisition_executor::test_live_executor_runs_real_orchestrator_and_connector_with_intercepted_transport",),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/integration/core_runtime/test_acquisition_authority_provider.py",
        ("tests.integration.core_runtime.test_acquisition_authority_provider::test_real_worker_replay_refuses_absent_decision_verification_appointment",),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/integration/core_runtime/test_acquisition_authority_served.py",
        ("tests.integration.core_runtime.test_acquisition_authority_served::test_served_acquisition_selects_committed_human_authority_and_reopens_worker",),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/integration/core_runtime/test_acquisition_tenant_custody.py",
        ("tests.integration.core_runtime.test_acquisition_tenant_custody::test_actual_acquisition_producers_preserve_tenant_custody_through_reentry",),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/integration/core_runtime/test_acquisition_world_growth_chain.py",
        (
            "tests.integration.core_runtime.test_acquisition_world_growth_chain::test_actual_wdi_admits_delta_and_reenters_same_case[False]",
            "tests.integration.core_runtime.test_acquisition_world_growth_chain::test_actual_wdi_admits_delta_and_reenters_same_case[True]",
            "tests.integration.core_runtime.test_acquisition_world_growth_chain::test_both_reentry_paths_keep_empty_selection_refusal",
            "tests.integration.core_runtime.test_acquisition_world_growth_chain::test_default_wdi_cost_selection_is_absent_before_served_execution",
            "tests.integration.core_runtime.test_acquisition_world_growth_chain::test_deferred_admission_refuses_unknown_outcome_and_missing_negative",
        ),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/integration/runtime_quality/test_evaluation_safety_promotion_bridge.py",
        (
            "tests.integration.runtime_quality.test_evaluation_safety_promotion_bridge::test_compiled_source_content_binding_survives_retained_semantic_markers",
            "tests.integration.runtime_quality.test_evaluation_safety_promotion_bridge::test_compiled_source_manifest_custody_requires_exact_writer_contract[artifact_id]",
            "tests.integration.runtime_quality.test_evaluation_safety_promotion_bridge::test_compiled_source_manifest_custody_requires_exact_writer_contract[artifact_schema]",
            "tests.integration.runtime_quality.test_evaluation_safety_promotion_bridge::test_compiled_source_manifest_custody_requires_exact_writer_contract[byte_size]",
            "tests.integration.runtime_quality.test_evaluation_safety_promotion_bridge::test_compiled_source_manifest_custody_requires_exact_writer_contract[integrity]",
            "tests.integration.runtime_quality.test_evaluation_safety_promotion_bridge::test_compiled_source_manifest_custody_requires_exact_writer_contract[media_type]",
            "tests.integration.runtime_quality.test_evaluation_safety_promotion_bridge::test_existing_generation_producer_is_read_before_candidate_absence_is_reported",
            "tests.integration.runtime_quality.test_evaluation_safety_promotion_bridge::test_matching_candidate_label_cannot_select_foreign_candidate_bytes",
            "tests.integration.runtime_quality.test_evaluation_safety_promotion_bridge::test_real_negative_n9_source_reaches_offer_cas_and_authoritative_classifier",
        ),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/unit/runtime/http/test_human_decision_guarded_custody.py",
        ("tests.unit.runtime.http.test_human_decision_guarded_custody::test_guarded_store_custodies_record_and_recovers_signed_orphan[True]",),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/unit/runtime/http/test_human_decision_service.py",
        ("tests.unit.runtime.http.test_human_decision_service::test_human_decision_hard_crash_reconciles_null_ref_signed_orphan_before_v2",),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/unit/runtime/http/test_nl_pipeline_materialization.py",
        ("tests.unit.runtime.http.test_nl_pipeline_materialization::test_plain_language_front_door_calls_real_design_problem_compiler",),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/unit/runtime/http/test_runtime_deployment_security.py",
        ("tests.unit.runtime.http.test_runtime_deployment_security::test_epoch_privileged_source_ports_are_captured_and_attested",),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/unit/runtime/quality/test_acquisition_movement_positive.py",
        (
            "tests.unit.runtime.quality.test_acquisition_movement_positive::test_native_supplier_requires_separate_gy_act_then_projects_to_cycle_board",
            "tests.unit.runtime.quality.test_acquisition_movement_positive::test_remove_decisive_native_bytes_keeps_receipt_markers_but_retracts_board_movement",
        ),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/unit/runtime/quality/test_epoch_deployment.py",
        (
            "tests.unit.runtime.quality.test_epoch_deployment::test_configured_policy_exchange_reaches_native_verifier_limitation",
            "tests.unit.runtime.quality.test_epoch_deployment::test_privileged_native_verifier_is_operational_and_deployment_local",
        ),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/unit/runtime/quality/test_promotion_epoch_deployment.py",
        ("tests.unit.runtime.quality.test_promotion_epoch_deployment::test_configured_positive_carrier_still_hits_unchanged_ep_d03_refusal",),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/unit/runtime/quality/test_promotion_safety.py",
        (
            "tests.unit.runtime.quality.test_promotion_safety::test_canonical_port_and_independent_reader_share_fixed_source_trust",
            "tests.unit.runtime.quality.test_promotion_safety::test_signed_source_custody_never_establishes_promotion_policy[None]",
        ),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/unit/runtime/quality/test_promotion_sequence.py",
        (
            "tests.unit.runtime.quality.test_promotion_sequence::test_frozen_v6_capture_preserves_history_and_refuses_current_admission",
            "tests.unit.runtime.quality.test_promotion_sequence::test_round1_v5_authority_receipt_cannot_enter_historical_comparison",
            "tests.unit.runtime.quality.test_promotion_sequence::test_round1_v5_v2_receipt_round_trips_but_cannot_regain_current_authority",
        ),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/unit/runtime/quality/test_generation_cycle.py",
        (
            "tests.unit.runtime.quality.test_generation_cycle::test_acquisition_required_invokes_n7_and_records_same_cycle_reentry",
            "tests.unit.runtime.quality.test_generation_cycle::test_controller_runs_counterexample_driven_revision_over_two_real_cycles",
            "tests.unit.runtime.quality.test_generation_cycle::test_generation_cycle_contract_mutations_turn_red",
            "tests.unit.runtime.quality.test_generation_cycle::test_generation_cycle_contract_write_refuses_stale_comparison_admission",
            "tests.unit.runtime.quality.test_generation_cycle::test_joint_port_rejects_candidate_unbound_resolution_from_another_context",
        ),
    ),
    (
        "B", "main", "phase0_merge",
        "policy-engine/tests/unit/runtime/quality/test_live_acquisition_executor.py",
        ("tests.unit.runtime.quality.test_live_acquisition_executor::test_live_executor_runs_real_orchestrator_and_connector_with_intercepted_transport",),
    ),
)
APPENDIX_REQUIRED_CASE_COUNT = sum(len(group[4]) for group in APPENDIX_REQUIRED_CASE_GROUPS)
APPENDIX_REQUIRED_CASE_COUNTS = {
    appendix: sum(len(group[4]) for group in APPENDIX_REQUIRED_CASE_GROUPS if group[0] == appendix)
    for appendix in ("A", "B")
}
if APPENDIX_REQUIRED_CASE_COUNT != 74 or APPENDIX_REQUIRED_CASE_COUNTS != {"A": 37, "B": 37}:
    raise RuntimeError("P41 Appendix A/B required-case inventory must contain 74 named cases")
if {group[3] for group in APPENDIX_REQUIRED_CASE_GROUPS} - set(PRE_REPAIR_TEST_PATHS):
    raise RuntimeError("P41 Appendix A/B identities include a test path outside the pre-repair denominator")

NATIVE_MARKERS: tuple[str, ...] = (
    "import jax",
    "from jax",
    "jax.numpy",
    "import torch",
    "from torch",
    "tensorflow",
    "import duckdb",
    "from duckdb",
    "duckdb.connect",
    "import numba",
    "from numba",
)

# These whole-file cases have measured high memory use or contain large
# runtime-bridge fixtures. Keep them exclusive even if an operator explicitly
# requests two workers. The native marker census remains a separate signal.
# Two resumed four-group waves exhausted the 256 MiB swap-growth budget while
# normative evidence intake and epoch verification properties ran together.
RESOURCE_EXCLUSIVE_TEST_PATHS = frozenset(
    {
        "policy-engine/tests/unit/runtime/http/test_control_service_di.py",
        "policy-engine/tests/unit/runtime/http/test_normative_evidence_intake.py",
        "policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py",
        "policy-engine/tests/integration/runtime_quality/test_evaluation_safety_promotion_bridge.py",
        "policy-engine/tests/unit/runtime/quality/test_epoch_transition_verification_properties.py",
        "policy-engine/tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py",
    }
)
CASE_SIGNATURE_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}
PREMEASURED_WALL_SECONDS = {
    "policy-engine/tests/unit/runtime/http/test_control_service_di.py": 647.049,
    "policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py": 2332.679,
    "policy-engine/tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py": 230.785,
    "policy-engine/tests/integration/runtime_quality/test_evaluation_safety_promotion_bridge.py": 265.948,
}


@dataclass(frozen=True)
class TestCaseResult:
    key: str
    classname: str
    name: str
    status: str
    seconds: float


@dataclass(frozen=True)
class Job:
    revision_key: str
    test_path: str
    test_blob_oid: str
    timeout_seconds: int
    timeout_basis: str
    exclusive_native: bool


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _appendix_identity_source_receipt() -> dict[str, Any]:
    """Report optional provenance for the tracked Appendix identity constants."""
    path = INTEGRATION_CHECKOUT / APPENDIX_IDENTITY_SOURCE
    record: dict[str, Any] = {
        "path": APPENDIX_IDENTITY_SOURCE,
        "expected_sha256": APPENDIX_IDENTITY_SOURCE_SHA256,
        "use": "identity provenance only; required identities are embedded in the tracked harness",
    }
    if not path.is_file():
        record.update({"status": "unavailable", "observed_sha256": None})
        return record
    try:
        observed = _sha256(path)
    except OSError as exc:
        record.update({"status": "unavailable", "observed_sha256": None, "read_error": type(exc).__name__})
        return record
    record.update({
        "status": "verified" if observed == APPENDIX_IDENTITY_SOURCE_SHA256 else "sha_mismatch",
        "observed_sha256": observed,
    })
    return record


def _git(checkout: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(checkout), *args])


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _checkout_status(checkout: Path) -> tuple[str, ...]:
    result = _git(checkout, "status", "--porcelain=v1", "--untracked-files=all")
    _require(result.returncode == 0, f"git status failed for {checkout}: {result.stderr}")
    return tuple(sorted(line[3:] for line in result.stdout.splitlines() if len(line) >= 4))


def _owned_package_paths(package_dir: Path, checkout: Path) -> set[str]:
    if not package_dir.is_relative_to(checkout):
        return set()
    return {
        (package_dir / "BASELINE_HARNESS.py").relative_to(checkout).as_posix(),
        (package_dir / "BASELINES.md").relative_to(checkout).as_posix(),
        (package_dir / "raw/.gitignore").relative_to(checkout).as_posix(),
    }


def _inspect_integration_checkout() -> dict[str, Any]:
    """Prove the output branch is attached and differs from Phase 0 only in this package."""
    top = _git(INTEGRATION_CHECKOUT, "rev-parse", "--show-toplevel")
    branch = _git(INTEGRATION_CHECKOUT, "symbolic-ref", "-q", "--short", "HEAD")
    head = _git(INTEGRATION_CHECKOUT, "rev-parse", "HEAD")
    _require(top.returncode == 0 and Path(top.stdout.strip()) == INTEGRATION_CHECKOUT, "integration checkout root mismatch")
    _require(branch.returncode == 0 and branch.stdout.strip() == "codex/e02-r2", "integration output checkout is not attached to codex/e02-r2")
    _require(head.returncode == 0, "integration checkout HEAD inspection failed")
    phase0_commit = next(revision["commit"] for revision in REVISIONS if revision["key"] == "phase0_merge")
    ancestry = _git(INTEGRATION_CHECKOUT, "merge-base", "--is-ancestor", phase0_commit, head.stdout.strip())
    _require(ancestry.returncode == 0, "integration output checkout is not a descendant of the Phase 0 merge")
    committed = _git(INTEGRATION_CHECKOUT, "diff", "--name-only", f"{phase0_commit}..{head.stdout.strip()}")
    _require(committed.returncode == 0, f"integration-vs-Phase0 path census failed: {committed.stderr.strip()}")
    dirty_paths = list(_checkout_status(INTEGRATION_CHECKOUT))
    changed_paths = sorted(set(committed.stdout.splitlines()) | set(dirty_paths))
    allowed_prefix = INTEGRATION_PACKAGE_RELATIVE + "/"
    raw_ignore_path = "policy-engine/.gitignore"
    if raw_ignore_path in changed_paths:
        original_ignore = _git(INTEGRATION_CHECKOUT, "show", f"{phase0_commit}:{raw_ignore_path}")
        _require(original_ignore.returncode == 0, "Phase 0 gitignore inspection failed")
        marker = "docs/superpowers/journals/**/raw/\n"
        _require(original_ignore.stdout.count(marker) == 1, "Phase 0 raw-ignore insertion point changed")
        expected_ignore = original_ignore.stdout.replace(
            marker,
            "docs/plans/active/agent-packages/PolicyOS_E02R2/raw/\n" + marker,
        )
        _require(
            (INTEGRATION_CHECKOUT / raw_ignore_path).read_text() == expected_ignore,
            "integration gitignore differs from the single E02R2 raw-output rule",
        )
    unexpected = [
        path
        for path in changed_paths
        if path != INTEGRATION_PACKAGE_RELATIVE
        and not path.startswith(allowed_prefix)
        and path != raw_ignore_path
    ]
    _require(not unexpected, f"integration tree differs from Phase 0 outside the baseline package and raw ignore: {unexpected}")
    return {
        "checkout": str(INTEGRATION_CHECKOUT),
        "branch": branch.stdout.strip(),
        "head": head.stdout.strip(),
        "phase0_commit": phase0_commit,
        "changed_paths_from_phase0": changed_paths,
        "source_test_schema_tree_matches_phase0": not unexpected,
    }


def _inspect_checkout(revision: dict[str, str], package_dir: Path) -> dict[str, Any]:
    checkout = Path(revision["checkout"])
    _require(checkout.is_dir(), f"checkout does not exist: {checkout}")
    top = _git(checkout, "rev-parse", "--show-toplevel")
    head = _git(checkout, "rev-parse", "HEAD")
    symbolic = _git(checkout, "symbolic-ref", "-q", "--short", "HEAD")
    _require(top.returncode == 0 and head.returncode == 0, f"Git inspection failed: {checkout}")
    actual_head = head.stdout.strip()
    _require(
        actual_head == revision["commit"],
        f"{revision['label']} checkout HEAD drift: expected {revision['commit']}, got {actual_head}",
    )
    status = _checkout_status(checkout)
    allowed = _owned_package_paths(package_dir, checkout) if revision["key"] == "phase0_merge" else set()
    unexpected = sorted(set(status) - allowed)
    _require(not unexpected, f"unexpected dirty paths at {revision['label']}: {unexpected}")

    data_entry = checkout / "policy-engine/production_data"
    _require(data_entry.exists(), f"production_data absent at {revision['label']}")
    _require(
        data_entry.resolve() == DATA_ROOT.resolve(),
        f"production_data resolves to unexpected path at {revision['label']}: {data_entry.resolve()}",
    )
    manifest = data_entry / "manifest.json"
    manifest_sha = _sha256(manifest)
    data_root_mode = stat.S_IMODE(DATA_ROOT.stat().st_mode)
    _require(DATA_ROOT.is_dir(), f"production_data root is not a directory: {DATA_ROOT}")
    _require(
        data_root_mode & 0o222 == 0,
        f"production_data root is writable: {DATA_ROOT} mode={data_root_mode:04o}",
    )
    manifest_mode = stat.S_IMODE(manifest.stat().st_mode)
    _require(
        manifest_sha == EXPECTED_DATA_MANIFEST_SHA256,
        f"production_data manifest changed: expected {EXPECTED_DATA_MANIFEST_SHA256}, got {manifest_sha}",
    )
    _require(manifest_mode & 0o222 == 0, "production_data manifest is writable")

    tree = _git(checkout, "ls-tree", "-r", "--name-only", revision["commit"], "--", "policy-engine/tests")
    _require(tree.returncode == 0, f"Git test-tree census failed at {revision['label']}: {tree.stderr}")
    all_test_paths = [line for line in tree.stdout.splitlines() if line.endswith(".py")]
    test_modules = [
        line for line in all_test_paths if Path(line).name.startswith("test_")
    ]
    expected = set(REQUESTED_TEST_PATHS)
    found_requested = sorted(path for path in test_modules if path in expected)
    missing_requested = sorted(expected - set(found_requested))
    _require(
        set(found_requested).isdisjoint(missing_requested)
        and set(found_requested) | set(missing_requested) == expected,
        f"requested test-path partition failed at {revision['label']}",
    )

    files: dict[str, dict[str, Any]] = {}
    for test_path in REQUESTED_TEST_PATHS:
        if test_path in missing_requested:
            files[test_path] = {"status": "MISSING", "git_blob_oid": None}
            continue
        blob = _git(checkout, "rev-parse", f"{revision['commit']}:{test_path}")
        worktree_path = checkout / test_path
        worktree_sha = _git(checkout, "hash-object", test_path)
        _require(blob.returncode == 0 and worktree_sha.returncode == 0, f"test blob inspect failed: {test_path}")
        blob_oid = blob.stdout.strip()
        _require(
            worktree_sha.stdout.strip() == blob_oid,
            f"test source differs from pinned Git blob at {revision['label']}: {test_path}",
        )
        source = worktree_path.read_text(encoding="utf-8")
        files[test_path] = {
            "status": "PRESENT",
            "git_blob_oid": blob_oid,
            "exclusive_native": any(marker in source for marker in NATIVE_MARKERS),
        }

    pytest_ini = _git(checkout, "rev-parse", f"{revision['commit']}:policy-engine/pytest.ini")
    _require(pytest_ini.returncode == 0, f"pytest.ini is missing at {revision['label']}")
    return {
        "key": revision["key"],
        "label": revision["label"],
        "commit": actual_head,
        "branch": symbolic.stdout.strip() if symbolic.returncode == 0 else "detached",
        "checkout": str(checkout),
        "status_paths": list(status),
        "owned_dirty_paths_allowed": sorted(allowed),
        "data_root": str(data_entry.resolve()),
        "data_root_mode": f"{data_root_mode:04o}",
        "data_root_read_only": True,
        "data_manifest_sha256": manifest_sha,
        "data_manifest_mode": f"{manifest_mode:04o}",
        "pytest_ini_blob": pytest_ini.stdout.strip(),
        "tracked_test_python_paths": len(all_test_paths),
        "tracked_test_modules": len(test_modules),
        "requested_present": len(found_requested),
        "requested_missing": missing_requested,
        "files": files,
    }


def _runtime_versions(env: dict[str, str]) -> dict[str, str]:
    result = _run(
        [str(RUNNER_PYTHON), "-c", "import sys, pytest; print(sys.version.split()[0]); print(pytest.__version__)"],
        cwd=PRODUCT_ROOT / "policy-engine",
        env=env,
    )
    _require(result.returncode == 0, f"shared Python environment unavailable: {result.stderr}")
    lines = result.stdout.splitlines()
    _require(len(lines) >= 2, "Python/pytest version probe returned no complete result")
    return {"python": lines[0], "pytest": lines[1]}


def _parse_junit(path: Path) -> tuple[str, list[TestCaseResult], str | None]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        return "UNRUN", [], f"JUnit unreadable: {type(exc).__name__}: {exc}"
    case_nodes = root.findall(".//testcase")
    if not case_nodes:
        return "UNRUN", [], "JUnit contains no testcase records"
    cases: list[TestCaseResult] = []
    for index, node in enumerate(case_nodes):
        classname = node.attrib.get("classname", "")
        name = node.attrib.get("name", "")
        failures = node.findall("failure")
        errors = node.findall("error")
        skips = node.findall("skipped")
        status = "failed" if failures else "error" if errors else "skipped" if skips else "passed"
        key = f"{classname}::{name}" if classname else name
        seconds_raw = node.attrib.get("time", "0")
        try:
            seconds = float(seconds_raw)
        except ValueError:
            seconds = 0.0
        cases.append(TestCaseResult(key, classname, name, status, seconds))

    counts = Counter(case.status for case in cases)
    if counts["failed"] or counts["error"]:
        return "fail", cases, None
    if not counts["passed"]:
        return "UNRUN", cases, "all collected cases were skipped"
    return "pass", cases, None


def _safe_environment(
    job_tmp: Path,
    home: Path,
    source_checkout: Path | None = None,
) -> dict[str, str]:
    checkout = source_checkout or INTEGRATION_CHECKOUT
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
        "HOME": str(home),
        "TMPDIR": str(job_tmp),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "TZ": "UTC",
        "POLISYOS_PRODUCTION_DATA_ROOT": str(DATA_ROOT),
        "JAX_PLATFORMS": "cpu",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHON_DOTENV_DISABLED": "1",
        "PYTHONPATH": os.pathsep.join((str(checkout / "policy-engine/src"), str(checkout / "policy-engine"))),
    }
    if "LC_ALL" in os.environ:
        env["LC_ALL"] = os.environ["LC_ALL"]
    return env


def _verify_import_origins(checkout: Path, base_env: dict[str, str]) -> dict[str, str]:
    """Require the shared venv to import each pinned checkout's own source."""
    env = dict(base_env)
    env["PYTHONPATH"] = os.pathsep.join(
        (str(checkout / "policy-engine/src"), str(checkout / "policy-engine"))
    )
    code = (
        "import importlib.util, json; "
        "names=('polisyos','tools'); "
        "specs={name: importlib.util.find_spec(name) for name in names}; "
        "print(json.dumps({name: (spec.origin if spec else None) for name,spec in specs.items()}))"
    )
    result = _run(
        [str(RUNNER_PYTHON), "-c", code],
        cwd=checkout / "policy-engine",
        env=env,
    )
    _require(result.returncode == 0, f"checkout import-origin probe failed at {checkout}: {result.stderr.strip()}")
    try:
        origins = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"checkout import-origin probe returned invalid JSON at {checkout}") from exc
    _require(set(origins) == {"polisyos", "tools"}, f"import-origin probe omitted a package at {checkout}")
    expected_origins = {
        "polisyos": checkout / "policy-engine/src/polisyos/__init__.py",
        "tools": checkout / "policy-engine/tools/__init__.py",
    }
    for name, origin in origins.items():
        _require(isinstance(origin, str), f"{name} has no source origin at {checkout}")
        origin_path = Path(origin).resolve()
        _require(
            origin_path == expected_origins[name].resolve(),
            f"{name} resolved to {origin_path}; expected exact pinned source {expected_origins[name].resolve()}",
        )
    return origins


def _parse_size(value: str) -> int:
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([KMGTP]?)\s*", value, re.IGNORECASE)
    _require(match is not None, f"unrecognized size value: {value!r}")
    units = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4, "P": 1024**5}
    return int(float(match.group(1)) * units[match.group(2).upper()])


def _tracked_process_group_ids() -> set[int]:
    with _PROCESS_GROUPS_LOCK:
        return set(_LIVE_PROCESS_GROUPS)


def _aggregate_process_group_metrics(process_group_ids: set[int]) -> dict[str, Any]:
    """Measure CPU/RSS across the active pytest groups as one admission unit."""
    if not process_group_ids:
        return {
            "active_process_group_count": 0,
            "aggregate_process_group_live_process_count": 0,
            "aggregate_process_group_cpu_percent_sum": 0,
            "aggregate_process_group_rss_kib_sum": 0,
            "aggregate_process_group_rss_by_group_kib": {},
        }
    ps = _run(["/bin/ps", "-axo", "pgid=,%cpu=,rss=,stat="])
    _require(ps.returncode == 0, f"aggregate ps resource sample failed: {ps.stderr.strip()}")
    cpu_percent = 0.0
    rss_kib = 0
    live_process_count = 0
    live_group_ids: set[int] = set()
    rss_by_group: dict[int, int] = {}
    for line in ps.stdout.splitlines():
        fields = line.split()
        if len(fields) != 4:
            continue
        try:
            group_id = int(fields[0])
            process_cpu = float(fields[1])
            process_rss = int(fields[2])
        except ValueError:
            continue
        if group_id not in process_group_ids:
            continue
        cpu_percent += process_cpu
        rss_kib += process_rss
        rss_by_group[group_id] = rss_by_group.get(group_id, 0) + process_rss
        if "Z" not in fields[3]:
            live_process_count += 1
            live_group_ids.add(group_id)
    return {
        "active_process_group_count": len(live_group_ids),
        "aggregate_process_group_live_process_count": live_process_count,
        "aggregate_process_group_cpu_percent_sum": round(cpu_percent),
        "aggregate_process_group_rss_kib_sum": rss_kib,
        "aggregate_process_group_rss_by_group_kib": {
            str(group_id): value for group_id, value in sorted(rss_by_group.items())
        },
    }


def _resource_snapshot(
    process_group_id: int,
    scratch_root: Path,
    *,
    allow_empty_group: bool = False,
) -> dict[str, Any]:
    """Read process-group and machine resource facts used by the run guard."""
    ps = _run(["/bin/ps", "-o", "%cpu=,rss=,stat=", "-g", str(process_group_id)])
    group_sample_status = "measured"
    if ps.returncode != 0:
        if allow_empty_group and ps.returncode == 1 and not ps.stdout.strip():
            group_sample_status = "empty_after_child_exit"
        else:
            raise RuntimeError(f"ps resource sample failed: {ps.stderr.strip()}")
    elif allow_empty_group and not ps.stdout.strip():
        group_sample_status = "empty_after_child_exit"
    elif not ps.stdout.strip():
        raise RuntimeError("ps returned no process-group rows while the child was live")
    cpu_percent = 0.0
    rss_kib = 0
    live_process_count = 0
    for line in ps.stdout.splitlines():
        fields = line.split()
        if len(fields) != 3:
            continue
        cpu_percent += float(fields[0])
        rss_kib += int(fields[1])
        if "Z" not in fields[2]:
            live_process_count += 1

    pressure = _run(["/usr/bin/memory_pressure"])
    _require(pressure.returncode == 0, f"memory_pressure failed: {pressure.stderr.strip()}")
    pressure_match = re.search(r"System-wide memory free percentage:\s*(\d+)%", pressure.stdout)
    _require(pressure_match is not None, "memory_pressure did not report system-wide free percentage")

    swap = _run(["/usr/sbin/sysctl", "vm.swapusage"])
    _require(swap.returncode == 0, f"sysctl vm.swapusage failed: {swap.stderr.strip()}")
    swap_match = re.search(r"used\s*=\s*([0-9.]+[KMGTP]?)", swap.stdout)
    _require(swap_match is not None, "sysctl vm.swapusage did not report used swap")

    disk_free = shutil.disk_usage(scratch_root).free
    memory_total = _run(["/usr/sbin/sysctl", "-n", "hw.memsize"])
    _require(memory_total.returncode == 0, f"sysctl hw.memsize failed: {memory_total.stderr.strip()}")
    try:
        memory_total_bytes = int(memory_total.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("sysctl hw.memsize did not return an integer") from exc
    active_group_ids = _tracked_process_group_ids()
    aggregate_metrics = _aggregate_process_group_metrics(active_group_ids)
    return {
        "sampled_at_utc": datetime.now(UTC).isoformat(),
        "process_group_id": process_group_id,
        "process_group_sample_status": group_sample_status,
        "process_group_live_process_count": live_process_count,
        "process_group_cpu_percent_sum": round(cpu_percent, 2),
        "process_group_rss_kib_sum": rss_kib,
        **aggregate_metrics,
        "system_memory_free_percent": int(pressure_match.group(1)),
        "system_memory_total_bytes": memory_total_bytes,
        "system_swap_used_bytes": _parse_size(swap_match.group(1)),
        "scratch_volume_free_bytes": disk_free,
    }


def _child_resource_snapshot(
    process: subprocess.Popen[bytes],
    scratch_root: Path,
) -> dict[str, Any]:
    """Sample a child group, retrying an empty-group race only after exit."""
    exited_before_sample = process.poll() is not None
    try:
        return _resource_snapshot(
            process.pid,
            scratch_root,
            allow_empty_group=exited_before_sample,
        )
    except RuntimeError:
        if process.poll() is None:
            raise
        return _resource_snapshot(process.pid, scratch_root, allow_empty_group=True)


def _resource_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    _require(bool(samples), "resource monitor produced no samples")
    return {
        "sample_count": len(samples),
        "initial": samples[0],
        "final": samples[-1],
        "initial_process_group_sample_measured": samples[0].get("process_group_sample_status") == "measured",
        "peak_process_group_cpu_percent_sum": max(
            row["process_group_cpu_percent_sum"] for row in samples
        ),
        "peak_process_group_rss_kib_sum": max(
            row["process_group_rss_kib_sum"] for row in samples
        ),
        "peak_active_process_group_count": max(
            row.get("active_process_group_count", 0) for row in samples
        ),
        "peak_aggregate_process_group_cpu_percent_sum": max(
            row.get("aggregate_process_group_cpu_percent_sum", 0) for row in samples
        ),
        "peak_aggregate_process_group_rss_kib_sum": max(
            row.get("aggregate_process_group_rss_kib_sum", 0) for row in samples
        ),
        "minimum_system_memory_free_percent": min(
            row["system_memory_free_percent"] for row in samples
        ),
        "peak_system_swap_used_bytes": max(
            row["system_swap_used_bytes"] for row in samples
        ),
        "minimum_scratch_volume_free_bytes": min(
            row["scratch_volume_free_bytes"] for row in samples
        ),
        "swap_growth_bytes": max(
            0,
            max(row["system_swap_used_bytes"] for row in samples)
            - samples[0]["system_swap_used_bytes"],
        ),
    }


def _resource_summary_for_report(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a three-valued aggregate resource verdict without hiding gaps."""
    relevant_rows = [
        row for row in runs
        if row.get("cell_presence") == "PRESENT"
        and not isinstance(row.get("safety_skip"), dict)
    ]
    required = {
        "peak_process_group_rss_kib_sum",
        "peak_process_group_cpu_percent_sum",
        "minimum_system_memory_free_percent",
        "swap_growth_bytes",
        "minimum_scratch_volume_free_bytes",
    }
    sampled_rows = [row for row in relevant_rows if isinstance(row.get("resource_metrics"), dict)]
    incomplete_rows = [
        row for row in relevant_rows
        if not isinstance(row.get("resource_metrics"), dict)
        or not required.issubset(row["resource_metrics"])
    ]
    complete_rows = [
        row for row in sampled_rows if required.issubset(row["resource_metrics"])
    ]
    guard_metadata = {
        (row["revision_key"], row["test_path"]): _resource_guard_metadata(
            row.get("resource_guard"),
            row.get("resource_guard_kind"),
            row.get("resource_guard_code"),
        )
        for row in relevant_rows
        if row.get("resource_guard")
    }
    guarded_rows = [row for row in relevant_rows if row.get("resource_guard")]
    hard_guard_rows = [
        row for row in guarded_rows
        if guard_metadata[(row["revision_key"], row["test_path"])]["kind"] == "hard_limit"
    ]
    unresolved_guard_rows = [row for row in guarded_rows if row not in hard_guard_rows]
    # A confirmed hard-limit breach is decisive even if the interrupted cell
    # has incomplete sampling. Stops, inspection failures, and unclassified
    # guards remain UNRUN even when their last sample was complete.
    status = (
        "fail" if hard_guard_rows
        else "UNRUN" if incomplete_rows or not complete_rows or unresolved_guard_rows
        else "pass"
    )
    reason = None
    coverage_caveat = (
        f"resource coverage incomplete for {len(incomplete_rows)}/{len(relevant_rows)} "
        f"present non-skipped cells; {len(complete_rows)} cells have complete measurements"
        if incomplete_rows else None
    )
    if hard_guard_rows:
        codes = sorted({
            guard_metadata[(row["revision_key"], row["test_path"])]["code"]
            for row in hard_guard_rows
        })
        reason = (
            f"hard resource guard in {len(hard_guard_rows)} present cells ({', '.join(codes)})"
        )
        if coverage_caveat:
            reason += f"; {coverage_caveat}"
    elif status == "UNRUN":
        reason = (
            coverage_caveat
            or f"resource guard or inspection is unresolved for {len(unresolved_guard_rows)} present cells"
        )
    metrics: dict[str, Any] = {}
    if complete_rows:
        observed = [row["resource_metrics"] for row in complete_rows]
        metrics = {
            "peak_process_group_rss_kib": max(item["peak_process_group_rss_kib_sum"] for item in observed),
            "peak_process_group_cpu_percent": max(item["peak_process_group_cpu_percent_sum"] for item in observed),
            "minimum_system_memory_free_percent": min(item["minimum_system_memory_free_percent"] for item in observed),
            "maximum_swap_growth_bytes": max(item["swap_growth_bytes"] for item in observed),
            "minimum_scratch_volume_free_bytes": min(item["minimum_scratch_volume_free_bytes"] for item in observed),
            "peak_active_process_group_count": max(
                (item.get("peak_active_process_group_count", 0) for item in observed),
                default=0,
            ),
            "peak_aggregate_process_group_rss_kib": max(
                (item.get("peak_aggregate_process_group_rss_kib_sum", 0) for item in observed),
                default=0,
            ),
            "peak_aggregate_process_group_cpu_percent": max(
                (item.get("peak_aggregate_process_group_cpu_percent_sum", 0) for item in observed),
                default=0,
            ),
        }
    return {
        "status": status,
        "sampled_cell_count": len(complete_rows),
        "incomplete_cell_count": len(incomplete_rows),
        "guarded_cell_count": len(guarded_rows),
        "hard_guard_cell_count": len(hard_guard_rows),
        "unresolved_guard_cell_count": len(unresolved_guard_rows),
        "reason": reason,
        "metrics": metrics,
    }


def _resource_guard_metadata(
    reason: str | None,
    kind: str | None = None,
    code: str | None = None,
) -> dict[str, str | None]:
    """Classify a resource stop; only source-issued hard-limit codes imply FAIL."""
    if reason is None:
        return {"kind": kind, "code": code}
    if code in RESOURCE_HARD_LIMIT_CODES:
        return {"kind": "hard_limit", "code": code}
    normalized = reason.casefold()
    for limit_code in RESOURCE_HARD_LIMIT_CODES:
        if f"hard-limit:{limit_code}:" in normalized:
            return {"kind": "hard_limit", "code": limit_code}
    if kind == "hard_limit":
        return {"kind": "operational_unrun", "code": code or "unclassified_hard_limit"}
    if "parent received sigint" in normalized or "parent received sigterm" in normalized:
        return {"kind": "interruption", "code": code}
    if "inspection" in normalized or "census" in normalized:
        return {"kind": "inspection", "code": code}
    return {"kind": kind or "operational_unrun", "code": code}


def _safety_skip_row(revision: dict[str, Any], test_path: str) -> dict[str, Any]:
    """Represent a prohibited test invocation as a typed, denominator-preserving UNRUN."""
    declaration = DECLARED_SAFETY_SKIPS[test_path]
    source = revision["files"][test_path]
    return {
        "revision_key": revision["key"],
        "revision_label": revision["label"],
        "commit": revision["commit"],
        "test_path": test_path,
        "cell_presence": "PRESENT",
        "test_blob_oid": source["git_blob_oid"],
        "timeout_seconds": None,
        "timeout_basis": "not applicable; test is not admitted for execution",
        "exclusive_native": bool(source.get("exclusive_native")),
        "command": [],
        "environment_keys": [],
        "cwd": str(Path(revision["checkout"]) / "policy-engine"),
        "returncode": None,
        "timed_out": False,
        "elapsed_seconds": 0.0,
        "suite_status": "UNRUN",
        "unrun_reason": declaration["reason"],
        "safety_skip": {
            "status": "UNRUN",
            "code": declaration["code"],
            "policy": declaration["policy"],
            "reason": declaration["reason"],
        },
        "case_counts": {},
        "cases": [],
        "artifacts": {},
        "resource_metrics": None,
    }


def _resource_guard_reason(snapshot: dict[str, Any], swap_start_bytes: int) -> str | None:
    if snapshot["process_group_rss_kib_sum"] > MAX_PROCESS_GROUP_RSS_KIB:
        return _typed_hard_resource_guard(
            "process_group_rss_limit_exceeded",
            "process group RSS exceeded "
            f"{MAX_PROCESS_GROUP_RSS_KIB} KiB"
        )
    if snapshot["system_memory_free_percent"] < MIN_MEMORY_FREE_PERCENT:
        return _typed_hard_resource_guard(
            "minimum_memory_free_percent_breached",
            "system memory free percentage fell below "
            f"{MIN_MEMORY_FREE_PERCENT}%"
        )
    if snapshot.get("aggregate_process_group_cpu_percent_sum", 0) > MAX_RUNNING_BATCH_CPU_PERCENT:
        return _typed_hard_resource_guard(
            "aggregate_cpu_hard_limit_exceeded",
            "aggregate pytest process-group CPU exceeded running hard limit "
            f"{MAX_RUNNING_BATCH_CPU_PERCENT}%"
        )
    if snapshot.get("active_process_group_count", 0) > MAX_PROCESS_GROUPS:
        return _typed_hard_resource_guard(
            "process_group_count_limit_exceeded",
            f"active pytest process groups exceeded {MAX_PROCESS_GROUPS}",
        )
    swap_growth = max(0, snapshot["system_swap_used_bytes"] - swap_start_bytes)
    if swap_growth > MAX_SWAP_GROWTH_BYTES:
        return _typed_hard_resource_guard(
            "maximum_swap_growth_exceeded",
            f"swap grew by more than {MAX_SWAP_GROWTH_BYTES} bytes",
        )
    if snapshot["scratch_volume_free_bytes"] < MIN_DISK_FREE_BYTES:
        return _typed_hard_resource_guard(
            "minimum_scratch_free_space_breached",
            f"scratch volume free space fell below {MIN_DISK_FREE_BYTES} bytes",
        )
    return None


def _typed_hard_resource_guard(code: str, reason: str) -> str:
    """Keep the originating hard-limit code attached as the guard propagates."""
    if code not in RESOURCE_HARD_LIMIT_CODES:
        raise RuntimeError(f"unknown hard resource guard code: {code}")
    return f"hard-limit:{code}: {reason}"


def _machine_admission_state(
    scratch_root: Path,
    baseline_swap_used_bytes: int,
) -> tuple[dict[str, Any] | None, str | None]:
    """Return a fresh machine sample and a fail-closed hard-guard reason."""
    try:
        snapshot = _resource_snapshot(os.getpgrp(), scratch_root)
        reason = _resource_guard_reason(snapshot, baseline_swap_used_bytes)
    except Exception as exc:
        return None, f"resource inspection unavailable before process admission: {type(exc).__name__}: {exc}"
    if reason is not None:
        return snapshot, f"machine resource guard before process admission: {reason}"
    return snapshot, None


def _machine_admission_block_reason(scratch_root: Path, baseline_swap_used_bytes: int) -> str | None:
    """Return a fail-closed reason when machine resources cannot admit a process."""
    return _machine_admission_state(scratch_root, baseline_swap_used_bytes)[1]


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def _terminate_orphaned_group(
    process: subprocess.Popen[bytes],
    scratch_root: Path,
) -> dict[str, Any]:
    """Terminate live descendants remaining after pytest's leader exited."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return _resource_snapshot(process.pid, scratch_root, allow_empty_group=True)
    deadline = time.monotonic() + 3.0
    latest = _resource_snapshot(process.pid, scratch_root, allow_empty_group=True)
    while latest["process_group_live_process_count"] and time.monotonic() < deadline:
        time.sleep(0.2)
        latest = _resource_snapshot(process.pid, scratch_root, allow_empty_group=True)
    if latest["process_group_live_process_count"]:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        time.sleep(0.1)
        latest = _resource_snapshot(process.pid, scratch_root, allow_empty_group=True)
    return latest


def _unrun_before_process_admission(
    job: Job,
    revision: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    guard_metadata = _resource_guard_metadata(reason)
    return {
        "revision_key": job.revision_key,
        "revision_label": revision["label"],
        "commit": revision["commit"],
        "test_path": job.test_path,
        "cell_presence": "PRESENT",
        "test_blob_oid": job.test_blob_oid,
        "timeout_seconds": job.timeout_seconds,
        "timeout_basis": "not started; resource admission did not pass",
        "exclusive_native": job.exclusive_native,
        "resource_exclusive": job.test_path in RESOURCE_EXCLUSIVE_TEST_PATHS,
        "resource_group_live_after_exit": False,
        "command": [],
        "environment_keys": [],
        "pythonpath_roots": [],
        "cwd": str(Path(revision["checkout"]) / "policy-engine"),
        "returncode": None,
        "timed_out": False,
        "resource_guard": reason,
        "resource_guard_kind": guard_metadata["kind"],
        "resource_guard_code": guard_metadata["code"],
        "elapsed_seconds": 0.0,
        "suite_status": "UNRUN",
        "inspection_error": reason,
        "case_counts": {},
        "cases": [],
        "artifacts": {},
    }


def _unrun_after_worker_exception(
    job: Job,
    revision: dict[str, Any],
    exc: Exception,
) -> dict[str, Any]:
    """Record an unknown execution state without inventing resource evidence."""
    reason = f"scheduler worker failed without a valid verdict: {type(exc).__name__}: {exc}"
    return {
        "revision_key": job.revision_key,
        "revision_label": revision["label"],
        "commit": revision["commit"],
        "test_path": job.test_path,
        "cell_presence": "PRESENT",
        "test_blob_oid": job.test_blob_oid,
        "timeout_seconds": job.timeout_seconds,
        "timeout_basis": "planned alarm recorded; whether it fired is not established",
        "exclusive_native": job.exclusive_native,
        "resource_exclusive": job.test_path in RESOURCE_EXCLUSIVE_TEST_PATHS,
        "resource_group_live_after_exit": None,
        "command": [],
        "command_status": "planned command was not recovered from the failed worker",
        "environment_keys": [],
        "pythonpath_roots": [],
        "cwd": str(Path(revision["checkout"]) / "policy-engine"),
        "returncode": None,
        "timed_out": None,
        "resource_guard": None,
        "resource_guard_kind": None,
        "resource_guard_code": None,
        "elapsed_seconds": None,
        "suite_status": "UNRUN",
        "inspection_error": reason,
        "worker_error": type(exc).__name__,
        "worker_traceback": "".join(traceback.format_exception(exc)),
        "case_counts": {},
        "cases": [],
        "artifacts": {},
    }


def _run_job(
    job: Job,
    revision: dict[str, Any],
    run_dir: Path,
    home: Path,
    scratch_root: Path,
    baseline_swap_used_bytes: int,
    launch_ready: threading.Event | None = None,
    expected_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stop_reason = _stop_requested_reason()
    if stop_reason is not None:
        if launch_ready is not None:
            launch_ready.set()
        return _unrun_before_process_admission(job, revision, stop_reason)
    try:
        admission_block = _machine_admission_block_reason(
            scratch_root,
            baseline_swap_used_bytes,
        )
    except Exception as exc:
        admission_block = f"resource inspection failed before Popen: {type(exc).__name__}: {exc}"
    if admission_block is not None:
        if launch_ready is not None:
            launch_ready.set()
        return _unrun_before_process_admission(job, revision, admission_block)
    checkout = Path(revision["checkout"])
    project_root = checkout / "policy-engine"
    test_arg = job.test_path.removeprefix("policy-engine/")
    stem = Path(job.test_path).stem
    cell_dir = run_dir / "cells" / job.revision_key
    cell_dir.mkdir(parents=True, exist_ok=True)
    path_digest = hashlib.sha256(job.test_path.encode("utf-8")).hexdigest()[:12]
    job_id = f"{stem}-{path_digest}"
    junit_path = cell_dir / f"{job_id}.junit.xml"
    stdout_path = cell_dir / f"{job_id}.stdout.log"
    stderr_path = cell_dir / f"{job_id}.stderr.log"
    temp_path = cell_dir / f"{job_id}.tmp"
    cache_path = cell_dir / f"{job_id}.pytest-cache"
    benchmark_path = cell_dir / f"{job_id}.benchmarks"
    for output_path in (junit_path, stdout_path, stderr_path, temp_path, cache_path, benchmark_path):
        _require(not output_path.exists(), f"refusing to overwrite prior run output: {output_path}")
    temp_path.mkdir(parents=True)
    cache_path.mkdir(parents=True)
    benchmark_path.mkdir(parents=True)
    job_tmp = temp_path / "tmp"
    job_tmp.mkdir()
    env = _safe_environment(job_tmp, home, checkout)
    addopts = (
        "-ra -q --import-mode=importlib --strict-markers "
        f"--benchmark-storage=file://{benchmark_path}"
    )
    command = [
        "/usr/bin/nice",
        "-n",
        "10",
        "/usr/bin/perl",
        "-e",
        "alarm shift; exec @ARGV",
        str(job.timeout_seconds),
        str(RUNNER_PYTHON),
        "-m",
        "pytest",
        test_arg,
        f"--junitxml={junit_path}",
        f"--basetemp={temp_path / 'pytest'}",
        "-o",
        f"cache_dir={cache_path}",
        "-o",
        f"addopts={addopts}",
    ]
    stop_reason = _stop_requested_reason()
    if stop_reason is not None:
        if launch_ready is not None:
            launch_ready.set()
        return _unrun_before_process_admission(job, revision, stop_reason)
    start = time.monotonic()
    launch_error: str | None = None
    resource_guard: str | None = None
    resource_samples: list[dict[str, Any]] = []
    returncode: int | None = None
    timed_out = False
    live_process_group_after_exit = False
    process: subprocess.Popen[bytes] | None = None
    initial_sample: dict[str, Any] | None = None
    try:
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                command,
                cwd=project_root,
                env=env,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
            with _PROCESS_GROUPS_LOCK:
                _LIVE_PROCESS_GROUPS[process.pid] = {
                    "process": process,
                    "expected_profile": expected_profile,
                    "revision_key": job.revision_key,
                    "test_path": job.test_path,
                }
            stop_reason = _stop_requested_reason()
            if stop_reason is not None:
                resource_guard = stop_reason
                _terminate_process_group(process)
            else:
                try:
                    initial_sample = _child_resource_snapshot(process, scratch_root)
                    resource_samples.append(initial_sample)
                    resource_guard = _resource_guard_reason(
                        initial_sample,
                        baseline_swap_used_bytes,
                    )
                    if resource_guard is not None:
                        _terminate_process_group(process)
                except Exception as exc:
                    resource_guard = (
                        f"initial resource inspection unavailable: {type(exc).__name__}: {exc}"
                    )
                    _terminate_process_group(process)
            if launch_ready is not None:
                launch_ready.set()
            while process.poll() is None:
                stop_reason = _stop_requested_reason()
                if stop_reason is not None:
                    resource_guard = stop_reason
                    _terminate_process_group(process)
                    break
                elapsed_now = time.monotonic() - start
                if elapsed_now >= job.timeout_seconds:
                    timed_out = True
                    _terminate_process_group(process)
                    break
                time.sleep(min(RESOURCE_SAMPLE_SECONDS, max(0.1, job.timeout_seconds - elapsed_now)))
                if process.poll() is not None:
                    break
                try:
                    snapshot = _child_resource_snapshot(process, scratch_root)
                except Exception as exc:
                    resource_guard = (
                        f"resource inspection unavailable: {type(exc).__name__}: {exc}"
                    )
                    _terminate_process_group(process)
                    break
                resource_samples.append(snapshot)
                resource_guard = _resource_guard_reason(
                    snapshot,
                    baseline_swap_used_bytes,
                )
                if resource_guard is not None:
                    _terminate_process_group(process)
                    break
            stop_reason = _stop_requested_reason()
            if stop_reason is not None and resource_guard is None:
                resource_guard = stop_reason
            if process.poll() is not None:
                returncode = process.returncode
                if returncode == -signal.SIGALRM:
                    timed_out = True
                    _terminate_process_group(process)
            try:
                final_sample = _child_resource_snapshot(process, scratch_root)
                resource_samples.append(final_sample)
                if (
                    process.poll() is not None
                    and final_sample["process_group_live_process_count"] > 0
                ):
                    resource_guard = (
                        "pytest leader exited while live process-group descendants remained; "
                        "the cell is UNRUN after targeted process-group termination"
                    )
                    final_sample = _terminate_orphaned_group(process, scratch_root)
                    resource_samples.append(final_sample)
                    if final_sample["process_group_live_process_count"] > 0:
                        live_process_group_after_exit = True
                        resource_guard += "; live descendants remained after SIGKILL"
                if resource_guard is None:
                    resource_guard = _resource_guard_reason(
                        final_sample,
                        baseline_swap_used_bytes,
                    )
            except Exception as exc:
                resource_guard = (
                    f"final resource inspection unavailable: {type(exc).__name__}: {exc}"
                )
    except OSError as exc:
        if process is not None and process.poll() is None:
            _terminate_process_group(process)
        launch_error = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        if process is not None and process.poll() is None:
            _terminate_process_group(process)
        launch_error = f"execution or resource inspection failed: {type(exc).__name__}: {exc}"
    finally:
        if process is not None:
            with _PROCESS_GROUPS_LOCK:
                _LIVE_PROCESS_GROUPS.pop(process.pid, None)
        if launch_ready is not None:
            launch_ready.set()
    elapsed = time.monotonic() - start
    if launch_error is not None or resource_guard is not None:
        suite_status, cases, inspection_error = "UNRUN", [], launch_error
        if resource_guard is not None:
            inspection_error = f"resource budget guard: {resource_guard}"
    elif timed_out:
        suite_status, cases, inspection_error = "UNRUN", [], "process time alarm fired"
    elif not junit_path.is_file():
        suite_status, cases, inspection_error = "UNRUN", [], "pytest did not produce JUnit XML"
    else:
        suite_status, cases, inspection_error = _parse_junit(junit_path)
        if returncode != 0 and suite_status == "pass":
            # A green-looking JUnit file cannot hide a process-level failure.
            suite_status = "fail"

    guard_metadata = _resource_guard_metadata(resource_guard)
    return {
        "revision_key": job.revision_key,
        "revision_label": revision["label"],
        "commit": revision["commit"],
        "test_path": job.test_path,
        "cell_presence": "PRESENT",
        "test_blob_oid": job.test_blob_oid,
        "timeout_seconds": job.timeout_seconds,
        "timeout_basis": job.timeout_basis,
        "exclusive_native": job.exclusive_native,
        "command": command,
        "environment_keys": sorted(env),
        "pythonpath_roots": [str(checkout / "policy-engine/src"), str(checkout / "policy-engine")],
        "cwd": str(project_root),
        "returncode": returncode,
        "timed_out": timed_out,
        "resource_guard": resource_guard,
        "resource_guard_kind": guard_metadata["kind"],
        "resource_guard_code": guard_metadata["code"],
        "resource_group_live_after_exit": live_process_group_after_exit,
        "resource_exclusive": job.test_path in RESOURCE_EXCLUSIVE_TEST_PATHS,
        "resource_metrics": _resource_summary(resource_samples) if resource_samples else None,
        "elapsed_seconds": round(elapsed, 3),
        "suite_status": suite_status,
        "inspection_error": inspection_error,
        "case_counts": dict(Counter(case.status for case in cases)),
        "cases": [asdict(case) for case in cases],
        "artifacts": {
            "junit": _artifact(junit_path),
            "stdout": _artifact(stdout_path),
            "stderr": _artifact(stderr_path),
        },
    }


def _artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "sha256": None, "bytes": 0}
    return {"path": str(path), "sha256": _sha256(path), "bytes": path.stat().st_size}


def _retained_artifact_path(
    artifact_ref: str,
    expected_sha: str,
    package_dir: Path,
) -> Path | None:
    """Resolve a checkpoint artifact after its run was moved to package raw.

    Only the exact ``p41-*/cells/...`` location may be relocated. The recorded
    digest, not the path shape, decides whether the retained file is usable.
    """
    path = Path(artifact_ref)
    original = path if path.is_absolute() else INTEGRATION_CHECKOUT / path
    durable_root = (package_dir / "raw").resolve()
    if original.is_file() and original.resolve().is_relative_to(durable_root):
        durable_parts = original.resolve().relative_to(durable_root).parts
        if (
            len(durable_parts) >= 4
            and durable_parts[0].startswith("p41-")
            and durable_parts[1] == "cells"
            and _sha256(original) == expected_sha
        ):
            return original
        return None
    for ancestor in original.parents:
        if not ancestor.name.startswith("p41-"):
            continue
        relative = original.relative_to(ancestor)
        if (
            len(relative.parts) < 3
            or relative.parts[0] != "cells"
            or any(part in {".", ".."} for part in relative.parts)
        ):
            continue
        retained = durable_root / ancestor.name / relative
        return (
            retained
            if retained.is_file()
            and retained.resolve().is_relative_to(durable_root / ancestor.name / "cells")
            and _sha256(retained) == expected_sha
            else None
        )
    return None


def _canonicalize_published_artifact_paths(
    runs: list[dict[str, Any]],
    external_run_dir: Path,
    destination: Path,
    package_dir: Path,
) -> None:
    """Record the exact retained path of every byte-bearing output before publish."""
    for row in runs:
        for artifact in row.get("artifacts", {}).values():
            expected_sha = artifact.get("sha256")
            if expected_sha is None:
                continue
            original = Path(artifact["path"])
            if original.is_relative_to(external_run_dir):
                _require(
                    original.is_file() and _sha256(original) == expected_sha,
                    f"current run artifact is absent or changed: {original}",
                )
                resolved = destination / original.relative_to(external_run_dir)
            else:
                resolved = _retained_artifact_path(artifact["path"], expected_sha, package_dir)
                _require(resolved is not None, f"reused artifact is absent or changed: {original}")
            artifact["path"] = (
                resolved.relative_to(INTEGRATION_CHECKOUT).as_posix()
                if resolved.is_relative_to(INTEGRATION_CHECKOUT)
                else str(resolved)
            )


def _verify_published_artifacts(
    runs: list[dict[str, Any]],
    integration_checkout: Path,
) -> list[dict[str, str]]:
    verified: list[dict[str, str]] = []
    for row in runs:
        for artifact_name, artifact in row.get("artifacts", {}).items():
            expected_sha = artifact.get("sha256")
            if expected_sha is None:
                continue
            artifact_ref = Path(artifact["path"])
            artifact_path = artifact_ref if artifact_ref.is_absolute() else integration_checkout / artifact_ref
            _require(artifact_path.is_file(), f"published {artifact_name} artifact is missing: {artifact_path}")
            actual_sha = _sha256(artifact_path)
            _require(actual_sha == expected_sha, f"published {artifact_name} artifact hash changed: {artifact_path}")
            verified.append({
                "revision_key": row["revision_key"],
                "test_path": row["test_path"],
                "artifact": artifact_name,
                "sha256": actual_sha,
            })
    return verified


def _move_test_byproducts(run_dir: Path, scratch_root: Path, run_id: str) -> Path:
    """Keep pytest temp/cache trees external to the durable receipt directory."""
    byproduct_root = scratch_root / "byproducts" / run_id
    for cell_dir in sorted((run_dir / "cells").glob("*")):
        if not cell_dir.is_dir():
            continue
        for entry in sorted(cell_dir.iterdir()):
            if not (entry.name.endswith(".tmp") or entry.name.endswith(".pytest-cache") or entry.name.endswith(".benchmarks")):
                continue
            destination = byproduct_root / cell_dir.name / entry.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(entry), str(destination))
    return byproduct_root


def _move_completed_byproducts_to_trash(
    byproduct_root: Path,
    run_id: str,
    package_raw: Path,
) -> dict[str, Any]:
    """Retire completed pytest byproducts into Trash and retain a mapping receipt."""
    if not byproduct_root.exists():
        return {"path": None, "manifest_path": None, "manifest_sha256": None, "directory_count": 0}

    directories = sorted(
        path
        for path in byproduct_root.rglob("*")
        if path.is_dir() and path.name.endswith((".tmp", ".pytest-cache", ".benchmarks"))
    )
    entries: list[dict[str, Any]] = []
    for source in directories:
        size = _run(["du", "-sk", str(source)])
        _require(size.returncode == 0, f"could not size pytest byproduct {source}: {size.stderr.strip()}")
        file_count = _run(["find", str(source), "-type", "f"])
        _require(file_count.returncode == 0, f"could not count pytest byproduct {source}: {file_count.stderr.strip()}")
        relative = source.relative_to(byproduct_root)
        entries.append(
            {
                "source_path": str(source),
                "trash_destination": str(Path.home() / ".Trash" / f"e02-r2-{run_id}-byproducts" / relative),
                "size_bytes": int(size.stdout.split()[0]) * 1024,
                "file_count": len(file_count.stdout.splitlines()),
                "kind": source.suffix,
            }
        )

    trash_root = Path.home() / ".Trash" / f"e02-r2-{run_id}-byproducts"
    _require(not trash_root.exists(), f"refusing to reuse Trash destination: {trash_root}")
    moved = _run(["mv", str(byproduct_root), str(trash_root)])
    _require(moved.returncode == 0, f"mv to Trash failed: {moved.stderr.strip()}")
    source_absent = not byproduct_root.exists()
    destination_exists = trash_root.exists()
    _require(source_absent and destination_exists, "Trash move did not verify")
    destination_stat: dict[str, Any]
    try:
        stat = trash_root.stat()
        destination_stat = {
            "status": "measured",
            "inode": stat.st_ino,
            "mode": stat.st_mode,
            "mtime_ns": stat.st_mtime_ns,
        }
    except OSError as exc:
        destination_stat = {
            "status": "unavailable",
            "error": f"{type(exc).__name__}: {exc}",
        }

    manifest = {
        "schema": "policyos.e02r2.p41-trash-moves.v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "move_method": "mv",
        "mv_exit_code": moved.returncode,
        "source_absent_after_move": source_absent,
        "destination_exists_after_move": destination_exists,
        "destination_stat": destination_stat,
        "source_run": run_id,
        "trash_root": str(trash_root),
        "moved_directory_count": len(entries),
        "moved_file_count": sum(row["file_count"] for row in entries),
        "moved_allocated_bytes": sum(row["size_bytes"] for row in entries),
        "entries": entries,
        "limitations": [
            "Moving to Trash retains these outputs but does not promise disk space will be reclaimed.",
            "No active basetemp, deciding JUnit/log receipt, or production_data path was moved.",
        ],
    }
    manifest_path = package_raw / f"p41-trash-moves-{run_id}.json"
    _require(not manifest_path.exists(), f"refusing to overwrite Trash manifest: {manifest_path}")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "path": str(trash_root),
        "manifest_path": manifest_path.relative_to(package_raw.parent).as_posix(),
        "manifest_sha256": _sha256(manifest_path),
        "directory_count": len(entries),
    }


def _profile_key(job: Job) -> tuple[str, str, str]:
    """Keep resource evidence scoped to the pinned runtime revision as well as the test bytes."""
    return (job.revision_key, job.test_path, job.test_blob_oid)


def _profile_light(job: Job, profiles: dict[tuple[str, str, str], dict[str, Any]]) -> bool:
    profile = profiles.get(_profile_key(job))
    if profile is None or job.exclusive_native or job.test_path in RESOURCE_EXCLUSIVE_TEST_PATHS:
        return False
    return (
        profile["elapsed_seconds"] <= 60
        and profile["peak_process_group_rss_kib"] >= ADAPTIVE_MIN_GROUP_RSS_KIB
        and profile["peak_process_group_rss_kib"] <= ADAPTIVE_MAX_GROUP_RSS_KIB
        and profile["peak_process_group_cpu_percent_sum"] <= ADAPTIVE_MAX_GROUP_CPU_PERCENT
        and profile["swap_growth_bytes"] == 0
    )


def _can_admit_profiled_job(
    job: Job,
    profiles: dict[tuple[str, str, str], dict[str, Any]],
    scratch_root: Path,
    baseline_swap_used_bytes: int,
) -> tuple[bool, str | None, bool]:
    """Check one staggered launch against current aggregate load and reserve."""
    profile = profiles.get(_profile_key(job))
    if profile is None or not _profile_light(job, profiles):
        return False, "job has no exact-runtime/test measured-light profile", False
    snapshot, hard_reason = _machine_admission_state(scratch_root, baseline_swap_used_bytes)
    if hard_reason is not None or snapshot is None:
        return False, hard_reason or "resource inspection did not return a sample", True
    if snapshot["active_process_group_count"] >= MAX_PROCESS_GROUPS:
        return False, f"already at {MAX_PROCESS_GROUPS} active pytest process groups", False
    if snapshot["system_memory_free_percent"] < ADAPTIVE_MIN_MEMORY_FREE_PERCENT:
        return False, f"admission reserve below {ADAPTIVE_MIN_MEMORY_FREE_PERCENT}% free memory", False
    # The hard resource guard already caps swap growth; a change within that
    # bound, including a decrease, is not a separate admission failure.

    projected_rss_kib = math.ceil(
        profile["peak_process_group_rss_kib"] * ADAPTIVE_RSS_PROJECTION_MULTIPLIER
    )
    projected_batch_rss_kib = (
        snapshot["aggregate_process_group_rss_kib_sum"] + projected_rss_kib
    )
    if projected_batch_rss_kib > ADAPTIVE_MAX_BATCH_RSS_KIB:
        return False, "projected active pytest RSS exceeds batch cap", False
    projected_cpu = (
        snapshot["aggregate_process_group_cpu_percent_sum"]
        + profile["peak_process_group_cpu_percent_sum"]
    )
    if projected_cpu > ADAPTIVE_MAX_BATCH_CPU_PERCENT:
        return False, "projected active pytest CPU exceeds batch cap", False

    active_rss_by_group = snapshot.get("aggregate_process_group_rss_by_group_kib", {})
    with _PROCESS_GROUPS_LOCK:
        active_groups = dict(_LIVE_PROCESS_GROUPS)
    measured_group_ids = {int(group_id) for group_id in active_rss_by_group}
    missing_group_ids = set(active_groups) - measured_group_ids
    unaccounted_group_ids = measured_group_ids - set(active_groups)
    if unaccounted_group_ids:
        return False, "active process-group RSS census does not match tracked PGIDs", True
    for process_group_id in missing_group_ids:
        process = active_groups[process_group_id].get("process")
        if not isinstance(process, subprocess.Popen) or process.poll() is None:
            return False, "a live tracked process group is absent from the RSS census", True
        active_groups.pop(process_group_id)
    future_active_growth_kib = 0
    for process_group_id, active_group in active_groups.items():
        active_profile = active_group.get("expected_profile")
        if not isinstance(active_profile, dict):
            return False, "an active pytest group has no measured profile", False
        actual_rss_kib = active_rss_by_group.get(str(process_group_id))
        if not isinstance(actual_rss_kib, int):
            return False, f"active process-group RSS is unavailable for PGID {process_group_id}", True
        expected_peak_kib = math.ceil(
            active_profile["peak_process_group_rss_kib"] * ADAPTIVE_RSS_PROJECTION_MULTIPLIER
        )
        future_active_growth_kib += max(0, expected_peak_kib - actual_rss_kib)
    free_headroom_bytes = max(
        0,
        snapshot["system_memory_total_bytes"]
        * (snapshot["system_memory_free_percent"] - HARD_MEMORY_RESERVE_PERCENT)
        // 100,
    )
    projected_future_growth_bytes = (future_active_growth_kib + projected_rss_kib) * 1024
    if projected_future_growth_bytes > free_headroom_bytes:
        return False, "projected active growth plus new job would cross the 30% hard memory reserve", False
    return True, None, False


def _schedule(
    jobs: list[Job],
    records: dict[str, dict[str, Any]],
    run_dir: Path,
    home: Path,
    scratch_root: Path,
    baseline_swap_used_bytes: int,
    workers: int,
    light_profiles: dict[tuple[str, str, str], dict[str, Any]] | None = None,
    on_complete: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    global _SCHEDULER_HALT_REASON
    by_revision = {record["key"]: record for record in records.values()}
    completed: list[dict[str, Any]] = []
    profiles = light_profiles if light_profiles is not None else {}
    halt_reason = _SCHEDULER_HALT_REASON or _stop_requested_reason()

    def not_admitted(job: Job, reason: str) -> dict[str, Any]:
        record = by_revision[job.revision_key]
        row = _unrun_before_process_admission(job, record, reason)
        completed.append(row)
        if on_complete is not None:
            on_complete(row)
        return row

    def execute_batch(batch: list[Job]) -> None:
        global _SCHEDULER_HALT_REASON
        nonlocal halt_reason
        if not batch:
            return
        pending: dict[concurrent.futures.Future[dict[str, Any]], Job] = {}
        next_index = 0

        def record_future(
            future: concurrent.futures.Future[dict[str, Any]],
            job: Job,
        ) -> None:
            nonlocal halt_reason
            try:
                row = future.result()
            except Exception as exc:
                row = _unrun_after_worker_exception(job, by_revision[job.revision_key], exc)
            profiles.update(_measured_light_profiles([row]))
            completed.append(row)
            if on_complete is not None:
                on_complete(row)
            if row.get("worker_error"):
                halt_reason = (
                    f"scheduler paused after worker error at {row['revision_key']}:{row['test_path']}: "
                    f"{row['inspection_error']}"
                )
            elif row.get("resource_group_live_after_exit"):
                halt_reason = (
                    f"scheduler stopped after {row['revision_key']}:{row['test_path']} left live descendants "
                    "after targeted SIGTERM/SIGKILL"
                )
            elif row.get("resource_guard"):
                halt_reason = (
                    f"scheduler paused after resource guard at {row['revision_key']}:{row['test_path']}: "
                    f"{row['resource_guard']}"
                )

        pool_size = max(1, min(workers, MAX_PROCESS_GROUPS, len(batch)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=pool_size) as pool:
            while next_index < len(batch) or pending:
                requested_stop = _stop_requested_reason()
                if requested_stop is not None:
                    halt_reason = requested_stop
                    _SCHEDULER_HALT_REASON = requested_stop
                if halt_reason is not None:
                    for job in batch[next_index:]:
                        not_admitted(job, halt_reason)
                    next_index = len(batch)
                    if not pending:
                        break

                if next_index < len(batch):
                    job = batch[next_index]
                    is_profiled = _profile_light(job, profiles)
                    can_launch = False
                    admission_reason: str | None = None
                    hard_block = False
                    if is_profiled:
                        can_launch, admission_reason, hard_block = _can_admit_profiled_job(
                            job,
                            profiles,
                            scratch_root,
                            baseline_swap_used_bytes,
                        )
                    elif not pending:
                        _, admission_reason = _machine_admission_state(
                            scratch_root,
                            baseline_swap_used_bytes,
                        )
                        hard_block = admission_reason is not None
                        can_launch = not hard_block

                    if can_launch and len(pending) < pool_size:
                        ready = threading.Event()
                        future = pool.submit(
                            _run_job,
                            job,
                            by_revision[job.revision_key],
                            run_dir,
                            home,
                            scratch_root,
                            baseline_swap_used_bytes,
                            ready,
                            profiles.get(_profile_key(job)) if is_profiled else None,
                        )
                        if not ready.wait(PROCESS_GROUP_STARTUP_SECONDS) and not future.done():
                            halt_reason = (
                                f"process admission handshake exceeded {PROCESS_GROUP_STARTUP_SECONDS}s; "
                                "no further jobs will be launched"
                            )
                            pending[future] = job
                            next_index += 1
                            continue
                        if future.done():
                            record_future(future, job)
                            next_index += 1
                            continue
                        pending[future] = job
                        next_index += 1
                        time.sleep(PROCESS_GROUP_LAUNCH_STAGGER_SECONDS)
                        continue

                    if hard_block:
                        halt_reason = admission_reason or "resource inspection failed before Popen"
                        for unrun_job in batch[next_index:]:
                            not_admitted(unrun_job, halt_reason)
                        next_index = len(batch)
                        continue
                    if pending:
                        done, _ = concurrent.futures.wait(
                            pending,
                            timeout=0.5,
                            return_when=concurrent.futures.FIRST_COMPLETED,
                        )
                        for future in done:
                            completed_job = pending.pop(future)
                            record_future(future, completed_job)
                        continue
                    halt_reason = (
                        f"process admission paused before Popen for {job.revision_key}:{job.test_path}: "
                        f"{admission_reason or 'projected resource reserve was insufficient'}"
                    )
                    for unrun_job in batch[next_index:]:
                        not_admitted(unrun_job, halt_reason)
                    next_index = len(batch)
                    continue

                if pending:
                    done, _ = concurrent.futures.wait(
                        pending,
                        timeout=0.5,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )
                    for future in done:
                        completed_job = pending.pop(future)
                        record_future(future, completed_job)

    # Up to five exact-runtime/test measured-light groups may overlap. Every launch is
    # staggered and re-sampled against live aggregate CPU/RSS, with 35% free
    # memory at admission and a projected 30% hard reserve. Unknown, native,
    # and measured-heavy jobs run alone; red or unavailable guards yield
    # checkpointed UNRUN cells without starting a process.
    pending_light: list[Job] = []
    for job in jobs:
        requested_stop = _stop_requested_reason()
        if requested_stop is not None:
            halt_reason = requested_stop
            _SCHEDULER_HALT_REASON = requested_stop
        if halt_reason is not None:
            not_admitted(job, halt_reason)
            continue
        if workers < 2 or not _profile_light(job, profiles):
            if pending_light:
                execute_batch(pending_light)
                pending_light = []
            if halt_reason is not None:
                not_admitted(job, halt_reason)
                continue
            execute_batch([job])
            continue
        candidate_batch = pending_light + [job]
        candidate_profiles = [profiles[_profile_key(item)] for item in candidate_batch]
        batch_fits = (
            len(candidate_batch) <= min(workers, MAX_PROCESS_GROUPS)
            and sum(
                profile["peak_process_group_rss_kib"] * ADAPTIVE_RSS_PROJECTION_MULTIPLIER
                for profile in candidate_profiles
            ) <= ADAPTIVE_MAX_BATCH_RSS_KIB
            and sum(
                profile["peak_process_group_cpu_percent_sum"]
                for profile in candidate_profiles
            ) <= ADAPTIVE_MAX_BATCH_CPU_PERCENT
        )
        if batch_fits:
            pending_light = candidate_batch
            if len(pending_light) == min(workers, MAX_PROCESS_GROUPS):
                execute_batch(pending_light)
                pending_light = []
        else:
            if pending_light:
                execute_batch(pending_light)
            pending_light = []
            if halt_reason is not None:
                not_admitted(job, halt_reason)
            else:
                pending_light = [job]
    if pending_light:
        if halt_reason is None:
            execute_batch(pending_light)
        else:
            for job in pending_light:
                not_admitted(job, halt_reason)
    if halt_reason is not None:
        _SCHEDULER_HALT_REASON = halt_reason
    return completed


def _measured_light_profiles(
    runs: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    profiles: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in runs:
        metrics = row.get("resource_metrics")
        if (
            row.get("cell_presence") != "PRESENT"
            or row.get("suite_status") == "UNRUN"
            or not isinstance(metrics, dict)
            or row.get("exclusive_native")
            or row.get("resource_exclusive")
        ):
            continue
        profile = {
            "elapsed_seconds": row.get("elapsed_seconds"),
            "peak_process_group_rss_kib": metrics.get(
                "peak_process_group_rss_kib_sum",
                metrics.get("peak_process_group_rss_kib"),
            ),
            "peak_process_group_cpu_percent_sum": metrics.get("peak_process_group_cpu_percent_sum"),
            "swap_growth_bytes": metrics.get("swap_growth_bytes"),
        }
        if (
            isinstance(profile["elapsed_seconds"], (int, float))
            and isinstance(profile["peak_process_group_rss_kib"], int)
            and isinstance(profile["peak_process_group_cpu_percent_sum"], (int, float))
            and isinstance(profile["swap_growth_bytes"], int)
            and metrics.get("initial_process_group_sample_measured") is True
            and profile["elapsed_seconds"] <= 60
            and profile["peak_process_group_rss_kib"] >= ADAPTIVE_MIN_GROUP_RSS_KIB
            and profile["peak_process_group_rss_kib"] <= ADAPTIVE_MAX_GROUP_RSS_KIB
            and profile["peak_process_group_cpu_percent_sum"] <= ADAPTIVE_MAX_GROUP_CPU_PERCENT
            and profile["swap_growth_bytes"] == 0
        ):
            # The same test blob can consume several GiB more after a runtime
            # change. A profile from main never admits its E02/merge sibling.
            profiles[(row["revision_key"], row["test_path"], row["test_blob_oid"])] = profile
    return profiles


def _write_checkpoint_manifest(
    checkpoint_dir: Path,
    run_id: str,
    test_paths: tuple[str, ...],
    revision_records: list[dict[str, Any]],
    runtime: dict[str, str],
    env_keys: list[str],
) -> Path:
    checkpoint_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = checkpoint_dir / "manifest.json"
    manifest = {
        "schema": "policyos.e02r2.p41-checkpoint.v1",
        "run_id": run_id,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "harness_sha256": _sha256(Path(__file__).resolve()),
        "requested_test_path_count": len(test_paths),
        "requested_test_paths": list(test_paths),
        "data_root": str(DATA_ROOT),
        "data_manifest_sha256": EXPECTED_DATA_MANIFEST_SHA256,
        "runtime": runtime,
        "environment_policy": {
            "allowlisted_keys": env_keys,
            "source_import_policy": "checkout-local-PYTHONPATH",
            "secret_values_logged": False,
            "dotenv_disabled": True,
            "jax_platforms": "cpu",
        },
        "revisions": revision_records,
    }
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return manifest_path


def _append_checkpoint_row(progress_path: Path, row: dict[str, Any]) -> None:
    checkpoint = {
        "schema": "policyos.e02r2.p41-checkpoint-row.v1",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "run": row,
    }
    with progress_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(checkpoint, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _normalized_command(command: list[str]) -> list[str]:
    normalized: list[str] = []
    for index, argument in enumerate(command):
        if argument.startswith("--junitxml="):
            normalized.append("--junitxml=<run-output>")
        elif argument.startswith("--basetemp="):
            normalized.append("--basetemp=<run-output>")
        elif argument.startswith("cache_dir="):
            normalized.append("cache_dir=<run-output>")
        elif index == 6:
            normalized.append("<alarm-seconds>")
        elif argument.startswith("addopts="):
            normalized.append(re.sub(r"--benchmark-storage=file://[^ ]+", "--benchmark-storage=file://<run-output>", argument))
        else:
            normalized.append(argument)
    return normalized


def _expected_normalized_command(test_path: str) -> list[str]:
    test_arg = test_path.removeprefix("policy-engine/")
    benchmark = "--benchmark-storage=file://<run-output>"
    return [
        "/usr/bin/nice",
        "-n",
        "10",
        "/usr/bin/perl",
        "-e",
        "alarm shift; exec @ARGV",
        "<alarm-seconds>",
        str(RUNNER_PYTHON),
        "-m",
        "pytest",
        test_arg,
        "--junitxml=<run-output>",
        "--basetemp=<run-output>",
        "-o",
        "cache_dir=<run-output>",
        "-o",
        f"addopts=-ra -q --import-mode=importlib --strict-markers {benchmark}",
    ]


def _reject_invalid_checkpoint_cell(
    result_path: Path,
    strict_checkpoint: bool,
    message: str,
) -> None:
    if strict_checkpoint:
        raise RuntimeError(f"invalid checkpoint receipt {result_path}: {message}")


def _verified_reuse_rows(
    result_paths: list[Path],
    revision_records: list[dict[str, Any]],
    runtime: dict[str, str],
    env_keys: list[str],
    package_dir: Path,
) -> dict[tuple[str, str], dict[str, Any]]:
    revisions = {record["key"]: record for record in revision_records}
    reused: dict[tuple[str, str], dict[str, Any]] = {}
    for result_path in result_paths:
        strict_checkpoint = result_path.is_dir()

        if result_path.is_dir():
            manifest_path = result_path / "manifest.json"
            progress_path = result_path / "progress.jsonl"
            _require(manifest_path.is_file() and progress_path.is_file(), f"checkpoint directory is incomplete: {result_path}")
            prior = json.loads(manifest_path.read_text(encoding="utf-8"))
            checkpoint_rows = []
            for line_number, line in enumerate(progress_path.read_text(encoding="utf-8").splitlines(), start=1):
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"checkpoint journal line {line_number} is invalid: {result_path}") from exc
                _require(event.get("schema") == "policyos.e02r2.p41-checkpoint-row.v1", f"checkpoint journal schema mismatch: {result_path}:{line_number}")
                checkpoint_rows.append(event["run"])
            prior["runs"] = checkpoint_rows
            prior_result_sha = hashlib.sha256(
                manifest_path.read_bytes() + progress_path.read_bytes()
            ).hexdigest()
        else:
            _require(result_path.is_file(), f"reuse result file is absent: {result_path}")
            prior = json.loads(result_path.read_text(encoding="utf-8"))
            prior_result_sha = _sha256(result_path)
        _require(prior.get("schema") in {
            "policyos.e02r2.p41-baseline.v1",
            "policyos.e02r2.p41-timeout-rerun.v1",
            "policyos.e02r2.p41-checkpoint.v1",
        }, f"unsupported reuse results schema: {result_path}")
        _require(prior.get("runtime") == runtime, f"reuse runtime differs: {result_path}")
        _require(prior.get("data_manifest_sha256") == EXPECTED_DATA_MANIFEST_SHA256, f"reuse data manifest differs: {result_path}")
        environment_policy = prior.get("environment_policy", {})
        if environment_policy.get("allowlisted_keys") != env_keys:
            _reject_invalid_checkpoint_cell(result_path, strict_checkpoint, "allowlisted environment keys differ")
            continue
        legacy_policy_candidate = (
            result_path.is_dir()
            and prior.get("schema") == "policyos.e02r2.p41-checkpoint.v1"
            and prior.get("run_id") == LEGACY_CHECKPOINT_RUN_ID
            and result_path.parent.name == LEGACY_CHECKPOINT_RUN_ID
            and prior.get("harness_sha256") == LEGACY_CHECKPOINT_HARNESS_SHA256
            and environment_policy.get("source_import_policy") is None
        )
        if (
            environment_policy.get("source_import_policy") != "checkout-local-PYTHONPATH"
            and not legacy_policy_candidate
        ):
            _reject_invalid_checkpoint_cell(result_path, strict_checkpoint, "source import policy is absent or differs")
            continue
        prior_revisions = {row["key"]: row for row in prior.get("revisions", [])}
        _require(set(prior_revisions) == set(revisions), f"reuse revision set differs: {result_path}")
        legacy_revision_identity = True
        for key, record in revisions.items():
            revision_match = (
                prior_revisions[key].get("commit") == record["commit"]
                and prior_revisions[key].get("checkout") == record["checkout"]
                and prior_revisions[key].get("pytest_ini_blob") == record["pytest_ini_blob"]
                and prior_revisions[key].get("module_import_origins") == record.get("module_import_origins")
            )
            legacy_revision_identity = legacy_revision_identity and revision_match
            if not legacy_policy_candidate:
                _require(revision_match, f"reuse checkout/config identity differs for {key}: {result_path}")
        if legacy_policy_candidate and not legacy_revision_identity:
            raise RuntimeError(f"legacy checkpoint revision identity differs: {result_path}")
        prior_path_list = prior.get("requested_test_paths")
        if not isinstance(prior_path_list, list):
            prior_path_list = sorted({row["test_path"] for row in prior.get("runs", [])})
        for row in prior.get("runs", []):
            if row.get("suite_status") not in {"pass", "fail"} or row.get("resource_guard"):
                continue
            key = (row.get("revision_key"), row.get("test_path"))
            _require(key[1] in prior_path_list, f"reuse cell is outside its declared path denominator: {result_path} {key}")
            if key[1] not in REQUESTED_TEST_PATHS:
                continue
            current_revision = revisions.get(key[0])
            _require(current_revision is not None, f"reuse cell has unknown revision: {key}")
            if row.get("commit") != current_revision["commit"]:
                _reject_invalid_checkpoint_cell(
                    result_path,
                    strict_checkpoint,
                    f"cell runtime commit differs from its pinned revision for {key}",
                )
                continue
            current_file = current_revision["files"].get(key[1])
            if not current_file or current_file.get("status") != "PRESENT" or current_file.get("git_blob_oid") != row.get("test_blob_oid"):
                continue
            if row.get("cwd") != str(Path(current_revision["checkout"]) / "policy-engine"):
                _reject_invalid_checkpoint_cell(result_path, strict_checkpoint, f"cell working directory differs for {key}")
                continue
            expected_pythonpath_roots = [
                str(Path(current_revision["checkout"]) / "policy-engine/src"),
                str(Path(current_revision["checkout"]) / "policy-engine"),
            ]
            if row.get("pythonpath_roots") != expected_pythonpath_roots:
                _reject_invalid_checkpoint_cell(result_path, strict_checkpoint, f"cell Python path roots differ for {key}")
                continue
            if row.get("environment_keys") != env_keys:
                _reject_invalid_checkpoint_cell(result_path, strict_checkpoint, f"cell environment keys differ for {key}")
                continue
            if not row.get("command") or not row.get("resource_metrics"):
                _reject_invalid_checkpoint_cell(result_path, strict_checkpoint, f"cell command or resource measurements are absent for {key}")
                continue
            if _normalized_command(row["command"]) != _expected_normalized_command(key[1]):
                _reject_invalid_checkpoint_cell(result_path, strict_checkpoint, f"cell command differs for {key}")
                continue
            policy = prior.get("environment_policy", {})
            if policy.get("dotenv_disabled") is not True or policy.get("jax_platforms") != "cpu":
                _reject_invalid_checkpoint_cell(result_path, strict_checkpoint, f"cell runtime environment policy differs for {key}")
                continue
            if policy.get("allowlisted_keys") != env_keys:
                _reject_invalid_checkpoint_cell(result_path, strict_checkpoint, f"cell allowlist differs for {key}")
                continue
            if key in reused:
                _reject_invalid_checkpoint_cell(result_path, strict_checkpoint, f"duplicate completed cell {key}")
                continue
            artifacts = row.get("artifacts", {})
            junit = artifacts.get("junit", {})
            junit_ref = junit.get("path")
            if not junit_ref:
                _reject_invalid_checkpoint_cell(result_path, strict_checkpoint, f"JUnit path is absent for {key}")
                continue
            junit_path = _retained_artifact_path(junit_ref, junit.get("sha256"), package_dir)
            if junit_path is None:
                _reject_invalid_checkpoint_cell(
                    result_path,
                    strict_checkpoint,
                    f"JUnit artifact is absent or its SHA-256 differs for {key}",
                )
                continue
            parsed_status, parsed_cases, parse_error = _parse_junit(junit_path)
            stored_cases = row.get("cases")
            parsed_case_identity = [(case.key, case.status) for case in parsed_cases]
            stored_case_identity = (
                [(case.get("key"), case.get("status")) for case in stored_cases]
                if isinstance(stored_cases, list) and all(isinstance(case, dict) for case in stored_cases)
                else None
            )
            status_is_reconciled = (
                row.get("suite_status") == "pass"
                and parsed_status == "pass"
                and row.get("returncode") == 0
            ) or (
                row.get("suite_status") == "fail"
                and (
                    parsed_status == "fail"
                    or (parsed_status == "pass" and row.get("returncode") not in {None, 0})
                )
            )
            if (
                parsed_status == "UNRUN"
                or parse_error is not None
                or not status_is_reconciled
                or stored_case_identity != parsed_case_identity
            ):
                _reject_invalid_checkpoint_cell(
                    result_path,
                    strict_checkpoint,
                    f"JUnit outcome does not reconcile with completed row {key}: "
                    f"parsed={parsed_status}, row={row.get('suite_status')}, error={parse_error}"
                )
                continue
            reused_row = dict(row)
            reused_row["reused_from_results_json"] = str(result_path)
            reused_row["reused_from_results_sha256"] = prior_result_sha
            reused_row["source_import_policy_reuse"] = (
                "legacy-derivation: exact old harness digest, pinned import origins, and row PYTHONPATH roots"
                if legacy_policy_candidate
                else "explicit checkpoint manifest"
            )
            reused[key] = reused_row
    return reused


_BUILTIN_PYTEST_FIXTURES = frozenset(
    {
        "capfd", "capfdbinary", "capsys", "capsysbinary", "cache", "doctest_namespace",
        "monkeypatch", "pytestconfig", "record_property", "record_testsuite_property",
        "recwarn", "request", "tmp_path", "tmp_path_factory", "tmpdir", "tmpdir_factory",
        "unused_tcp_port", "unused_tcp_port_factory", "unused_udp_port", "unused_udp_port_factory",
    }
)
_PYTEST_HOOKS = frozenset(
    {
        "pytest_addoption", "pytest_collection_modifyitems", "pytest_configure",
        "pytest_generate_tests", "pytest_ignore_collect", "pytest_itemcollected",
        "pytest_runtest_call", "pytest_runtest_makereport", "pytest_runtest_setup",
        "pytest_runtest_teardown", "pytest_sessionfinish", "pytest_sessionstart",
    }
)


def _ast_text(node: ast.AST) -> str:
    return ast.dump(node, annotate_fields=True, include_attributes=False)


def _bound_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
            names.add(child.id)
        elif isinstance(child, ast.arg):
            names.add(child.arg)
    return names


def _fixture_function(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name) and target.id == "fixture":
            return True
        if isinstance(target, ast.Attribute) and target.attr == "fixture":
            return True
    return False


def _case_context_signature(
    revision_key: str,
    test_path: str,
    case_key: str,
) -> dict[str, Any]:
    cache_key = (revision_key, test_path, case_key)
    if cache_key in CASE_SIGNATURE_CACHE:
        return CASE_SIGNATURE_CACHE[cache_key]
    revision = next(row for row in REVISIONS if row["key"] == revision_key)
    checkout = Path(revision["checkout"])
    source_result = _git(checkout, "show", f"{revision['commit']}:{test_path}")
    if source_result.returncode != 0:
        result = {"established": False, "reason": "pinned test source could not be read"}
        CASE_SIGNATURE_CACHE[cache_key] = result
        return result
    try:
        module = ast.parse(source_result.stdout)
    except SyntaxError as exc:
        result = {"established": False, "reason": f"pinned test source does not parse: {exc.msg}"}
        CASE_SIGNATURE_CACHE[cache_key] = result
        return result

    classname, separator, reported_name = case_key.rpartition("::")
    if not separator:
        result = {"established": False, "reason": "JUnit case key has no qualified function name"}
        CASE_SIGNATURE_CACHE[cache_key] = result
        return result
    function_name = reported_name.split("[", 1)[0]
    reported_class = classname.rsplit(".", 1)[-1]
    candidate_classes = [node for node in module.body if isinstance(node, ast.ClassDef) and node.name == reported_class]
    if candidate_classes:
        class_node = candidate_classes[0] if len(candidate_classes) == 1 else None
        functions = [
            node for node in (class_node.body if class_node else [])
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
        ]
    else:
        class_node = None
        functions = [
            node for node in module.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
        ]
    if len(functions) != 1:
        result = {"established": False, "reason": f"test function resolved to {len(functions)} definitions"}
        CASE_SIGNATURE_CACHE[cache_key] = result
        return result
    function_node = functions[0]

    import_nodes = [node for node in module.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    unresolved_helper_imports = [
        node for node in import_nodes
        if isinstance(node, ast.ImportFrom)
        and (node.level > 0 or (node.module or "").startswith(("tests.", "policy_engine.tests.")))
    ]
    module_marks = [
        node for node in module.body
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and "pytestmark" in _bound_names(node)
    ]
    module_plugins = [
        node for node in module.body
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and "pytest_plugins" in _bound_names(node)
    ]

    fixture_nodes: list[ast.AST] = []
    hook_nodes: list[ast.AST] = []
    fixture_names: set[str] = set()
    module_bindings: dict[str, ast.AST] = {}
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            module_bindings[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for name in _bound_names(node):
                module_bindings[name] = node
        if _fixture_function(node):
            fixture_nodes.append(node)
            fixture_names.add(node.name)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in _PYTEST_HOOKS:
            hook_nodes.append(node)
    if class_node is not None:
        for node in class_node.body:
            if _fixture_function(node):
                fixture_nodes.append(node)
                fixture_names.add(node.name)

    # Include helpers and constants that the exact test body resolves locally.
    dependency_nodes: dict[str, str] = {}
    closure_roots = [function_node, *fixture_nodes, *hook_nodes, *module_marks, *module_plugins]
    pending_names = {
        node.id for root in closure_roots for node in ast.walk(root)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    pending_names.update(
        node.attr for root in closure_roots for node in ast.walk(root)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self"
    )
    class_helper_nodes: dict[str, ast.AST] = {}
    if class_node is not None:
        class_methods = [
            node for node in class_node.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        while True:
            new_methods = [
                node for node in class_methods
                if node.name in pending_names and f"{class_node.name}.{node.name}" not in class_helper_nodes
            ]
            if not new_methods:
                break
            for node in new_methods:
                class_helper_nodes[f"{class_node.name}.{node.name}"] = node
                pending_names.update(
                    child.id for child in ast.walk(node)
                    if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
                )
                pending_names.update(
                    child.attr for child in ast.walk(node)
                    if isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name) and child.value.id == "self"
                )
    visited: set[str] = set()
    while pending_names:
        name = pending_names.pop()
        if name in visited:
            continue
        visited.add(name)
        node = module_bindings.get(name)
        if node is None or node is function_node or _fixture_function(node):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            continue
        if isinstance(node, ast.ClassDef) and class_node is node:
            continue
        dependency_nodes[name] = _ast_text(node)
        pending_names.update(
            child.id for child in ast.walk(node)
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
        )
    dependency_nodes.update({name: _ast_text(node) for name, node in class_helper_nodes.items()})

    # Resolve local/conftest fixtures and collection hooks; an unknown fixture
    # or dynamic helper import keeps the outcome diff visible but unattributed.
    conftest_hashes: list[tuple[str, str]] = []
    conftest_fixture_names: set[str] = set()
    conftest_hook_names: set[str] = set()
    unresolved_conftest_helper_import = False
    conftest_has_plugins = False
    test_parent = Path(test_path).parent.parts
    for depth in range(len(test_parent) + 1):
        conftest_path = Path(*test_parent[:depth], "conftest.py").as_posix()
        conftest_source = _git(checkout, "show", f"{revision['commit']}:{conftest_path}")
        if conftest_source.returncode != 0:
            continue
        conftest_hashes.append((conftest_path, hashlib.sha256(conftest_source.stdout.encode("utf-8")).hexdigest()))
        try:
            conftest_module = ast.parse(conftest_source.stdout)
        except SyntaxError:
            continue
        for node in conftest_module.body:
            if isinstance(node, ast.ImportFrom) and (
                node.level > 0 or (node.module or "").startswith(("tests.", "policy_engine.tests."))
            ):
                unresolved_conftest_helper_import = True
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and "pytest_plugins" in _bound_names(node):
                conftest_has_plugins = True
            if _fixture_function(node):
                conftest_fixture_names.add(node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in _PYTEST_HOOKS:
                conftest_hook_names.add(node.name)

    parameter_names: set[str] = set()
    for decorator in function_node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        target = decorator.func
        if isinstance(target, ast.Attribute) and target.attr == "parametrize" and decorator.args:
            names_node = decorator.args[0]
            if isinstance(names_node, ast.Constant) and isinstance(names_node.value, str):
                parameter_names.update(name.strip() for name in names_node.value.split(","))
            elif isinstance(names_node, (ast.Tuple, ast.List)):
                parameter_names.update(
                    element.value for element in names_node.elts
                    if isinstance(element, ast.Constant) and isinstance(element.value, str)
                )
    fixture_args = {
        argument.arg
        for argument in [*function_node.args.posonlyargs, *function_node.args.args, *function_node.args.kwonlyargs]
        if argument.arg not in {"self", "cls"} and argument.arg not in parameter_names
    }
    unresolved_fixture_args = sorted(
        fixture_args - fixture_names - conftest_fixture_names - _BUILTIN_PYTEST_FIXTURES
    )
    dynamic_collection = any(node.name == "pytest_generate_tests" for node in hook_nodes) or "pytest_generate_tests" in conftest_hook_names

    class_context: dict[str, Any] | None = None
    if class_node is not None:
        class_context = {
            "name": class_node.name,
            "bases": [_ast_text(node) for node in class_node.bases],
            "decorators": [_ast_text(node) for node in class_node.decorator_list],
            "keywords": [_ast_text(node) for node in class_node.keywords],
            "pytestmark": [
                _ast_text(node) for node in class_node.body
                if isinstance(node, (ast.Assign, ast.AnnAssign)) and "pytestmark" in _bound_names(node)
            ],
        }
    function_sha = hashlib.sha256(_ast_text(function_node).encode("utf-8")).hexdigest()
    case_context = {
        "function": _ast_text(function_node),
        "class": class_context,
        "imports": [_ast_text(node) for node in import_nodes],
        "module_marks": [_ast_text(node) for node in module_marks],
        "module_plugins": [_ast_text(node) for node in module_plugins],
        "fixtures": sorted(_ast_text(node) for node in fixture_nodes),
        "hooks": sorted(_ast_text(node) for node in hook_nodes),
        "dependencies": dependency_nodes,
        "conftest_hashes": conftest_hashes,
    }
    context_sha = hashlib.sha256(json.dumps(case_context, sort_keys=True).encode("utf-8")).hexdigest()
    reasons = []
    if unresolved_helper_imports:
        reasons.append("test-side helper import target not statically resolved")
    if unresolved_conftest_helper_import:
        reasons.append("conftest helper import target not statically resolved")
    if module_plugins or conftest_has_plugins:
        reasons.append("pytest plugin fixture/collection behavior not statically resolved")
    if unresolved_fixture_args:
        reasons.append("fixture arguments unresolved: " + ",".join(unresolved_fixture_args))
    if dynamic_collection:
        reasons.append("pytest_generate_tests may supply dynamic case parameters")
    result = {
        "established": not reasons,
        "reason": "; ".join(reasons) if reasons else None,
        "function_sha256": function_sha,
        "context_sha256": context_sha,
    }
    CASE_SIGNATURE_CACHE[cache_key] = result
    return result


def _case_diff(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cells = {(row["revision_key"], row["test_path"]): row for row in results}
    diffs: list[dict[str, Any]] = []
    for left_key, right_key, pair_label in COMPARISON_PAIRS:
        for test_path in REQUESTED_TEST_PATHS:
            left = cells.get((left_key, test_path))
            right = cells.get((right_key, test_path))
            if not left or not right:
                diffs.append({"pair": pair_label, "test_path": test_path, "status": "UNRUN", "reason": "cell not recorded"})
                continue
            left_sha = left.get("test_blob_oid")
            right_sha = right.get("test_blob_oid")
            same_source = left_sha is not None and left_sha == right_sha
            left_cases = {case["key"]: case["status"] for case in left.get("cases", [])}
            right_cases = {case["key"]: case["status"] for case in right.get("cases", [])}
            if left.get("cell_presence") == "MISSING" or right.get("cell_presence") == "MISSING":
                diffs.append({
                    "pair": pair_label,
                    "test_path": test_path,
                    "status": "MISSING",
                    "reason": "test file absent at one or both revisions",
                    "left_test_blob_oid": left_sha,
                    "right_test_blob_oid": right_sha,
                    "same_test_source": same_source,
                })
                continue
            if left["suite_status"] == "UNRUN" or right["suite_status"] == "UNRUN":
                diffs.append({
                    "pair": pair_label,
                    "test_path": test_path,
                    "status": "UNRUN",
                    "reason": "inspection or execution incomplete",
                    "left_test_blob_oid": left_sha,
                    "right_test_blob_oid": right_sha,
                    "same_test_source": same_source,
                })
                continue
            if left_cases == right_cases and (
                left.get("suite_status") != right.get("suite_status")
                or left.get("returncode") != right.get("returncode")
                or left.get("timed_out") != right.get("timed_out")
                or left.get("resource_guard") != right.get("resource_guard")
            ):
                diffs.append({
                    "pair": pair_label,
                    "test_path": test_path,
                    "case": None,
                    "status": "SUITE_INTEGRITY_TRANSITION",
                    "before_suite_status": left.get("suite_status"),
                    "after_suite_status": right.get("suite_status"),
                    "before_returncode": left.get("returncode"),
                    "after_returncode": right.get("returncode"),
                    "before_timed_out": left.get("timed_out"),
                    "after_timed_out": right.get("timed_out"),
                    "before_resource_guard": left.get("resource_guard"),
                    "after_resource_guard": right.get("resource_guard"),
                    "same_junit_case_statuses": True,
                    "same_test_source": same_source,
                    "left_test_blob_oid": left_sha,
                    "right_test_blob_oid": right_sha,
                    "owner_attribution": "UNRESOLVED",
                    "reason": "JUnit case keys/statuses are identical but suite/process integrity differs",
                })
            for case_key in sorted(set(left_cases) | set(right_cases)):
                before = left_cases.get(case_key, "NOT_PRESENT")
                after = right_cases.get(case_key, "NOT_PRESENT")
                if before == after:
                    continue
                if before == "NOT_PRESENT" or after == "NOT_PRESENT":
                    classification = "CASE_SET_CHANGED"
                    equivalence = "not_applicable"
                    left_signature: dict[str, Any] = {}
                    right_signature: dict[str, Any] = {}
                else:
                    left_signature = _case_context_signature(left_key, test_path, case_key)
                    right_signature = _case_context_signature(right_key, test_path, case_key)
                    left_function_sha = left_signature.get("function_sha256")
                    right_function_sha = right_signature.get("function_sha256")
                    if (
                        left_signature.get("established") is True
                        and right_signature.get("established") is True
                        and left_signature.get("context_sha256") == right_signature.get("context_sha256")
                    ):
                        equivalence = "same_case_input_signature"
                    elif left_function_sha and left_function_sha == right_function_sha:
                        equivalence = (
                            "BODY_SAME_FIXTURE_SCOPE_CHANGED"
                            if left_signature.get("established") and right_signature.get("established")
                            else "BODY_SAME_INPUT_CLOSURE_UNMEASURED"
                        )
                    elif left_function_sha and right_function_sha:
                        equivalence = "CASE_DEFINITION_CHANGED"
                    else:
                        equivalence = "not_established"

                    if before == "passed" and after in {"failed", "error"}:
                        classification = "PASS_TO_FAIL"
                    elif before == "passed" and after == "skipped":
                        classification = "PASS_TO_SKIP"
                    else:
                        classification = "OTHER_OUTCOME_CHANGE"
                diffs.append({
                    "pair": pair_label,
                    "test_path": test_path,
                    "case": case_key,
                    "before": before,
                    "after": after,
                    "status": classification,
                    "same_test_source": same_source,
                    "left_test_blob_oid": left_sha,
                    "right_test_blob_oid": right_sha,
                    "case_input_equivalence": equivalence,
                    "owner_attribution": "UNRESOLVED",
                    "left_function_ast_sha256": left_signature.get("function_sha256"),
                    "right_function_ast_sha256": right_signature.get("function_sha256"),
                    "left_case_context_sha256": left_signature.get("context_sha256"),
                    "right_case_context_sha256": right_signature.get("context_sha256"),
                    "case_input_reason": "; ".join(
                        reason for reason in (left_signature.get("reason"), right_signature.get("reason")) if reason
                    ) or None,
                })
    return diffs


def _appendix_case_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve each in-scope required Appendix identity from both JUnit cells."""
    cells = {(row["revision_key"], row["test_path"]): row for row in results}
    pairs = {(left, right): label for left, right, label in COMPARISON_PAIRS}
    required: list[dict[str, Any]] = []
    for appendix, left_key, right_key, test_path, case_keys in APPENDIX_REQUIRED_CASE_GROUPS:
        if test_path not in REQUESTED_TEST_PATHS:
            continue
        for case_key in case_keys:
            left = cells.get((left_key, test_path))
            right = cells.get((right_key, test_path))
            left_case = next((case for case in (left or {}).get("cases", []) if case.get("key") == case_key), None)
            right_case = next((case for case in (right or {}).get("cases", []) if case.get("key") == case_key), None)
            reason: str | None = None
            if left is None or right is None:
                reason = "required comparison cell was not recorded"
            elif left.get("cell_presence") != "PRESENT" or right.get("cell_presence") != "PRESENT":
                reason = "required test file is missing or its source presence is unverified at one comparison base"
            elif left.get("suite_status") not in {"pass", "fail"} or right.get("suite_status") not in {"pass", "fail"}:
                reason = "one or both required suite cells are incomplete or UNRUN"
            elif left_case is None or right_case is None:
                missing_at = []
                if left_case is None:
                    missing_at.append(left_key)
                if right_case is None:
                    missing_at.append(right_key)
                reason = "exact JUnit case key was not collected at " + ", ".join(missing_at)
            if reason:
                status = "UNRUN"
                before = left_case.get("status") if left_case and left and left.get("suite_status") in {"pass", "fail"} else "UNRUN"
                after = right_case.get("status") if right_case and right and right.get("suite_status") in {"pass", "fail"} else "UNRUN"
            else:
                before = left_case["status"]
                after = right_case["status"]
                if before == after:
                    status = "SAME"
                elif before == "passed" and after in {"failed", "error"}:
                    status = "PASS_TO_FAIL"
                elif before == "passed" and after == "skipped":
                    status = "PASS_TO_SKIP"
                else:
                    status = "OTHER_OUTCOME_CHANGE"
            required.append({
                "appendix": appendix,
                "pair": pairs[(left_key, right_key)],
                "left_revision_key": left_key,
                "right_revision_key": right_key,
                "test_path": test_path,
                "junit_case_key": case_key,
                "before": before,
                "after": after,
                "status": status,
                "reason": reason,
                "left_suite_status": left.get("suite_status") if left else "UNRUN",
                "right_suite_status": right.get("suite_status") if right else "UNRUN",
                "observed_partial_before": left_case.get("status") if left_case else None,
                "observed_partial_after": right_case.get("status") if right_case else None,
                "left_returncode": left.get("returncode") if left else None,
                "right_returncode": right.get("returncode") if right else None,
                "left_test_blob_oid": left.get("test_blob_oid") if left else None,
                "right_test_blob_oid": right.get("test_blob_oid") if right else None,
            })
    return required


def _md_cell(record: dict[str, Any] | None) -> str:
    if record is None:
        return "UNRUN (no result record)"
    status = record.get("suite_status", "UNRUN")
    sha = record.get("test_blob_oid")
    if record.get("cell_presence") == "MISSING":
        return "UNRUN (verified path absent)"
    counts = record.get("case_counts", {})
    counts_text = ",".join(f"{key[0]}={value}" for key, value in sorted(counts.items())) or "no cases"
    return f"{status} ({counts_text}); SHA `{sha}`"


def _write_report(
    package_dir: Path,
    raw_dir: Path,
    report: dict[str, Any],
    *,
    output_path: Path | None = None,
) -> None:
    matrix = {(row["revision_key"], row["test_path"]): row for row in report["runs"]}
    initial_results = package_dir / "raw/p41-20260924T084614Z-77175/results.json"
    remap_receipt = package_dir / "raw/p41-initial-artifact-path-remap.json"
    initial_results_sha = _sha256(initial_results) if initial_results.is_file() else "not available"
    remap_sha = _sha256(remap_receipt) if remap_receipt.is_file() else "not available"
    prior_timeout_paths = (
        package_dir / "raw/p41-timeout-rerun-20260924T112317Z-14479/results.json",
        package_dir / "raw/p41-timeout-rerun-20260924T120847Z-43051/results.json",
        package_dir / "raw/p41-timeout-rerun-20260924T122853Z-47867/results.json",
    )
    prior_timeout_citations = "; ".join(
        f"`{result_path.relative_to(package_dir)}` SHA-256 `{_sha256(result_path)}`"
        for result_path in prior_timeout_paths
        if result_path.is_file()
    ) or "no retained timeout rerun receipt"
    resource_result = report.get("resource_summary")
    if not isinstance(resource_result, dict):
        resource_result = _resource_summary_for_report(report["runs"])
    resource_metrics = resource_result.get("metrics", {})
    if resource_result.get("status") == "UNRUN":
        resource_summary = (
            "Resource measurements: UNRUN; "
            f"{resource_result.get('reason') or 'resource summary inputs are incomplete'}. "
            f"{resource_result.get('sampled_cell_count', 0)} cells have complete resource samples."
        )
    elif resource_result.get("status") == "fail":
        resource_summary = (
            "Resource measurements: FAIL; "
            f"{resource_result.get('reason') or 'a resource guard fired'}. "
            f"{resource_result.get('sampled_cell_count', 0)} cells have complete resource samples."
        )
    else:
        resource_summary = (
            f"Resource measurements: PASS; {resource_result['sampled_cell_count']} present process groups; "
            f"peak group RSS {resource_metrics['peak_process_group_rss_kib']} KiB; "
            f"peak group CPU {resource_metrics['peak_process_group_cpu_percent']}%; "
            f"peak concurrent pytest groups {resource_metrics['peak_active_process_group_count']}; "
            f"peak aggregate pytest RSS {resource_metrics['peak_aggregate_process_group_rss_kib']} KiB; "
            f"peak aggregate pytest CPU {resource_metrics['peak_aggregate_process_group_cpu_percent']}%; "
            f"minimum system free memory {resource_metrics['minimum_system_memory_free_percent']}%; "
            f"maximum swap growth {resource_metrics['maximum_swap_growth_bytes']} bytes; "
            f"minimum scratch free space {resource_metrics['minimum_scratch_volume_free_bytes']} bytes."
        )
    resource_policy = (
        f"This invocation admits at most {report['environment_policy']['max_process_groups']} "
        f"pytest process groups (harness maximum {MAX_PROCESS_GROUPS}; CLI default {DEFAULT_PROCESS_GROUPS}). "
        f"A light profile must finish within 60 seconds, use {ADAPTIVE_MIN_GROUP_RSS_KIB}–"
        f"{ADAPTIVE_MAX_GROUP_RSS_KIB} KiB RSS and at most {ADAPTIVE_MAX_GROUP_CPU_PERCENT}% CPU, "
        "with zero swap growth. Each launch is staggered by 0.5 seconds and rechecked against "
        "current process-group RSS/CPU, memory free percent, swap and disk. Reserve admission "
        "projects 1.25x RSS and the remaining peak-growth budget of every active profiled group, "
        "plus the candidate against free memory above the "
        f"{HARD_MEMORY_RESERVE_PERCENT}% hard reserve. "
        f"Projected admission CPU is capped at {ADAPTIVE_MAX_BATCH_CPU_PERCENT}%; the sampled running "
        f"hard limit is {MAX_RUNNING_BATCH_CPU_PERCENT}% to tolerate short accounting jitter while "
        "remaining below seven CPU cores. Profiles are scoped to the pinned runtime revision and "
        "test blob. Each revision/path cell in this matrix is unique; completed exact cells "
        "are reused rather than dispatched again. This pre-repair scope has no safe profiled "
        "overlap. Unprofiled, native, measured-heavy and resource-exclusive groups run alone "
        "and are scheduled after bounded ordinary cells. Each child is sampled "
        "every five seconds. A red or unavailable guard "
        "pauses dispatch and checkpoints unstarted cells as UNRUN. SIGINT/SIGTERM sets a cooperative "
        "stop event; active workers terminate only their own PGID, and the scheduler drains and "
        "checkpoints active and unstarted cells as UNRUN. Live descendants left after the leader "
        "exits are targeted for termination; survivors of SIGKILL stop further admission."
    )
    lines = [
        "# Four-base P41 test baselines",
        "",
        f"Run: `{report['run_id']}`. This is a measurement of the Phase 0 merge head before repair.",
        "",
        "## Discrepancies and scope",
        "",
        f"The earlier initial and five controlled-timeout receipts did not record effective source import origins. The shared venv's editable `.pth` pointed at the execution-base checkout outside pytest; repository `conftest.py` may then prepend each checkout's source during pytest startup. Those receipts do not prove that the wrong code was imported, but their source identity was not established. This matrix requires checkout-local `PYTHONPATH` and verifies `polisyos` and `tools` origins before execution. It reuses {report.get('reused_cell_count', 0)} completed checkpoint rows only after pinned checkout/origin, per-row `PYTHONPATH`, env/command, source-blob, and JUnit SHA checks; the earlier manifest without explicit source-import policy additionally requires its exact legacy-harness digest and matching row evidence. It does not reuse initial or timeout-rerun result files. The three retained timeout-rerun receipts are: {prior_timeout_citations}.",
        "",
        f"The original 7-group initial wave had no resource samples and remains provisional (`raw/p41-20260924T084614Z-77175/results.json` SHA-256 `{initial_results_sha}`). Its 300 moved JUnit/log artifacts are byte-mapped in `raw/p41-initial-artifact-path-remap.json` SHA-256 `{remap_sha}`; the six no-byte timeout artifacts are represented explicitly. The source-import discrepancy is resolved only for this controlled replay.",
        "",
        resource_policy,
        "",
        resource_summary,
        "",
        f"The requested denominator is **{report['requested_test_path_count']} test paths** (`policy-engine/tests/**/*.py`, selected by exact Appendix A/B, R14, hardening, and planned touched-file paths). The complete tracked-test census counted {report['tree_python_path_denominator']} Python paths across the four pinned Git trees; requested-file availability is recorded per revision below.",
        "",
        f"The four-base matrix has {report['matrix_cell_count']} cells: {report['present_cell_count']} present and executed or explicitly UNRUN, {report['missing_cell_count']} verified missing. Missing means the exact path is absent from that revision's tracked Git tree; it is not a pass. The whole-file SHA is retained as context; per-case attribution uses the exact test AST and statically resolved test-input closure.",
        "",
        (
            f"Shared runner: Python {report['runtime']['python']}, "
            f"pytest {report['runtime']['pytest']}; CPU JAX. "
            "Main-revision timing pilots use three times a previously controlled duration "
            f"for known long files (or an explicit {BOOTSTRAP_ALARM_SECONDS}s pilot ceiling); "
            "other bases use three times the larger of the measured main and previously "
            f"controlled whole-file durations, with a {MIN_MEASURED_ALARM_SECONDS}s floor "
            "when the pilot has cases. If the pilot has no cases, sibling alarms include "
            f"its alarm and use at least {BOOTSTRAP_ALARM_SECONDS}s and the previous "
            "controlled ceiling, if any; the pilot's actual status is recorded separately. "
            "Runtime revisions cannot share a light profile merely because test bytes "
            "match; each unprofiled sibling runs alone."
        ),
        "",
        f"Production data input: `{report['data_root']}/manifest.json` SHA-256 `{report['data_manifest_sha256']}`. The path resolved identically from all four checkouts; preflight also verifies that the production_data root and manifest have no write bits (the per-checkout mode and read-only verdict are in `results.json`). Environment values were allowlisted; `.env` loading was disabled and no environment values are recorded.",
        "",
        "The harness predicate is: a selected test case's status at a fixed Git revision and test-source blob under the shared local environment. It reads Git HEAD/tree/blob identities, the production-data manifest hash, pytest JUnit case status, and process exit status. Exit status checks runner integrity; JUnit supplies the per-case result. `UNRUN` means the harness could not inspect/execute a cell. Native-resource isolation is detected from direct imports/use in each test module; transitive or dynamic native use is `unresolved_by_construction`.",
        "",
        "P38 divergence: the property is the actual test-case outcome; the implementation reads JUnit testcase status and uses process exit only as a runner-integrity signal. A divergent case is a test that passed but pytest exits nonzero after a session/plugin error, or a missing/incomplete JUnit artifact; those cells are marked `FAIL` or `UNRUN`, never green by exit code alone. P41 attribution compares the exact testcase AST and test-input closure: method/decorators, class context, imports, marks, fixtures/hooks, local helpers/constants, and applicable conftest files. The full test-file SHA is recorded but is not an attribution gate. Dynamic or unresolved test-side dependencies stay `not_established`; identical method AST with changed/unmeasured fixture scope is reported separately.",
        "",
        (
            f"R6 named-case note: `{R6_DISCRIMINATING_CASE[0]}` / `{R6_DISCRIMINATING_CASE[1]}` has identical method ASTs across all four bases but differing test-context signatures, and at least one input closure is unresolved (see `r6_discriminating_case_inputs` in `results.json`). Any observed pass-to-fail remains recorded as `PASS_TO_FAIL`; the closure difference withholds owner attribution, not the R6 repair requirement."
            if R6_DISCRIMINATING_CASE[0] in REQUESTED_TEST_PATHS
            else "R6 discriminating case is outside this selected scope; no R6 per-case conclusion is made here."
        ),
        "",
        "## Revision and environment identity",
        "",
        f"The report/output checkout is `{report['output_checkout']['checkout']}` on `{report['output_checkout']['branch']}` at `{report['output_checkout']['head']}` (postflight `{report['output_checkout']['postflight_head']}`). Its complete tracked/dirty path delta from Phase 0 is confined to `{INTEGRATION_PACKAGE_RELATIVE}` and one byte-checked `policy-engine/.gitignore` rule for that package's ignored `raw/` outputs; the tested Phase 0 checkout remains the separate exact 73c worktree. The integration checkout's product source, tests, and schema therefore match Phase 0 for this measurement.",
        "",
        "| Revision | Commit | Branch | Worktree | Tracked test `.py` paths / `test_*.py` modules | Requested present | Data root mode | pytest.ini blob |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for rev in report["revisions"]:
        lines.append(
            f"| {rev['label']} | `{rev['commit']}` | `{rev['branch']}` | `{rev['checkout']}` | {rev['tracked_test_python_paths']} / {rev['tracked_test_modules']} | {rev['requested_present']}/{report['requested_test_path_count']} | `{rev['data_root_mode']}` read-only | `{rev['pytest_ini_blob']}` |"
        )
    lines.extend([
        "",
    ])
    safety_skips = report.get("safety_skipped_cells", [])
    if safety_skips:
        lines.extend([
            "## Declared safety skips (UNRUN)",
            "",
            "These cells remain in the requested denominator. The test was not launched because its helper copies from the read-only production_data tree, which is prohibited.",
            "",
            "| Revision | Test file | Status | Code | Reason |",
            "|---|---|---|---|---|",
        ])
        for cell in safety_skips:
            lines.append(
                f"| {cell['revision_key']} | `{cell['test_path']}` | UNRUN | `{cell['code']}` | {cell['reason']} |"
            )
        lines.append("")
    lines.extend([
        "## Whole-file four-base matrix",
        "",
        "Each cell lists the suite result, JUnit case counts (`p` passed, `f` failed, `e` error, `s` skipped), and the test-file Git blob OID. Full JUnit, stdout, stderr, and machine-readable results are in the cited raw run directory.",
    ])
    for label, paths in (
        ("Appendix A/B and initial repair paths (32)", INITIAL_TEST_PATHS),
        ("Additional pre-repair touched paths (68)", ADDON_TEST_PATHS),
        (
            f"Additional selected paths ({sum(path not in set(INITIAL_TEST_PATHS + ADDON_TEST_PATHS) for path in REQUESTED_TEST_PATHS)})",
            tuple(path for path in REQUESTED_TEST_PATHS if path not in set(INITIAL_TEST_PATHS + ADDON_TEST_PATHS)),
        ),
    ):
        selected_paths = [path for path in paths if path in REQUESTED_TEST_PATHS]
        if not selected_paths:
            continue
        lines.extend([
            "",
            f"### {label}",
            "",
            "| Test file | 78187878e | 00d946c2b | 5fd3ebcc1 | 73c656744 |",
            "|---|---|---|---|---|",
        ])
        for test_path in selected_paths:
            cells = [
                _md_cell(matrix.get((rev["key"], test_path)))
                for rev in report["revisions"]
            ]
            lines.append(f"| `{test_path.removeprefix('policy-engine/')}` | " + " | ".join(cells) + " |")

    missing = [
        (rev["label"], path)
        for rev in report["revisions"]
        for path, source in rev["files"].items()
        if source["status"] == "MISSING"
    ]
    lines.extend(["", "## Verified missing cells", ""])
    if missing:
        lines.extend(f"- `{label}`: `{path}`" for label, path in missing)
    else:
        lines.append("None.")

    diff_counts = Counter(diff["status"] for diff in report["case_diffs"])
    appendix_counts = Counter(case["status"] for case in report["appendix_case_results"])
    appendix_count_text = ", ".join(
        f"`{status}`={count}" for status, count in sorted(appendix_counts.items())
    ) or "no Appendix identities in this scope"
    lines.extend([
        "",
        "## Exact Appendix A/B named cases",
        "",
        f"The tracked harness embeds {APPENDIX_REQUIRED_CASE_COUNT} exact required identities (37 A, 37 B). The earlier identity-source receipt is optional provenance only (status: `{report.get('appendix_case_identity_source', {}).get('status', 'unavailable')}`); it is never used for outcomes. A required case is `UNRUN` if its exact JUnit key is missing or either relevant suite cell is missing, incomplete, or `UNRUN`.",
        "",
        f"In-scope identity outcomes: {len(report['appendix_case_results'])}/{APPENDIX_REQUIRED_CASE_COUNT}; {appendix_count_text}.",
        "",
        "| Appendix | Required comparison | Test path | Exact JUnit case key | Before | After | Status | Reason |",
        "|---|---|---|---|---|---|---|---|",
    ])
    if report["appendix_case_results"]:
        for case in report["appendix_case_results"]:
            lines.append(
                f"| {case['appendix']} | {case['pair']} | `{case['test_path']}` | `{case['junit_case_key']}` | {case['before']} | {case['after']} | {case['status']} | {case.get('reason') or '—'} |"
            )
    else:
        lines.append("| — | — | — | — | — | — | No Appendix identities selected | — |")
    lines.extend([
        "",
        "## Per-case outcome diffs",
        "",
        "`PASS_TO_FAIL` always records the observed JUnit transition. `case_input_equivalence` separately compares the exact testcase AST and the statically resolved test-side input closure; it does not claim full production behavioral-input closure. Every owner remains `UNRESOLVED` here until the changed-path intersection is reviewed. Whole-file SHA differences alone never relabel unchanged test cases or waive a pass-to-fail.",
        "",
        "Counts: " + (", ".join(f"`{status}`={count}" for status, count in sorted(diff_counts.items())) or "no case changes"),
        "",
        "| Comparison | Test path | Case | Before | After | Status | Test input closure | Owner | Same source blob |",
        "|---|---|---|---|---|---|---|---|---|",
    ])
    nontrivial_diffs = [
        diff for diff in report["case_diffs"] if diff["status"] not in {"MISSING", "UNRUN"}
    ]
    if nontrivial_diffs:
        for diff in nontrivial_diffs:
            lines.append(
                f"| {diff['pair']} | `{diff['test_path']}` | `{diff.get('case') or ('suite' if diff['status'].startswith('SUITE_') else '—')}` | {diff.get('before', diff.get('before_suite_status', '—'))} | {diff.get('after', diff.get('after_suite_status', '—'))} | {diff['status']} | {diff.get('case_input_equivalence', '—')} | {diff.get('owner_attribution', 'UNRESOLVED')} | {diff.get('same_test_source', '—')} |"
            )
    else:
        lines.append("| — | — | — | — | — | No comparable case changes | — | — | — |")

    lines.extend([
        "",
        "## Inputs, output receipts, and limitations",
        "",
        f"Harness SHA-256: `{report['harness_sha256']}`. Machine-readable matrix: `{report['raw_package_path']}/results.json` SHA-256 `{report['results_sha256']}`.",
        "",
        "Every run record in `results.json` includes the complete command, allowlisted environment variable names, timeout basis, return code, elapsed time, test-source SHA, case identities/statuses, and SHA-256/size for its JUnit, stdout, and stderr files. Logs are retained in the raw directory; values from the inherited environment are never logged.",
        "",
        "Unresolved by construction: dynamic/generated tests not represented by the named tracked files; native dependencies loaded transitively rather than directly named in a test module; tests that intentionally mutate ignored paths; and issue-owner attribution for identical red results, which requires review of the retained failing case output.",
        "",
    ])
    (output_path or (package_dir / "BASELINES.md")).write_text("\n".join(lines), encoding="utf-8")


def _publish_typed_unrun_receipt(
    *,
    package_dir: Path,
    external_run_dir: Path,
    run_id: str,
    scope: str,
    failure_stage: str,
    reason: str,
    environment_keys: list[str],
    resource_snapshot: dict[str, Any] | None = None,
    inspection_inputs: list[dict[str, Any]] | None = None,
) -> int:
    """Retain a typed UNRUN matrix when admission fails before test execution."""
    destination = package_dir / "raw" / run_id
    _require(not destination.exists(), f"refusing to overwrite typed UNRUN receipt: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    cells = [
        {
            "revision_key": revision["key"],
            "revision_label": revision["label"],
            "commit": revision["commit"],
            "test_path": test_path,
            "cell_presence": "UNRUN",
            "test_blob_oid": None,
            "suite_status": "UNRUN",
            "inspection_error": reason,
            "returncode": None,
            "cases": [],
            "artifacts": {},
        }
        for revision in REVISIONS
        for test_path in REQUESTED_TEST_PATHS
    ]
    appendix_cases = [
        {
            "appendix": appendix,
            "pair": next(label for left, right, label in COMPARISON_PAIRS if (left, right) == (left_key, right_key)),
            "left_revision_key": left_key,
            "right_revision_key": right_key,
            "test_path": test_path,
            "junit_case_key": case_key,
            "before": "UNRUN",
            "after": "UNRUN",
            "status": "UNRUN",
            "reason": "no test process was admitted before this required case could be collected",
        }
        for appendix, left_key, right_key, test_path, case_keys in APPENDIX_REQUIRED_CASE_GROUPS
        if test_path in REQUESTED_TEST_PATHS
        for case_key in case_keys
    ]
    output_checkout: dict[str, Any] | None
    try:
        output_checkout = _inspect_integration_checkout()
    except Exception:
        output_checkout = None
    report = {
        "schema": "policyos.e02r2.p41-baseline.v1",
        "verdict": "UNRUN",
        "failure_stage": failure_stage,
        "reason": reason,
        "exit_code": 2,
        "run_id": run_id,
        "scope": scope,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "harness_sha256": _sha256(Path(__file__).resolve()),
        "requested_test_path_count": len(REQUESTED_TEST_PATHS),
        "requested_test_paths": list(REQUESTED_TEST_PATHS),
        "matrix_cell_count": len(cells),
        "present_cell_count": None,
        "missing_cell_count": None,
        "unrun_cell_count": len(cells),
        "source_presence_verdict": "UNRUN",
        "output_checkout": output_checkout,
        "expected_revisions": [
            {
                "key": revision["key"],
                "label": revision["label"],
                "commit": revision["commit"],
                "checkout": revision["checkout"],
                "inspection_status": "UNRUN",
            }
            for revision in REVISIONS
        ],
        "environment_policy": {
            "allowlisted_keys": environment_keys,
            "secret_values_logged": False,
            "dotenv_disabled": True,
            "jax_platforms": "cpu",
            "source_import_policy": "checkout-local-PYTHONPATH-required",
        },
        "data_root_expected": str(DATA_ROOT),
        "data_root_status": "UNRUN",
        "data_manifest_expected_sha256": EXPECTED_DATA_MANIFEST_SHA256,
        "resource_start_snapshot": resource_snapshot,
        "inspection_inputs": inspection_inputs or [],
        "inspection_disclosure": {
            "verdict": "UNRUN",
            "failed_stage": failure_stage,
            "failed_gate": reason,
            "completed_test_outcomes_reused": False,
        },
        "runs": cells,
        "appendix_required_case_count": APPENDIX_REQUIRED_CASE_COUNT,
        "appendix_case_identity_source": {
            **_appendix_identity_source_receipt(),
            "use": "exact test identity provenance only; no outcomes reused",
        },
        "appendix_case_result_count": len(appendix_cases),
        "appendix_case_unselected_count": APPENDIX_REQUIRED_CASE_COUNT - len(appendix_cases),
        "appendix_case_results": appendix_cases,
    }
    (external_run_dir / "results.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (external_run_dir / "UNRUN.md").write_text(
        f"# P41 baseline UNRUN\n\n"
        f"Run `{run_id}` did not admit any test process. Stage: `{failure_stage}`.\n\n"
        f"Reason: {reason}\n\n"
        f"The {len(cells)} matrix cells and {len(appendix_cases)} in-scope required Appendix cases remain `UNRUN`; source presence, JUnit outcomes, and owners were not inferred. "
        f"See `results.json` for the full typed cell denominator.\n",
        encoding="utf-8",
    )
    moved = _run(["mv", str(external_run_dir), str(destination)])
    _require(moved.returncode == 0, f"could not publish typed UNRUN receipt: {moved.stderr.strip()}")
    _require(not external_run_dir.exists() and destination.is_dir(), "typed UNRUN receipt move did not verify")
    results_path = destination / "results.json"
    reread = json.loads(results_path.read_text(encoding="utf-8"))
    _require(
        reread.get("verdict") == "UNRUN" and len(reread.get("runs", [])) == len(cells),
        "typed UNRUN receipt readback failed",
    )
    print(f"P41 matrix UNRUN before test admission ({len(cells)} cells): {reason}")
    print(f"Raw receipt: {destination.relative_to(INTEGRATION_CHECKOUT)}")
    print(f"results.json sha256: {_sha256(results_path)}")
    return 2


def _reuse_input_disclosures(result_paths: list[Path]) -> list[dict[str, Any]]:
    """Return safe path and digest metadata for every inspected reuse input."""
    disclosed: list[dict[str, Any]] = []
    for result_path in result_paths:
        item: dict[str, Any] = {
            "path": str(result_path),
            "kind": "checkpoint_directory" if result_path.is_dir() else "results_file",
            "exists": result_path.exists(),
        }
        candidates = (
            [result_path / "manifest.json", result_path / "progress.jsonl"]
            if result_path.is_dir()
            else [result_path]
        )
        file_inputs: list[dict[str, Any]] = []
        for path in candidates:
            entry: dict[str, Any] = {"path": str(path), "exists": path.is_file(), "sha256": None}
            if path.is_file():
                try:
                    entry["sha256"] = _sha256(path)
                except Exception as exc:
                    entry["inspection_error"] = f"{type(exc).__name__}: {exc}"
            file_inputs.append(entry)
        item["files"] = file_inputs
        disclosed.append(item)
    return disclosed


def run_matrix(args: argparse.Namespace) -> int:
    package_dir = Path(__file__).resolve().parent
    integration_checkout = INTEGRATION_CHECKOUT
    expected_counts = {"initial": 32, "touched": 68, "pre-repair": 100}
    expected_count = expected_counts.get(args.scope, len(REQUESTED_TEST_PATHS))
    _require(len(REQUESTED_TEST_PATHS) == expected_count, f"{args.scope} test denominator is not {expected_count}")
    _require(len(set(REQUESTED_TEST_PATHS)) == len(REQUESTED_TEST_PATHS), "duplicate requested test path")

    now = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"p41-{args.scope}-{now}-{os.getpid()}"
    external_run_dir = args.scratch_root / run_id
    _require(not external_run_dir.exists(), f"refusing to overwrite existing scratch run: {external_run_dir}")
    external_run_dir.mkdir(parents=True)
    home = external_run_dir / "isolated-home"
    home.mkdir()
    probe_env = _safe_environment(external_run_dir / "probe-tmp", home)
    (external_run_dir / "probe-tmp").mkdir()

    try:
        output_checkout_identity = _inspect_integration_checkout()
        appendix_identity_source = _appendix_identity_source_receipt()
        revision_records = [_inspect_checkout(revision, package_dir) for revision in REVISIONS]
        for revision_record in revision_records:
            revision_record["module_import_origins"] = _verify_import_origins(
                Path(revision_record["checkout"]), probe_env
            )
        runtime = _runtime_versions(probe_env)
        ini_blobs = {revision["pytest_ini_blob"] for revision in revision_records}
        _require(len(ini_blobs) == 1, f"pytest.ini differs across baselines: {sorted(ini_blobs)}")
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        (external_run_dir / "preflight-error.txt").write_text(
            f"UNRUN: preflight inspection failed: {reason}\n",
            encoding="utf-8",
        )
        return _publish_typed_unrun_receipt(
            package_dir=package_dir,
            external_run_dir=external_run_dir,
            run_id=run_id,
            scope=args.scope,
            failure_stage="preflight_inspection",
            reason=reason,
            environment_keys=sorted(probe_env),
        )

    try:
        start_snapshot = _resource_snapshot(os.getpgrp(), args.scratch_root)
        start_guard = _resource_guard_reason(
            start_snapshot,
            start_snapshot["system_swap_used_bytes"],
        )
    except Exception as exc:
        return _publish_typed_unrun_receipt(
            package_dir=package_dir,
            external_run_dir=external_run_dir,
            run_id=run_id,
            scope=args.scope,
            failure_stage="resource_preflight",
            reason=f"{type(exc).__name__}: {exc}",
            environment_keys=sorted(probe_env),
        )
    if start_guard is not None:
        return _publish_typed_unrun_receipt(
            package_dir=package_dir,
            external_run_dir=external_run_dir,
            run_id=run_id,
            scope=args.scope,
            failure_stage="resource_admission_guard",
            reason=start_guard,
            environment_keys=sorted(probe_env),
            resource_snapshot=start_snapshot,
        )
    reuse_paths = args.reuse_results + ([args.resume_run] if args.resume_run is not None else [])
    try:
        reuse_cells = _verified_reuse_rows(
            reuse_paths,
            revision_records,
            runtime,
            sorted(probe_env),
            package_dir,
        )
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        return _publish_typed_unrun_receipt(
            package_dir=package_dir,
            external_run_dir=external_run_dir,
            run_id=run_id,
            scope=args.scope,
            failure_stage="resume_receipt_inspection",
            reason=reason,
            environment_keys=sorted(probe_env),
            resource_snapshot=start_snapshot,
            inspection_inputs=_reuse_input_disclosures(reuse_paths),
        )

    checkpoint_dir = external_run_dir / "checkpoint"
    checkpoint_manifest_path = _write_checkpoint_manifest(
        checkpoint_dir,
        run_id,
        REQUESTED_TEST_PATHS,
        revision_records,
        runtime,
        sorted(probe_env),
    )
    progress_path = checkpoint_dir / "progress.jsonl"
    with progress_path.open("x", encoding="utf-8"):
        pass

    def checkpoint_row(row: dict[str, Any]) -> None:
        _append_checkpoint_row(progress_path, row)

    # A declared safety skip is a measured matrix outcome (typed UNRUN), not a
    # missing cell and not a reason to shrink the requested denominator.
    excluded_safety_reuse_cells = sorted(
        (revision_key, test_path)
        for revision_key, test_path in reuse_cells
        if test_path in DECLARED_SAFETY_SKIPS
    )
    for key in excluded_safety_reuse_cells:
        reuse_cells.pop(key)
    for row in sorted(
        reuse_cells.values(),
        key=lambda item: (item["revision_key"], item["test_path"]),
    ):
        checkpoint_row(row)

    safety_skip_rows = [
        _safety_skip_row(revision, test_path)
        for revision in revision_records
        for test_path in DECLARED_SAFETY_SKIPS
        if test_path in REQUESTED_TEST_PATHS
        and test_path in revision["files"]
        and revision["files"][test_path]["status"] == "PRESENT"
    ]
    for row in safety_skip_rows:
        checkpoint_row(row)

    # The main checkout is the timing pilot and also supplies its matrix cells.
    main_revision = next(record for record in revision_records if record["key"] == "main")
    main_jobs = [
        Job(
            revision_key="main",
            test_path=test_path,
            test_blob_oid=main_revision["files"][test_path]["git_blob_oid"],
            timeout_seconds=max(
                BOOTSTRAP_ALARM_SECONDS,
                math.ceil(PREMEASURED_WALL_SECONDS.get(test_path, 0) * TIMEOUT_MULTIPLIER),
            ),
            timeout_basis=(
                f"3x previously controlled whole-file duration {PREMEASURED_WALL_SECONDS[test_path]}s"
                if test_path in PREMEASURED_WALL_SECONDS
                else "explicit 1800s main timing-pilot ceiling"
            ),
            exclusive_native=bool(main_revision["files"][test_path]["exclusive_native"]),
        )
        for test_path in REQUESTED_TEST_PATHS
        if test_path not in DECLARED_SAFETY_SKIPS
        and main_revision["files"][test_path]["status"] == "PRESENT"
        and ("main", test_path) not in reuse_cells
    ]
    workers = min(args.workers, MAX_PROCESS_GROUPS)
    revision_map = {r["key"]: r for r in revision_records}
    runs = [row for (revision_key, _), row in reuse_cells.items() if revision_key == "main"]
    runs.extend(safety_skip_rows)
    main_results = {row["test_path"]: row for row in runs if row["revision_key"] == "main"}
    light_profiles = _measured_light_profiles(list(reuse_cells.values()))
    main_jobs_by_path = {job.test_path: job for job in main_jobs}
    ready_sibling_jobs: list[Job] = []

    def dispatch_ready_siblings(*, flush: bool = False) -> None:
        while (
            len(ready_sibling_jobs) >= workers
            or (flush and ready_sibling_jobs)
            or (_SCHEDULER_HALT_REASON is not None and ready_sibling_jobs)
        ):
            batch_size = (
                len(ready_sibling_jobs)
                if _SCHEDULER_HALT_REASON is not None
                else min(workers, MAX_PROCESS_GROUPS, len(ready_sibling_jobs))
            )
            batch = ready_sibling_jobs[:batch_size]
            del ready_sibling_jobs[:batch_size]
            sibling_rows = _schedule(
                batch,
                revision_map,
                external_run_dir,
                home,
                args.scratch_root,
                start_snapshot["system_swap_used_bytes"],
                workers,
                light_profiles,
                checkpoint_row,
            )
            runs.extend(sibling_rows)
            light_profiles.update(_measured_light_profiles(sibling_rows))
            if _SCHEDULER_HALT_REASON is not None:
                break

    # Run each unmeasured main pilot alone to establish its timing bound.
    # Same-blob siblings at other runtime revisions still run alone unless
    # that exact revision/test cell has independent measured-light evidence.
    remaining_jobs: list[Job] = []
    for test_path in REQUESTED_TEST_PATHS:
        if test_path in DECLARED_SAFETY_SKIPS:
            continue
        if test_path in main_jobs_by_path:
            pilot_rows = _schedule(
                [main_jobs_by_path[test_path]],
                revision_map,
                external_run_dir,
                home,
                args.scratch_root,
                start_snapshot["system_swap_used_bytes"],
                workers,
                light_profiles,
                checkpoint_row,
            )
            runs.extend(pilot_rows)
            if pilot_rows:
                main_results[test_path] = pilot_rows[0]
                light_profiles.update(_measured_light_profiles(pilot_rows))
        pilot = main_results.get(test_path)
        same_blob_jobs: list[Job] = []
        for revision in revision_records:
            if revision["key"] == "main":
                continue
            file_record = revision["files"][test_path]
            if file_record["status"] != "PRESENT":
                continue
            if (revision["key"], test_path) in reuse_cells:
                continue
            measured_prior = PREMEASURED_WALL_SECONDS.get(test_path)
            if pilot and pilot.get("elapsed_seconds") is not None and pilot.get("cases"):
                measured_main = float(pilot["elapsed_seconds"])
                measured_ceiling = max(measured_main, measured_prior or 0.0)
                timeout_seconds = max(
                    MIN_MEASURED_ALARM_SECONDS,
                    math.ceil(measured_ceiling * TIMEOUT_MULTIPLIER),
                )
                timeout_basis = (
                    f"3x max(measured main {measured_main}s, previously controlled "
                    f"{measured_prior or 0.0}s); minimum {MIN_MEASURED_ALARM_SECONDS}s"
                )
            else:
                if measured_prior is not None:
                    pilot_alarm = int(pilot.get("timeout_seconds") or 0) if pilot else 0
                    timeout_seconds = max(
                        BOOTSTRAP_ALARM_SECONDS,
                        pilot_alarm,
                        math.ceil(measured_prior * TIMEOUT_MULTIPLIER),
                    )
                    timeout_basis = (
                        f"max({BOOTSTRAP_ALARM_SECONDS}s, main pilot alarm {pilot_alarm}s, "
                        f"3x previously controlled whole-file duration {measured_prior}s); "
                        "main pilot did not yield measurable cases"
                    )
                else:
                    pilot_alarm = int(pilot.get("timeout_seconds") or 0) if pilot else 0
                    timeout_seconds = max(BOOTSTRAP_ALARM_SECONDS, pilot_alarm)
                    timeout_basis = (
                        f"max({BOOTSTRAP_ALARM_SECONDS}s explicit fallback, main pilot alarm "
                        f"{pilot_alarm}s); main pilot did not yield measurable cases"
                    )
            candidate = Job(
                revision_key=revision["key"],
                test_path=test_path,
                test_blob_oid=file_record["git_blob_oid"],
                timeout_seconds=timeout_seconds,
                timeout_basis=timeout_basis,
                exclusive_native=bool(file_record["exclusive_native"]),
            )
            if _profile_light(candidate, light_profiles):
                same_blob_jobs.append(candidate)
            else:
                remaining_jobs.append(candidate)
        if same_blob_jobs:
            ready_sibling_jobs.extend(same_blob_jobs)
            dispatch_ready_siblings()
    dispatch_ready_siblings(flush=True)
    # Preserve the full denominator while doing bounded ordinary work before
    # long native/resource-exclusive cells that may stop admission on failure.
    remaining_jobs.sort(
        key=lambda job: (
            job.test_path in RESOURCE_EXCLUSIVE_TEST_PATHS,
            job.exclusive_native,
            job.timeout_seconds,
            job.test_path,
            job.revision_key,
        )
    )
    runs.extend(
        row for (revision_key, _), row in reuse_cells.items()
        if revision_key != "main"
    )
    runs.extend(
        _schedule(
            remaining_jobs,
            revision_map,
            external_run_dir,
            home,
            args.scratch_root,
            start_snapshot["system_swap_used_bytes"],
            workers,
            light_profiles,
            checkpoint_row,
        )
    )
    for revision in revision_records:
        for test_path, source in revision["files"].items():
            if source["status"] != "MISSING":
                continue
            runs.append({
                "revision_key": revision["key"],
                "revision_label": revision["label"],
                "commit": revision["commit"],
                "test_path": test_path,
                "cell_presence": "MISSING",
                "test_blob_oid": None,
                "timeout_seconds": None,
                "timeout_basis": "not applicable; path absent from pinned Git tree",
                "exclusive_native": False,
                "command": [],
                "environment_keys": [],
                "cwd": str(Path(revision["checkout"]) / "policy-engine"),
                "returncode": None,
                "timed_out": False,
                "elapsed_seconds": 0.0,
                "suite_status": "UNRUN",
                "inspection_error": "verified test path absent at pinned revision",
                "case_counts": {},
                "cases": [],
                "artifacts": {},
            })

    # A post-run P41 custody check catches branch movement or unexpected source
    # changes. It runs only after all pytest processes have completed.
    post_status: dict[str, list[str]] = {}
    for revision, record in zip(REVISIONS, revision_records, strict=True):
        checkout = Path(revision["checkout"])
        head = _git(checkout, "rev-parse", "HEAD")
        _require(head.returncode == 0 and head.stdout.strip() == record["commit"], f"HEAD moved during run: {revision['label']}")
        status = list(_checkout_status(checkout))
        allowed = _owned_package_paths(package_dir, checkout) if revision["key"] == "phase0_merge" else set()
        unexpected = sorted(set(status) - allowed)
        _require(not unexpected, f"unexpected post-run dirty paths at {revision['label']}: {unexpected}")
        post_status[revision["key"]] = status
    output_checkout_postflight = _inspect_integration_checkout()
    _require(
        output_checkout_postflight["head"] == output_checkout_identity["head"]
        and output_checkout_postflight["branch"] == output_checkout_identity["branch"],
        "integration output checkout branch or HEAD moved during baseline run",
    )

    case_diffs = _case_diff(runs)
    appendix_case_results = _appendix_case_results(runs)
    r6_discriminating_case_inputs = {
        revision["key"]: _case_context_signature(
            revision["key"], R6_DISCRIMINATING_CASE[0], R6_DISCRIMINATING_CASE[1]
        )
        for revision in revision_records
        if R6_DISCRIMINATING_CASE[0] in revision["files"]
        and revision["files"][R6_DISCRIMINATING_CASE[0]]["status"] == "PRESENT"
        and R6_DISCRIMINATING_CASE[0] in REQUESTED_TEST_PATHS
    }
    file_sha256 = _sha256(Path(__file__).resolve())
    package_raw = package_dir / "raw"
    destination = package_raw / run_id
    _require(not destination.exists(), f"refusing to overwrite package raw run: {destination}")
    raw_package_path = f"{package_raw.relative_to(integration_checkout).as_posix()}/{run_id}"
    report: dict[str, Any] = {
        "schema": "policyos.e02r2.p41-baseline.v1",
        "scope": args.scope,
        "run_id": run_id,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "harness_sha256": file_sha256,
        "requested_test_path_count": len(REQUESTED_TEST_PATHS),
        "requested_test_paths": list(REQUESTED_TEST_PATHS),
        "matrix_cell_count": len(REVISIONS) * len(REQUESTED_TEST_PATHS),
        "present_cell_count": sum(r["status"] != "MISSING" for rev in revision_records for r in rev["files"].values()),
        "missing_cell_count": sum(r["status"] == "MISSING" for rev in revision_records for r in rev["files"].values()),
        "tree_python_path_denominator": sum(r["tracked_test_python_paths"] for r in revision_records),
        "tree_python_path_denominators_by_revision": {
            r["key"]: r["tracked_test_python_paths"] for r in revision_records
        },
        "data_root": str(DATA_ROOT),
        "data_manifest_sha256": EXPECTED_DATA_MANIFEST_SHA256,
        "output_checkout": {
            **output_checkout_identity,
            "postflight_head": output_checkout_postflight["head"],
            "postflight_branch": output_checkout_postflight["branch"],
        },
        "resource_start_snapshot": start_snapshot,
        "checkpoint": {
            "manifest_path": "checkpoint/manifest.json",
            "manifest_sha256": _sha256(checkpoint_manifest_path),
            "progress_path": "checkpoint/progress.jsonl",
            "completed_row_count": sum(1 for _ in progress_path.open(encoding="utf-8")),
            "resume_command": f"--resume-run {raw_package_path}/checkpoint",
        },
        "measured_light_profile_count": len(light_profiles),
        "reused_cell_count": len(reuse_cells),
        "excluded_safety_reuse_cells": [
            {"revision_key": revision_key, "test_path": test_path}
            for revision_key, test_path in excluded_safety_reuse_cells
        ],
        "safety_skipped_cells": [
            {
                "revision_key": row["revision_key"],
                "test_path": row["test_path"],
                **row["safety_skip"],
            }
            for row in safety_skip_rows
        ],
        "reused_cells": [
            {
                "revision_key": revision_key,
                "test_path": test_path,
                "results_json": row.get("reused_from_results_json"),
                "results_sha256": row.get("reused_from_results_sha256"),
                "source_import_policy_reuse": row.get("source_import_policy_reuse"),
            }
            for (revision_key, test_path), row in sorted(reuse_cells.items())
        ],
        "runtime": runtime,
        "environment_policy": {
            "allowlisted_keys": sorted(probe_env),
            "secret_values_logged": False,
            "dotenv_disabled": True,
            "jax_platforms": "cpu",
            "source_import_policy": "checkout-local-PYTHONPATH",
            "module_import_origins_by_revision": {
                row["key"]: row["module_import_origins"] for row in revision_records
            },
            "max_process_groups": workers,
            "resource_guard": {
                "max_process_group_rss_kib": MAX_PROCESS_GROUP_RSS_KIB,
                "minimum_system_memory_free_percent": MIN_MEMORY_FREE_PERCENT,
                "maximum_swap_growth_bytes": MAX_SWAP_GROWTH_BYTES,
                "minimum_scratch_volume_free_bytes": MIN_DISK_FREE_BYTES,
                "sample_interval_seconds": RESOURCE_SAMPLE_SECONDS,
                "adaptive_minimum_memory_free_percent": ADAPTIVE_MIN_MEMORY_FREE_PERCENT,
                "adaptive_minimum_group_rss_kib": ADAPTIVE_MIN_GROUP_RSS_KIB,
                "adaptive_max_group_rss_kib": ADAPTIVE_MAX_GROUP_RSS_KIB,
                "adaptive_max_group_cpu_percent": ADAPTIVE_MAX_GROUP_CPU_PERCENT,
                "adaptive_max_batch_rss_kib": ADAPTIVE_MAX_BATCH_RSS_KIB,
                "adaptive_max_batch_cpu_percent": ADAPTIVE_MAX_BATCH_CPU_PERCENT,
                "max_running_batch_cpu_percent": MAX_RUNNING_BATCH_CPU_PERCENT,
                "projected_rss_multiplier": ADAPTIVE_RSS_PROJECTION_MULTIPLIER,
                "hard_reserve_projection": (
                    "sum(max(1.25*expected_peak_rss-current_group_rss,0)) for active PGIDs; "
                    "active growth plus candidate peak must fit free headroom"
                ),
                "hard_memory_reserve_percent": HARD_MEMORY_RESERVE_PERCENT,
                "launch_stagger_seconds": PROCESS_GROUP_LAUNCH_STAGGER_SECONDS,
                "cooperative_stop_signals": ["SIGINT", "SIGTERM"],
                "max_active_process_groups": MAX_PROCESS_GROUPS,
                "resource_exclusive_paths": sorted(RESOURCE_EXCLUSIVE_TEST_PATHS),
            },
        },
        "revisions": revision_records,
        "post_run_status_paths": post_status,
        "runs": sorted(runs, key=lambda row: (row["revision_key"], row["test_path"])),
        "resource_summary": _resource_summary_for_report(runs),
        "case_diffs": case_diffs,
        "appendix_required_case_count": APPENDIX_REQUIRED_CASE_COUNT,
        "appendix_case_identity_source": {
            **appendix_identity_source,
            "use": "exact test identity provenance only; no outcomes reused",
        },
        "appendix_case_result_count": len(appendix_case_results),
        "appendix_case_unselected_count": APPENDIX_REQUIRED_CASE_COUNT - len(appendix_case_results),
        "appendix_case_results": appendix_case_results,
        "r6_discriminating_case_inputs": r6_discriminating_case_inputs,
        "unresolved_by_construction": [
            f"Generated/dynamic test modules outside the {len(REQUESTED_TEST_PATHS)} named tracked paths.",
            "Native libraries loaded transitively or dynamically when no direct marker exists in a test module.",
            "Ignored-path mutations produced inside tests.",
            "Owner attribution for reds until retained failure output is reviewed.",
        ],
    }

    # Only after all test processes are finished do outputs enter the integration
    # checkout. The external run directory is retained if publishing fails.
    report["raw_package_path"] = raw_package_path
    byproduct_root = _move_test_byproducts(external_run_dir, args.scratch_root, run_id)
    report["byproducts_trash"] = _move_completed_byproducts_to_trash(
        byproduct_root,
        run_id,
        package_raw,
    )
    _canonicalize_published_artifact_paths(
        report["runs"], external_run_dir, destination, package_dir
    )
    (external_run_dir / "results.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    published = _run(["mv", str(external_run_dir), str(destination)])
    _require(published.returncode == 0, f"could not publish baseline run: {published.stderr.strip()}")
    _require(not external_run_dir.exists() and destination.is_dir(), "baseline output move did not verify")
    report["published_artifacts_verified"] = _verify_published_artifacts(
        report["runs"],
        integration_checkout,
    )
    results_path = destination / "results.json"
    report["results_sha256"] = _sha256(results_path)
    if args.scope in {"initial", "pre-repair"}:
        _write_report(package_dir, destination, report)
    elif args.scope == "custom":
        _write_report(package_dir, destination, report, output_path=destination / "BASELINES.md")
    else:
        (destination / "scope-summary.md").write_text(
            f"# P41 {args.scope} matrix\n\n"
            f"Run `{run_id}` covers {len(REQUESTED_TEST_PATHS)} requested test paths at four pinned bases. "
            f"See `results.json` (SHA-256 `{report['results_sha256']}`) for per-cell JUnit outcomes, "
            "Git blob SHAs, missing paths, and complete stdout/stderr receipts.\n",
            encoding="utf-8",
        )

    unrun_count = sum(row["suite_status"] == "UNRUN" for row in runs)
    print(f"Completed {len(runs)} matrix cells; {report['missing_cell_count']} cells are verified MISSING; {unrun_count} are UNRUN.")
    print(f"Raw outputs: {destination.relative_to(integration_checkout)}")
    baselines_path = destination / "BASELINES.md" if args.scope == "custom" else package_dir / "BASELINES.md"
    print(f"BASELINES.md: {baselines_path}")
    print(f"results.json sha256: {_sha256(results_path)}")
    return 2 if unrun_count else 0


def run_timeout_rerun(args: argparse.Namespace) -> int:
    """Repeat selected whole-file cells whose first alarm fired."""
    package_dir = Path(__file__).resolve().parent
    prior_path = args.prior_results
    _require(prior_path is not None and prior_path.is_file(), "--prior-results must name the initial results.json")
    prior_sha256 = _sha256(prior_path)
    prior = json.loads(prior_path.read_text(encoding="utf-8"))
    _require(prior.get("schema") == "policyos.e02r2.p41-baseline.v1", "prior matrix schema mismatch")
    prior_paths = prior.get("requested_test_paths")
    if not isinstance(prior_paths, list):
        prior_paths = sorted({row["test_path"] for row in prior.get("runs", [])})
    _require(
        len(prior_paths) == prior.get("requested_test_path_count")
        and len(prior_paths) == len(set(prior_paths)),
        "prior matrix test-path denominator is incomplete or duplicated",
    )
    global REQUESTED_TEST_PATHS
    REQUESTED_TEST_PATHS = tuple(prior_paths)
    prior_cells = {(row["revision_key"], row["test_path"]): row for row in prior["runs"]}
    eligible_targets = {
        key
        for key, row in prior_cells.items()
        if row.get("cell_presence") == "PRESENT"
        and row.get("suite_status") == "UNRUN"
        and row.get("timed_out") is True
    }

    now = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"p41-timeout-rerun-{now}-{os.getpid()}"
    external_run_dir = args.scratch_root / run_id
    _require(not external_run_dir.exists(), f"refusing to overwrite rerun scratch: {external_run_dir}")
    external_run_dir.mkdir(parents=True)
    home = external_run_dir / "isolated-home"
    home.mkdir()
    probe_tmp = external_run_dir / "probe-tmp"
    probe_tmp.mkdir()
    probe_env = _safe_environment(probe_tmp, home)

    output_checkout_identity = _inspect_integration_checkout()
    revision_records = [_inspect_checkout(revision, package_dir) for revision in REVISIONS]
    for revision_record in revision_records:
        revision_record["module_import_origins"] = _verify_import_origins(
            Path(revision_record["checkout"]), probe_env
        )
    revision_by_key = {record["key"]: record for record in revision_records}
    runtime = _runtime_versions(probe_env)
    _require(
        {record["pytest_ini_blob"] for record in revision_records} == {record["pytest_ini_blob"] for record in prior["revisions"]},
        "pytest.ini blob changed since the initial matrix",
    )

    jobs: list[Job] = []
    prior_attempts: list[dict[str, Any]] = []
    requested_targets: list[tuple[str, str]] = []
    for target in args.rerun_target or []:
        revision_key, separator, test_path = target.partition(":")
        _require(bool(separator) and bool(test_path), f"invalid --rerun-target value: {target!r}")
        requested_targets.append((revision_key, test_path))
    selected_targets = requested_targets or sorted(eligible_targets)
    _require(len(set(selected_targets)) == len(selected_targets), "duplicate --rerun-target")
    _require(
        set(selected_targets).issubset(eligible_targets),
        "--rerun-target must select present cells marked timed-out UNRUN by the prior matrix",
    )
    for revision_key, test_path in selected_targets:
        previous = prior_cells.get((revision_key, test_path))
        _require(previous is not None, f"initial matrix has no cell for {revision_key}:{test_path}")
        _require(
            previous.get("cell_presence") == "PRESENT"
            and previous.get("suite_status") == "UNRUN"
            and previous.get("timed_out") is True,
            f"cell is not a timed-out UNRUN: {revision_key}:{test_path}",
        )
        current = revision_by_key[revision_key]["files"][test_path]
        _require(current["status"] == "PRESENT", f"rerun path missing at {revision_key}: {test_path}")
        _require(
            current["git_blob_oid"] == previous["test_blob_oid"],
            f"test source changed since initial timeout: {revision_key}:{test_path}",
        )
        initial_timeout = int(previous["timeout_seconds"])
        _require(args.timeout_seconds > initial_timeout, f"rerun alarm must exceed prior {initial_timeout}s alarm")
        prior_attempts.append(previous)
        jobs.append(
            Job(
                revision_key=revision_key,
                test_path=test_path,
                test_blob_oid=current["git_blob_oid"],
                timeout_seconds=args.timeout_seconds,
                timeout_basis=(
                    f"explicit {args.timeout_seconds}s whole-file rerun after initial {initial_timeout}s alarm fired"
                ),
                exclusive_native=bool(current["exclusive_native"]),
            )
        )

    workers = min(args.workers, MAX_PROCESS_GROUPS)
    start_snapshot = _resource_snapshot(os.getpgrp(), args.scratch_root)
    start_guard = _resource_guard_reason(
        start_snapshot,
        start_snapshot["system_swap_used_bytes"],
    )
    _require(start_guard is None, f"run-level resource guard before timeout rerun: {start_guard}")
    runs = _schedule(
        jobs,
        revision_by_key,
        external_run_dir,
        home,
        args.scratch_root,
        start_snapshot["system_swap_used_bytes"],
        workers,
    )
    post_status: dict[str, list[str]] = {}
    for revision, record in zip(REVISIONS, revision_records, strict=True):
        checkout = Path(revision["checkout"])
        head = _git(checkout, "rev-parse", "HEAD")
        _require(head.returncode == 0 and head.stdout.strip() == record["commit"], f"HEAD moved during rerun: {revision['label']}")
        status = list(_checkout_status(checkout))
        allowed = _owned_package_paths(package_dir, checkout) if revision["key"] == "phase0_merge" else set()
        unexpected = sorted(set(status) - allowed)
        _require(not unexpected, f"unexpected post-rerun dirty paths at {revision['label']}: {unexpected}")
        post_status[revision["key"]] = status
    output_checkout_postflight = _inspect_integration_checkout()
    _require(
        output_checkout_postflight["head"] == output_checkout_identity["head"]
        and output_checkout_postflight["branch"] == output_checkout_identity["branch"],
        "integration output checkout branch or HEAD moved during timeout rerun",
    )

    report: dict[str, Any] = {
        "schema": "policyos.e02r2.p41-timeout-rerun.v1",
        "run_id": run_id,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "harness_sha256": _sha256(Path(__file__).resolve()),
        "prior_results_path": str(prior_path),
        "prior_results_sha256": prior_sha256,
        "prior_harness_sha256": prior["harness_sha256"],
        "requested_cell_count": len(selected_targets),
        "requested_test_path_count": len(REQUESTED_TEST_PATHS),
        "requested_test_paths": list(REQUESTED_TEST_PATHS),
        "requested_targets": [
            {"revision_key": revision_key, "test_path": test_path}
            for revision_key, test_path in selected_targets
        ],
        "timeout_seconds": args.timeout_seconds,
        "runtime": runtime,
        "data_root": str(DATA_ROOT),
        "data_manifest_sha256": EXPECTED_DATA_MANIFEST_SHA256,
        "output_checkout": {
            **output_checkout_identity,
            "postflight_head": output_checkout_postflight["head"],
            "postflight_branch": output_checkout_postflight["branch"],
        },
        "resource_start_snapshot": start_snapshot,
        "environment_policy": {
            "allowlisted_keys": sorted(probe_env),
            "secret_values_logged": False,
            "dotenv_disabled": True,
            "jax_platforms": "cpu",
            "source_import_policy": "checkout-local-PYTHONPATH",
            "module_import_origins_by_revision": {
                row["key"]: row["module_import_origins"] for row in revision_records
            },
            "max_process_groups": workers,
            "resource_guard": {
                "max_process_group_rss_kib": MAX_PROCESS_GROUP_RSS_KIB,
                "minimum_system_memory_free_percent": MIN_MEMORY_FREE_PERCENT,
                "maximum_swap_growth_bytes": MAX_SWAP_GROWTH_BYTES,
                "minimum_scratch_volume_free_bytes": MIN_DISK_FREE_BYTES,
                "sample_interval_seconds": RESOURCE_SAMPLE_SECONDS,
                "resource_exclusive_paths": sorted(RESOURCE_EXCLUSIVE_TEST_PATHS),
            },
        },
        "revisions": revision_records,
        "prior_attempts": prior_attempts,
        "post_run_status_paths": post_status,
        "runs": sorted(runs, key=lambda row: (row["revision_key"], row["test_path"])),
        "unresolved_by_construction": [
            "The rerun settles only the six initially timed-out cells; all other cells remain in the linked initial matrix.",
            "Native libraries loaded transitively or dynamically without a direct marker remain unresolved by construction.",
        ],
    }

    integration_checkout = INTEGRATION_CHECKOUT
    destination = package_dir / "raw" / run_id
    _require(not destination.exists(), f"refusing to overwrite package raw rerun: {destination}")
    report["raw_package_path"] = destination.relative_to(integration_checkout).as_posix()
    byproduct_root = _move_test_byproducts(external_run_dir, args.scratch_root, run_id)
    report["byproducts_trash"] = _move_completed_byproducts_to_trash(
        byproduct_root,
        run_id,
        package_dir / "raw",
    )
    _canonicalize_published_artifact_paths(
        report["runs"], external_run_dir, destination, package_dir
    )
    (external_run_dir / "results.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    published = _run(["mv", str(external_run_dir), str(destination)])
    _require(published.returncode == 0, f"could not publish timeout rerun: {published.stderr.strip()}")
    _require(not external_run_dir.exists() and destination.is_dir(), "timeout rerun move did not verify")
    report["published_artifacts_verified"] = _verify_published_artifacts(
        report["runs"],
        integration_checkout,
    )
    results_path = destination / "results.json"
    report["results_sha256"] = _sha256(results_path)
    (destination / "rerun-summary.md").write_text(
        f"# P41 timeout rerun\n\n"
        f"Initial matrix `{prior_path}` SHA-256 `{prior_sha256}` recorded {len(selected_targets)} selected present cells as timed-out UNRUN. "
        f"This rerun used the same four checkouts, environment policy and data manifest, with an explicit {args.timeout_seconds}s alarm. "
        f"Rerun results: `results.json` SHA-256 `{report['results_sha256']}`.\n",
        encoding="utf-8",
    )
    unrun_count = sum(row["suite_status"] == "UNRUN" for row in runs)
    print(f"Reran {len(runs)} timed-out whole-file cells; {unrun_count} remain UNRUN.")
    print(f"Raw outputs: {destination.relative_to(integration_checkout)}")
    print(f"results.json sha256: {_sha256(results_path)}")
    return 2 if unrun_count else 0


def _normalize_custom_test_paths(raw_paths: list[str]) -> tuple[str, ...]:
    """Validate exact repository-relative test paths for an ad hoc P41 replay."""
    _require(bool(raw_paths), "custom four-base scope requires at least one --test-file")
    normalized: list[str] = []
    for raw_path in raw_paths:
        path = Path(raw_path)
        parts = path.parts
        _require(not path.is_absolute(), f"--test-file must be repository-relative: {raw_path!r}")
        _require(path.as_posix() == raw_path, f"--test-file must use normalized POSIX path syntax: {raw_path!r}")
        _require(".." not in parts and "." not in parts, f"--test-file cannot traverse directories: {raw_path!r}")
        _require(parts[:2] == ("policy-engine", "tests"), f"--test-file must be under policy-engine/tests: {raw_path!r}")
        _require(path.suffix == ".py" and path.name.startswith("test_"), f"--test-file must name a test_*.py module: {raw_path!r}")
        normalized.append(path.as_posix())
    _require(len(normalized) == len(set(normalized)), "duplicate --test-file path")
    return tuple(normalized)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="store_true",
        help="run the four-base matrix and publish raw artifacts after all pytest jobs finish",
    )
    parser.add_argument("--scope", choices=("initial", "touched", "pre-repair"))
    parser.add_argument(
        "--test-file",
        action="append",
        default=[],
        metavar="policy-engine/tests/.../test_name.py",
        help="add one exact test path to a custom four-base scope; repeat for several; requires --run and cannot be combined with --scope",
    )
    parser.add_argument("--rerun-timeouts", action="store_true")
    parser.add_argument("--prior-results", type=Path)
    parser.add_argument(
        "--reuse-results",
        type=Path,
        action="append",
        default=[],
        help="reuse matching completed cells from a controlled prior run after identity/hash checks",
    )
    parser.add_argument(
        "--resume-run",
        type=Path,
        help="resume completed cells from an interrupted run's scratch/raw checkpoint directory",
    )
    parser.add_argument(
        "--rerun-target",
        action="append",
        default=[],
        metavar="REVISION_KEY:TEST_PATH",
        help="select an initially timed-out whole-file cell; repeat to select several",
    )
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--workers", type=int, default=DEFAULT_PROCESS_GROUPS)
    parser.add_argument("--scratch-root", type=Path, default=SCRATCH_ROOT)
    args = parser.parse_args()
    if args.run == args.rerun_timeouts:
        parser.error("pass exactly one of --run or --rerun-timeouts")
    if not 1 <= args.workers <= MAX_PROCESS_GROUPS:
        parser.error(f"--workers must be between 1 and {MAX_PROCESS_GROUPS}")
    args.scratch_root.mkdir(parents=True, exist_ok=True)
    if args.rerun_timeouts:
        if args.test_file or args.scope is not None:
            parser.error("--rerun-timeouts cannot be combined with --test-file or --scope")
        if args.prior_results is None:
            parser.error("--rerun-timeouts requires --prior-results")
        if args.timeout_seconds < 1800:
            parser.error("timeout reruns require an explicit alarm of at least 1800 seconds")
        global REQUESTED_TEST_PATHS
        REQUESTED_TEST_PATHS = INITIAL_TEST_PATHS
        return _run_with_stop_handlers(lambda: run_timeout_rerun(args))
    if args.test_file:
        if args.scope is not None:
            parser.error("custom --test-file paths cannot be combined with --scope")
        args.scope = "custom"
        REQUESTED_TEST_PATHS = _normalize_custom_test_paths(args.test_file)
    else:
        args.scope = args.scope or "pre-repair"
        scope_paths = {
            "initial": INITIAL_TEST_PATHS,
            "touched": ADDON_TEST_PATHS,
            "pre-repair": PRE_REPAIR_TEST_PATHS,
        }
        REQUESTED_TEST_PATHS = scope_paths[args.scope]
    return _run_with_stop_handlers(lambda: run_matrix(args))


if __name__ == "__main__":
    raise SystemExit(main())
