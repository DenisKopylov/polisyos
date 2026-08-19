#!/usr/bin/env python3
"""Validate the Layer 3 GY-N5 joint simulation horizon contract."""

from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

# Completed-work terminals per mode, owned here because this module's own return mapping is the
# only place that knows them. ``corrupt_field_drift_check`` reports "fail" when the drift was
# DETECTED (the correct outcome) and "pass" when it was missed, while ``main`` exits
# ``0 if status == "pass" else 1`` -- so this lane's healthy terminal is exit 1 and its DEFECT
# terminal is exit 0. The default {0} would admit exactly the failures and reject the good runs.
TIMING_HEALTHY_TERMINAL_EXIT_CODES: dict[str, list[int]] = {
    "corrupt-field-drift-check": [1],
}

import argparse
import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

import jax.numpy as jnp

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    ExecPlan,
    LoweredIR,
    LoweredIRRef,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
    ProgramOp,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.methods.catalog.simulation.dynamics import (
    _abm_result_stub,
    build_content_bound_abm_result,
)
from polisyos.ir.analytics.interventions import (
    InterventionContext,
    NodeIntervention,
    QueryTarget,
    VariableAssignment,
    identification_plan_for_intervention,
)
from polisyos.ir.analytics.ncm import ExogenousSpec, NCMSpec, StructuralEquation
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
    ConstraintRegistry,
)
from polisyos.ir.linker import LinkedIntervention, link_trinity
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.registry.registry_fragments import RegistryBundle
from polisyos.ir.trinity import TrinityBundle
from polisyos.runtime.quality.design_axes.coupling_composition import (
    CouplingEdge,
    build_coupling_graph,
)
from polisyos.runtime.quality.intervention_atom_binding import (
    InterventionAtomBinding,
    build_intervention_atom_binding,
    intervention_atom_target_selector_ref,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    EnginePlan,
    HorizonSpec,
    JointSimulationControllerError,
    JointSimulationHorizonController,
    JointSimulationRequest,
    ProofReceiptError,
    verify_simulation_receipt,
)
from polisyos.runtime.quality.world_model_record import (
    BranchMode,
    DataForgeBindingRef,
    FabricWorldRef,
    FoundryBindingRef,
    PolicySlotBinding,
    ResolvedSubstrateEntryRef,
    SimulationModelRef,
    SkgCausalPriorRef,
    SubstrateRegistryRef,
    WorldModelRecord,
    world_model_record_content_hash,
)
from tools.lib.timing import run_timed_entrypoint

OUTPUT_PATH = (
    "architecture/policy_design_case/layer3_gy_joint_simulation_horizon_contract.json"
)
SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy.joint_simulation_horizon_contract.v1"
ABM_STUB_SOURCE_FLIP_MUTATION_ID = "source_flip_abm_production_stub_restored"


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def build_live_payload(repo_root: Path) -> dict[str, Any]:
    """Recompute the N5 contract by exercising the live controller."""

    controller = JointSimulationHorizonController()
    static_result = controller.run(_request())
    dynamic_result = controller.run(_dynamic_request())
    none_result = controller.run(_declared_request(_request(), "none"))
    time_unrolled_result = controller.run(_declared_request(_dynamic_request(), "time_unrolled_SCM"))
    with tempfile.TemporaryDirectory(prefix="gy-n5-program-graph-") as tmp_dir:
        program_graph_result = controller.run(_program_graph_request(Path(tmp_dir)))
    coupling_blocked = controller.run(
        _request().model_copy(update={"coupling_graph": _coupling_graph("shared_resource")})
    )
    coupled_supported = controller.run(_coupled_request())
    queue_output_shape_gate = controller.run(_queue_tag_counterexample_request())
    unbacked_semantics = controller.run(
        _request().model_copy(
            update={
                "engine_plan": (
                    _request().engine_plan[0].model_copy(
                        update={"declared_equilibrium_semantics": "game_model"}
                    ),
                )
            }
        )
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.joint_simulation_horizon",
        "producer": "tools.quality.validation.check_layer3_gy_joint_simulation_horizon_contract",
        "source_modules": [
            "src/polisyos/runtime/quality/joint_simulation_horizon.py",
            "src/polisyos/runtime/quality/intervention_atom_binding.py",
            "src/polisyos/runtime/quality/world_model_record.py",
            "src/polisyos/foundry/execute/_internal/graph/__init__.py",
            "src/polisyos/foundry/methods/catalog/causal/ncm_engine.py",
            "src/polisyos/foundry/methods/catalog/simulation/coupled.py",
            "src/polisyos/foundry/methods/catalog/simulation/dynamics.py",
            "src/polisyos/ir/analytics/phase4_dynamics.py",
        ],
        "pattern_pass": {
            "relevant_ids": ["P01", "P02", "P05", "P17", "P28", "P29", "P31", "P32", "P33"],
            "target_correct_pattern": (
                "real engine run plus content-bound K_sim receipt; no K_world shrinkage"
            ),
            "missing_capability_labels": [],
            "acceptance_signal": "controller_run_and_mutation_red",
        },
        "positive_gate": {
            "status": "pass",
            "static_scm": _result_gate(static_result, ("income_subsidy", "balance_grant")),
            "dynamic_horizon": _result_gate(
                dynamic_result,
                ("capacity_inflow", "demand_inflow"),
            ),
            "none_semantics": _result_gate(none_result, ("income_subsidy", "balance_grant")),
            "time_unrolled_scm": _result_gate(
                time_unrolled_result,
                ("capacity_inflow", "demand_inflow"),
            ),
            "program_graph_equilibrium_scm": _result_gate(
                program_graph_result,
                ("income_subsidy", "balance_grant"),
            ),
            "registry_output_shape_gate": _registry_output_shape_gate(
                queue_output_shape_gate
            ),
            "coupling_gate": _coupling_gate_result(coupling_blocked, coupled_supported),
            "equilibrium_resolution_gate": _equilibrium_resolution_gate(unbacked_semantics),
            "abm_stub_strangle": _abm_stub_strangle_probe(repo_root),
        },
    }
    payload["behavioral_mutations"] = _mutation_reports(dynamic_result, payload)
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a committed or mutated payload semantically."""

    issues = _validate_payload_core(payload)
    mutation_reports = payload.get("behavioral_mutations")
    if not isinstance(mutation_reports, list) or not mutation_reports:
        issues.append({"code": "behavioral_mutations_missing"})
    else:
        for report in mutation_reports:
            if not isinstance(report, dict):
                issues.append({"code": "behavioral_mutation_invalid"})
                continue
            if report.get("status") != "red":
                issues.append(
                    {
                        "code": "behavioral_mutation_not_red",
                        "mutation": report.get("mutation"),
                    }
                )
    return {"status": "pass" if not issues else "fail", "issues": issues}


def _validate_payload_core(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate the semantic contract, excluding the mutation-report wrapper."""

    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "schema_version_drift"})
    positive = payload.get("positive_gate")
    if not isinstance(positive, dict):
        issues.append({"code": "positive_gate_missing"})
        return issues
    static_gate = positive.get("static_scm")
    dynamic_gate = positive.get("dynamic_horizon")
    none_gate = positive.get("none_semantics")
    time_unrolled_gate = positive.get("time_unrolled_scm")
    program_graph_gate = positive.get("program_graph_equilibrium_scm")
    if not isinstance(static_gate, dict):
        issues.append({"code": "static_scm_gate_missing"})
    else:
        issues.extend(
            _validate_gate(
                static_gate,
                expected_engine="ncm_parallel_worlds",
                expected_temporal="static",
                expected_output_shape="static_point",
                expected_semantics="static_SCM",
                require_evolving_state=False,
            )
        )
    if not isinstance(dynamic_gate, dict):
        issues.append({"code": "dynamic_horizon_gate_missing"})
    else:
        issues.extend(
            _validate_gate(
                dynamic_gate,
                expected_engine="system_dynamics",
                expected_temporal="multi_period",
                expected_output_shape="time_series_trajectory",
                expected_semantics="dynamic_SCM",
                require_evolving_state=True,
            )
        )
    if not isinstance(none_gate, dict):
        issues.append({"code": "none_semantics_gate_missing"})
    else:
        issues.extend(
            _validate_gate(
                none_gate,
                expected_engine="ncm_parallel_worlds",
                expected_temporal="static",
                expected_output_shape="static_point",
                expected_semantics="none",
                require_evolving_state=False,
            )
        )
    if not isinstance(time_unrolled_gate, dict):
        issues.append({"code": "time_unrolled_scm_gate_missing"})
    else:
        issues.extend(
            _validate_gate(
                time_unrolled_gate,
                expected_engine="system_dynamics",
                expected_temporal="multi_period",
                expected_output_shape="time_series_trajectory",
                expected_semantics="time_unrolled_SCM",
                require_evolving_state=True,
            )
        )
    if not isinstance(program_graph_gate, dict):
        issues.append({"code": "program_graph_equilibrium_scm_gate_missing"})
    else:
        issues.extend(
            _validate_gate(
                program_graph_gate,
                expected_engine="program_graph",
                expected_temporal="multi_period",
                expected_output_shape="program_state_trajectory",
                expected_semantics="equilibrium_SCM",
                require_evolving_state=True,
            )
        )
    registry_shape_gate = positive.get("registry_output_shape_gate")
    if not isinstance(registry_shape_gate, dict):
        issues.append({"code": "registry_output_shape_gate_missing"})
    else:
        issues.extend(_validate_registry_output_shape_gate(registry_shape_gate))
    coupling_gate = positive.get("coupling_gate")
    if not isinstance(coupling_gate, dict):
        issues.append({"code": "coupling_gate_missing"})
    else:
        issues.extend(_validate_coupling_gate(coupling_gate))
    semantics_gate = positive.get("equilibrium_resolution_gate")
    if not isinstance(semantics_gate, dict):
        issues.append({"code": "equilibrium_resolution_gate_missing"})
    else:
        issues.extend(_validate_equilibrium_resolution_gate(semantics_gate))
    strangle = positive.get("abm_stub_strangle")
    if not isinstance(strangle, dict):
        issues.append({"code": "abm_stub_strangle_missing"})
    else:
        issues.extend(_validate_abm_stub_strangle(strangle))
    return issues


def check(repo_root: Path) -> dict[str, Any]:
    """Validate committed artifact drift and live behavior."""

    output_path = repo_root / OUTPUT_PATH
    issues: list[dict[str, Any]] = []
    if not output_path.exists():
        issues.append({"code": "joint_simulation_contract_missing", "path": OUTPUT_PATH})
        return {"status": "fail", "issues": issues}
    committed = json.loads(output_path.read_text(encoding="utf-8"))
    live = build_live_payload(repo_root)
    if committed != live:
        issues.append({"code": "joint_simulation_contract_drift", "path": OUTPUT_PATH})
    issues.extend(validate_payload(committed)["issues"])
    return {"status": "pass" if not issues else "fail", "issues": issues}


def validate(repo_root: Path) -> dict[str, Any]:
    """Validate committed artifact drift and live behavior."""

    return check(repo_root)


def rederive_audit(repo_root: Path) -> dict[str, Any]:
    """Run and validate the live N5 owners without reading the frozen artifact."""

    return validate_payload(build_live_payload(repo_root))


def write(repo_root: Path) -> None:
    """Write the recomputed N5 contract artifact."""

    output_path = repo_root / OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_live_payload(repo_root), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def corrupt_field_drift_check(repo_root: Path) -> dict[str, Any]:
    """Mutate a decisive field and assert the validator turns red."""

    live = build_live_payload(repo_root)
    corrupted = copy.deepcopy(live)
    first_term = corrupted["positive_gate"]["dynamic_horizon"]["interaction_terms"][0]
    first_step = sorted(first_term["by_step"])[0]
    first_term["by_step"][first_step] = float(first_term["by_step"][first_step]) + 1.0
    report = validate_payload(corrupted)
    if report["issues"]:
        return {
            "status": "fail",
            "issues": [
                {
                    "code": "corrupt_field_drift_detected",
                    "detected_issue_codes": sorted(
                        str(issue.get("code"))
                        for issue in report["issues"]
                        if isinstance(issue, dict)
                    ),
                },
                *report["issues"],
            ],
        }
    return {"status": "pass", "issues": [{"code": "corrupt_field_drift_not_detected"}]}


def _run_abm_stub_source_flip(repo_root: Path) -> dict[str, Any]:
    """Reconnect coupled production to the fenced stub and require causal RED."""

    source_path = (
        repo_root / "src/polisyos/foundry/methods/catalog/simulation/coupled.py"
    )
    original = source_path.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    old_import = (
        "from polisyos.foundry.methods.catalog.simulation.dynamics import (\n"
        "    build_content_bound_abm_result,\n"
        ")\n"
    )
    new_import = (
        "from polisyos.foundry.methods.catalog.simulation.dynamics import (\n"
        "    _abm_result_stub,\n"
        "    build_content_bound_abm_result,\n"
        ")\n"
    )
    old_call = (
        "    abm_result = build_content_bound_abm_result(\n"
        '        method_id="simulation.coupled_policy.des_abm",\n'
        "        horizon=horizon,\n"
        "        payload=result,\n"
        "        diagnostics=diagnostics,\n"
        "    )\n"
    )
    new_call = (
        "    abm_result = _abm_result_stub(\n"
        '        method_id="simulation.coupled_policy.des_abm",\n'
        "        horizon=horizon,\n"
        "    )\n"
    )
    guards = {"import": text.count(old_import), "call": text.count(old_call)}
    if guards != {"import": 1, "call": 1}:
        return {
            "mutation_id": ABM_STUB_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": {"source_guard_counts": guards},
        }

    completed: subprocess.CompletedProcess[str] | None = None
    harness_error: str | None = None
    started = time.monotonic()
    try:
        mutated = text.replace(old_import, new_import, 1).replace(
            old_call,
            new_call,
            1,
        )
        source_path.write_text(mutated, encoding="utf-8")
        completed = subprocess.run(
            (
                sys.executable,
                "-m",
                "pytest",
                (
                    "tests/unit/foundry/methods/catalog/simulation/"
                    "test_coupled_policy.py::"
                    "test_coupled_policy_simulation_runs_des_abm_feedback"
                ),
                "-q",
            ),
            cwd=repo_root,
            env={
                **os.environ,
                "PYTHONPATH": f"{repo_root / 'src'}:{repo_root}",
                "JAX_PLATFORMS": "cpu",
            },
            text=True,
            capture_output=True,
            timeout=240,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - returned as harness evidence.
        harness_error = str(exc)
    finally:
        source_path.write_bytes(original)

    restored = source_path.read_bytes()
    restored_hash = hashlib.sha256(restored).hexdigest()
    if restored != original or restored_hash != original_hash:
        return {
            "mutation_id": ABM_STUB_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": {
                "error": "source_restore_hash_mismatch",
                "before": original_hash,
                "after": restored_hash,
            },
        }
    if harness_error is not None or completed is None:
        return {
            "mutation_id": ABM_STUB_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": harness_error or "source_flip_probe_not_run",
        }

    output = f"{completed.stdout}\n{completed.stderr}"
    stub_fence_observed = "abm_result_stub_strangled" in output
    mutation_red = completed.returncode != 0 and stub_fence_observed
    return {
        "mutation_id": ABM_STUB_SOURCE_FLIP_MUTATION_ID,
        "result": "RED" if mutation_red else "GREEN_MUTATION_SURVIVED",
        "guard": "coupled production defaults to content-bound ABM evidence",
        "proof": {
            "command": [str(item) for item in completed.args],
            "exit_code": completed.returncode,
            "stub_fence_observed": stub_fence_observed,
            "source_restored_sha256": restored_hash,
            "wall_time_seconds": round(time.monotonic() - started, 6),
            "stdout_tail": "\n".join(completed.stdout.splitlines()[-20:]),
            "stderr_tail": "\n".join(completed.stderr.splitlines()[-20:]),
        },
    }


def run_source_flip_mutations(repo_root: Path) -> tuple[dict[str, Any], ...]:
    """Run every restoring N5 source mutation serially."""

    return (_run_abm_stub_source_flip(repo_root),)


def _mutation_reports(result: Any, live_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []

    fake_receipt = result.receipt.model_copy(update={"trajectory_hash": _ref("e")})
    try:
        verify_simulation_receipt(fake_receipt, result.content_bound_payload())
    except ProofReceiptError:
        reports.append({"mutation": "fabricated_proof_ref", "status": "red"})
    else:
        reports.append({"mutation": "fabricated_proof_ref", "status": "green"})

    housing = _request(policy_domain="housing_zoning").model_copy(
        update={
            "engine_plan": (
                EnginePlan(
                    engine_kind="coupled_des_abm",
                    objective_ref="objective://housing",
                    eligibility_conditions=("feedback", "service_queue"),
                    coupled_state={"initial_income": [1000.0], "is_employed": [1.0]},
                    coupled_params={"n_steps": 3, "benefit_amount": 100.0},
                ),
            )
        }
    )
    housing_result = JointSimulationHorizonController().run(housing)
    reports.append(
        {
            "mutation": "unemployment_kernel_for_non_matching_domain",
            "status": "red"
            if housing_result.engine_decisions[0].decision == "unsupported"
            and not housing_result.trajectories
            else "green",
        }
    )

    cyclic_result = JointSimulationHorizonController().run(_request(ncm=_cyclic_ncm()))
    reports.append(
        {
            "mutation": "cyclic_objective_silently_grounded",
            "status": "red"
            if cyclic_result.engine_decisions[0].decision == "unsupported"
            and not cyclic_result.trajectories
            else "green",
        }
    )

    feedback_request = _request().model_copy(
        update={"coupling_graph": _coupling_graph("feedback")}
    )
    production_feedback = JointSimulationHorizonController().run(feedback_request)
    bypass_feedback = JointSimulationHorizonController.for_contract_testing(
        disable_coupling_gate=True
    ).run(feedback_request)
    reports.append(
        {
            "mutation": "coupling_gate_removed_silently_sums_feedback",
            "status": "red"
            if production_feedback.engine_decisions[0].decision == "unsupported"
            and not production_feedback.trajectories
            and bypass_feedback.engine_decisions[0].decision == "selected"
            and bool(bypass_feedback.trajectories)
            else "green",
        }
    )

    unbacked_plan = _request().engine_plan[0].model_copy(
        update={"declared_equilibrium_semantics": "game_model"}
    )
    unbacked_request = _request().model_copy(update={"engine_plan": (unbacked_plan,)})
    production_unbacked = JointSimulationHorizonController().run(unbacked_request)
    trusted_unbacked = JointSimulationHorizonController.for_contract_testing(
        trust_declared_equilibrium_semantics=True
    ).run(unbacked_request)
    reports.append(
        {
            "mutation": "equilibrium_semantics_label_trusted",
            "status": "red"
            if production_unbacked.engine_decisions[0].decision == "unsupported"
            and not production_unbacked.trajectories
            and trusted_unbacked.engine_decisions[0].decision == "selected"
            and trusted_unbacked.equilibrium_semantics.get("objective://firm-survival")
            == "game_model"
            else "green",
        }
    )

    queue_request = _queue_tag_counterexample_request()
    production_queue = JointSimulationHorizonController().run(queue_request)
    trusted_queue_opened = False
    try:
        trusted_queue = JointSimulationHorizonController.for_contract_testing(
            trust_method_tags_for_semantics=True
        ).run(queue_request)
        trusted_queue_opened = trusted_queue.engine_decisions[0].decision == "selected"
    except JointSimulationControllerError as exc:
        trusted_queue_opened = "method_registry_temporal_output_missing" in str(exc)
    reports.append(
        {
            "mutation": "method_tag_trusted_over_output_shape",
            "status": "red"
            if production_queue.engine_decisions[0].decision == "unsupported"
            and production_queue.engine_decisions[0].reason
            == "method_output_shape_does_not_back_semantics"
            and trusted_queue_opened
            else "green",
        }
    )

    gated_request = _request().model_copy(
        update={"coupling_graph": _coupling_graph("shared_resource")}
    )
    try:
        JointSimulationHorizonController.for_contract_testing(
            force_run_receipt_for_no_trajectories=True
        ).run(gated_request)
    except ProofReceiptError:
        reports.append({"mutation": "stub_shaped_engine_run_receipt", "status": "red"})
    else:
        reports.append({"mutation": "stub_shaped_engine_run_receipt", "status": "green"})

    try:
        JointSimulationHorizonController().run(
            _request(world_model_record_ref="pending_world_model_record_ref")
        )
    except JointSimulationControllerError:
        reports.append({"mutation": "pending_wmr_ref", "status": "red"})
    else:
        reports.append({"mutation": "pending_wmr_ref", "status": "green"})

    shrunk_result = JointSimulationHorizonController.for_contract_testing(
        shrink_world_credal_state=True
    ).run(_dynamic_request())
    shrunk = copy.deepcopy(dict(live_payload))
    shrunk["positive_gate"]["dynamic_horizon"] = _result_gate(
        shrunk_result,
        ("capacity_inflow", "demand_inflow"),
    )
    shrink_issues = _validate_payload_core(shrunk)
    reports.append(
        {
            "mutation": "k_sim_shrinks_k_world",
            "status": "red"
            if any(issue.get("code") == "k_sim_shrank_k_world" for issue in shrink_issues)
            else "green",
        }
    )

    fabricated_result = JointSimulationHorizonController.for_contract_testing(
        fabricate_interaction_terms=True
    ).run(_dynamic_request())
    fabricated = copy.deepcopy(dict(live_payload))
    fabricated["positive_gate"]["dynamic_horizon"] = _result_gate(
        fabricated_result,
        ("capacity_inflow", "demand_inflow"),
    )
    fabricated_report = _validate_payload_core(fabricated)
    reports.append(
        {
            "mutation": "fabricated_interaction_term",
            "status": "red"
            if any(
                issue.get("code") == "fabricated_interaction_term_detected"
                for issue in fabricated_report
            )
            else "green",
        }
    )

    static_fake = copy.deepcopy(dict(live_payload))
    static_gate = static_fake["positive_gate"]["static_scm"]
    static_gate["horizon_steps"] = [0, 1]
    for trajectory in static_gate["trajectories"]:
        trajectory["points"].append(copy.deepcopy(trajectory["points"][0]))
        trajectory["points"][-1]["step"] = 1
    static_fake_issues = _validate_payload_core(static_fake)
    reports.append(
        {
            "mutation": "static_engine_result_presented_as_horizon",
            "status": "red"
            if any(
                issue.get("code") == "static_result_presented_as_horizon"
                for issue in static_fake_issues
            )
            else "green",
        }
    )

    no_advance = copy.deepcopy(dict(live_payload))
    for trajectory in no_advance["positive_gate"]["dynamic_horizon"]["trajectories"]:
        if trajectory["run_level"] != "joint":
            continue
        first_state = copy.deepcopy(trajectory["points"][0]["engine_state"])
        for point in trajectory["points"][1:]:
            point["engine_state"] = copy.deepcopy(first_state)
    no_advance_issues = _validate_payload_core(no_advance)
    reports.append(
        {
            "mutation": "dynamic_engine_state_does_not_advance",
            "status": "red"
            if any(
                issue.get("code") == "dynamic_state_not_advanced"
                for issue in no_advance_issues
            )
            else "green",
        }
    )
    return reports


def _coupling_gate_result(blocked: Any, supported: Any) -> dict[str, Any]:
    return {
        "unsupported_shared_resource": {
            "decision": blocked.engine_decisions[0].decision,
            "reason": blocked.engine_decisions[0].reason,
            "blockers": list(blocked.engine_decisions[0].blockers),
            "trajectory_count": len(blocked.trajectories),
            "interaction_count": len(blocked.interaction_terms),
            "feedback_classification": blocked.feedback_classification.model_dump(
                mode="json"
            ),
            "receipt": blocked.receipt.model_dump(mode="json"),
        },
        "supported_coupled_des_abm": {
            "decision": supported.engine_decisions[0].decision,
            "engine_kind": supported.engine_decisions[0].engine_kind,
            "trajectory_levels": sorted({item.run_level for item in supported.trajectories}),
            "feedback_classification": supported.feedback_classification.model_dump(
                mode="json"
            ),
            "receipt": supported.receipt.model_dump(mode="json"),
        },
    }


def _registry_output_shape_gate(result: Any) -> dict[str, Any]:
    return {
        "decision": result.engine_decisions[0].decision,
        "reason": result.engine_decisions[0].reason,
        "blockers": list(result.engine_decisions[0].blockers),
        "equilibrium_semantics": result.equilibrium_semantics,
        "trajectory_count": len(result.trajectories),
        "receipt": result.receipt.model_dump(mode="json"),
    }


def _equilibrium_resolution_gate(result: Any) -> dict[str, Any]:
    return {
        "decision": result.engine_decisions[0].decision,
        "reason": result.engine_decisions[0].reason,
        "blockers": list(result.engine_decisions[0].blockers),
        "equilibrium_semantics": result.equilibrium_semantics,
        "trajectory_count": len(result.trajectories),
        "receipt": result.receipt.model_dump(mode="json"),
    }


def _abm_stub_strangle_probe(repo_root: Path | None = None) -> dict[str, Any]:
    """Exercise the real fence and census every production simulation caller."""

    root = (repo_root or Path(__file__).resolve().parents[3]).resolve()
    payload = {
        "trajectory": [{"step": 0, "final_queue_length": 1.0}],
        "metrics": {"completed_count": 2},
    }
    diagnostics = {"warnings": [], "engine": "simulation.coupled_policy.des_abm"}
    stub_rejected = False
    try:
        _abm_result_stub(method_id="simulation.coupled_policy.des_abm", horizon=3)
    except RuntimeError as exc:
        stub_rejected = "abm_result_stub_strangled" in str(exc)
    fixture_only = _abm_result_stub(
        method_id="simulation.coupled_policy.des_abm",
        horizon=3,
        fixture_only=True,
    )
    content_bound = build_content_bound_abm_result(
        method_id="simulation.coupled_policy.des_abm",
        horizon=3,
        payload=payload,
        diagnostics=diagnostics,
    )
    return {
        "stub_rejected": stub_rejected,
        "content_bound_has_diagnostic": (
            content_bound.identifiability_certificate is not None
            and content_bound.identifiability_certificate.status == "diagnostic_attached"
        ),
        "legacy_stub_marker_absent": "phase4_abm_result_stub"
        not in content_bound.model_dump_json(),
        "fixture_only_is_non_authority": (
            "phase4_abm_result_stub" in fixture_only.model_dump_json()
            and "content_bound_abm_result" not in fixture_only.model_dump_json()
        ),
        "production_stub_callers": _production_abm_stub_callers(root),
    }


def _production_abm_stub_callers(repo_root: Path) -> list[str]:
    """Return every executable legacy-stub call under production simulation code."""

    simulation_root = (
        repo_root / "src/polisyos/foundry/methods/catalog/simulation"
    )
    callers: list[str] = []
    for path in sorted(simulation_root.rglob("*.py")):
        module = ast.parse(path.read_text(encoding="utf-8"))
        callers.extend(
            f"{path.relative_to(repo_root).as_posix()}:{node.lineno}"
            for node in ast.walk(module)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_abm_result_stub"
        )
    return callers


def _result_gate(result: Any, joint_atom_ids: tuple[str, str]) -> dict[str, Any]:
    interaction_terms = [
        {
            "atom_ids": list(interaction.atom_ids),
            "outcome": interaction.outcome,
            "by_step": {str(k): v for k, v in interaction.by_step.items()},
            "formula": interaction.formula,
        }
        for interaction in result.interaction_terms
    ]
    joint = result.trajectory_for("joint", joint_atom_ids)
    return {
        "world_model_record_ref": result.world_model_record_ref,
        "world_model_record_content_hash": result.world_model_record_content_hash,
        "engine_decisions": [item.model_dump(mode="json") for item in result.engine_decisions],
        "equilibrium_semantics": result.equilibrium_semantics,
        "selected_outcomes": list(result.selected_outcomes),
        "trajectory_levels": sorted({item.run_level for item in result.trajectories}),
        "horizon_steps": [point.step for point in joint.points],
        "trajectories": [item.model_dump(mode="json") for item in result.trajectories],
        "receipt": result.receipt.model_dump(mode="json"),
        "receipt_payload_hash": result.receipt.payload_hash,
        "uncertainty_kind": result.uncertainty_kind,
        "world_credal_state_before": result.world_credal_state_before,
        "world_credal_state_after": result.world_credal_state_after,
        "interaction_terms": interaction_terms,
        "joint_terminal_outcomes": joint.points[-1].outcomes,
    }


def _validate_gate(
    gate: Mapping[str, Any],
    *,
    expected_engine: str,
    expected_temporal: str,
    expected_output_shape: str,
    expected_semantics: str,
    require_evolving_state: bool,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if gate.get("uncertainty_kind") != "K_sim":
        issues.append({"code": "simulation_uncertainty_kind_not_k_sim"})
    if gate.get("world_credal_state_before") != gate.get("world_credal_state_after"):
        issues.append({"code": "k_sim_shrank_k_world"})
    decisions = gate.get("engine_decisions")
    if not isinstance(decisions, list) or not decisions:
        issues.append({"code": "engine_decisions_missing"})
        decisions = []
    else:
        selected = decisions[0]
        if selected.get("engine_kind") != expected_engine:
            issues.append({"code": "positive_engine_mismatch"})
        if selected.get("decision") != "selected":
            issues.append({"code": "positive_engine_not_selected"})
        if selected.get("temporal_capability") != expected_temporal:
            issues.append({"code": "temporal_capability_mismatch"})
        if selected.get("output_shape") != expected_output_shape:
            issues.append({"code": "engine_output_shape_capability_mismatch"})
    semantics = gate.get("equilibrium_semantics")
    if isinstance(semantics, Mapping) and decisions:
        objective = str(decisions[0].get("objective_ref"))
        if semantics.get(objective) != expected_semantics:
            issues.append({"code": "equilibrium_semantics_mismatch"})
    trajectories = gate.get("trajectories")
    if not isinstance(trajectories, list) or not trajectories:
        issues.append({"code": "trajectories_missing"})
        trajectories = []
    levels = {trajectory.get("run_level") for trajectory in trajectories if isinstance(trajectory, dict)}
    if levels != {"individual", "pairwise", "joint"}:
        issues.append({"code": "subset_lattice_missing"})
    horizon_steps = gate.get("horizon_steps")
    if expected_temporal == "static":
        if not isinstance(horizon_steps, list) or len(horizon_steps) != 1:
            issues.append({"code": "static_result_presented_as_horizon"})
        for trajectory in trajectories:
            if len(trajectory.get("points", [])) != 1:
                issues.append({"code": "static_result_presented_as_horizon"})
                break
    else:
        if not isinstance(horizon_steps, list) or len(horizon_steps) < 2:
            issues.append({"code": "dynamic_horizon_missing"})
    selected_outcomes = gate.get("selected_outcomes")
    if not isinstance(selected_outcomes, list) or not selected_outcomes:
        issues.append({"code": "selected_outcomes_missing"})
        selected_outcomes = []
    expected_terms = _derive_interactions(trajectories, selected_outcomes)
    authored_terms = _normalize_terms(gate.get("interaction_terms"))
    if not authored_terms:
        issues.append({"code": "interaction_terms_missing"})
    elif not _terms_match(authored_terms, expected_terms):
        issues.append({"code": "fabricated_interaction_term_detected"})
    receipt = gate.get("receipt")
    if not isinstance(receipt, dict):
        issues.append({"code": "receipt_missing"})
    elif receipt.get("diagnostics_attached") is not True:
        issues.append({"code": "receipt_diagnostics_missing"})
    elif receipt.get("calibration_status") != "content_bound_run_receipt":
        issues.append({"code": "positive_run_receipt_status_wrong"})
    elif int(receipt.get("trajectory_count", 0)) <= 0:
        issues.append({"code": "positive_run_receipt_trajectory_count_missing"})
    if require_evolving_state:
        if _joint_state_count(trajectories) < 2:
            issues.append({"code": "dynamic_state_not_advanced"})
        if _joint_outcome_count(trajectories, selected_outcomes) < 2:
            issues.append({"code": "dynamic_outcome_not_advanced"})
    return issues


def _validate_coupling_gate(gate: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    blocked = gate.get("unsupported_shared_resource")
    if not isinstance(blocked, Mapping):
        issues.append({"code": "unsupported_coupling_probe_missing"})
    else:
        blockers = {str(item) for item in blocked.get("blockers", [])}
        classification = blocked.get("feedback_classification", {})
        if blocked.get("decision") != "unsupported":
            issues.append({"code": "unsupported_coupling_not_gated"})
        if blocked.get("trajectory_count") != 0 or blocked.get("interaction_count") != 0:
            issues.append({"code": "unsupported_coupling_summed"})
        receipt = blocked.get("receipt", {})
        if not isinstance(receipt, Mapping):
            issues.append({"code": "unsupported_coupling_receipt_missing"})
        elif receipt.get("calibration_status") != "unsupported_coupling_gated":
            issues.append({"code": "unsupported_coupling_run_receipt_minted"})
        elif receipt.get("trajectory_count") != 0:
            issues.append({"code": "unsupported_coupling_receipt_trajectory_count_nonzero"})
        if "unsupported_coupling_class:shared_resource" not in blockers:
            issues.append({"code": "unsupported_coupling_typed_blocker_missing"})
        if isinstance(classification, Mapping):
            if classification.get("support_status") != "unsupported":
                issues.append({"code": "unsupported_coupling_support_status_wrong"})
            if classification.get("engine_supported") is not False:
                issues.append({"code": "unsupported_coupling_engine_supported_wrong"})
        else:
            issues.append({"code": "unsupported_coupling_classification_missing"})
    supported = gate.get("supported_coupled_des_abm")
    if not isinstance(supported, Mapping):
        issues.append({"code": "supported_coupled_probe_missing"})
    else:
        classification = supported.get("feedback_classification", {})
        if supported.get("decision") != "selected":
            issues.append({"code": "supported_coupled_not_selected"})
        if supported.get("engine_kind") != "coupled_des_abm":
            issues.append({"code": "supported_coupled_engine_mismatch"})
        if set(supported.get("trajectory_levels", [])) != {"individual", "pairwise", "joint"}:
            issues.append({"code": "supported_coupled_subset_lattice_missing"})
        if isinstance(classification, Mapping):
            if classification.get("support_status") != "supported":
                issues.append({"code": "supported_coupled_support_status_wrong"})
            if classification.get("shared_resource") is not True:
                issues.append({"code": "supported_coupled_shared_resource_missing"})
        else:
            issues.append({"code": "supported_coupled_classification_missing"})
    return issues


def _validate_equilibrium_resolution_gate(gate: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    blockers = {str(item) for item in gate.get("blockers", [])}
    semantics = gate.get("equilibrium_semantics", {})
    if gate.get("decision") != "unsupported":
        issues.append({"code": "unbacked_equilibrium_semantics_not_gated"})
    if "declared_semantics_unbacked:game_model" not in blockers:
        issues.append({"code": "unbacked_equilibrium_semantics_blocker_missing"})
    if gate.get("trajectory_count") != 0:
        issues.append({"code": "unbacked_equilibrium_semantics_ran_engine"})
    receipt = gate.get("receipt", {})
    if not isinstance(receipt, Mapping):
        issues.append({"code": "unbacked_equilibrium_semantics_receipt_missing"})
    elif receipt.get("calibration_status") != "no_run":
        issues.append({"code": "unbacked_equilibrium_semantics_run_receipt_minted"})
    if (
        not isinstance(semantics, Mapping)
        or semantics.get("objective://firm-survival") != "unsupported"
    ):
        issues.append({"code": "unbacked_equilibrium_semantics_resolution_wrong"})
    return issues


def _validate_registry_output_shape_gate(gate: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    blockers = {str(item) for item in gate.get("blockers", [])}
    if gate.get("decision") != "unsupported":
        issues.append({"code": "registry_output_shape_gate_not_gated"})
    if gate.get("reason") != "method_output_shape_does_not_back_semantics":
        issues.append({"code": "registry_output_shape_gate_reason_wrong"})
    if "output_shape:scalar_final_value" not in blockers:
        issues.append({"code": "registry_output_shape_blocker_missing"})
    if "declared_semantics_unbacked:agent_based_model" not in blockers:
        issues.append({"code": "registry_output_shape_semantics_blocker_missing"})
    if gate.get("trajectory_count") != 0:
        issues.append({"code": "registry_output_shape_ran_engine"})
    receipt = gate.get("receipt", {})
    if not isinstance(receipt, Mapping):
        issues.append({"code": "registry_output_shape_receipt_missing"})
    elif receipt.get("calibration_status") != "no_run":
        issues.append({"code": "registry_output_shape_run_receipt_minted"})
    return issues


def _validate_abm_stub_strangle(probe: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if probe.get("stub_rejected") is not True:
        issues.append({"code": "abm_stub_not_strangled"})
    if probe.get("content_bound_has_diagnostic") is not True:
        issues.append({"code": "abm_content_bound_diagnostic_missing"})
    if probe.get("legacy_stub_marker_absent") is not True:
        issues.append({"code": "abm_legacy_stub_marker_present"})
    if probe.get("fixture_only_is_non_authority") is not True:
        issues.append({"code": "abm_fixture_only_authority_ambiguous"})
    if probe.get("production_stub_callers") != []:
        issues.append(
            {
                "code": "abm_production_stub_caller_present",
                "callers": probe.get("production_stub_callers"),
            }
        )
    return issues


def _derive_interactions(
    trajectories: list[Any],
    selected_outcomes: list[Any],
) -> dict[tuple[tuple[str, str], str], dict[str, float]]:
    individual: dict[str, Mapping[str, Any]] = {}
    pairwise: list[Mapping[str, Any]] = []
    for raw in trajectories:
        if not isinstance(raw, Mapping):
            continue
        atom_ids = tuple(str(item) for item in raw.get("atom_ids", []))
        if raw.get("run_level") == "individual" and len(atom_ids) == 1:
            individual[atom_ids[0]] = raw
        elif raw.get("run_level") == "pairwise" and len(atom_ids) == 2:
            pairwise.append(raw)
    expected: dict[tuple[tuple[str, str], str], dict[str, float]] = {}
    for trajectory in pairwise:
        atom_ids = tuple(str(item) for item in trajectory.get("atom_ids", []))
        if atom_ids[0] not in individual or atom_ids[1] not in individual:
            continue
        left = _points_by_step(individual[atom_ids[0]])
        right = _points_by_step(individual[atom_ids[1]])
        for outcome in selected_outcomes:
            by_step: dict[str, float] = {}
            for point in trajectory.get("points", []):
                step = str(point.get("step"))
                effect = point.get("effect", {})
                by_step[step] = (
                    float(effect.get(outcome, 0.0))
                    - float(left[step].get("effect", {}).get(outcome, 0.0))
                    - float(right[step].get("effect", {}).get(outcome, 0.0))
                )
            expected[(atom_ids, str(outcome))] = by_step
    return expected


def _points_by_step(trajectory: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(point.get("step")): point
        for point in trajectory.get("points", [])
        if isinstance(point, Mapping)
    }


def _normalize_terms(raw_terms: Any) -> dict[tuple[tuple[str, str], str], dict[str, float]]:
    if not isinstance(raw_terms, list):
        return {}
    terms: dict[tuple[tuple[str, str], str], dict[str, float]] = {}
    for raw in raw_terms:
        if not isinstance(raw, Mapping):
            continue
        atom_ids = tuple(str(item) for item in raw.get("atom_ids", []))
        if len(atom_ids) != 2:
            continue
        by_step = raw.get("by_step", {})
        if not isinstance(by_step, Mapping):
            continue
        terms[(atom_ids, str(raw.get("outcome")))] = {
            str(step): float(value) for step, value in by_step.items()
        }
    return terms


def _terms_match(
    authored: Mapping[tuple[tuple[str, str], str], Mapping[str, float]],
    expected: Mapping[tuple[tuple[str, str], str], Mapping[str, float]],
) -> bool:
    if set(authored) != set(expected):
        return False
    for key, expected_by_step in expected.items():
        authored_by_step = authored[key]
        if set(authored_by_step) != set(expected_by_step):
            return False
        for step, expected_value in expected_by_step.items():
            if abs(float(authored_by_step[step]) - float(expected_value)) > 1e-9:
                return False
    return True


def _joint_state_count(trajectories: list[Any]) -> int:
    states: set[str] = set()
    for trajectory in trajectories:
        if not isinstance(trajectory, Mapping) or trajectory.get("run_level") != "joint":
            continue
        for point in trajectory.get("points", []):
            if not isinstance(point, Mapping):
                continue
            states.add(json.dumps(point.get("engine_state", {}), sort_keys=True))
    return len(states)


def _joint_outcome_count(trajectories: list[Any], selected_outcomes: list[Any]) -> int:
    outcomes: set[str] = set()
    selected = tuple(str(item) for item in selected_outcomes)
    for trajectory in trajectories:
        if not isinstance(trajectory, Mapping) or trajectory.get("run_level") != "joint":
            continue
        for point in trajectory.get("points", []):
            if not isinstance(point, Mapping):
                continue
            raw_outcomes = point.get("outcomes", {})
            if not isinstance(raw_outcomes, Mapping):
                continue
            outcomes.add(
                json.dumps(
                    {key: raw_outcomes.get(key) for key in selected},
                    sort_keys=True,
                )
            )
    return len(outcomes)


def _ref(char: str) -> str:
    return "sha256:" + char * 64


def _intervention(*, intervention_id: str, rate: str = "0.20") -> InterventionSpec:
    return InterventionSpec.model_validate(
        {
            "intervention_id": intervention_id,
            "kind": "tax_subsidy",
            "target": SelectorPredicate(
                field="id",
                operator=SelectorOperator.EQUALS,
                value="all",
            ),
            "schedule": ScheduleSpec(start_step=0, duration_steps=4),
            "params": {"rate": Decimal(rate)},
            "priority": 1,
            "target_population_type": "wartime_msme",
            "target_sector_ids": ["manufacturing"],
            "target_region_ids": ["UA-30"],
        }
    )


def _bundle(intervention: InterventionSpec) -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_ua_msme_credit", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_ua_msme_credit",
            problem_frame_ref=_ref("a"),
            interventions=[intervention],
        ),
        model_spec=ModelSpec(model_id="model_ua_msme", data_snapshot_ref=_ref("b")),
    )


def _registries() -> RegistryBundle:
    return RegistryBundle(
        mechanisms=DEFAULT_MECHANISM_REGISTRY,
        slots=DEFAULT_SLOT_REGISTRY,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        units=DEFAULT_UNITS_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        constraints=ConstraintRegistry(constraints={}),
    )


def _linked(intervention: InterventionSpec) -> LinkedIntervention:
    linked_bundle, report = link_trinity(_bundle(intervention), _registries())
    if not report.ok:
        raise RuntimeError("fixture_link_report_failed")
    return linked_bundle.bindings.interventions[0]


def _atom(
    *,
    intervention_id: str,
    causal_variable: str,
    engine_variable: str,
    value: float,
    world_model_record_ref: str,
) -> InterventionAtomBinding:
    intervention = _intervention(intervention_id=intervention_id)
    causal = NodeIntervention(
        assignments=(VariableAssignment(variable=causal_variable, value=value),)
    )
    return build_intervention_atom_binding(
        problem_frame_ref=_ref("a"),
        policy_spec_ref=_ref("c"),
        intervention=intervention,
        linked_intervention=_linked(intervention),
        causal_intervention=causal,
        query_target=QueryTarget(
            outcome_variables=("firm_survival",),
            conditioning=("baseline_credit_access",),
            functional="average_treatment_effect",
        ),
        identification_plan=identification_plan_for_intervention(causal),
        causal_context=InterventionContext(
            source_domain="observed_ua_msme_panel",
            target_domain="wartime_msme",
            selection_diagram_ref=intervention_atom_target_selector_ref(intervention),
            available_data_refs=("data_snapshot:ua_msme_credit_panel",),
            assumptions=("target_selector_content_bound",),
        ),
        world_model_record_ref=world_model_record_ref,
        producer_ref=f"test.joint_simulation:{intervention_id}",
        operator_proof_type_map={"tax_subsidy": "node"},
        mechanism_variable_map={"tax_subsidy": ("agents.income", "government.balance")},
        mechanism_config_overrides={"joint_simulation_engine_variable": engine_variable},
    )


def _world_record(*, policy_domain: str = "fiscal_credit") -> WorldModelRecord:
    fields: dict[str, Any] = {
        "schema_version": "policyos.runtime.world_model_record.v1",
        "authority_status": "bound",
        "producer_ref": "test.world_model_record",
        "region_or_jurisdiction": "UA-30",
        "population_scope": "wartime_msme",
        "policy_domain": policy_domain,
        "valid_time_scope": "2026-05-24/2026-12-31",
        "tx_time_scope": "2026-05-24T12:00:00+00:00",
        "resolution": "firm_month",
        "branch_mode": BranchMode.OBSERVED,
        "fabric_world_ref": FabricWorldRef(
            snapshot_root="/tmp/policyos-test-world",  # noqa: S108 - deterministic fixture path.
            snapshot_id="snapshot-2026-05-24",
            branch="main",
            world_query_policy="as_of_valid_and_tx_time",
            provenance_manifest_ref="manifest://fabric/test",
            content_query_digest=_ref("1"),
            content_query_row_count=2,
        ),
        "data_forge_binding_ref": DataForgeBindingRef(
            snapshot_id="snapshot-2026-05-24",
            release_id="release-1",
            role="academic",
            read_api_identity="data_forge.read_api.test",
            snapshot_ref="snapshot://data-forge/test",
            merkle_root="merkle:test",
            data_hash=_ref("2"),
            provenance_manifest_ref="manifest://data-forge/test",
        ),
        "simulation_model_ref": SimulationModelRef(
            model_spec_ref=_ref("3"),
            model_spec_hash=_ref("4"),
            model_id="model_ua_msme_world",
            data_snapshot_ref=_ref("5"),
            registry_bundle_ref=_ref("6"),
            ncm_refs=("ncm://fixture/msme-interaction",),
            fidelity_level="high",
            calibrated=True,
            calibration_ref=_ref("7"),
        ),
        "foundry_binding_ref": FoundryBindingRef(
            input_bindings_ref=_ref("8"),
            bound_state_snapshot_ref=_ref("9"),
            mapping_rules_ref=_ref("a"),
            state_slot_digest=_ref("b"),
        ),
        "skg_causal_prior_ref": SkgCausalPriorRef(
            skg_snapshot_ref="skg://test",
            skg_version_id="skg-v1",
            source_data_snapshot_id="snapshot-2026-05-24",
        ),
        "substrate_registry_ref": SubstrateRegistryRef(
            substrate_version_id="substrate_version_1111111111111111",
            content_hash=_ref("c"),
            resolved_entries=(
                ResolvedSubstrateEntryRef(
                    source_id="l5_measurement_registry",
                    family_id="firm_fundamentals",
                    layer="L5",
                    coverage_score=0.8,
                    trust_tier="authoritative_partial_coverage",
                    trust_cap=0.85,
                    identification_mode="point_identified",
                    schema_regime_id="ukraine_schema_v2",
                    data_version="l5-calibration-d2",
                    snapshot_id="snapshot-2026-05-24",
                    source_snapshot_id="snapshot-2026-05-24",
                    entry_content_hash=_ref("d"),
                ),
            ),
        ),
        "policy_slot_map": (
            PolicySlotBinding(
                slot_id="agents.income",
                state_path="agents.income",
                entity_scope="agent",
                temporal_granularity="month",
            ),
            PolicySlotBinding(
                slot_id="government.balance",
                state_path="government_balance",
                entity_scope="government",
                temporal_granularity="month",
            ),
        ),
    }
    candidate = WorldModelRecord.model_construct(
        world_model_record_id="world_model_record_0000000000000000",
        content_hash=_ref("0"),
        **fields,
    )
    content_hash = world_model_record_content_hash(candidate)
    return WorldModelRecord(
        world_model_record_id=f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
    )


def _ncm_with_cross_term() -> NCMSpec:
    return NCMSpec(
        endogenous_vars=["income_delta", "balance_delta", "firm_survival"],
        exogenous_specs=[
            ExogenousSpec(variable="u_income", associated_endogenous="income_delta"),
            ExogenousSpec(variable="u_balance", associated_endogenous="balance_delta"),
            ExogenousSpec(variable="u_survival", associated_endogenous="firm_survival"),
        ],
        structural_equations=[
            StructuralEquation(
                variable="income_delta",
                parents=[],
                exogenous="u_income",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {}},
            ),
            StructuralEquation(
                variable="balance_delta",
                parents=[],
                exogenous="u_balance",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {}},
            ),
            StructuralEquation(
                variable="firm_survival",
                parents=["income_delta", "balance_delta"],
                exogenous="u_survival",
                equation_type="nonlinear",
                equation_params={
                    "noise_expression": (
                        "1.0 + (2.0 * income_delta) + (3.0 * balance_delta) "
                        "+ (5.0 * income_delta * balance_delta) + u"
                    ),
                },
            ),
        ],
        is_acyclic=True,
        markov_condition_verified=True,
        independence_model="dag_markov",
        fit_method="symbolic",
    )


def _cyclic_ncm() -> NCMSpec:
    return _ncm_with_cross_term().model_copy(
        update={
            "is_acyclic": False,
            "structural_equations": [
                StructuralEquation(
                    variable="income_delta",
                    parents=["firm_survival"],
                    exogenous="u_income",
                    equation_type="linear",
                ),
                StructuralEquation(
                    variable="firm_survival",
                    parents=["income_delta"],
                    exogenous="u_survival",
                    equation_type="linear",
                ),
            ],
        }
    )


def _request(
    *,
    ncm: NCMSpec | None = None,
    world_model_record_ref: str | None = None,
    policy_domain: str = "fiscal_credit",
) -> JointSimulationRequest:
    record = _world_record(policy_domain=policy_domain)
    ref = world_model_record_ref or record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="income_subsidy",
            causal_variable="agents.income",
            engine_variable="income_delta",
            value=1.0,
            world_model_record_ref=ref,
        ),
        _atom(
            intervention_id="balance_grant",
            causal_variable="government.balance",
            engine_variable="balance_delta",
            value=1.0,
            world_model_record_ref=ref,
        ),
    )
    return JointSimulationRequest(
        world_model_record_ref=ref,
        world_model_record=record,
        intervention_atoms=atoms,
        selected_outcomes=("firm_survival",),
        baseline_state={"income_delta": 0.0, "balance_delta": 0.0, "firm_survival": 1.0},
        horizon=HorizonSpec(start=0, end=3, step=1),
        engine_plan=(
            EnginePlan(
                engine_kind="ncm_parallel_worlds",
                objective_ref="objective://firm-survival",
                ncm_spec=ncm or _ncm_with_cross_term(),
                variable_map={
                    "agents.income": "income_delta",
                    "government.balance": "balance_delta",
                    "firm_survival": "firm_survival",
                },
                eligibility_conditions=("acyclic", "counterfactual_do_worlds"),
            ),
        ),
        world_credal_state_before={"firm_survival": {"low": 0.2, "high": 0.8}},
    )


def _declared_request(
    request: JointSimulationRequest,
    semantics: str,
) -> JointSimulationRequest:
    plan = request.engine_plan[0].model_copy(
        update={"declared_equilibrium_semantics": semantics}
    )
    return request.model_copy(update={"engine_plan": (plan,)})


def _program_graph_request(tmp_path: Path) -> JointSimulationRequest:
    return _request().model_copy(
        update={
            "engine_plan": (_program_graph_plan(tmp_path),),
            "selected_outcomes": ("mean_income",),
            "baseline_state": {"mean_income": 0.0},
        }
    )


def _program_graph_plan(tmp_path: Path) -> EnginePlan:
    store = FileSystemCAS(tmp_path / "cas")
    ir_ref = store.put_json(
        {"fixture": "joint_simulation_program_graph_contract"},
        PutOptions(
            kind="ir.lowered_fixture",
            media_type="application/json",
            schema=SchemaInfo(name="test.lowered_fixture", version="1.0"),
        ),
    )
    lowered_ref = store.put_json(
        LoweredIR(ir_ref=ir_ref),
        PutOptions(
            kind="foundry.lowered_ir",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.LoweredIR", version="0.2"),
        ),
    )
    params_ref = store.put_json(
        {
            "binding_id": "binding.program_graph_subsidy",
            "mechanism_id": "tax_subsidy",
            "intervention_ids": ["program_graph_income_subsidy"],
            "priority": 1,
            "params": {"rate": Decimal("0.0")},
            "schedule": ScheduleSpec(start_step=0, duration_steps=4).model_dump(mode="json"),
            "selector": SelectorPredicate(
                field="id",
                operator=SelectorOperator.EQUALS,
                value="all",
            ).model_dump(mode="json"),
            "selected_fidelity": "fluid",
            "notes": ["joint_simulation_program_graph_contract"],
        },
        PutOptions(
            kind="foundry.lowered_mechanism_payload",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.LoweredMechanismPayload", version="0.2.0"),
        ),
    )
    program_ref = store.put_json(
        ProgramGraph(
            ir_ref=ir_ref,
            lowered_ir_ref=LoweredIRRef(artifact_id=lowered_ref.artifact_id),
            nodes=[
                ProgramNode(
                    node_id="apply_subsidy",
                    node_kind="op",
                    mechanism_type="tax_subsidy",
                    params_ref=params_ref,
                    op=ProgramOp(op_kind="apply_mechanism"),
                    inputs=["agents.income"],
                    outputs=["agents.income", "government.balance"],
                )
            ],
            edges=[],
        ),
        PutOptions(
            kind="foundry.program_graph",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ProgramGraph", version="0.2"),
        ),
    )
    exec_plan_ref = store.put_json(
        ExecPlan(
            program_ref=ProgramGraphRef(artifact_id=program_ref.artifact_id),
            order=["apply_subsidy"],
        ),
        PutOptions(
            kind="foundry.exec_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ExecPlan", version="0.2"),
        ),
    )
    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    base_state = base_state.replace(
        agents=base_state.agents.replace(
            income=jnp.asarray([1000.0, 2000.0], dtype=jnp.float32)
        )
    )
    return EnginePlan(
        engine_kind="program_graph",
        objective_ref="objective://program-graph-equilibrium-smoke",
        declared_equilibrium_semantics="equilibrium_SCM",
        eligibility_conditions=("acyclic", "state_transition"),
        variable_map={"mean_income": "agents.income"},
        program_store=store,
        program_graph_ref=program_ref,
        exec_plan_ref=exec_plan_ref,
        program_base_state=base_state,
        program_parameter_overrides_by_atom={
            "income_subsidy": {"apply_subsidy": {"rate": 0.10}},
            "balance_grant": {"apply_subsidy": {"rate": 0.20}},
        },
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
        constraint_registry=ConstraintRegistry(constraints={}),
    )


def _dynamic_request() -> JointSimulationRequest:
    record = _world_record()
    ref = record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="capacity_inflow",
            causal_variable="agents.income",
            engine_variable="exogenous_inflows.0",
            value=2.0,
            world_model_record_ref=ref,
        ),
        _atom(
            intervention_id="demand_inflow",
            causal_variable="government.balance",
            engine_variable="exogenous_inflows.1",
            value=3.0,
            world_model_record_ref=ref,
        ),
    )
    return JointSimulationRequest(
        world_model_record_ref=ref,
        world_model_record=record,
        intervention_atoms=atoms,
        selected_outcomes=("stock0", "stock1"),
        baseline_state={"stock0": 10.0, "stock1": 0.0},
        horizon=HorizonSpec(start=0, end=3, step=1),
        engine_plan=(
            EnginePlan(
                engine_kind="system_dynamics",
                objective_ref="objective://stock-flow",
                variable_map={
                    "agents.income": "exogenous_inflows.0",
                    "government.balance": "exogenous_inflows.1",
                    "stock0": "stock:0",
                    "stock1": "stock:1",
                },
                eligibility_conditions=("multi_period", "dynamic_scm"),
                system_dynamics_state={
                    "initial_stocks": [10.0, 0.0],
                    "flow_matrix": [[0.0, 0.1], [0.0, 0.0]],
                    "exogenous_inflows": [0.0, 0.0],
                },
                system_dynamics_params={"dt": 1.0},
            ),
        ),
        world_credal_state_before={"stock0": {"low": 8.0, "high": 12.0}},
    )


def _coupled_request() -> JointSimulationRequest:
    return _request(policy_domain="unemployment_claims_benefit").model_copy(
        update={
            "coupling_graph": _coupling_graph("shared_resource"),
            "selected_outcomes": ("final_queue_length",),
            "baseline_state": {"final_queue_length": 0.0},
            "engine_plan": (
                EnginePlan(
                    engine_kind="coupled_des_abm",
                    objective_ref="objective://claims-queue",
                    eligibility_conditions=(
                        "unemployment_claims",
                        "benefit_queue",
                        "service_queue",
                    ),
                    variable_map={
                        "agents.income": "benefit_amount",
                        "government.balance": "service_rate",
                    },
                    coupled_state={
                        "initial_income": [1000.0, 600.0, 400.0],
                        "initial_savings": [0.0, 0.0, 0.0],
                        "is_employed": [0.0, 0.0, 0.0],
                    },
                    coupled_params={
                        "benefit_amount": 0.0,
                        "service_rate": 0.5,
                        "initial_queue_length": 0.0,
                        "seed": 7,
                    },
                ),
            ),
        }
    )


def _queue_tag_counterexample_request() -> JointSimulationRequest:
    return _request(policy_domain="unemployment_claims_benefit").model_copy(
        update={
            "selected_outcomes": ("final_queue_length",),
            "baseline_state": {"final_queue_length": 0.0},
            "engine_plan": (
                EnginePlan(
                    engine_kind="method_registry_estimator",
                    objective_ref="objective://queue-tag-counterexample",
                    method_fqn="simulation.discrete_event.queue@1.0.0",
                    declared_equilibrium_semantics="agent_based_model",
                    eligibility_conditions=("multi_period", "agent_based_model"),
                    variable_map={
                        "agents.income": "arrival_rate",
                        "government.balance": "service_rate",
                    },
                    coupled_state={"queue_length": 0.0},
                    system_dynamics_params={
                        "service_rate": 1.0,
                        "arrival_rate": 2.0,
                        "n_steps": 3,
                    },
                ),
            ),
        }
    )


def _coupling_graph(kind: str) -> Any:
    if kind == "shared_resource":
        edges = (
            CouplingEdge(
                boundary_ref="boundary://eligibility-delivery",
                source_module_ref="module://eligibility",
                target_module_ref="module://delivery",
                relation="shared_resource:budget_capacity",
                interaction_strength="medium",
                feedback_intensity="none",
                evidence_ref="evidence://shared-resource",
            ),
        )
    elif kind == "feedback":
        edges = (
            CouplingEdge(
                boundary_ref="boundary://eligibility-delivery",
                source_module_ref="module://eligibility",
                target_module_ref="module://delivery",
                relation="claim_volume",
                interaction_strength="medium",
                feedback_intensity="medium",
                evidence_ref="evidence://feedback-forward",
            ),
            CouplingEdge(
                boundary_ref="boundary://delivery-eligibility",
                source_module_ref="module://delivery",
                target_module_ref="module://eligibility",
                relation="queue_delay_response",
                interaction_strength="medium",
                feedback_intensity="medium",
                evidence_ref="evidence://feedback-return",
            ),
        )
    else:
        raise RuntimeError(f"unknown coupling graph fixture {kind}")
    return build_coupling_graph(
        design_ref=f"design://joint-simulation/{kind}",
        module_refs=("module://eligibility", "module://delivery"),
        module_discovery_ref="discovery://fixture",
        interaction_edges=edges,
        evidence_state="observed",
        rule_version_ref="policyos.layer2.s5.coupling_composition.test",
    )


def main(argv: list[str] | None = None) -> int:
    started_at = time.perf_counter()
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--rederive-audit", action="store_true")
    parser.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--source-flip-mutations", action="store_true")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    if args.source_flip_mutations:
        results = run_source_flip_mutations(repo_root)
        report = {"results": list(results)}
        report["validator_wall_time_seconds"] = round(
            time.perf_counter() - started_at,
            6,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if all(row.get("result") == "RED" for row in results) else 1
    if args.rederive_audit:
        report = rederive_audit(repo_root)
        report["validator_wall_time_seconds"] = round(
            time.perf_counter() - started_at,
            6,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "pass" else 1
    if args.write:
        write(repo_root)
    if args.corrupt_field_drift_check:
        report = corrupt_field_drift_check(repo_root)
        report["validator_wall_time_seconds"] = round(time.perf_counter() - started_at, 6)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if report["status"] == "fail" else 0
    if args.check or not args.write:
        report = check(repo_root)
        report["validator_wall_time_seconds"] = round(time.perf_counter() - started_at, 6)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "pass" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(
        run_timed_entrypoint(
            main,
            script_path=__file__,
            argv=sys.argv[1:],
            started_perf_counter=_TIMING_STARTED_AT,
        )
    )
