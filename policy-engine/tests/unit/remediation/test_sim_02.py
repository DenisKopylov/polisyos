"""Behavioral witnesses for SIM-02 output, atom, and trajectory semantics.

The existing N5 tests cover the happy paths of the joint controller.  This
file keeps the three E02 counterexamples together so that a future repair is
driven by the observable controller boundary:

* B18 must not turn a missing/non-finite selected outcome into a numeric zero;
* B20 must not make incompatible atom assignments order-dependent; and
* B22 must not turn uncovered horizon steps into an implicit last-value hold.

The native path controls call the existing stock-flow, NCM, and artifact-backed
program-graph producers. Deliberately malformed envelopes and trajectory rows
also exercise the actual adapter guards; those controls do not establish an
external model's semantics. Persisted results are loaded by a fresh CAS reader.

Resource profile is P-CORE for NumPy stock-flow/NCM controls and P-JAX for the
tiny native program graph. Coupled-output controls remain bounded adapter
checks; native coupled execution has its own controlled slot.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any, ClassVar, Literal

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.foundry.methods.catalog.simulation.coupled import (
    CoupledPolicySimulationEstimator,
)
from polisyos.foundry.methods.catalog.simulation.dynamics import (
    StockFlowSystemDynamicsEstimator,
)
from polisyos.foundry.methods.selection.registry import MethodRegistry
from polisyos.ir.analytics.interventions import (
    ConditionalIntervention,
    ConditionalPolicy,
    InterventionContext,
    NodeIntervention,
    VariableAssignment,
    identification_plan_for_intervention,
)
from polisyos.runtime.quality import joint_simulation_horizon as joint_simulation_horizon_module
from polisyos.runtime.quality.intervention_atom_binding import (
    InterventionAtomBinding,
    build_intervention_atom_binding,
    intervention_atom_content_hash,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    EnginePlan,
    HorizonSpec,
    JointSimulationControllerError,
    JointSimulationHorizonController,
    JointSimulationRequest,
    JointSimulationResult,
)
from tests.unit.runtime.quality.test_joint_simulation_horizon import (
    _atom,
    _coupling_graph,
    _linked,
    _program_graph_plan,
    _request,
)


def _persist_and_read_result(
    result: JointSimulationResult,
    tmp_path: Path,
    *,
    expected_request: JointSimulationRequest | None = None,
) -> JointSimulationResult:
    """Read persisted diagnostics while preserving numerical consumer admission."""
    from polisyos.core.artifacts import read_core_json_artifact
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import verify_simulation_receipt

    cas_root = tmp_path / "retained-result-cas"
    writer = FileSystemCAS(cas_root)
    result_ref = persist_joint_simulation_result(result, store=writer)
    written_bytes = writer.get_bytes(result_ref)
    reader = FileSystemCAS(cas_root)
    expected_bindings = {
        "expected_world_model_record_content_hash": result.world_model_record_content_hash,
        "expected_atom_ids": result.atom_ids,
        "expected_selected_outcomes": result.selected_outcomes,
        "expected_receipt_payload_hash": result.receipt.payload_hash,
        "expected_request": expected_request,
    }
    if result.trajectories:
        restored = load_joint_simulation_result(result_ref, store=reader, **expected_bindings)
    else:
        with pytest.raises(GenerationCycleError) as refused:
            load_joint_simulation_result(result_ref, store=reader, **expected_bindings)
        assert refused.value.code == "joint_simulation_result_trajectory_missing"
        audit_payload = read_core_json_artifact(reader, result_ref).value
        restored = JointSimulationResult.model_validate(audit_payload)
        restored._content_payload = {
            key: value for key, value in audit_payload.items() if key != "receipt"
        }
        verify_simulation_receipt(restored.receipt, restored.content_bound_payload())
    assert reader.get_bytes(result_ref) == written_bytes
    assert restored.content_bound_payload() == result.content_bound_payload()
    return restored


def _assert_retained_failure(
    result: JointSimulationResult,
    *,
    expected_code: str,
    expected_context: dict[str, str] | None = None,
    completed_roles: tuple[tuple[str, tuple[str, ...]], ...] = (),
) -> None:
    """Assert a specific failed event without discarding completed role outputs."""
    assert result.diagnostics["physical_work_interruption"] == "n5_physical_work_failed"
    assert result.diagnostics["physical_work_capture_status"] == "observed"
    assert [
        (trajectory.run_level, trajectory.atom_ids) for trajectory in result.trajectories
    ] == list(completed_roles)
    observations = result.physical_work_observations
    assert len(observations) == len(completed_roles) + 1
    assert [observation.status for observation in observations] == [
        *("completed" for _role in completed_roles),
        "failed",
    ]
    failure = observations[-1]
    assert failure.error_type == "JointSimulationControllerError"
    assert failure.error_code == expected_code
    if expected_context is not None:
        assert failure.error_context == expected_context
    assert "n5_physical_work_failed" in result.promotion_ready_value_packet["authority_blockers"]
    assert result.receipt.trajectory_count == len(completed_roles)
    assert result.diagnostics["engine_run_claimed"] is bool(completed_roles)
    if not completed_roles:
        assert result.receipt.calibration_status == "no_run"
        assert result.marginal_effects == {}
    assert result.interaction_terms == ()
    assert result.higher_order_residuals == {}


def _single_step_ncm_request() -> JointSimulationRequest:
    """Build a request whose static NCM matches its one-point horizon."""
    return _request().model_copy(update={"horizon": HorizonSpec(start=0, end=0, step=1)})


def _request_with_same_target_assignments(
    *,
    left_value: float,
    right_value: float,
    reverse: bool = False,
    policy_domain: str = "fiscal_credit",
) -> JointSimulationRequest:
    """Build an NCM request whose two atoms target the same world variable."""
    request = _request(policy_domain=policy_domain).model_copy(
        update={"horizon": HorizonSpec(start=0, end=0, step=1)}
    )
    world_record_ref = request.world_model_record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="income_subsidy",
            causal_variable="agents.income",
            engine_variable="income_delta",
            value=left_value,
            world_model_record_ref=world_record_ref,
        ),
        _atom(
            intervention_id="balance_grant",
            causal_variable="agents.income",
            engine_variable="income_delta",
            value=right_value,
            world_model_record_ref=world_record_ref,
        ),
    )
    if reverse:
        atoms = tuple(reversed(atoms))
    return request.model_copy(update={"intervention_atoms": atoms})


def _coupled_request(
    *,
    left_value: float = 1.0,
    right_value: float = 1.0,
    reverse: bool = False,
    horizon: HorizonSpec | None = None,
    initial_queue_length: Any = 4.0,
) -> JointSimulationRequest:
    """Build a real coupled-engine request without invoking its JAX producer."""
    request = _request_with_same_target_assignments(
        left_value=left_value,
        right_value=right_value,
        reverse=reverse,
        policy_domain="unemployment_claims_benefit",
    )
    return request.model_copy(
        update={
            "coupling_graph": _coupling_graph("shared_resource"),
            "selected_outcomes": ("final_queue_length",),
            "baseline_state": {"final_queue_length": 0.0},
            "horizon": horizon or HorizonSpec(start=0, end=3, step=1),
            "engine_plan": (
                EnginePlan(
                    engine_kind="coupled_des_abm",
                    objective_ref="objective://sim02-queue",
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
                        "initial_income": [1000.0, 600.0],
                        "initial_savings": [0.0, 0.0],
                        "is_employed": [0.0, 0.0],
                    },
                    coupled_params={
                        "benefit_amount": 0.0,
                        "service_rate": 0.5,
                        **(
                            {"initial_queue_length": initial_queue_length}
                            if initial_queue_length is not None
                            else {}
                        ),
                    },
                ),
            ),
        }
    )


def _system_dynamics_request(
    *,
    selected_outcomes: tuple[str, ...] = ("stock0",),
    horizon: HorizonSpec | None = None,
    overrides_by_atom: dict[str, dict[str, Any]] | None = None,
    system_dynamics_params: dict[str, Any] | None = None,
) -> JointSimulationRequest:
    """Build a registered stock-flow request with deterministic small inputs."""
    request = _request()
    return request.model_copy(
        update={
            "selected_outcomes": selected_outcomes,
            "baseline_state": dict.fromkeys(selected_outcomes, 10.0),
            "horizon": horizon or HorizonSpec(start=0, end=2, step=1),
            "engine_plan": (
                EnginePlan(
                    engine_kind="system_dynamics",
                    objective_ref="objective://sim02-stock-flow",
                    variable_map={
                        "agents.income": "exogenous_inflows.0",
                        "government.balance": "exogenous_inflows.1",
                        "stock0": "stock:0",
                        "stock1": "stock:1",
                        "mass_balance": "mass_balance",
                    },
                    system_dynamics_state={
                        "initial_stocks": [10.0, 0.0],
                        "flow_matrix": [[0.0, 0.0], [0.0, 0.0]],
                        "exogenous_inflows": [0.0, 0.0],
                    },
                    system_dynamics_params=(
                        {"dt": 1.0} if system_dynamics_params is None else system_dynamics_params
                    ),
                    system_dynamics_state_overrides_by_atom=overrides_by_atom or {},
                ),
            ),
        }
    )


def _assert_assignment_conflict_refusal(
    result: JointSimulationResult,
    *,
    objective_ref: str,
) -> None:
    """Assert the public result records a non-authoritative pre-run refusal."""
    assert len(result.engine_decisions) == 1
    decision = result.engine_decisions[0]
    assert decision.decision == "unsupported"
    assert decision.reason == "intervention_assignment_conflict"
    assert decision.blockers == ("intervention_assignment_conflict",)
    assert result.diagnostics["unsupported_objectives"] == [objective_ref]
    assert result.diagnostics["unsupported_reasons"] == [
        {
            "objective_ref": objective_ref,
            "reason": "intervention_assignment_conflict",
            "blockers": ["intervention_assignment_conflict"],
        }
    ]
    assert result.diagnostics["engine_run_claimed"] is False
    assert result.trajectories == ()
    assert result.marginal_effects == {}
    assert result.interaction_terms == ()
    assert result.higher_order_residuals == {}
    assert result.promotion_ready_value_packet["effect_basis_status"] == (
        "not_applicable_no_trajectory"
    )
    assert result.receipt.trajectory_count == 0
    assert result.receipt.authoritative_for == ()
    assert result.receipt.calibration_status == "no_run"


@pytest.mark.parametrize(
    ("world_summaries", "selected_outcomes", "expected_code"),
    [
        pytest.param(
            [],
            ("firm_survival",),
            "ncm_world_summaries_missing",
            id="empty-world-summaries",
        ),
        pytest.param(
            [{"world_index": 0}],
            ("firm_survival",),
            "ncm_outcome_missing",
            id="missing-selected-outcome",
        ),
        pytest.param(
            [{"world_index": 0, "firm_survival": {"mean": 2.0}}],
            ("firm_survival", "missing_outcome"),
            "ncm_outcome_missing",
            id="mixed-valid-and-missing-selected-outcome",
        ),
        pytest.param(
            [{"world_index": 0, "firm_survival": {"mean": float("nan")}}],
            ("firm_survival",),
            "ncm_outcome_non_finite",
            id="nan-selected-outcome",
        ),
        pytest.param(
            [{"world_index": 0, "firm_survival": {"mean": float("inf")}}],
            ("firm_survival",),
            "ncm_outcome_non_finite",
            id="infinite-selected-outcome",
        ),
        pytest.param(
            [{"world_index": 0, "firm_survival": {"mean": None}}],
            ("firm_survival",),
            "ncm_outcome_non_numeric",
            id="null-selected-outcome",
        ),
        pytest.param(
            [{"world_index": 0, "firm_survival": {"mean": True}}],
            ("firm_survival",),
            "ncm_outcome_non_numeric",
            id="boolean-selected-outcome",
        ),
    ],
)
def test_ncm_selected_outcome_missing_or_nonfinite_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    world_summaries: list[dict[str, Any]],
    selected_outcomes: tuple[str, ...],
    expected_code: str,
) -> None:
    """B18: absence and invalid numbers must not become an observed zero."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "counterfactual_result": {
                "world_summaries": world_summaries,
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fake_pure_step))
    request = _single_step_ncm_request().model_copy(update={"selected_outcomes": selected_outcomes})

    result = JointSimulationHorizonController().run(request)
    restored = _persist_and_read_result(result, tmp_path)
    _assert_retained_failure(restored, expected_code=expected_code)


def test_ncm_explicit_zero_is_preserved_as_a_real_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B18 positive control: an explicit finite zero remains numeric zero."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {"world_index": 0, "firm_survival": {"mean": 0.0}},
                ],
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fake_pure_step))

    result = JointSimulationHorizonController().run(_single_step_ncm_request())

    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[0].outcomes == {"firm_survival": 0.0}


@pytest.mark.parametrize(
    ("producer_output", "expected_code"),
    [
        pytest.param(None, "ncm_result_malformed", id="non-mapping-envelope"),
        pytest.param(
            {"counterfactual_result": {"world_summaries": [{"firm_survival": {"mean": []}}]}},
            "ncm_outcome_missing",
            id="empty-selected-value",
        ),
    ],
)
def test_ncm_malformed_result_is_typed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    producer_output: object,
    expected_code: str,
) -> None:
    """B18 malformed envelopes and empty values cannot become numeric outcomes."""

    def fake_pure_step(state: Any, params: Any) -> object:
        del state, params
        return producer_output

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fake_pure_step))

    result = JointSimulationHorizonController().run(_single_step_ncm_request())
    restored = _persist_and_read_result(result, tmp_path)
    _assert_retained_failure(restored, expected_code=expected_code)


@pytest.mark.parametrize("reverse", [False, True], ids=("left-right", "right-left"))
def test_conflicting_atom_assignments_are_rejected_instead_of_last_wins(
    monkeypatch: pytest.MonkeyPatch,
    reverse: bool,
) -> None:
    """B20: different values for one target slot are not list-order semantics."""

    calls = 0

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        del state, params
        return {}

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fake_pure_step))

    request = _request_with_same_target_assignments(
        left_value=1.0,
        right_value=2.0,
        reverse=reverse,
    )

    result = JointSimulationHorizonController().run(request)
    _assert_assignment_conflict_refusal(result, objective_ref=request.engine_plan[0].objective_ref)
    assert calls == 0


def test_identical_atom_assignments_are_order_invariant() -> None:
    """B20 positive control: compatible duplicate assignments preserve behavior."""

    left_first = JointSimulationHorizonController().run(
        _request_with_same_target_assignments(left_value=1.0, right_value=1.0)
    )
    right_first = JointSimulationHorizonController().run(
        _request_with_same_target_assignments(
            left_value=1.0,
            right_value=1.0,
            reverse=True,
        )
    )

    left_joint = left_first.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    right_joint = right_first.trajectory_for("joint", ("balance_grant", "income_subsidy"))
    assert left_joint.points == right_joint.points


class _ShortTrajectoryMethod:
    """Tiny registry method that exposes one point for a three-step request."""

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="short_trajectory",
        namespace="tests.sim02",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))}),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="SIM-02 short-trajectory test method.",
        tags=frozenset({"simulation", "sim02"}),
        assumptions={
            "joint_simulation_output_shape": "time_series_trajectory",
            "joint_simulation_equilibrium_semantics": "dynamic_SCM",
        },
    )

    @staticmethod
    def pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "result": {
                "trajectory": [[10.0]],
                "final_stocks": [99.0],
            }
        }


def _short_trajectory_request(method_fqn: str) -> JointSimulationRequest:
    """Build a dynamic request whose runner returns less coverage than asked."""
    request = _request()
    return request.model_copy(
        update={
            "selected_outcomes": ("stock0",),
            "baseline_state": {"stock0": 10.0},
            "horizon": HorizonSpec(start=0, end=2, step=1),
            "engine_plan": (
                EnginePlan(
                    engine_kind="method_registry_estimator",
                    objective_ref="objective://sim02-short-trajectory",
                    method_fqn=method_fqn,
                    variable_map={
                        "agents.income": "queue_length",
                        "government.balance": "queue_length",
                        "stock0": "stock:0",
                    },
                    coupled_state={"queue_length": 0.0},
                ),
            ),
        }
    )


def _method_registry_write_request(
    method_fqn: str,
    *,
    left_value: float,
    right_value: float,
    reverse: bool = False,
) -> JointSimulationRequest:
    """Build a selected method-registry request with one shared state target."""
    request = _request()
    world_ref = request.world_model_record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="income_subsidy",
            causal_variable="agents.income",
            engine_variable="queue_length",
            value=left_value,
            world_model_record_ref=world_ref,
        ),
        _atom(
            intervention_id="balance_grant",
            causal_variable="government.balance",
            engine_variable="queue_length",
            value=right_value,
            world_model_record_ref=world_ref,
        ),
    )
    if reverse:
        atoms = tuple(reversed(atoms))
    plan = EnginePlan(
        engine_kind="method_registry_estimator",
        objective_ref="objective://sim02-method-registry-writes",
        method_fqn=method_fqn,
        variable_map={
            "agents.income": "queue_length",
            "government.balance": "queue_length",
            "stock0": "stock:0",
        },
        coupled_state={"queue_length": 0.0},
    )
    return request.model_copy(
        update={
            "intervention_atoms": atoms,
            "selected_outcomes": ("stock0",),
            "baseline_state": {"stock0": 0.0},
            "horizon": HorizonSpec(start=0, end=0, step=1),
            "engine_plan": (plan,),
        }
    )


@pytest.mark.parametrize("reverse", [False, True], ids=("left-right", "right-left"))
def test_method_registry_conflict_is_rejected_before_runner(
    monkeypatch: pytest.MonkeyPatch,
    reverse: bool,
) -> None:
    """B20: registry methods reject conflicting writes before any invocation."""
    registry = MethodRegistry._create_fresh()
    method_fqn = registry.register(_ShortTrajectoryMethod)
    calls: list[object] = []

    def observed(state: Any, params: Any) -> dict[str, Any]:
        calls.append(state)
        return {"result": {"trajectory": [[float(state["queue_length"])]]}}

    monkeypatch.setattr(_ShortTrajectoryMethod, "pure_step", staticmethod(observed))
    request = _method_registry_write_request(
        method_fqn,
        left_value=1.0,
        right_value=2.0,
        reverse=reverse,
    )

    result = JointSimulationHorizonController(method_registry=registry).run(request)

    _assert_assignment_conflict_refusal(result, objective_ref=request.engine_plan[0].objective_ref)
    assert calls == []


def test_method_registry_equal_writes_are_applied_to_runner_state_in_both_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B20: equal duplicate writes reach the selected method's consumed state."""
    registry = MethodRegistry._create_fresh()
    method_fqn = registry.register(_ShortTrajectoryMethod)
    seen: list[float] = []

    def echo_state(state: Any, params: Any) -> dict[str, Any]:
        del params
        value = float(state["queue_length"])
        seen.append(value)
        return {"result": {"trajectory": [[value]]}}

    monkeypatch.setattr(_ShortTrajectoryMethod, "pure_step", staticmethod(echo_state))
    outputs = []
    for reverse in (False, True):
        request = _method_registry_write_request(
            method_fqn,
            left_value=4.0,
            right_value=4.0,
            reverse=reverse,
        )
        result = JointSimulationHorizonController(method_registry=registry).run(request)
        ids = tuple(atom.intervention_id for atom in request.intervention_atoms)
        joint = result.trajectory_for("joint", ids)
        outputs.append(joint.points[0].outcomes["stock0"])
        assert joint.points[0].outcomes["stock0"] == 4.0
    assert outputs == [4.0, 4.0]
    assert seen and set(seen) == {4.0}


def test_horizon_grid_rejects_a_truncated_requested_endpoint() -> None:
    """B22: the producer cannot silently omit an off-grid requested endpoint."""
    with pytest.raises(ValueError, match="horizon_end_not_on_step_grid"):
        HorizonSpec(start=0, end=5, step=2)

    assert HorizonSpec(start=1, end=5, step=2).steps() == (1, 3, 5)


def test_short_trajectory_is_not_silently_extended_by_final_value() -> None:
    """B22: uncovered horizon steps remain partial or fail closed, never hold-last."""

    registry = MethodRegistry._create_fresh()
    method_fqn = registry.register(_ShortTrajectoryMethod)

    result = JointSimulationHorizonController(method_registry=registry).run(
        _short_trajectory_request(method_fqn)
    )

    # A permitted partial result has only the point the method actually
    # emitted.  It must carry an explicit status and cannot expose final_stocks
    # as a silent hold-last reconstruction for steps 1 and 2.
    joint = result.trajectory_for(
        "joint",
        ("income_subsidy", "balance_grant"),
    )
    assert [point.step for point in joint.points] == [0]
    assert [point.outcomes for point in joint.points] == [{"stock0": 10.0}]
    assert joint.diagnostics.get("coverage_status") == "partial"
    assert tuple(joint.diagnostics.get("covered_steps", ())) == (0,)
    assert joint.diagnostics.get("hold_last", False) is False
    assert joint.diagnostics["time_alignment_status"] == "not_established"


@pytest.mark.parametrize("reverse", [False, True], ids=("left-right", "right-left"))
def test_coupled_conflicting_assignments_refuse_before_method_invocation(
    monkeypatch: pytest.MonkeyPatch,
    reverse: bool,
) -> None:
    """The selected coupled engine cannot observe order-dependent atoms."""
    calls = 0

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        del state, params
        return {"result": {"initial_queue_length": 0.0}}

    monkeypatch.setattr(
        CoupledPolicySimulationEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    request = _coupled_request(left_value=1.0, right_value=2.0, reverse=reverse)

    result = JointSimulationHorizonController().run(request)

    _assert_assignment_conflict_refusal(result, objective_ref=request.engine_plan[0].objective_ref)
    assert calls == 0


@pytest.mark.parametrize(
    ("left_value", "right_value"),
    [
        pytest.param(True, 1, id="bool-versus-int"),
        pytest.param(True, 1.0, id="bool-versus-float"),
        pytest.param(1, 1.0, id="int-versus-float"),
        pytest.param(
            {"enabled": True, "thresholds": [1, 2.0]},
            {"enabled": 1, "thresholds": [1, 2.0]},
            id="nested-bool-versus-int",
        ),
        pytest.param(
            {"enabled": True, "thresholds": [1, 2.0]},
            {"enabled": True, "thresholds": [1.0, 2.0]},
            id="nested-int-versus-float",
        ),
    ],
)
@pytest.mark.parametrize("reverse", [False, True], ids=("left-right", "right-left"))
def test_program_parameter_conflicts_refuse_before_graph_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    left_value: Any,
    right_value: Any,
    reverse: bool,
) -> None:
    """B20 rejects type-distinct program writes before graph execution."""
    assert left_value == right_value
    base = _request()
    source_atoms = base.intervention_atoms
    plan = _program_graph_plan(tmp_path).model_copy(
        update={
            "program_parameter_overrides_by_atom": {
                "income_subsidy": {"apply_subsidy": {"rate": left_value}},
                "balance_grant": {"apply_subsidy": {"rate": right_value}},
            }
        }
    )
    request = base.model_copy(
        update={
            "intervention_atoms": tuple(reversed(source_atoms)) if reverse else source_atoms,
            "engine_plan": (plan,),
        }
    )
    calls = 0
    original_execute = joint_simulation_horizon_module.execute_program_graph

    def observed_execute(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original_execute(*args, **kwargs)

    monkeypatch.setattr(joint_simulation_horizon_module, "execute_program_graph", observed_execute)

    result = JointSimulationHorizonController().run(request)

    _assert_assignment_conflict_refusal(result, objective_ref=request.engine_plan[0].objective_ref)
    assert calls == 0


@pytest.mark.parametrize(
    ("left_value", "right_value"),
    [
        pytest.param(True, True, id="bool"),
        pytest.param(1, 1, id="int"),
        pytest.param(1.0, 1.0, id="float"),
        pytest.param(
            {"enabled": True, "thresholds": [1, 2.0]},
            {"thresholds": [1, 2.0], "enabled": True},
            id="nested-json-values",
        ),
    ],
)
def test_identical_program_parameter_overrides_merge_independent_of_atom_order(
    tmp_path: Path,
    left_value: Any,
    right_value: Any,
) -> None:
    """Equal typed values merge; arbitrary JSON does not pretend to be a tax rate."""
    plan = _program_graph_plan(tmp_path).model_copy(
        update={
            "program_parameter_overrides_by_atom": {
                "income_subsidy": {"apply_subsidy": {"rate": left_value}},
                "balance_grant": {"apply_subsidy": {"rate": right_value}},
            }
        }
    )
    merged = []
    for reverse in (False, True):
        atoms = _request().intervention_atoms
        value = joint_simulation_horizon_module._program_parameter_overrides(
            tuple(reversed(atoms)) if reverse else atoms,
            plan,
        )
        assert value is not None
        assert type(value["apply_subsidy"]["rate"]) is type(left_value)
        assert json.dumps(value["apply_subsidy"]["rate"], sort_keys=True) == json.dumps(
            left_value, sort_keys=True
        )
        merged.append(value)
    assert merged[0] == merged[1]


def test_identical_program_parameter_writes_reach_persisted_graph_consumer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same-typed aliases execute the real graph and survive a fresh CAS reader."""
    original_execute = joint_simulation_horizon_module.execute_program_graph
    observed_rates: list[Any] = []

    def observe_execute(*args: Any, **kwargs: Any) -> Any:
        parameter_overrides = kwargs.get("parameter_overrides")
        assert isinstance(parameter_overrides, Mapping)
        rate = parameter_overrides["apply_subsidy"]["rate"]
        observed_rates.append(rate)
        return original_execute(*args, **kwargs)

    monkeypatch.setattr(joint_simulation_horizon_module, "execute_program_graph", observe_execute)
    outputs: list[list[float]] = []

    for reverse in (False, True):
        case_root = tmp_path / ("right-left" if reverse else "left-right")
        plan = _program_graph_plan(case_root, rates_by_atom=(0.10, 0.10))
        base = _request()
        atoms = tuple(reversed(base.intervention_atoms)) if reverse else base.intervention_atoms
        request = base.model_copy(
            update={
                "intervention_atoms": atoms,
                "engine_plan": (plan,),
                "selected_outcomes": ("mean_income",),
                "baseline_state": {"mean_income": 0.0},
            }
        )

        produced = JointSimulationHorizonController().run(request)
        restored = _persist_and_read_result(
            produced,
            case_root / "readback",
            expected_request=request,
        )

        assert restored.engine_decisions[0].decision == "selected"
        assert restored.engine_decisions[0].engine_kind == "program_graph"
        assert restored.physical_work_observations
        assert all(item.status == "completed" for item in restored.physical_work_observations)
        joint = restored.trajectory_for("joint", tuple(atom.intervention_id for atom in atoms))
        values = [point.outcomes["mean_income"] for point in joint.points]
        assert values == pytest.approx([1650.0, 1815.0, 1996.5, 2196.15])
        outputs.append(values)

    assert observed_rates
    assert all(type(rate) is float and rate == 0.10 for rate in observed_rates)
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize(
    ("state", "expected_code"),
    [
        pytest.param({}, "program_graph_outcome_missing", id="missing-selected-state"),
        pytest.param(
            {"firm_survival": float("nan")},
            "program_graph_outcome_non_finite",
            id="non-finite-selected-state",
        ),
        pytest.param(
            {"firm_survival": {"mean": 1.0}},
            "program_graph_outcome_non_numeric",
            id="malformed-selected-state",
        ),
    ],
)
def test_program_graph_selected_outcome_is_typed_at_adapter_boundary(
    state: dict[str, Any],
    expected_code: str,
) -> None:
    """B18 checks malformed values at the actual graph outcome guard."""
    plan = EnginePlan(
        engine_kind="program_graph",
        objective_ref="objective://sim02-program-output",
    )

    with pytest.raises(JointSimulationControllerError) as raised:
        joint_simulation_horizon_module._program_graph_outcomes(state, ("firm_survival",), plan)

    assert raised.value.code == expected_code


def test_program_graph_explicit_zero_is_preserved_at_controller_boundary(
    tmp_path: Path,
) -> None:
    """A native artifact-backed zero-rate graph preserves a real scalar zero."""
    plan = _program_graph_plan(tmp_path, rates_by_atom=(0.0, 0.0)).model_copy(
        update={"variable_map": {"balance": "government_balance"}}
    )
    request = _request().model_copy(
        update={
            "selected_outcomes": ("balance",),
            "baseline_state": {"balance": 0.0},
            "horizon": HorizonSpec(start=0, end=0, step=1),
            "engine_plan": (plan,),
        }
    )

    result = JointSimulationHorizonController().run(request)
    restored = _persist_and_read_result(result, tmp_path)
    joint = restored.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[0].outcomes == {"balance": 0.0}


def test_system_state_override_conflict_refuses_before_method_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """System-dynamics atom overlays cannot silently replace each other."""
    calls = 0

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        del state, params
        return {"result": {"trajectory": [[10.0], [10.0], [10.0]]}}

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    request = _system_dynamics_request(
        overrides_by_atom={
            "income_subsidy": {"initial_stocks": [4.0, 0.0]},
            "balance_grant": {"initial_stocks": [8.0, 0.0]},
        }
    )

    result = JointSimulationHorizonController().run(request)

    _assert_assignment_conflict_refusal(result, objective_ref=request.engine_plan[0].objective_ref)
    assert calls == 0


def test_identical_system_state_overrides_merge_independent_of_atom_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compatible nested state writes preserve the same state under permutation."""
    received_states: list[dict[str, Any]] = []

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del params
        received_states.append(state)
        return {"result": {"trajectory": [[4.0, 0.0], [4.0, 0.0], [4.0, 0.0]]}}

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    captured_joint_states = []
    for reverse in (False, True):
        request = _system_dynamics_request(
            overrides_by_atom={
                "income_subsidy": {"initial_stocks": [4.0, 0.0]},
                "balance_grant": {"initial_stocks": [4.0, 0.0]},
            }
        )
        if reverse:
            request = request.model_copy(
                update={"intervention_atoms": tuple(reversed(request.intervention_atoms))}
            )
        before = len(received_states)
        JointSimulationHorizonController().run(request)
        captured_joint_states.append(received_states[-1])
        assert len(received_states) > before

    assert captured_joint_states == [
        {
            "initial_stocks": [4.0, 0.0],
            "flow_matrix": [[0.0, 0.0], [0.0, 0.0]],
            "exogenous_inflows": [1.0, 1.0],
        },
        {
            "initial_stocks": [4.0, 0.0],
            "flow_matrix": [[0.0, 0.0], [0.0, 0.0]],
            "exogenous_inflows": [1.0, 1.0],
        },
    ]


@pytest.mark.parametrize(
    ("result", "initial_queue_length", "expected_code"),
    [
        pytest.param({}, None, "coupled_outcome_missing", id="missing-queue-output"),
        pytest.param(
            {"queue_length_trajectory": [float("nan")]},
            0.0,
            "coupled_outcome_non_finite",
            id="non-finite-queue-output",
        ),
        pytest.param(
            {"queue_length_trajectory": [0.0]},
            "unknown",
            "coupled_outcome_non_numeric",
            id="malformed-initial-queue",
        ),
    ],
)
def test_coupled_selected_queue_output_is_typed_and_never_defaulted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    result: dict[str, Any],
    initial_queue_length: Any,
    expected_code: str,
) -> None:
    """Missing and malformed queue output cannot be emitted as numeric zero."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {"result": result}

    monkeypatch.setattr(
        CoupledPolicySimulationEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )

    produced = JointSimulationHorizonController().run(
        _coupled_request(initial_queue_length=initial_queue_length)
    )
    restored = _persist_and_read_result(produced, tmp_path)
    _assert_retained_failure(restored, expected_code=expected_code)


def test_identical_coupled_assignments_merge_independent_of_atom_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compatible direct queue-engine inputs do not depend on atom ordering."""
    received_params: list[dict[str, Any]] = []

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state
        received_params.append(dict(params))
        return {"result": {"queue_length_trajectory": [3.0, 2.0, 1.0]}}

    monkeypatch.setattr(
        CoupledPolicySimulationEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    results = [
        JointSimulationHorizonController().run(
            _coupled_request(left_value=1.0, right_value=1.0, reverse=reverse)
        )
        for reverse in (False, True)
    ]

    assert received_params
    assert all(params["benefit_amount"] == 1.0 for params in received_params)
    left = results[0].trajectory_for("joint", ("income_subsidy", "balance_grant"))
    right = results[1].trajectory_for("joint", ("balance_grant", "income_subsidy"))
    assert left.points == right.points
    assert left.diagnostics["time_alignment_status"] == "not_established"


def test_coupled_omitted_initial_queue_uses_registered_method_contract_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A declared method default is an effective input, not a missing output."""
    received_params: list[dict[str, Any]] = []

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state
        received_params.append(dict(params))
        return {"result": {"queue_length_trajectory": [1.0, 2.0, 3.0]}}

    declared_default = next(
        parameter.default
        for parameter in CoupledPolicySimulationEstimator.signature.parameters
        if parameter.name == "initial_queue_length"
    )
    monkeypatch.setattr(
        CoupledPolicySimulationEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )

    result = JointSimulationHorizonController().run(_coupled_request(initial_queue_length=None))

    assert received_params
    assert all(params["initial_queue_length"] == declared_default for params in received_params)
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[0].outcomes["final_queue_length"] == declared_default


def test_coupled_short_queue_trajectory_is_partial_and_does_not_hold_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the configured initial value and actual queue rows cover the horizon."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "result": {
                "queue_length_trajectory": [3.0],
                "final_queue_length": 99.0,
            }
        }

    monkeypatch.setattr(
        CoupledPolicySimulationEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    result = JointSimulationHorizonController().run(_coupled_request())
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))

    assert [point.step for point in joint.points] == [0, 1]
    assert [point.outcomes["final_queue_length"] for point in joint.points] == [4.0, 3.0]
    assert joint.diagnostics["coverage_status"] == "partial"
    assert tuple(joint.diagnostics["covered_steps"]) == (0, 1)
    assert joint.diagnostics["hold_last"] is False
    assert joint.diagnostics["time_alignment_status"] == "not_established"


def test_coupled_empty_queue_trajectory_keeps_only_known_initial_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty emitted trajectory is partial, not a held terminal value."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {"result": {"queue_length_trajectory": [], "final_queue_length": 99.0}}

    monkeypatch.setattr(
        CoupledPolicySimulationEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    result = JointSimulationHorizonController().run(_coupled_request())
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))

    assert [point.step for point in joint.points] == [0]
    assert [point.outcomes["final_queue_length"] for point in joint.points] == [4.0]
    assert joint.diagnostics["coverage_status"] == "partial"
    assert tuple(joint.diagnostics["covered_steps"]) == (0,)
    assert joint.diagnostics["hold_last"] is False
    assert joint.diagnostics["time_alignment_status"] == "not_established"


@pytest.mark.parametrize(
    ("result", "selected_outcomes", "expected_code"),
    [
        pytest.param(
            {"trajectory": [[10.0, 0.0]], "final_stocks": [10.0, 0.0]},
            ("mass_balance",),
            "system_dynamics_outcome_missing",
            id="missing-mass-balance",
        ),
        pytest.param(
            {"trajectory": [[10.0, 0.0], [float("inf"), 0.0]]},
            ("stock0",),
            "system_dynamics_outcome_non_finite",
            id="non-finite-stock",
        ),
        pytest.param(
            {"trajectory": [[10.0, 0.0], [[10.0], [0.0]]]},
            ("stock0",),
            "system_dynamics_trajectory_contract_invalid",
            id="malformed-transition-shape",
        ),
    ],
)
def test_system_dynamics_selected_output_is_typed_and_never_defaulted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    result: dict[str, Any],
    selected_outcomes: tuple[str, ...],
    expected_code: str,
) -> None:
    """Missing mass-balance and non-finite stocks fail as typed evidence."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {"result": result}

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )

    produced = JointSimulationHorizonController().run(
        _system_dynamics_request(selected_outcomes=selected_outcomes)
    )
    restored = _persist_and_read_result(produced, tmp_path)
    _assert_retained_failure(restored, expected_code=expected_code)


def test_system_dynamics_run_level_scalar_is_not_repeated_across_horizon(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A single final mass-balance value is not a per-step time series."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "result": {
                "trajectory": [[10.0, 0.0], [10.0, 0.0], [10.0, 0.0]],
                "mass_balance": 0.0,
            }
        }

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )

    produced = JointSimulationHorizonController().run(
        _system_dynamics_request(selected_outcomes=("mass_balance",))
    )
    restored = _persist_and_read_result(produced, tmp_path)
    _assert_retained_failure(
        restored,
        expected_code="system_dynamics_temporal_outcome_series_missing",
    )


def test_system_dynamics_single_point_does_not_label_final_summary_as_initial(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Even zero in a final-only summary does not establish an initial observation."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {"result": {"trajectory": [[10.0, 0.0]], "mass_balance": 0.0}}

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    request = _system_dynamics_request(
        selected_outcomes=("mass_balance",),
        horizon=HorizonSpec(start=0, end=0, step=1),
    )

    result = JointSimulationHorizonController().run(request)
    restored = _persist_and_read_result(result, tmp_path)
    _assert_retained_failure(
        restored, expected_code="system_dynamics_temporal_outcome_series_missing"
    )


def test_system_dynamics_short_trajectory_is_partial_without_final_stock_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A final_stocks value cannot stand in for absent trajectory rows."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "result": {
                "trajectory": [[10.0, 0.0]],
                "final_stocks": [99.0],
                "mass_balance": 0.0,
            }
        }

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    result = JointSimulationHorizonController().run(_system_dynamics_request())
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))

    assert [point.step for point in joint.points] == [0]
    assert [point.outcomes["stock0"] for point in joint.points] == [10.0]
    assert joint.diagnostics["coverage_status"] == "partial"
    assert tuple(joint.diagnostics["covered_steps"]) == (0,)
    assert joint.diagnostics["hold_last"] is False
    assert joint.diagnostics["time_alignment_status"] == "not_established"


def test_empty_system_dynamics_trajectory_has_no_outcome_row_to_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An empty producer trajectory is distinguishable from the known short prefix."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {"result": {"trajectory": [], "final_stocks": [99.0]}}

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )

    produced = JointSimulationHorizonController().run(_system_dynamics_request())
    restored = _persist_and_read_result(produced, tmp_path)
    _assert_retained_failure(restored, expected_code="trajectory_coverage_incomplete")


def test_method_registry_missing_selected_output_is_not_filled_from_final_state(
    tmp_path: Path,
) -> None:
    """The generic registry adapter also refuses a missing selected value."""
    registry = MethodRegistry._create_fresh()
    method_fqn = registry.register(_ShortTrajectoryMethod)
    request = _short_trajectory_request(method_fqn).model_copy(
        update={
            "selected_outcomes": ("missing_value",),
            "baseline_state": {"missing_value": 0.0},
        }
    )

    produced = JointSimulationHorizonController(method_registry=registry).run(request)
    restored = _persist_and_read_result(produced, tmp_path)
    _assert_retained_failure(restored, expected_code="method_registry_outcome_missing")


def test_empty_method_registry_trajectory_is_not_filled_from_final_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An empty temporal method result cannot use its terminal summary as coverage."""
    registry = MethodRegistry._create_fresh()
    method_fqn = registry.register(_ShortTrajectoryMethod)

    def empty_trajectory(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {"result": {"trajectory": [], "final_stocks": [99.0]}}

    monkeypatch.setattr(_ShortTrajectoryMethod, "pure_step", staticmethod(empty_trajectory))

    produced = JointSimulationHorizonController(method_registry=registry).run(
        _short_trajectory_request(method_fqn)
    )
    restored = _persist_and_read_result(produced, tmp_path)
    _assert_retained_failure(restored, expected_code="trajectory_coverage_incomplete")


def test_non_unit_horizon_step_changes_real_stockflow_rows() -> None:
    """The producer receives the requested step; row labels are not physical-time proof."""
    request = _system_dynamics_request(
        selected_outcomes=("stock0", "stock1"),
        horizon=HorizonSpec(start=0, end=4, step=2),
        system_dynamics_params={},
    )

    result = JointSimulationHorizonController().run(request)

    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert [point.step for point in joint.points] == [0, 2, 4]
    assert [point.outcomes["stock0"] for point in joint.points] == [10.0, 12.0, 14.0]
    assert [point.outcomes["stock1"] for point in joint.points] == [0.0, 2.0, 4.0]
    assert joint.diagnostics["time_alignment_status"] == "not_established"
    assert type(joint.diagnostics["declared_step_parameter_matches_request"]) is bool
    assert joint.diagnostics["declared_step_parameter_matches_request"] is True
    assert joint.diagnostics["effective_method_time_step"] == 2.0
    serialized_joint = next(
        item
        for item in result.model_dump(mode="json")["trajectories"]
        if item["run_level"] == "joint"
    )
    assert serialized_joint["diagnostics"]["declared_step_parameter_matches_request"] is True
    assert result.diagnostics["physical_time_basis_status"] == "not_established"
    assert (
        "horizon_time_alignment_not_established"
        in (result.promotion_ready_value_packet["authority_blockers"])
    )


def test_configured_stockflow_step_mismatch_remains_visible() -> None:
    """An explicit method dt is preserved and marked when labels use another step."""
    request = _system_dynamics_request(
        selected_outcomes=("stock0",),
        horizon=HorizonSpec(start=0, end=4, step=2),
        system_dynamics_params={"dt": 1.0},
    )

    result = JointSimulationHorizonController().run(request)

    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert [point.step for point in joint.points] == [0, 2, 4]
    assert [point.outcomes["stock0"] for point in joint.points] == [10.0, 11.0, 12.0]
    assert joint.diagnostics["time_alignment_status"] == "not_established"
    assert joint.diagnostics["requested_time_step"] == 2
    assert type(joint.diagnostics["declared_step_parameter_matches_request"]) is bool
    assert joint.diagnostics["declared_step_parameter_matches_request"] is False
    assert joint.diagnostics["effective_method_time_step"] == 1.0
    serialized_joint = next(
        item
        for item in result.model_dump(mode="json")["trajectories"]
        if item["run_level"] == "joint"
    )
    assert serialized_joint["diagnostics"]["declared_step_parameter_matches_request"] is False


_StockFlowContour = Literal["system_dynamics", "registry_system_state", "registry_coupled_state"]


def _native_stockflow_write_request(
    contour: _StockFlowContour,
    *,
    left_target: str,
    right_target: str,
    left_value: float = 1.0,
    right_value: float = 2.0,
    reverse: bool = False,
    array_state: bool = False,
    extra_state: dict[str, Any] | None = None,
) -> JointSimulationRequest:
    """Use the numerical stock-flow owner through each actual state adapter."""
    request = _system_dynamics_request()
    state = {
        **request.engine_plan[0].system_dynamics_state,
        **(extra_state or {}),
    }
    if array_state:
        state["exogenous_inflows"] = np.asarray(state["exogenous_inflows"], dtype=float)
    plan_updates: dict[str, Any] = {
        "engine_kind": (
            "system_dynamics" if contour == "system_dynamics" else "method_registry_estimator"
        ),
        "method_fqn": StockFlowSystemDynamicsEstimator.signature.fqn,
        "variable_map": {
            **request.engine_plan[0].variable_map,
            "agents.income": left_target,
            "government.balance": right_target,
        },
        "system_dynamics_state": {} if contour == "registry_coupled_state" else state,
        "coupled_state": state if contour == "registry_coupled_state" else {},
    }
    world_ref = request.world_model_record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="income_subsidy",
            causal_variable="agents.income",
            engine_variable=left_target,
            value=left_value,
            world_model_record_ref=world_ref,
        ),
        _atom(
            intervention_id="balance_grant",
            causal_variable="government.balance",
            engine_variable=right_target,
            value=right_value,
            world_model_record_ref=world_ref,
        ),
    )
    return request.model_copy(
        update={
            "intervention_atoms": tuple(reversed(atoms)) if reverse else atoms,
            "engine_plan": (request.engine_plan[0].model_copy(update=plan_updates),),
        }
    )


_DirectAssignmentAdapter = Literal["ncm", "coupled", "system_dynamics", "registry"]


def _direct_assignment_adapter_request(
    adapter: _DirectAssignmentAdapter,
) -> JointSimulationRequest:
    """Keep one real bound node atom and an otherwise admissible numerical plan."""
    if adapter == "ncm":
        request = _single_step_ncm_request()
    elif adapter == "coupled":
        request = _coupled_request(horizon=HorizonSpec(start=0, end=1, step=1))
    elif adapter == "system_dynamics":
        request = _system_dynamics_request()
    else:
        request = _native_stockflow_write_request(
            "registry_system_state",
            left_target="exogenous_inflows.0",
            right_target="exogenous_inflows.1",
        )
    return request.model_copy(update={"intervention_atoms": request.intervention_atoms[:1]})


def _rebuild_direct_assignment_atom(
    source: InterventionAtomBinding,
    causal: NodeIntervention | ConditionalIntervention,
) -> InterventionAtomBinding:
    """Use the real linker and atom owner for a different valid proof-kernel expression."""
    intervention = source.to_trinity_intervention_spec()
    return build_intervention_atom_binding(
        problem_frame_ref=source.problem_frame_ref,
        policy_spec_ref=source.policy_spec_ref,
        intervention=intervention,
        linked_intervention=_linked(intervention),
        causal_intervention=causal,
        query_target=source.to_query_target(),
        identification_plan=identification_plan_for_intervention(causal),
        causal_context=InterventionContext.model_validate(source.causal_do_expr.context),
        world_model_record_ref=source.world_model_record_ref,
        producer_ref="test.sim02.real_linked_direct_assignment",
        operator_proof_type_map={intervention.kind: causal.intervention_type},
        mechanism_variable_map={intervention.kind: source.target_world_slots},
        mechanism_config_overrides=source.direct_effect_bundle.mechanism_config_overrides,
    )


def _assert_direct_assignment_preflight_refusal(
    result: JointSimulationResult,
    expected_reason: str,
) -> None:
    """Require the specific direct-adapter refusal before any physical work event."""
    assert len(result.engine_decisions) == 1
    assert result.engine_decisions[0].decision == "unsupported"
    assert result.engine_decisions[0].reason == expected_reason
    assert result.engine_decisions[0].blockers == (expected_reason,)
    assert result.trajectories == ()
    assert result.physical_work_observations == ()
    assert result.diagnostics["engine_run_claimed"] is False
    assert result.receipt.calibration_status == "no_run"
    assert result.receipt.authoritative_for == ()


@pytest.mark.parametrize("adapter", ["ncm", "coupled", "system_dynamics", "registry"])
def test_direct_adapters_refuse_real_conditional_atom_before_producer(
    monkeypatch: pytest.MonkeyPatch,
    adapter: _DirectAssignmentAdapter,
) -> None:
    """A valid non-node expression cannot silently become an empty do-assignment."""
    request = _direct_assignment_adapter_request(adapter)
    source = request.intervention_atoms[0]
    target = source.causal_do_expr.assignments[0].variable
    conditional = _rebuild_direct_assignment_atom(
        source,
        ConditionalIntervention(assignments=(ConditionalPolicy(target=target, policy_expr="1.0"),)),
    )
    assert isinstance(conditional.to_causal_intervention(), ConditionalIntervention)
    assert conditional.causal_do_expr.assignments == ()
    assert conditional.causal_do_expr.write_variables == (target,)
    assert intervention_atom_content_hash(conditional) == conditional.content_hash
    method = (
        NCMEngineMethod
        if adapter == "ncm"
        else CoupledPolicySimulationEstimator
        if adapter == "coupled"
        else StockFlowSystemDynamicsEstimator
    )
    original = method.pure_step
    calls = []

    def observed(state: Any, params: Any) -> dict[str, Any]:
        calls.append("physical-call")
        return original(state, params)

    monkeypatch.setattr(method, "pure_step", staticmethod(observed))
    controller = JointSimulationHorizonController()
    assert controller._select_engine(request).decision.decision == "selected"

    result = controller.run(request.model_copy(update={"intervention_atoms": (conditional,)}))

    _assert_direct_assignment_preflight_refusal(
        result, "intervention_direct_assignment_unsupported"
    )
    assert calls == []


@pytest.mark.parametrize("adapter", ["ncm", "coupled", "system_dynamics", "registry"])
@pytest.mark.parametrize("mismatch", ["different-value", "different-type", "zero-sign"])
def test_direct_adapters_refuse_content_valid_divergent_node_payload(
    monkeypatch: pytest.MonkeyPatch,
    adapter: _DirectAssignmentAdapter,
    mismatch: str,
) -> None:
    """A rehashed candidate must not select one meaning while executing another."""
    request = _direct_assignment_adapter_request(adapter)
    source = request.intervention_atoms[0]
    target = source.causal_do_expr.assignments[0].variable
    projected_value = 0.0 if mismatch == "zero-sign" else 1.0
    matching = _rebuild_direct_assignment_atom(
        source,
        NodeIntervention(assignments=(VariableAssignment(variable=target, value=projected_value),)),
    )
    payload = deepcopy(matching.causal_do_expr.expression_payload)
    payload["assignments"][0]["value"] = (
        -0.0 if mismatch == "zero-sign" else 1 if mismatch == "different-type" else 2.0
    )
    draft = matching.model_copy(
        update={
            "causal_do_expr": matching.causal_do_expr.model_copy(
                update={"expression_payload": payload}
            )
        }
    )
    revised_hash = intervention_atom_content_hash(draft)
    divergent = InterventionAtomBinding.model_validate(
        {
            **draft.model_dump(mode="python"),
            "atom_id": f"atom_{revised_hash.removeprefix('sha256:')[:16]}",
            "content_hash": revised_hash,
        }
    )
    assert intervention_atom_content_hash(divergent) == divergent.content_hash
    actual = divergent.to_node_intervention().assignments[0].value
    projected = divergent.causal_do_expr.assignments[0].value
    if mismatch == "zero-sign":
        assert type(actual) is float and type(projected) is float
        assert actual == projected == 0.0
        assert actual.hex() == (-0.0).hex()
        assert projected.hex() == (0.0).hex()
    elif mismatch == "different-type":
        assert type(actual) is int and type(projected) is float
        assert actual == projected == 1.0
    else:
        assert actual == 2.0
        assert projected == 1.0
    method = (
        NCMEngineMethod
        if adapter == "ncm"
        else CoupledPolicySimulationEstimator
        if adapter == "coupled"
        else StockFlowSystemDynamicsEstimator
    )
    original = method.pure_step
    calls = []

    def observed(state: Any, params: Any) -> dict[str, Any]:
        calls.append("physical-call")
        return original(state, params)

    monkeypatch.setattr(method, "pure_step", staticmethod(observed))
    controller = JointSimulationHorizonController()
    assert (
        controller._select_engine(
            request.model_copy(update={"intervention_atoms": (matching,)})
        ).decision.decision
        == "selected"
    )

    result = controller.run(request.model_copy(update={"intervention_atoms": (divergent,)}))

    _assert_direct_assignment_preflight_refusal(
        result, "intervention_assignment_projection_mismatch"
    )
    assert calls == []


@pytest.mark.parametrize("zero", [0.0, -0.0], ids=("positive-zero", "negative-zero"))
def test_direct_node_same_sign_zero_runs_real_ncm(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    zero: float,
) -> None:
    """Positive zero executes; the unsupported negative sign refuses before work."""
    request = _direct_assignment_adapter_request("ncm")
    source = request.intervention_atoms[0]
    target = source.causal_do_expr.assignments[0].variable
    matching = _rebuild_direct_assignment_atom(
        source, NodeIntervention(assignments=(VariableAssignment(variable=target, value=zero),))
    )
    request = request.model_copy(update={"intervention_atoms": (matching,)})
    original = NCMEngineMethod.pure_step
    consumed = []

    def observed(state: Any, params: Any) -> dict[str, Any]:
        consumed.append(state["ncm_query_data"].interventions[0]["income_delta"])
        return original(state, params)

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(observed))

    produced = JointSimulationHorizonController().run(request)
    if np.signbit(zero):
        assert consumed == []
        _assert_direct_assignment_preflight_refusal(
            produced, "intervention_assignment_signed_zero_unsupported"
        )
        restored_refusal = _persist_and_read_result(produced, tmp_path)
        _assert_direct_assignment_preflight_refusal(
            restored_refusal, "intervention_assignment_signed_zero_unsupported"
        )
        return
    restored = _persist_and_read_result(produced, tmp_path, expected_request=request)

    assert restored.engine_decisions[0].decision == "selected"
    assert len(consumed) == 1
    assert type(consumed[0]) is float
    assert consumed[0].hex() == zero.hex()
    assert len(restored.physical_work_observations) == 1
    assert restored.physical_work_observations[0].status == "completed"
    joint = restored.trajectory_for("joint", ("income_subsidy",))
    assert joint.points[0].outcomes == {"firm_survival": 1.0}
    assert joint.points[0].effect == {"firm_survival": 0.0}


def test_negative_zero_producer_output_retains_prior_role_and_specific_cause(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An unpersistable selected output stops work without erasing a completed role."""
    original = NCMEngineMethod.pure_step
    calls = []

    def signed_zero_second_output(state: Any, params: Any) -> dict[str, Any]:
        output = original(state, params)
        calls.append("physical-call")
        if len(calls) == 2:
            output["counterfactual_result"]["world_summaries"][0]["firm_survival"]["mean"] = -0.0
        return output

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(signed_zero_second_output))

    produced = JointSimulationHorizonController().run(_single_step_ncm_request())
    restored = _persist_and_read_result(produced, tmp_path)

    assert len(calls) == 2
    _assert_retained_failure(
        restored,
        expected_code="n5_signed_zero_output_not_persistable",
        completed_roles=(("individual", ("income_subsidy",)),),
    )
    assert restored.trajectories[0].points[0].outcomes == {"firm_survival": 3.0}
    assert restored.trajectories[0].points[0].effect == {"firm_survival": 2.0}


def test_negative_zero_replication_mean_retains_completed_physical_work_and_prior_role(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A signed-zero aggregate is a projection failure after completed producer calls."""
    original = NCMEngineMethod.pure_step
    calls = []
    altered_values = []

    def subnormal_second_role(state: Any, params: Any) -> dict[str, Any]:
        output = original(state, params)
        calls.append("physical-call")
        if len(calls) in (3, 4):
            value = -5e-324 if len(calls) == 3 else 0.0
            altered_values.append(value)
            output["counterfactual_result"]["world_summaries"][0]["firm_survival"]["mean"] = value
        return output

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(subnormal_second_role))
    request = _single_step_ncm_request().model_copy(update={"replications": 2})

    produced = JointSimulationHorizonController().run(request)
    restored = _persist_and_read_result(produced, tmp_path)

    assert len(calls) == 4
    assert [value.hex() for value in altered_values] == ["-0x0.0000000000001p-1022", "0x0.0p+0"]
    assert restored.diagnostics["physical_work_interruption"] == "n5_replication_projection_failed"
    assert (
        restored.diagnostics["projection_error_code"] == "n5_signed_zero_aggregate_not_persistable"
    )
    assert restored.diagnostics["projection_error_context"] == {
        "stage": "replication_aggregation",
        "producer_call": "completed",
    }
    assert len(restored.physical_work_observations) == 4
    assert all(item.status == "completed" for item in restored.physical_work_observations)
    assert all(item.error_type is None for item in restored.physical_work_observations)
    assert restored.diagnostics["physical_work_units"] == 4
    assert [(item.run_level, item.atom_ids) for item in restored.trajectories] == [
        ("individual", ("income_subsidy",))
    ]
    point = restored.trajectories[0].points[0]
    assert point.outcomes == {"firm_survival": 3.0}
    assert point.effect == {"firm_survival": 2.0}
    assert point.replication_sampling is not None
    assert point.replication_sampling.replicate_count == 2
    assert restored.receipt.trajectory_count == 1
    assert restored.diagnostics["engine_run_claimed"] is True
    assert restored.interaction_terms == ()
    assert (
        "n5_replication_projection_failed"
        in (restored.promotion_ready_value_packet["authority_blockers"])
    )


@pytest.mark.parametrize("location", ["payload", "diagnostics"])
def test_receipt_builder_signed_zero_guard_is_v5_only(location: str) -> None:
    """V5 rejects unpersistable signs without changing historical receipt construction."""
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JOINT_SIMULATION_HORIZON_NUMERIC_TOLERANCE_SCHEMA_VERSION,
        JOINT_SIMULATION_HORIZON_PAIRED_INTERACTION_UNCERTAINTY_SCHEMA_VERSION,
        ProofReceiptError,
        build_content_bound_simulation_receipt,
        verify_simulation_receipt,
    )

    result = JointSimulationHorizonController().run(_single_step_ncm_request())
    positive_payload = deepcopy(result.content_bound_payload())
    assert positive_payload["schema_version"] == (
        JOINT_SIMULATION_HORIZON_NUMERIC_TOLERANCE_SCHEMA_VERSION
    )
    positive_payload["diagnostics"]["receipt_zero_probe"] = {"nested": [{"value": 0.0}]}
    positive_payload["trajectories"][0]["points"][0]["engine_state"]["receipt_zero_probe"] = {
        "nested": [{"value": 0.0}]
    }
    positive_receipt = build_content_bound_simulation_receipt(
        engine_kind=result.receipt.engine_kind,
        payload=positive_payload,
        diagnostics=positive_payload["diagnostics"],
    )
    verify_simulation_receipt(positive_receipt, positive_payload)

    negative_payload = deepcopy(positive_payload)
    negative_diagnostics = deepcopy(positive_payload["diagnostics"])
    if location == "payload":
        negative_payload["trajectories"][0]["points"][0]["engine_state"]["receipt_zero_probe"][
            "nested"
        ][0]["value"] = -0.0
    else:
        # Keep the payload positive to exercise the independently supplied diagnostics too.
        negative_diagnostics["receipt_zero_probe"]["nested"][0]["value"] = -0.0
    with pytest.raises(ProofReceiptError) as refusal:
        build_content_bound_simulation_receipt(
            engine_kind=result.receipt.engine_kind,
            payload=negative_payload,
            diagnostics=negative_diagnostics,
        )
    assert refusal.value.code == "n5_signed_zero_payload_not_persistable"

    # This is the historical builder contract only, not a legacy artifact migration
    # or a claim that Core .2 can persist this negative-zero payload losslessly.
    legacy_payload = deepcopy(negative_payload)
    legacy_payload["schema_version"] = (
        JOINT_SIMULATION_HORIZON_PAIRED_INTERACTION_UNCERTAINTY_SCHEMA_VERSION
    )
    legacy_payload["diagnostics"] = negative_diagnostics
    legacy_receipt = build_content_bound_simulation_receipt(
        engine_kind=result.receipt.engine_kind,
        payload=legacy_payload,
        diagnostics=legacy_payload["diagnostics"],
    )
    verify_simulation_receipt(legacy_receipt, legacy_payload)
    assert legacy_receipt.schema_version == (
        JOINT_SIMULATION_HORIZON_PAIRED_INTERACTION_UNCERTAINTY_SCHEMA_VERSION
    )
    legacy_positive = deepcopy(positive_payload)
    legacy_positive["schema_version"] = legacy_payload["schema_version"]
    legacy_positive_receipt = build_content_bound_simulation_receipt(
        engine_kind=result.receipt.engine_kind,
        payload=legacy_positive,
        diagnostics=legacy_positive["diagnostics"],
    )
    assert legacy_receipt.payload_hash != legacy_positive_receipt.payload_hash


def test_program_graph_keeps_real_conditional_atom_on_explicit_override_path(
    tmp_path: Path,
) -> None:
    """Candidate overrides retain an explicit unestablished atom-semantics boundary."""
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        build_content_bound_simulation_receipt,
        verify_simulation_receipt,
    )

    request = _native_program_population_request(tmp_path, {"method": "mean", "unit": "usd"})
    source = request.intervention_atoms[0]
    conditional = _rebuild_direct_assignment_atom(
        source,
        ConditionalIntervention(
            assignments=(ConditionalPolicy(target="agents.income", policy_expr="1.0"),)
        ),
    )
    request = request.model_copy(update={"intervention_atoms": (conditional,)})

    produced = JointSimulationHorizonController().run(request)
    restored = _persist_and_read_result(produced, tmp_path, expected_request=request)

    assert restored.engine_decisions[0].decision == "selected"
    assert restored.engine_decisions[0].engine_kind == "program_graph"
    assert len(restored.physical_work_observations) == 1
    assert restored.physical_work_observations[0].status == "completed"
    joint = restored.trajectory_for("joint", ("income_subsidy",))
    # These are the declared rate override's outputs, not an execution of policy_expr.
    assert joint.points[0].outcomes == {"mean_income": 1650.0, "balance": -300.0}
    limitation = "program_parameter_override_atom_semantics_not_established"
    assert restored.diagnostics["intervention_semantics_limitation"] == limitation
    assert limitation in restored.promotion_ready_value_packet["authority_blockers"]

    payload = deepcopy(restored.content_bound_payload())
    payload["promotion_ready_value_packet"]["authority_blockers"] = [
        blocker
        for blocker in payload["promotion_ready_value_packet"]["authority_blockers"]
        if blocker != limitation
    ]
    assert payload["diagnostics"]["intervention_semantics_limitation"] == limitation
    receipt = build_content_bound_simulation_receipt(
        engine_kind=restored.receipt.engine_kind,
        payload=payload,
        diagnostics=payload["diagnostics"],
    )
    verify_simulation_receipt(receipt, payload)
    reissued = JointSimulationResult.model_validate(
        {**payload, "receipt": receipt.model_dump(mode="json")}
    )
    reissued._content_payload = payload
    assert reissued.receipt.payload_hash != restored.receipt.payload_hash
    cas_path = tmp_path / "reissued-program-semantics"
    writer = FileSystemCAS(cas_path)
    reissued_ref = persist_joint_simulation_result(reissued, store=writer)

    with pytest.raises(
        GenerationCycleError, match="joint_simulation_result_execution_binding_invalid"
    ) as refusal:
        load_joint_simulation_result(
            reissued_ref,
            store=FileSystemCAS.open_existing_read_only(cas_path),
            expected_request=request,
            expected_receipt_payload_hash=reissued.receipt.payload_hash,
        )

    assert refusal.value.__cause__ is not None
    assert "selected_intervention_semantics_limitation_mismatch" in str(refusal.value.__cause__)


def _physical_identity_probe_plan(value: Any, *, numpy_carrier: bool = False) -> EnginePlan:
    """Keep one live state value available to the actual physical identity owner."""
    plan = _system_dynamics_request().engine_plan[0]
    state = {**plan.system_dynamics_state, "identity_probe": value}
    if numpy_carrier:
        state["identity_carrier"] = np.asarray([2.0, 3.0], dtype=np.float64)
    return plan.model_copy(update={"system_dynamics_state": state})


def test_physical_plan_identity_distinguishes_live_list_and_tuple_state() -> None:
    """Equal container contents do not erase the receiver's mutability contract."""
    list_plan = _physical_identity_probe_plan([1.0, 2.0])
    tuple_plan = _physical_identity_probe_plan((1.0, 2.0))
    assert type(list_plan.system_dynamics_state["identity_probe"]) is list
    assert type(tuple_plan.system_dynamics_state["identity_probe"]) is tuple

    list_identity = joint_simulation_horizon_module._physical_plan_identity(list_plan)
    tuple_identity = joint_simulation_horizon_module._physical_plan_identity(tuple_plan)

    assert list_identity != tuple_identity
    assert list_identity == joint_simulation_horizon_module._physical_plan_identity(list_plan)


def test_physical_plan_identity_preserves_legacy_ordinary_json_projection() -> None:
    """An ordinary JSON plan keeps the exact pre-change physical-plan projection."""
    plan = _system_dynamics_request().engine_plan[0]
    # Before typed state identity, _physical_run_ref bound this exact plan component.
    legacy_plan_projection = plan.model_dump(mode="json")

    identity = joint_simulation_horizon_module._physical_plan_identity(plan)

    assert identity == legacy_plan_projection
    assert "encoding" not in identity


def test_physical_plan_identity_distinguishes_tuple_and_list_program_parameters() -> None:
    """Program-override tuples retain their live type even without any NumPy value."""
    list_plan = EnginePlan(
        engine_kind="program_graph",
        objective_ref="objective://sim02-typed-program-parameter-identity",
        program_parameter_overrides_by_atom={
            "income_subsidy": {"policy_node": {"thresholds": [1.0, 2.0]}}
        },
    )
    tuple_plan = EnginePlan(
        engine_kind="program_graph",
        objective_ref="objective://sim02-typed-program-parameter-identity",
        program_parameter_overrides_by_atom={
            "income_subsidy": {"policy_node": {"thresholds": (1.0, 2.0)}}
        },
    )
    list_value = list_plan.program_parameter_overrides_by_atom["income_subsidy"]["policy_node"][
        "thresholds"
    ]
    tuple_value = tuple_plan.program_parameter_overrides_by_atom["income_subsidy"]["policy_node"][
        "thresholds"
    ]
    assert type(list_value) is list
    assert type(tuple_value) is tuple
    assert list_plan.model_dump(mode="json") == tuple_plan.model_dump(mode="json")

    assert joint_simulation_horizon_module._physical_plan_identity(
        list_plan
    ) != joint_simulation_horizon_module._physical_plan_identity(tuple_plan)


def test_physical_plan_identity_distinguishes_numpy_scalar_and_zero_dimensional_array() -> None:
    """The same dtype, shape and bytes do not equate a scalar with a mutable array."""
    scalar_plan = _physical_identity_probe_plan(np.float64(1.0))
    array_plan = _physical_identity_probe_plan(np.asarray(1.0, dtype=np.float64))
    scalar = scalar_plan.system_dynamics_state["identity_probe"]
    array = array_plan.system_dynamics_state["identity_probe"]
    assert type(scalar) is np.float64
    assert type(array) is np.ndarray
    assert array.ndim == 0
    assert np.asarray(scalar).dtype == array.dtype
    assert np.asarray(scalar).tobytes() == array.tobytes()

    assert joint_simulation_horizon_module._physical_plan_identity(
        scalar_plan
    ) != joint_simulation_horizon_module._physical_plan_identity(array_plan)


def test_physical_plan_identity_preserves_numpy_scalar_type_before_serialization() -> None:
    """A NumPy-bearing plan binds its live scalar type before a serializer can coerce it."""
    numpy_plan = _physical_identity_probe_plan(np.float64(1.0), numpy_carrier=True)
    python_plan = _physical_identity_probe_plan(1.0, numpy_carrier=True)
    assert type(numpy_plan.system_dynamics_state["identity_probe"]) is np.float64
    assert type(python_plan.system_dynamics_state["identity_probe"]) is float
    assert (
        numpy_plan.system_dynamics_state["identity_probe"]
        == python_plan.system_dynamics_state["identity_probe"]
    )
    assert type(numpy_plan.system_dynamics_state["identity_carrier"]) is np.ndarray
    assert type(python_plan.system_dynamics_state["identity_carrier"]) is np.ndarray

    assert joint_simulation_horizon_module._physical_plan_identity(
        numpy_plan
    ) != joint_simulation_horizon_module._physical_plan_identity(python_plan)


@pytest.mark.parametrize(
    "contour", ["system_dynamics", "registry_system_state", "registry_coupled_state"]
)
@pytest.mark.parametrize("alias_kind", ["repeated-list", "repeated-array", "overlapping-views"])
def test_native_adapters_refuse_mutable_aliases_before_any_producer_call(
    monkeypatch: pytest.MonkeyPatch,
    contour: _StockFlowContour,
    alias_kind: str,
) -> None:
    """Shared storage in live state is rejected before copying can hide its topology."""
    original = StockFlowSystemDynamicsEstimator.pure_step
    calls: list[dict[str, Any]] = []

    def observed(state: Any, params: Any) -> dict[str, Any]:
        calls.append(deepcopy(state))
        return original(state, params)

    monkeypatch.setattr(StockFlowSystemDynamicsEstimator, "pure_step", staticmethod(observed))
    if alias_kind == "repeated-list":
        initial: Any = [10.0, 0.0]
        inflows = initial
    elif alias_kind == "repeated-array":
        initial = np.asarray([10.0, 0.0], dtype=np.float64)
        inflows = initial
    else:
        backing = np.asarray([10.0, 0.0, 0.0], dtype=np.float64)
        initial, inflows = backing[:2], backing[1:]
        assert initial is not inflows
        assert np.shares_memory(initial, inflows)
    request = _native_stockflow_write_request(
        contour,
        left_target="exogenous_inflows.0",
        right_target="exogenous_inflows.1",
        extra_state={"initial_stocks": initial, "exogenous_inflows": inflows},
    )
    live_state = (
        request.engine_plan[0].coupled_state
        if contour == "registry_coupled_state"
        else request.engine_plan[0].system_dynamics_state
    )
    assert live_state["initial_stocks"] is initial
    assert live_state["exogenous_inflows"] is inflows

    result = JointSimulationHorizonController().run(request)

    assert result.engine_decisions[0].decision == "unsupported"
    assert result.engine_decisions[0].reason == "n5_plan_mutable_alias_unsupported"
    assert result.engine_decisions[0].blockers == ("n5_plan_mutable_alias_unsupported",)
    assert result.trajectories == ()
    assert result.physical_work_observations == ()
    assert result.diagnostics["engine_run_claimed"] is False
    assert calls == []


@pytest.mark.parametrize(
    "contour", ["system_dynamics", "registry_system_state", "registry_coupled_state"]
)
def test_native_adapters_accept_distinct_equal_arrays_without_cross_slot_mutation(
    monkeypatch: pytest.MonkeyPatch,
    contour: _StockFlowContour,
) -> None:
    """Equal independent arrays stay usable and writes affect only the target slot."""
    original = StockFlowSystemDynamicsEstimator.pure_step
    calls: list[dict[str, Any]] = []

    def observed(state: Any, params: Any) -> dict[str, Any]:
        calls.append(deepcopy(state))
        return original(state, params)

    monkeypatch.setattr(StockFlowSystemDynamicsEstimator, "pure_step", staticmethod(observed))
    initial = np.asarray([10.0, 0.0], dtype=np.float64)
    inflows = np.asarray([10.0, 0.0], dtype=np.float64)
    assert initial is not inflows
    assert np.array_equal(initial, inflows)
    assert not np.shares_memory(initial, inflows)
    request = _native_stockflow_write_request(
        contour,
        left_target="exogenous_inflows.0",
        right_target="exogenous_inflows.1",
        extra_state={"initial_stocks": initial, "exogenous_inflows": inflows},
    )

    result = JointSimulationHorizonController().run(request)

    assert result.engine_decisions[0].decision == "selected"
    assert calls
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert [point.outcomes["stock0"] for point in joint.points] == [10.0, 11.0, 12.0]
    assert np.array_equal(calls[-1]["initial_stocks"], [10.0, 0.0])
    assert np.array_equal(calls[-1]["exogenous_inflows"], [1.0, 2.0])
    assert not np.shares_memory(calls[-1]["initial_stocks"], calls[-1]["exogenous_inflows"])
    assert np.array_equal(initial, [10.0, 0.0])
    assert np.array_equal(inflows, [10.0, 0.0])


@pytest.mark.parametrize(
    "contour", ["system_dynamics", "registry_system_state", "registry_coupled_state"]
)
@pytest.mark.parametrize(("left_index", "right_index"), [("0", "00"), ("0", "+0"), ("-1", "1")])
@pytest.mark.parametrize("array_state", [False, True], ids=("list", "ndarray"))
@pytest.mark.parametrize("reverse", [False, True], ids=("left-right", "right-left"))
def test_native_adapters_refuse_resolved_index_alias_conflict_before_producer(
    monkeypatch: pytest.MonkeyPatch,
    contour: _StockFlowContour,
    left_index: str,
    right_index: str,
    array_state: bool,
    reverse: bool,
) -> None:
    """The same bounded element conflicts regardless of index spelling or order."""
    original = StockFlowSystemDynamicsEstimator.pure_step
    calls: list[dict[str, Any]] = []

    def observed(state: Any, params: Any) -> dict[str, Any]:
        calls.append(deepcopy(state))
        return original(state, params)

    monkeypatch.setattr(StockFlowSystemDynamicsEstimator, "pure_step", staticmethod(observed))
    request = _native_stockflow_write_request(
        contour,
        left_target=f"exogenous_inflows.{left_index}",
        right_target=f"exogenous_inflows.{right_index}",
        array_state=array_state,
        reverse=reverse,
    )

    result = JointSimulationHorizonController().run(request)

    _assert_assignment_conflict_refusal(result, objective_ref=request.engine_plan[0].objective_ref)
    assert calls == []


@pytest.mark.parametrize(
    "contour", ["system_dynamics", "registry_system_state", "registry_coupled_state"]
)
@pytest.mark.parametrize("right_index", ["00", "+0"])
def test_native_adapters_equal_alias_writes_are_applied_once_in_both_orders(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    contour: _StockFlowContour,
    right_index: str,
) -> None:
    """Compatible aliases do not add twice or stop legitimate numerical work."""
    original = StockFlowSystemDynamicsEstimator.pure_step
    calls: list[dict[str, Any]] = []

    def observed(state: Any, params: Any) -> dict[str, Any]:
        calls.append(deepcopy(state))
        return original(state, params)

    monkeypatch.setattr(StockFlowSystemDynamicsEstimator, "pure_step", staticmethod(observed))
    outcomes = []
    for reverse in (False, True):
        request = _native_stockflow_write_request(
            contour,
            left_target="exogenous_inflows.0",
            right_target=f"exogenous_inflows.{right_index}",
            right_value=1.0,
            reverse=reverse,
        )
        result = JointSimulationHorizonController().run(request)
        restored = _persist_and_read_result(result, tmp_path)
        ids = tuple(atom.intervention_id for atom in request.intervention_atoms)
        joint = restored.trajectory_for("joint", ids)
        values = [point.outcomes["stock0"] for point in joint.points]
        assert values == [10.0, 11.0, 12.0]
        outcomes.append(values)
    assert outcomes[0] == outcomes[1]
    assert calls
    assert all(list(state["exogenous_inflows"]) == [1.0, 0.0] for state in calls)


@pytest.mark.parametrize(
    "contour", ["system_dynamics", "registry_system_state", "registry_coupled_state"]
)
def test_native_adapters_keep_distinct_mapping_keys_and_distinct_indices(
    monkeypatch: pytest.MonkeyPatch,
    contour: _StockFlowContour,
) -> None:
    """Mapping key identity is preserved while list indexing remains numerical."""
    original = StockFlowSystemDynamicsEstimator.pure_step
    calls: list[dict[str, Any]] = []

    def observed(state: Any, params: Any) -> dict[str, Any]:
        calls.append(deepcopy(state))
        return original(state, params)

    monkeypatch.setattr(StockFlowSystemDynamicsEstimator, "pure_step", staticmethod(observed))
    for left, right, extra in (
        ("probe.0", "probe.00", {"probe": {"0": 0.0, "00": 0.0}}),
        ("exogenous_inflows.0", "exogenous_inflows.1", {}),
    ):
        joint_values = []
        for reverse in (False, True):
            request = _native_stockflow_write_request(
                contour,
                left_target=left,
                right_target=right,
                extra_state=extra,
                reverse=reverse,
            )
            result = JointSimulationHorizonController().run(request)
            ids = tuple(atom.intervention_id for atom in request.intervention_atoms)
            joint = result.trajectory_for("joint", ids)
            joint_values.append([point.outcomes["stock0"] for point in joint.points])
            if extra:
                assert calls[-1]["probe"] == {"0": 1.0, "00": 2.0}
            else:
                assert list(calls[-1]["exogenous_inflows"]) == [1.0, 2.0]
        assert joint_values[0] == joint_values[1]
        assert joint_values[0] == ([10.0, 10.0, 10.0] if extra else [10.0, 11.0, 12.0])


@pytest.mark.parametrize(
    "contour", ["system_dynamics", "registry_system_state", "registry_coupled_state"]
)
@pytest.mark.parametrize("reverse", [False, True], ids=("left-right", "right-left"))
def test_native_adapters_refuse_container_prefix_writes_before_producer(
    monkeypatch: pytest.MonkeyPatch,
    contour: _StockFlowContour,
    reverse: bool,
) -> None:
    """Replacing a container conflicts with writing one of its descendants."""
    original = StockFlowSystemDynamicsEstimator.pure_step
    calls = []

    def observed(state: Any, params: Any) -> dict[str, Any]:
        calls.append(deepcopy(state))
        return original(state, params)

    monkeypatch.setattr(StockFlowSystemDynamicsEstimator, "pure_step", staticmethod(observed))
    request = _native_stockflow_write_request(
        contour,
        left_target="exogenous_inflows",
        right_target="exogenous_inflows.0",
        reverse=reverse,
    )
    result = JointSimulationHorizonController().run(request)
    _assert_assignment_conflict_refusal(result, objective_ref=request.engine_plan[0].objective_ref)
    assert calls == []


@pytest.mark.parametrize(
    "contour", ["system_dynamics", "registry_system_state", "registry_coupled_state"]
)
@pytest.mark.parametrize(
    "value", [0.5, 1e100, 1.0], ids=("lossy-fraction", "overflowing-integer", "exact-integer")
)
def test_native_adapters_reconcile_assignment_after_integer_array_write(
    monkeypatch: pytest.MonkeyPatch,
    contour: _StockFlowContour,
    value: float,
) -> None:
    """A numeric assignment must survive the receiver's actual dtype conversion."""
    original = StockFlowSystemDynamicsEstimator.pure_step
    calls: list[dict[str, Any]] = []

    def observed(state: Any, params: Any) -> dict[str, Any]:
        calls.append(deepcopy(state))
        return original(state, params)

    monkeypatch.setattr(StockFlowSystemDynamicsEstimator, "pure_step", staticmethod(observed))
    request = _native_stockflow_write_request(
        contour,
        left_target="initial_stocks.0",
        right_target="exogenous_inflows.1",
        left_value=value,
        extra_state={"initial_stocks": np.asarray([10, 0], dtype=np.int64)},
    )

    result = JointSimulationHorizonController().run(request)

    if value != 1.0:
        assert result.engine_decisions[0].decision == "unsupported"
        assert result.engine_decisions[0].reason == "intervention_assignment_lossy"
        assert result.engine_decisions[0].blockers == ("intervention_assignment_lossy",)
        assert result.trajectories == ()
        assert result.diagnostics["engine_run_claimed"] is False
        assert result.receipt.calibration_status == "no_run"
        assert calls == []
    else:
        assert result.engine_decisions[0].decision == "selected"
        assert calls
        assert all(state["initial_stocks"].dtype == np.dtype("int64") for state in calls)
        joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
        assert joint.points[0].outcomes["stock0"] == 1.0
        assert calls[-1]["initial_stocks"][0] == 1


@pytest.mark.parametrize(
    "contour", ["system_dynamics", "registry_system_state", "registry_coupled_state"]
)
@pytest.mark.parametrize(
    "target",
    ["exogenous_inflows.2", "exogenous_inflows.-3", "exogenous_inflows.invalid", "missing.0"],
)
def test_native_adapters_refuse_unresolved_or_out_of_bounds_target_before_producer(
    monkeypatch: pytest.MonkeyPatch,
    contour: _StockFlowContour,
    target: str,
) -> None:
    """An unresolved address has an explicit refusal before any numerical call."""
    original = StockFlowSystemDynamicsEstimator.pure_step
    calls = []

    def observed(state: Any, params: Any) -> dict[str, Any]:
        calls.append(deepcopy(state))
        return original(state, params)

    monkeypatch.setattr(StockFlowSystemDynamicsEstimator, "pure_step", staticmethod(observed))
    request = _native_stockflow_write_request(
        contour,
        left_target=target,
        right_target="exogenous_inflows.1",
    )

    result = JointSimulationHorizonController().run(request)

    # Registry plans with ``system_dynamics_state`` are intentionally routed
    # through the canonical system-dynamics state resolver by
    # ``_method_state_for_subset``. The coupled-state registry route owns its
    # separate method-registry refusal.
    expected_code = (
        "method_registry_intervention_binding_missing"
        if contour == "registry_coupled_state"
        else "system_dynamics_intervention_binding_missing"
    )
    assert result.engine_decisions[0].decision == "unsupported"
    assert result.engine_decisions[0].reason == expected_code
    assert result.engine_decisions[0].blockers == (expected_code,)
    assert result.trajectories == ()
    assert result.diagnostics["engine_run_claimed"] is False
    assert calls == []


@pytest.mark.parametrize(
    ("invalid_output", "expected_code", "expected_context"),
    [
        pytest.param(
            {"counterfactual_result": {"world_summaries": []}},
            "ncm_world_summaries_missing",
            {"slot": "counterfactual_result.world_summaries"},
            id="missing-envelope",
        ),
        pytest.param(
            {"counterfactual_result": {"world_summaries": [{"firm_survival": {"mean": np.nan}}]}},
            "ncm_outcome_non_finite",
            {"outcome": "firm_survival"},
            id="nonfinite-selected-outcome",
        ),
    ],
)
def test_native_ncm_partial_failure_retains_exact_cause_after_fresh_read(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    invalid_output: dict[str, Any],
    expected_code: str,
    expected_context: dict[str, str],
) -> None:
    """A corrupted second real invocation retains its predecessor and stops work."""
    original = NCMEngineMethod.pure_step
    calls: list[dict[str, Any]] = []

    def corrupt_second_output(state: Any, params: Any) -> dict[str, Any]:
        output = original(state, params)
        calls.append(deepcopy(output))
        return deepcopy(invalid_output) if len(calls) == 2 else output

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(corrupt_second_output))
    result = JointSimulationHorizonController().run(_single_step_ncm_request())
    restored = _persist_and_read_result(result, tmp_path)

    assert len(calls) == 2
    _assert_retained_failure(
        restored,
        expected_code=expected_code,
        expected_context=expected_context,
        completed_roles=(("individual", ("income_subsidy",)),),
    )
    expected_value = calls[0]["counterfactual_result"]["world_summaries"][0]["firm_survival"][
        "mean"
    ]
    assert restored.trajectories[0].points[0].outcomes == {"firm_survival": expected_value}
    assert restored.trajectories[0].points[0].outcomes["firm_survival"] != 0.0
    assert restored.diagnostics["physical_work_units"] == 2
    assert restored.diagnostics["interaction_evidence_issues"]


def test_unknown_native_failure_does_not_invent_typed_cause_or_persist_secret(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Exception prose cannot impersonate a whitelisted structured cause."""
    original = NCMEngineMethod.pure_step
    calls = 0
    private_marker = "private-output-do-not-persist"

    def fail_second(state: Any, params: Any) -> dict[str, Any]:
        nonlocal calls
        output = original(state, params)
        calls += 1
        if calls == 2:
            raise ValueError(f"ncm_outcome_non_finite: {private_marker}")
        return output

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fail_second))
    result = JointSimulationHorizonController().run(_single_step_ncm_request())
    restored = _persist_and_read_result(result, tmp_path)

    assert calls == 2
    assert [item.status for item in restored.physical_work_observations] == ["completed", "failed"]
    assert len(restored.trajectories) == 1
    failure = restored.physical_work_observations[-1]
    assert failure.error_type == "ValueError"
    assert failure.error_code is None
    assert failure.error_context is None
    assert "error_code" not in failure.model_dump(mode="json")
    assert "error_context" not in failure.model_dump(mode="json")
    assert private_marker not in json.dumps(restored.model_dump(mode="json"))


def test_native_ncm_explicit_zero_remains_observed_after_fresh_read(tmp_path: Path) -> None:
    """A constant-zero structural equation remains a measured simulation zero."""
    request = _single_step_ncm_request()
    plan = request.engine_plan[0]
    assert plan.ncm_spec is not None
    equations = list(plan.ncm_spec.structural_equations)
    equations[-1] = equations[-1].model_copy(
        update={"parents": [], "equation_params": {"noise_expression": "0.0"}}
    )
    plan = plan.model_copy(
        update={"ncm_spec": plan.ncm_spec.model_copy(update={"structural_equations": equations})}
    )
    request = request.model_copy(
        update={
            "engine_plan": (plan,),
            "baseline_state": {"firm_survival": 0.0},
            "evidence_state": {},
        }
    )

    result = JointSimulationHorizonController().run(request)
    restored = _persist_and_read_result(result, tmp_path)
    joint = restored.trajectory_for("joint", ("income_subsidy", "balance_grant"))

    assert joint.points[0].outcomes == {"firm_survival": 0.0}
    assert joint.points[0].effect == {"firm_survival": 0.0}
    assert all(item.status == "completed" for item in restored.physical_work_observations)
    assert "physical_work_interruption" not in restored.diagnostics


def test_canonical_scm_graph_plan_runs_native_ncm_and_fresh_bound_consumer(
    tmp_path: Path,
) -> None:
    """Read-only canonical graph containers do not invalidate a real selected NCM plan."""
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel
    from polisyos.ir.analytics.ncm import NCMSpec, candidate_ncm_spec_from_declaration
    from polisyos.ir.analytics.structural_causal_model import StructuralCausalModelSpec
    from tests._helpers.controlled_candidate_profile import _ControlledCandidateNCMParameters

    # Use the same declaration fixture and canonical NCM producer as served N4-to-N5.
    parameters = _ControlledCandidateNCMParameters(
        target_world_slot="agents.income",
        outcome_variable="firm_survival",
        target_baseline=0.0,
        outcome_baseline=1.0,
        outcome_per_target_unit=2.0,
        outcome_noise_stddev=0.0,
    )
    ncm = candidate_ncm_spec_from_declaration(parameters)
    assert isinstance(ncm, NCMSpec)
    assert isinstance(ncm.scm_spec, StructuralCausalModelSpec)
    graph = ncm.scm_spec.graph
    assert isinstance(graph, CausalGraphModel)
    assert tuple(graph.nodes) == ("agents.income", "firm_survival")
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert isinstance(edge, CausalEdge)
    assert (edge.src, edge.dst) == ("agents.income", "firm_survival")
    with pytest.raises(TypeError, match="published graph containers are immutable"):
        graph.nodes.append("unadmitted-node")
    with pytest.raises(TypeError, match="published graph containers are immutable"):
        edge.metadata["unadmitted-field"] = True

    base = _single_step_ncm_request()
    plan = EnginePlan(
        engine_kind="ncm_parallel_worlds",
        objective_ref="objective://sim02-canonical-scm-graph",
        ncm_spec=ncm,
        variable_map={"agents.income": "agents.income", "firm_survival": "firm_survival"},
        eligibility_conditions=("acyclic", "counterfactual_do_worlds"),
    )
    request = base.model_copy(
        update={
            "intervention_atoms": base.intervention_atoms[:1],
            "engine_plan": (plan,),
            "baseline_state": {"firm_survival": 1.0},
            "evidence_state": {"agents.income": 0.0, "firm_survival": 1.0},
        }
    )
    assert joint_simulation_horizon_module._physical_plan_identity(plan) == plan.model_dump(
        mode="json"
    )

    produced = JointSimulationHorizonController().run(request)
    restored = _persist_and_read_result(produced, tmp_path, expected_request=request)

    assert restored.engine_decisions[0].decision == "selected"
    assert restored.engine_decisions[0].method_fqn == NCMEngineMethod.signature.fqn
    assert len(restored.physical_work_observations) == 1
    assert restored.physical_work_observations[0].status == "completed"
    assert restored.physical_work_observations[0].error_type is None
    assert "physical_work_interruption" not in restored.diagnostics
    joint = restored.trajectory_for("joint", ("income_subsidy",))
    assert joint.points[0].outcomes == {"firm_survival": 3.0}
    assert joint.points[0].effect == {"firm_survival": 2.0}
    assert restored.trajectory_for("individual", ("income_subsidy",)).points == joint.points
    assert joint.diagnostics["physical_run_reused"] is True
    assert restored.world_credal_state_after == restored.world_credal_state_before
    assert (
        "simulation_only_k_sim_not_world_evidence"
        in (restored.promotion_ready_value_packet["authority_blockers"])
    )


@pytest.mark.parametrize("contour", ["system_dynamics", "registry_system_state"])
@pytest.mark.parametrize(
    "retained_source_rows", [1, 2, 3, 4], ids=("short-one", "short-two", "full", "surplus")
)
def test_native_temporal_rows_preserve_roles_coordinates_and_prefix_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    contour: _StockFlowContour,
    retained_source_rows: int,
) -> None:
    """A declared prefix projects actual stock rows without final-value padding."""
    original = StockFlowSystemDynamicsEstimator.pure_step

    def bounded_output(state: Any, params: Any) -> dict[str, Any]:
        numerical_params = {**params, "n_steps": max(2, retained_source_rows - 1)}
        output = original(state, numerical_params)
        output["result"]["trajectory"] = output["result"]["trajectory"][:retained_source_rows]
        return output

    monkeypatch.setattr(StockFlowSystemDynamicsEstimator, "pure_step", staticmethod(bounded_output))
    request = _native_stockflow_write_request(
        contour,
        left_target="exogenous_inflows.0",
        right_target="exogenous_inflows.1",
        right_value=1.0,
    ).model_copy(update={"horizon": HorizonSpec(start=7, end=11, step=2)})
    plan = request.engine_plan[0].model_copy(update={"system_dynamics_params": {"dt": 2.0}})
    request = request.model_copy(update={"engine_plan": (plan,)})

    result = JointSimulationHorizonController().run(request)
    restored = _persist_and_read_result(result, tmp_path)
    joint = restored.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    count = min(retained_source_rows, 3)

    assert [point.step for point in joint.points] == [7, 9, 11][:count]
    assert [point.outcomes["stock0"] for point in joint.points] == [10.0, 12.0, 14.0][:count]
    assert [point.engine_state["row_role"] for point in joint.points] == [
        "initial",
        "transition",
        "transition",
    ][:count]
    assert [point.engine_state["source_coordinate"] for point in joint.points] == [0.0, 2.0, 4.0][
        :count
    ]
    assert all(np.isfinite(point.engine_state["source_coordinate"]) for point in joint.points)
    assert all("mass_balance" not in point.engine_state for point in joint.points)
    assert joint.diagnostics["row_contract"] == "initial_then_transitions.v1"
    assert joint.diagnostics["source_row_count"] == retained_source_rows
    assert joint.diagnostics["retained_row_count"] == count
    assert joint.diagnostics["excluded_source_rows"] == max(0, retained_source_rows - 3)
    assert joint.diagnostics["slice_basis"] == "declared_prefix"
    assert joint.diagnostics["coverage_status"] == ("complete" if count == 3 else "partial")
    assert list(joint.diagnostics["covered_steps"]) == [7, 9, 11][:count]
    assert joint.diagnostics["hold_last"] is False
    assert joint.diagnostics["time_alignment_status"] == "not_established"
    assert restored.diagnostics["physical_time_basis_status"] == "not_established"


@pytest.mark.parametrize("contour", ["system_dynamics", "registry_system_state"])
def test_native_final_summary_binds_only_reconciled_full_source_endpoint(
    tmp_path: Path,
    contour: _StockFlowContour,
) -> None:
    """The final mass summary has its own recomputed terminal source coordinate."""
    request = _native_stockflow_write_request(
        contour,
        left_target="exogenous_inflows.0",
        right_target="exogenous_inflows.1",
        right_value=1.0,
    ).model_copy(update={"horizon": HorizonSpec(start=7, end=11, step=2)})
    plan = request.engine_plan[0].model_copy(update={"system_dynamics_params": {"dt": 2.0}})
    request = request.model_copy(update={"engine_plan": (plan,)})

    produced = JointSimulationHorizonController().run(request)
    restored = _persist_and_read_result(produced, tmp_path)
    joint = restored.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    summary = joint.diagnostics["final_summary"]

    # Two stocks each receive one unit per computational time unit for four units.
    assert summary == {
        "role": "producer_final_summary",
        "mass_balance": 8.0,
        "row_binding_status": "recomputed_from_producer_rows",
        "source_row_index": 2,
        "source_coordinate": 4.0,
    }
    assert joint.points[-1].step == 11
    assert joint.points[-1].engine_state["source_coordinate"] == 4.0
    assert all("mass_balance" not in point.engine_state for point in joint.points)
    assert all("mass_balance" not in point.outcomes for point in joint.points)
    assert joint.diagnostics["time_alignment_status"] == "not_established"


@pytest.mark.parametrize("contour", ["system_dynamics", "registry_system_state"])
@pytest.mark.parametrize(
    ("source_rows", "reported_mass_balance"),
    [
        pytest.param(1, 8.0, id="truncated-to-initial"),
        pytest.param(2, 8.0, id="truncated-after-transition"),
        pytest.param(4, 12.0, id="surplus-source-row"),
        pytest.param(3, 9.0, id="unreconciled-full-row-summary"),
    ],
)
def test_native_final_summary_retains_unbound_value_without_claiming_prefix_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    contour: _StockFlowContour,
    source_rows: int,
    reported_mass_balance: float,
) -> None:
    """A final scalar does not acquire an endpoint merely from returned row count."""
    original = StockFlowSystemDynamicsEstimator.pure_step

    def altered_output(state: Any, params: Any) -> dict[str, Any]:
        actual_params = {**params, "n_steps": max(2, source_rows - 1)}
        output = original(state, actual_params)
        output["result"]["trajectory"] = output["result"]["trajectory"][:source_rows]
        if source_rows == 3:
            output["result"]["mass_balance"] = reported_mass_balance
        return output

    monkeypatch.setattr(StockFlowSystemDynamicsEstimator, "pure_step", staticmethod(altered_output))
    request = _native_stockflow_write_request(
        contour,
        left_target="exogenous_inflows.0",
        right_target="exogenous_inflows.1",
        right_value=1.0,
    ).model_copy(update={"horizon": HorizonSpec(start=7, end=11, step=2)})
    plan = request.engine_plan[0].model_copy(update={"system_dynamics_params": {"dt": 2.0}})
    request = request.model_copy(update={"engine_plan": (plan,)})

    produced = JointSimulationHorizonController().run(request)
    restored = _persist_and_read_result(produced, tmp_path)
    joint = restored.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    summary = joint.diagnostics["final_summary"]

    assert summary == {
        "role": "producer_final_summary",
        "mass_balance": reported_mass_balance,
        "row_binding_status": "not_established",
    }
    assert "source_row_index" not in summary
    assert "source_coordinate" not in summary
    assert joint.diagnostics["source_row_count"] == source_rows
    assert [point.outcomes["stock0"] for point in joint.points] == [10.0, 12.0, 14.0][
        : min(source_rows, 3)
    ]
    assert all("mass_balance" not in point.engine_state for point in joint.points)
    assert all("mass_balance" not in point.outcomes for point in joint.points)


@pytest.mark.parametrize("contour", ["system_dynamics", "registry_system_state"])
def test_native_single_point_retains_initial_stock_and_declares_excluded_transition(
    tmp_path: Path,
    contour: _StockFlowContour,
) -> None:
    """A one-point request cannot relabel the producer's later value as initial."""
    request = _native_stockflow_write_request(
        contour,
        left_target="exogenous_inflows.0",
        right_target="exogenous_inflows.1",
    ).model_copy(update={"horizon": HorizonSpec(start=9, end=9, step=1)})

    result = JointSimulationHorizonController().run(request)
    restored = _persist_and_read_result(result, tmp_path)
    joint = restored.trajectory_for("joint", ("income_subsidy", "balance_grant"))

    assert [point.step for point in joint.points] == [9]
    assert joint.points[0].outcomes == {"stock0": 10.0}
    assert joint.points[0].engine_state["row_role"] == "initial"
    assert joint.points[0].engine_state["source_coordinate"] == 0.0
    assert "mass_balance" not in joint.points[0].engine_state
    assert joint.diagnostics["source_row_count"] == 2
    assert joint.diagnostics["retained_row_count"] == 1
    assert joint.diagnostics["excluded_source_rows"] == 1
    assert joint.diagnostics["slice_basis"] == "declared_prefix"


def _native_program_population_request(
    tmp_path: Path,
    aggregation: dict[str, Any] | None,
) -> JointSimulationRequest:
    """Produce an actual two-agent population and a separate scalar balance."""
    plan = _program_graph_plan(tmp_path)
    declaration = EnginePlan(
        engine_kind="program_graph",
        objective_ref=plan.objective_ref,
        outcome_aggregations={} if aggregation is None else {"mean_income": aggregation},
    )
    plan = plan.model_copy(
        update={
            "variable_map": {"mean_income": "agents.income", "balance": "government_balance"},
            "outcome_aggregations": declaration.outcome_aggregations,
        }
    )
    return _request().model_copy(
        update={
            "engine_plan": (plan,),
            "horizon": HorizonSpec(start=0, end=0, step=1),
            "selected_outcomes": ("mean_income", "balance"),
            "baseline_state": {"mean_income": 1500.0, "balance": 0.0},
        }
    )


@pytest.mark.parametrize(
    ("aggregation", "expected_value", "expected_weight_sum"),
    [
        pytest.param(
            {"method": "mean", "unit": "usd"},
            1650.0,
            2.0,
            id="population-mean",
        ),
        pytest.param(
            {"method": "weighted_mean", "unit": "usd", "weights": (1.0, 3.0)},
            1925.0,
            4.0,
            id="weighted-population-mean",
        ),
    ],
)
def test_native_program_population_aggregation_declares_basis_and_preserves_scalar(
    tmp_path: Path,
    aggregation: dict[str, Any],
    expected_value: float,
    expected_weight_sum: float,
) -> None:
    """A real vector has a declared estimand; a scalar needs no invented averaging."""
    request = _native_program_population_request(tmp_path, aggregation)
    results = []
    for reverse in (False, True):
        reordered = request.model_copy(
            update={
                "intervention_atoms": (
                    tuple(reversed(request.intervention_atoms))
                    if reverse
                    else request.intervention_atoms
                )
            }
        )
        produced = JointSimulationHorizonController().run(reordered)
        restored = _persist_and_read_result(produced, tmp_path)
        ids = tuple(atom.intervention_id for atom in reordered.intervention_atoms)
        point = restored.trajectory_for("joint", ids).points[0]
        assert point.outcomes["mean_income"] == pytest.approx(expected_value, abs=1e-5)
        assert point.effect["mean_income"] == pytest.approx(expected_value - 1500.0, abs=1e-5)
        assert point.outcomes["balance"] == pytest.approx(-300.0, abs=1e-5)
        basis = point.engine_state["outcome_aggregation_basis"]["mean_income"]
        assert basis["method"] == aggregation["method"]
        assert basis["unit"] == "usd"
        assert basis["unit_binding_status"] == "matched_producer_slot"
        assert basis["unit_slot_id"] == "agents.income"
        assert basis["element_count"] == 2
        assert basis["effective_weight_sum"] == expected_weight_sum
        results.append(point.outcomes)
    assert results[0] == results[1]


@pytest.mark.parametrize(
    ("aggregation", "expected_code"),
    [
        pytest.param(
            None, "program_graph_outcome_aggregation_not_established", id="undeclared-vector"
        ),
        pytest.param(
            {"method": "weighted_mean", "unit": "usd", "weights": (1.0,)},
            "program_graph_outcome_aggregation_invalid",
            id="wrong-weight-denominator",
        ),
        pytest.param(
            {"method": "weighted_mean", "unit": "usd", "weights": (0.0, 0.0)},
            "program_graph_outcome_aggregation_invalid",
            id="zero-weight-denominator",
        ),
        pytest.param(
            {"method": "mean", "unit": "eur"},
            "program_graph_outcome_aggregation_unit_mismatch",
            id="unit-mismatch-is-not-conversion",
        ),
    ],
)
def test_native_program_population_refuses_ambiguous_or_invalid_aggregation(
    tmp_path: Path,
    aggregation: dict[str, Any] | None,
    expected_code: str,
) -> None:
    """Actual graph artifacts cannot turn an undeclared vector into a scalar effect."""
    request = _native_program_population_request(tmp_path, aggregation)
    produced = JointSimulationHorizonController().run(request)
    restored = _persist_and_read_result(produced, tmp_path)
    _assert_retained_failure(
        restored,
        expected_code=expected_code,
        expected_context={"outcome": "mean_income"},
    )


@pytest.mark.parametrize(
    ("population", "expected_code"),
    [
        pytest.param(
            [[1.0, 3.0], [5.0, 7.0]],
            "program_graph_outcome_shape_unsupported",
            id="matrix-not-mean-four",
        ),
        pytest.param([], "program_graph_outcome_missing", id="empty-population"),
        pytest.param([1.0, np.nan], "program_graph_outcome_non_finite", id="nonfinite-member"),
        pytest.param([1.0, None], "program_graph_outcome_non_numeric", id="missing-member"),
    ],
)
def test_declared_population_aggregation_still_checks_shape_presence_and_finiteness(
    population: list[Any],
    expected_code: str,
) -> None:
    """A declaration supplies meaning and does not waive the actual value census."""
    plan = EnginePlan(
        engine_kind="program_graph",
        objective_ref="objective://sim02-population-output-guard",
        outcome_aggregations={"population": {"method": "mean", "unit": "usd"}},
    )

    with pytest.raises(JointSimulationControllerError) as raised:
        joint_simulation_horizon_module._program_graph_outcomes(
            {"population": population}, ("population",), plan
        )

    assert raised.value.code == expected_code


def test_selected_weighted_mean_avoids_intermediate_overflow_for_finite_population() -> None:
    """Normalization must preserve a finite aggregate when an unscaled dot product overflows."""
    plan = EnginePlan(
        engine_kind="program_graph",
        objective_ref="objective://sim02-large-population-aggregate",
        outcome_aggregations={
            "population": {"method": "weighted_mean", "unit": "usd", "weights": (1.0, 1.0)}
        },
    )
    basis: dict[str, Any] = {}

    value = joint_simulation_horizon_module._selected_outcome_value(
        [1e308, 1e308],
        outcome="population",
        engine_kind="program_graph",
        aggregation=plan.outcome_aggregations["population"],
        aggregation_basis=basis,
    )

    assert np.isfinite(value)
    assert value == 1e308
    assert basis["population"]["method"] == "weighted_mean"
    assert basis["population"]["element_count"] == 2
    assert basis["population"]["effective_weight_sum"] == 2.0
