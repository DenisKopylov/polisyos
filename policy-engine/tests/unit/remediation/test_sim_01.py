"""Behavioral witnesses for SIM-01 engine selection and execution binding."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast, get_args

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.foundry.methods.catalog.simulation.coupled import CoupledPolicySimulationEstimator
from polisyos.runtime.quality.generation_cycle import _joint_simulation_port_outcome
from polisyos.runtime.quality.joint_simulation_horizon import (
    EngineDecision,
    EngineKind,
    EnginePlan,
    HorizonSpec,
    JointSimulationControllerError,
    JointSimulationHorizonController,
    JointSimulationRequest,
    JointSimulationResult,
    SimulationTrajectory,
    TemporalCapability,
    TrajectoryPoint,
    build_content_bound_simulation_receipt,
)
from polisyos.runtime.quality.recursive_generation_cycle import _joint_simulation_is_unsupported
from tests.unit.runtime.quality.test_joint_simulation_horizon import (
    _atom,
    _coupling_graph,
    _request,
)


def _coupled_plan() -> EnginePlan:
    return EnginePlan(
        engine_kind="coupled_des_abm",
        objective_ref="objective://claims-queue-fallback",
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
    )


def _single_step_request():
    """Use one point when exercising the static NCM path."""
    return _request().model_copy(update={"horizon": HorizonSpec(start=0, end=0, step=1)})


def _coupled_request(
    *plans: EnginePlan,
    policy_domain: str = "unemployment_claims_benefit",
) -> JointSimulationRequest:
    """Exercise the native queue engine on one transition and the same atom scope."""

    return _request(policy_domain=policy_domain).model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=1, step=1),
            "coupling_graph": _coupling_graph("shared_resource"),
            "selected_outcomes": ("final_queue_length",),
            "baseline_state": {"final_queue_length": 0.0},
            "engine_plan": plans or (_coupled_plan(),),
        }
    )


def _record_native_coupled_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, Any]]:
    """Count actual method calls without replacing the numerical producer."""

    original = CoupledPolicySimulationEstimator.pure_step
    calls: list[dict[str, Any]] = []

    def recording_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        calls.append({"state": dict(state), "params": dict(params)})
        return original(state, params)

    monkeypatch.setattr(CoupledPolicySimulationEstimator, "pure_step", staticmethod(recording_step))
    return calls


def _trajectory(
    *,
    engine_kind: str = "ncm_parallel_worlds",
    method_fqn: str = "polisyos.foreign.engine@9.9.9",
    objective_ref: str = "objective://foreign-plan",
    physical_run_ref: str = "sha256:" + "f" * 64,
) -> SimulationTrajectory:
    return SimulationTrajectory(
        run_level="joint",
        atom_ids=("income_subsidy", "balance_grant"),
        engine_kind=engine_kind,  # type: ignore[arg-type]
        method_fqn=method_fqn,
        objective_ref=objective_ref,
        points=(
            TrajectoryPoint(
                step=0,
                outcomes={"firm_survival": 2.0},
                effect={"firm_survival": 1.0},
            ),
        ),
        diagnostics={"physical_run_ref": physical_run_ref},
    )


def test_unsupported_first_engine_falls_back_to_supported_second() -> None:
    """B07: coupling rejection must continue selection through the plan list."""

    request = _request(policy_domain="unemployment_claims_benefit").model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=1, step=1),
            "coupling_graph": _coupling_graph("shared_resource"),
            "selected_outcomes": ("final_queue_length",),
            "baseline_state": {"final_queue_length": 0.0},
            "engine_plan": (_request().engine_plan[0], _coupled_plan()),
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert [item.decision for item in result.engine_decisions] == ["unsupported", "selected"]
    assert result.engine_decisions[0].reason == "coupling_composition_gate_unsupported"
    assert result.engine_decisions[1].engine_kind == "coupled_des_abm"
    assert result.engine_decisions[1].decision == "selected"
    assert result.trajectories
    assert all(trajectory.engine_kind == "coupled_des_abm" for trajectory in result.trajectories)
    status, blockers = _joint_simulation_port_outcome(result, request=request)
    assert status == "joint_simulated"
    assert _joint_simulation_is_unsupported(result) is False
    assert "n5_coupling_blocked" not in blockers


def test_fallback_does_not_select_an_engine_without_the_required_coupling() -> None:
    """A same-coupling fallback with no capable engine must remain blocked."""

    base_request = _request(policy_domain="unemployment_claims_benefit")
    first_plan = base_request.engine_plan[0]
    unsupported_fallback = first_plan.model_copy(
        update={"objective_ref": "objective://no-coupled-fallback"}
    )
    request = base_request.model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=1, step=1),
            "coupling_graph": _coupling_graph("shared_resource"),
            "selected_outcomes": ("final_queue_length",),
            "baseline_state": {"final_queue_length": 0.0},
            "engine_plan": (first_plan, unsupported_fallback),
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert [item.decision for item in result.engine_decisions] == ["unsupported", "unsupported"]
    assert [item.reason for item in result.engine_decisions] == [
        "coupling_composition_gate_unsupported",
        "coupling_composition_gate_unsupported",
    ]
    assert not result.trajectories
    status, blockers = _joint_simulation_port_outcome(result)
    assert status == "simulation_blocked"
    assert _joint_simulation_is_unsupported(result) is True
    assert "n5_coupling_blocked" in blockers


@pytest.mark.parametrize(
    "bad_state",
    [
        {},
        {"initial_income": [[1000.0, 600.0, 400.0]]},
        {"initial_income": [1000.0, float("nan"), 400.0]},
    ],
    ids=("missing", "two-dimensional", "nonfinite"),
)
def test_coupled_required_input_rejection_precedes_real_second_plan_execution(
    monkeypatch: pytest.MonkeyPatch,
    bad_state: dict[str, Any],
) -> None:
    """TEST-SIM-01-01: invalid input is local to its plan and spends no physical work."""

    supported = _coupled_plan()
    rejected = supported.model_copy(
        update={
            "objective_ref": "objective://invalid-coupled-input",
            "coupled_state": bad_state,
        }
    )
    request = _coupled_request(rejected, supported)
    calls = _record_native_coupled_calls(monkeypatch)

    result = JointSimulationHorizonController().run(request)

    assert [row.decision for row in result.engine_decisions] == ["unsupported", "selected"]
    first, selected = result.engine_decisions
    assert first.objective_ref == rejected.objective_ref
    assert first.reason != "engine_eligibility_satisfied"
    assert any("initial_income" in blocker for blocker in first.blockers)
    assert selected.objective_ref == supported.objective_ref
    assert selected.engine_kind == "coupled_des_abm"
    assert len(calls) == len(result.physical_work_observations) == 3
    assert all(call["state"] == supported.coupled_state for call in calls)
    assert all(work.status == "completed" for work in result.physical_work_observations)
    assert result.diagnostics["physical_work_units"] == 3
    assert {row.objective_ref for row in result.trajectories} == {supported.objective_ref}
    joint = result.trajectory_for("joint", result.atom_ids)
    # Three active unemployed agents each emit one arrival; service cannot
    # finish at the first arrival instant. This oracle is independent of N5.
    assert [point.outcomes["final_queue_length"] for point in joint.points] == [0.0, 3.0]
    assert joint.points[-1].effect == {"final_queue_length": 3.0}
    status, blockers = _joint_simulation_port_outcome(result, request=request)
    assert status == "joint_simulated"
    assert "selected_plan_execution_binding_missing" not in blockers


def test_all_coupled_required_inputs_bad_preserve_history_without_runner_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TEST-SIM-01-01: no viable required vector means typed no-run, not a failed run."""

    first = _coupled_plan().model_copy(update={"coupled_state": {}})
    second = first.model_copy(
        update={
            "objective_ref": "objective://second-invalid-coupled-input",
            "coupled_state": {"initial_income": [[1.0]]},
        }
    )
    controller = JointSimulationHorizonController()
    runner_lookups: list[None] = []

    def runner_map() -> dict[str, object]:
        runner_lookups.append(None)
        raise AssertionError("all-invalid preflight reached an execution boundary")

    monkeypatch.setattr(controller, "_engine_runners", runner_map)

    result = controller.run(_coupled_request(first, second))

    assert [row.objective_ref for row in result.engine_decisions] == [
        first.objective_ref,
        second.objective_ref,
    ]
    assert [row.decision for row in result.engine_decisions] == ["unsupported", "unsupported"]
    assert all(
        any("initial_income" in blocker for blocker in row.blockers)
        for row in result.engine_decisions
    )
    assert result.receipt.calibration_status == "no_run"
    assert result.receipt.trajectory_count == 0
    assert result.trajectories == ()
    assert result.physical_work_observations == ()
    assert result.diagnostics["engine_run_claimed"] is False
    assert result.diagnostics["physical_work_units"] == 0
    assert runner_lookups == []
    status, _ = _joint_simulation_port_outcome(result)
    assert status == "simulation_blocked"


def test_coupled_optional_defaults_preserve_real_native_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TEST-SIM-01-01: signature presence cannot turn legal optional defaults into gates."""

    defaulted = _coupled_plan().model_copy(
        update={"coupled_state": {"initial_income": [1000.0, 600.0, 400.0]}}
    )
    explicit = defaulted.model_copy(
        update={
            "coupled_state": {
                **defaulted.coupled_state,
                "initial_savings": [0.0, 0.0, 0.0],
                "is_employed": [0.0, 0.0, 0.0],
                "risk_aversion": [0.5, 0.5, 0.5],
            }
        }
    )
    calls = _record_native_coupled_calls(monkeypatch)
    controller = JointSimulationHorizonController()

    default_result = controller.run(_coupled_request(defaulted))
    explicit_result = controller.run(_coupled_request(explicit))

    assert len(calls) == 6
    assert default_result.engine_decisions[0].decision == "selected"
    assert explicit_result.engine_decisions[0].decision == "selected"
    assert [row["state"] for row in calls[:3]] == [defaulted.coupled_state] * 3
    assert [row["state"] for row in calls[3:]] == [explicit.coupled_state] * 3
    for left, right in zip(default_result.trajectories, explicit_result.trajectories, strict=True):
        assert (left.run_level, left.atom_ids) == (right.run_level, right.atom_ids)
        assert [(point.outcomes, point.effect) for point in left.points] == [
            (point.outcomes, point.effect) for point in right.points
        ]
    joint = default_result.trajectory_for("joint", default_result.atom_ids)
    assert joint.points[-1].outcomes == {"final_queue_length": 3.0}


def test_coupled_alternatives_cannot_bypass_wrong_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TEST-SIM-01-01: valid vectors do not override the shared domain admission boundary."""

    first = _coupled_plan()
    second = first.model_copy(update={"objective_ref": "objective://foreign-domain-alternative"})
    calls = _record_native_coupled_calls(monkeypatch)

    result = JointSimulationHorizonController().run(
        _coupled_request(first, second, policy_domain="housing_zoning")
    )

    assert [row.decision for row in result.engine_decisions] == ["unsupported", "unsupported"]
    assert [row.reason for row in result.engine_decisions] == [
        "engine_eligibility_failed",
        "engine_eligibility_failed",
    ]
    assert all(row.blockers == ("policy_domain_mismatch",) for row in result.engine_decisions)
    assert result.trajectories == ()
    assert result.physical_work_observations == ()
    assert calls == []


def test_coupled_alternatives_cannot_bypass_global_budget_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """TEST-SIM-01-01: a rejected first plan cannot restart a shared exhausted budget."""

    from polisyos.scientist.orchestration.engine.producer_budget import ProducerBudgetObserver
    from tests.unit.runtime.quality.test_c49_native_stopping_budget import _producer_owner

    store, binding, state = _producer_owner(tmp_path, cap="0")
    observer = ProducerBudgetObserver(
        settlement_store=store, producer_run_binding=binding, budget_state=state
    )
    supported = _coupled_plan()
    rejected = supported.model_copy(
        update={"objective_ref": "objective://budget-first-invalid", "coupled_state": {}}
    )
    calls = _record_native_coupled_calls(monkeypatch)

    result = JointSimulationHorizonController(producer_budget_observer=observer).run(
        _coupled_request(rejected, supported)
    )

    assert [row.decision for row in result.engine_decisions] == ["unsupported", "selected"]
    assert result.engine_decisions[1].objective_ref == supported.objective_ref
    assert result.diagnostics["physical_work_interruption"] == "n5_current_budget_exhausted"
    assert result.diagnostics["budget_interruption_basis"]["status"] == "configured_limit_only"
    assert result.trajectories == ()
    assert result.physical_work_observations == ()
    assert calls == []
    assert observer.last_checked is None


def test_coupled_alternatives_do_not_retry_after_access_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TEST-SIM-01-01: access denial propagates rather than being a per-plan fallback."""

    from polisyos.core.artifacts.ownership import ArtifactOwnershipError

    first = _coupled_plan()
    second = first.model_copy(update={"objective_ref": "objective://after-access-denial"})
    calls: list[None] = []
    denied = ArtifactOwnershipError("controlled selected-backend access denial")

    def access_denied(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del state, params
        calls.append(None)
        raise denied

    monkeypatch.setattr(CoupledPolicySimulationEstimator, "pure_step", staticmethod(access_denied))
    with pytest.raises(ArtifactOwnershipError) as caught:
        JointSimulationHorizonController().run(_coupled_request(first, second))
    assert caught.value is denied
    assert calls == [None]


@pytest.mark.parametrize("engine_kind", get_args(EngineKind))
@pytest.mark.parametrize(
    ("temporal_capability", "expected_reason", "expected_blocker"),
    [
        (
            "static",
            "static_engine_cannot_ground_dynamic_horizon",
            "static_engine_temporal_capability",
        ),
        (
            "unsupported",
            "engine_temporal_capability_unavailable",
            "engine_temporal_capability_unsupported",
        ),
    ],
)
def test_shared_horizon_admission_rejects_non_multi_period_capability_for_every_engine_kind(
    monkeypatch: pytest.MonkeyPatch,
    engine_kind: EngineKind,
    temporal_capability: str,
    expected_reason: str,
    expected_blocker: str,
) -> None:
    """Every engine kind needs selector evidence of multi-period support."""

    controller = JointSimulationHorizonController()
    plan = (
        _single_step_request()
        .engine_plan[0]
        .model_copy(
            update={
                "engine_kind": cast("EngineKind", engine_kind),
                "eligibility_conditions": (),
            }
        )
    )
    request = _single_step_request().model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=2, step=1),
            "engine_plan": (plan,),
        }
    )

    def static_selector(candidate: EnginePlan) -> EngineDecision:
        return EngineDecision(
            engine_kind=candidate.engine_kind,
            objective_ref=candidate.objective_ref,
            decision="selected",
            method_fqn="test.static-capability",
            equilibrium_semantics="static_SCM",
            temporal_capability=cast("TemporalCapability", temporal_capability),
            output_shape="static_point",
            reason="engine_eligibility_satisfied",
        )

    selectors = dict.fromkeys(get_args(EngineKind), static_selector)
    monkeypatch.setattr(controller, "_engine_selectors", lambda _record: selectors)

    selected = controller._select_engine(request)

    assert selected.decision.decision == "unsupported"
    assert selected.decision.reason == expected_reason
    assert selected.decision.blockers == (expected_blocker,)


def test_unlabeled_static_first_plan_falls_through_to_real_dynamic_engine() -> None:
    """A missing temporal flag cannot make static NCM eligible for a multi-step request."""

    base = _request().model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=2, step=1),
            "selected_outcomes": ("stock0",),
            "baseline_state": {"stock0": 0.0},
        }
    )
    static_plan = base.engine_plan[0].model_copy(
        update={"eligibility_conditions": ("acyclic", "counterfactual_do_worlds")}
    )
    dynamic_plan = EnginePlan(
        engine_kind="system_dynamics",
        objective_ref="objective://temporal-fallback-stock-flow",
        variable_map={
            "agents.income": "exogenous_inflows.0",
            "government.balance": "exogenous_inflows.1",
            "stock0": "stock:0",
        },
        system_dynamics_state={
            "initial_stocks": [0.0, 0.0],
            "flow_matrix": [[0.0, 0.0], [0.0, 0.0]],
            "exogenous_inflows": [0.0, 0.0],
        },
        system_dynamics_params={"dt": 1.0},
    )
    request = base.model_copy(update={"engine_plan": (static_plan, dynamic_plan)})

    result = JointSimulationHorizonController().run(request)

    assert [item.decision for item in result.engine_decisions] == ["unsupported", "selected"]
    assert result.engine_decisions[0].reason == "static_engine_cannot_ground_dynamic_horizon"
    assert result.engine_decisions[0].blockers == ("static_engine_temporal_capability",)
    assert result.engine_decisions[1].engine_kind == "system_dynamics"
    assert result.engine_decisions[1].temporal_capability == "multi_period"
    assert result.trajectories
    assert {trajectory.engine_kind for trajectory in result.trajectories} == {"system_dynamics"}
    assert all(
        tuple(point.step for point in trajectory.points) == (0, 1, 2)
        for trajectory in result.trajectories
    )


def test_all_unlabeled_static_multistep_candidates_refuse_before_runner_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All static candidates preserve typed reasons and produce no N5 run."""

    base = _request()
    first = base.engine_plan[0].model_copy(
        update={"eligibility_conditions": ("acyclic", "counterfactual_do_worlds")}
    )
    second = first.model_copy(update={"objective_ref": "objective://second-static"})
    request = base.model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=2, step=1),
            "engine_plan": (first, second),
        }
    )
    controller = JointSimulationHorizonController()
    runner_lookups: list[None] = []

    def runner_map() -> dict[str, object]:
        runner_lookups.append(None)
        return {}

    monkeypatch.setattr(controller, "_engine_runners", runner_map)
    result = controller.run(request)

    assert [item.decision for item in result.engine_decisions] == ["unsupported", "unsupported"]
    assert [item.reason for item in result.engine_decisions] == [
        "static_engine_cannot_ground_dynamic_horizon",
        "static_engine_cannot_ground_dynamic_horizon",
    ]
    assert [item.blockers for item in result.engine_decisions] == [
        ("static_engine_temporal_capability",),
        ("static_engine_temporal_capability",),
    ]
    assert result.receipt.calibration_status == "no_run"
    assert result.diagnostics["engine_run_claimed"] is False
    assert not result.trajectories
    assert runner_lookups == []


@pytest.mark.parametrize("reverse", [False, True], ids=("left-right", "right-left"))
def test_composition_rejection_falls_back_before_execution(
    monkeypatch: pytest.MonkeyPatch,
    reverse: bool,
) -> None:
    """B07/B20: a selected-looking plan with conflicting writes is skipped."""

    base = _single_step_request()
    world_ref = base.world_model_record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="income_subsidy",
            causal_variable="agents.income",
            engine_variable="income_delta",
            value=1.0,
            world_model_record_ref=world_ref,
        ),
        _atom(
            intervention_id="balance_grant",
            causal_variable="government.balance",
            engine_variable="balance_delta",
            value=2.0,
            world_model_record_ref=world_ref,
        ),
    )
    if reverse:
        atoms = tuple(reversed(atoms))
    supported_plan = base.engine_plan[0].model_copy(
        update={"objective_ref": "objective://composition-fallback"}
    )
    conflicting_plan = base.engine_plan[0].model_copy(
        update={
            "objective_ref": "objective://composition-conflict",
            "variable_map": {
                "agents.income": "income_delta",
                "government.balance": "income_delta",
                "firm_survival": "firm_survival",
            },
        }
    )
    request = base.model_copy(
        update={
            "intervention_atoms": atoms,
            "engine_plan": (conflicting_plan, supported_plan),
        }
    )
    calls: list[object] = []

    def fixed_result(state: object, params: object) -> dict[str, object]:
        del params
        calls.append(state)
        return {"counterfactual_result": {"world_summaries": [{"firm_survival": {"mean": 1.0}}]}}

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fixed_result))
    result = JointSimulationHorizonController().run(request)

    assert [item.decision for item in result.engine_decisions] == ["unsupported", "selected"]
    assert result.engine_decisions[0].reason == "intervention_assignment_conflict"
    assert result.engine_decisions[1].objective_ref == supported_plan.objective_ref
    assert calls
    assert {item.objective_ref for item in result.trajectories} == {supported_plan.objective_ref}


def test_all_engine_candidates_incompatible_return_typed_rejection() -> None:
    """B07: no coupling-compatible candidate remains a typed no-run refusal."""

    first = _coupled_plan().model_copy(update={"declared_equilibrium_semantics": "game_model"})
    second = _request().engine_plan[0]
    request = _request(policy_domain="unemployment_claims_benefit").model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=0, step=1),
            "coupling_graph": _coupling_graph("shared_resource"),
            "engine_plan": (first, second),
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert len(result.engine_decisions) == 2
    assert all(item.decision == "unsupported" for item in result.engine_decisions)
    assert [item.reason for item in result.engine_decisions] == [
        "equilibrium_semantics_not_backed_by_engine",
        "coupling_composition_gate_unsupported",
    ]
    assert not result.trajectories
    assert result.receipt.calibration_status == "unsupported_coupling_gated"
    assert result.feedback_classification.support_status == "unsupported"
    assert result.feedback_classification.engine_supported is False
    assert "unsupported_coupling_class:shared_resource" in (
        result.feedback_classification.support_blockers
    )
    assert "all_engine_candidates_rejected" in result.feedback_classification.support_blockers
    assert "declared_semantics_unbacked:game_model" in (result.feedback_classification.limitations)
    assert result.diagnostics["unsupported_objectives"] == [
        first.objective_ref,
        second.objective_ref,
    ]
    assert [item["reason"] for item in result.diagnostics["unsupported_reasons"]] == [
        "equilibrium_semantics_not_backed_by_engine",
        "coupling_composition_gate_unsupported",
    ]
    assert {item["reason"] for item in result.content_bound_payload()["engine_decisions"]} == {
        "equilibrium_semantics_not_backed_by_engine",
        "coupling_composition_gate_unsupported",
    }
    assert result.diagnostics["coupling_support_status"] == "unsupported"
    assert result.diagnostics["coupling_gate_blocked"] is True
    status, blockers = _joint_simulation_port_outcome(result)
    assert status == "simulation_blocked"
    assert _joint_simulation_is_unsupported(result) is True
    assert "unsupported_coupling_class:shared_resource" in blockers

    no_coupling_request = _request(policy_domain="unemployment_claims_benefit").model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=0, step=1),
            "engine_plan": (
                first,
                second.model_copy(
                    update={
                        "engine_kind": "method_registry_estimator",
                        "method_fqn": None,
                    }
                ),
            ),
        }
    )
    no_coupling_result = JointSimulationHorizonController().run(no_coupling_request)
    assert no_coupling_result.receipt.calibration_status == "no_run"
    assert no_coupling_result.diagnostics["coupling_support_status"] == "not_applicable"
    assert no_coupling_result.diagnostics["coupling_gate_blocked"] is False
    assert no_coupling_result.feedback_classification.support_status == "not_applicable"
    _, no_coupling_blockers = _joint_simulation_port_outcome(no_coupling_result)
    assert "n5_coupling_blocked" not in no_coupling_blockers


def test_selected_plan_requires_its_executed_trajectory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B06: a selected decision without its content-bound physical run is not evidence."""

    controller = JointSimulationHorizonController()
    monkeypatch.setattr(
        controller,
        "_engine_runners",
        lambda: {
            "ncm_parallel_worlds": lambda request, plan, decision: [
                _trajectory(
                    engine_kind=decision.engine_kind,
                    method_fqn=decision.method_fqn or "",
                    objective_ref=plan.objective_ref,
                )
            ]
        },
    )

    with pytest.raises(
        JointSimulationControllerError,
        match="selected_plan_execution_binding_missing",
    ):
        controller.run(_single_step_request())


def test_rejected_engine_reasons_do_not_override_selected_success() -> None:
    """B06: history retains why an earlier candidate was rejected."""

    first = (
        _request().engine_plan[0].model_copy(update={"eligibility_conditions": ("multi_period",)})
    )
    second = (
        _request()
        .engine_plan[0]
        .model_copy(update={"objective_ref": "objective://fallback-after-temporal-rejection"})
    )
    request = _single_step_request().model_copy(update={"engine_plan": (first, second)})

    result = JointSimulationHorizonController().run(request)

    assert result.engine_decisions[0].decision == "unsupported"
    assert result.engine_decisions[0].reason == "static_engine_cannot_ground_dynamic_horizon"
    assert result.engine_decisions[1].decision == "selected"
    assert result.engine_decisions[1].objective_ref == second.objective_ref
    assert result.trajectories


def test_foreign_trajectory_cannot_satisfy_selected_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B06: a result from another engine/plan cannot authorize the selected one."""

    controller = JointSimulationHorizonController()
    monkeypatch.setattr(
        controller,
        "_engine_runners",
        lambda: {"ncm_parallel_worlds": lambda request, plan, decision: [_trajectory()]},
    )

    with pytest.raises(
        JointSimulationControllerError,
        match="selected_trajectory_binding_mismatch",
    ):
        controller.run(_single_step_request())


def _reissue_result_with_trajectory_ref(
    result: JointSimulationResult, ref: object
) -> JointSimulationResult:
    """Produce a self-consistent forged receipt so the physical join, not a stale hash, is tested."""
    payload = result.model_dump(mode="json", exclude={"receipt"})
    target = payload["trajectories"][0]["diagnostics"]
    selected_events = set(target.get("physical_work_event_ids", ()))
    assert selected_events
    target["physical_run_ref"] = ref
    if ref is None:
        # A missing physical ref cannot carry a valid observed-work join. Test
        # the selected-plan guard with capture explicitly unavailable instead.
        payload["diagnostics"]["physical_work_capture_status"] = "not_established"
        payload["diagnostics"]["physical_work_observations"] = []
        payload["diagnostics"]["physical_work_units"] = 0
        payload["diagnostics"]["producer_budget_observations"] = {}
        payload["diagnostics"]["budget_admission_status"] = "not_established"
        for trajectory in payload["trajectories"]:
            trajectory["diagnostics"].pop("physical_work_event_ids", None)
    else:
        # Retain a valid work join while changing the physical ref. Shared
        # role projections must change together; selected-plan replay still
        # has to reject this self-consistent foreign run.
        foreign_digest = ArtifactID.model_validate(ref).hex
        for observation in payload["diagnostics"]["physical_work_observations"]:
            if observation["event_id"] in selected_events:
                observation["physical_spec_ref"] = foreign_digest
        for trajectory in payload["trajectories"]:
            diag = trajectory["diagnostics"]
            if selected_events.intersection(diag.get("physical_work_event_ids", ())):
                diag["physical_run_ref"] = ref
    receipt = build_content_bound_simulation_receipt(
        engine_kind=result.receipt.engine_kind, payload=payload, diagnostics=payload["diagnostics"]
    )
    forged = JointSimulationResult.model_validate({**payload, "receipt": receipt})
    forged._content_payload = payload
    return forged


@pytest.mark.parametrize("foreign_ref", [None, "sha256:" + "f" * 64], ids=["absent", "foreign"])
def test_generation_consumer_refuses_same_triple_foreign_physical_run(foreign_ref: object) -> None:
    """B06: identical selected engine/method/objective cannot authorize a different run."""
    request = _single_step_request()
    result = JointSimulationHorizonController().run(request)
    assert result.trajectories
    forged = _reissue_result_with_trajectory_ref(result, foreign_ref)
    assert forged.engine_decisions == result.engine_decisions
    assert forged.trajectories[0].engine_kind == result.trajectories[0].engine_kind
    assert forged.trajectories[0].method_fqn == result.trajectories[0].method_fqn
    assert forged.trajectories[0].objective_ref == result.trajectories[0].objective_ref
    status, blockers = _joint_simulation_port_outcome(forged, request=request)
    assert status == "simulation_blocked"
    assert "selected_plan_execution_binding_missing" in blockers


def test_generation_consumer_refuses_changed_request_seed_without_changing_marker() -> None:
    """B06: an otherwise matching selected decision cannot carry another seed's run."""
    request = _single_step_request()
    result = JointSimulationHorizonController().run(request)
    changed = request.model_copy(update={"seed": request.seed + 1})
    status, blockers = _joint_simulation_port_outcome(result, request=changed)
    assert status == "simulation_blocked"
    assert "selected_plan_execution_binding_missing" in blockers


def test_generation_consumer_fallback_preserves_real_second_engine_numeric_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B06: a rejected alternative cannot suppress an independently calculable fallback."""

    def fixed_output(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {"counterfactual_result": {"world_summaries": [{"firm_survival": {"mean": 7.0}}]}}

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fixed_output))
    base = _single_step_request()
    first = base.engine_plan[0].model_copy(update={"eligibility_conditions": ("multi_period",)})
    second = base.engine_plan[0].model_copy(
        update={"objective_ref": "objective://numeric-fallback"}
    )
    request = base.model_copy(update={"engine_plan": (first, second)})
    result = JointSimulationHorizonController().run(request)
    assert [row.decision for row in result.engine_decisions] == ["unsupported", "selected"]
    assert result.engine_decisions[0].reason == "static_engine_cannot_ground_dynamic_horizon"
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[0].outcomes == {"firm_survival": 7.0}
    assert joint.points[0].effect == {"firm_survival": 6.0}
    status, _ = _joint_simulation_port_outcome(result, request=request)
    assert status == "joint_simulated"


def test_generation_consumer_refuses_changed_plan_with_same_selection_triple() -> None:
    """B06: equal engine, method and objective do not make two plans the same physical run."""
    request = _single_step_request()
    result = JointSimulationHorizonController().run(request)
    selected = request.engine_plan[0]
    changed_plan = selected.model_copy(
        update={"variable_map": {**selected.variable_map, "agents.income": "another_input"}}
    )
    changed_request = request.model_copy(update={"engine_plan": (changed_plan,)})
    status, blockers = _joint_simulation_port_outcome(result, request=changed_request)
    assert status == "simulation_blocked"
    assert "selected_plan_execution_binding_missing" in blockers


def test_generation_consumer_retains_candidate_without_owner_request() -> None:
    """Historical N5 remains candidate-only with the missing provenance declared."""
    result = JointSimulationHorizonController().run(_single_step_request())
    status, blockers = _joint_simulation_port_outcome(result)
    assert status == "joint_simulated"
    assert "n5_execution_request_provenance_not_established" in blockers


def test_fresh_selected_cas_refuses_foreign_physical_ref_with_valid_receipt(tmp_path: Any) -> None:
    """A self-consistent foreign trajectory remains refused at the fresh CAS reader."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )

    request = _single_step_request()
    result = JointSimulationHorizonController().run(request)
    forged = _reissue_result_with_trajectory_ref(result, "sha256:" + "f" * 64)
    store = FileSystemCAS(tmp_path / "cas")
    ref = persist_joint_simulation_result(forged, store=store)
    assert ref.manifest_profile_sha256 is not None
    profileless = ref.model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(
        GenerationCycleError, match="joint_simulation_result_selected_view_binding_missing"
    ):
        load_joint_simulation_result(profileless, store=store, expected_request=request)
    with pytest.raises(
        GenerationCycleError, match="joint_simulation_result_execution_binding_invalid"
    ):
        load_joint_simulation_result(ref, store=store, expected_request=request)


def test_native_coupled_fallback_cas_rechecks_full_selected_request_and_manifest(
    tmp_path: Path,
) -> None:
    """TEST-SIM-01-03: actual fallback numbers and history survive only their selected binding."""

    from polisyos.core.artifacts.manifest import WarningRecord
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )
    from polisyos.runtime.quality.world_model_record import world_model_record_content_hash

    supported = _coupled_plan()
    rejected = supported.model_copy(
        update={"objective_ref": "objective://cas-first-invalid", "coupled_state": {}}
    )
    request = _coupled_request(rejected, supported)
    result = JointSimulationHorizonController().run(request)
    assert [row.decision for row in result.engine_decisions] == ["unsupported", "selected"]
    joint = result.trajectory_for("joint", result.atom_ids)
    assert joint.points[-1].outcomes == {"final_queue_length": 3.0}
    cas_path = tmp_path / "native-coupled-fallback-cas"
    writer = FileSystemCAS(cas_path)
    result_ref = persist_joint_simulation_result(result, store=writer)
    forged = _reissue_result_with_trajectory_ref(result, "sha256:" + "f" * 64)
    forged_ref = persist_joint_simulation_result(forged, store=writer)
    assert result_ref.manifest_profile_sha256 is not None
    assert forged_ref.manifest_profile_sha256 is not None
    assert forged_ref.artifact_id != result_ref.artifact_id
    # Profiles describe the write contract, not the blob's content identity.
    # Persist a genuinely different view on the foreign blob before trying
    # its profile selector against the original content ID.
    forged_manifest = writer.get_manifest(forged_ref)
    foreign_manifest_ref = writer.put_bytes(
        writer.get_bytes(forged_ref),
        PutOptions(
            kind=forged_ref.kind,
            media_type=forged_ref.media_type,
            schema=forged_manifest.artifact_schema,
            canon=forged_manifest.canon,
            warnings=[WarningRecord(code="foreign_view_fixture", msg="Adversarial selected view")],
        ),
        return_selected_profile=True,
    )
    assert foreign_manifest_ref.artifact_id == forged_ref.artifact_id
    assert foreign_manifest_ref.manifest_profile_sha256 is not None
    assert foreign_manifest_ref.manifest_profile_sha256 != result_ref.manifest_profile_sha256
    fresh_store = FileSystemCAS.open_existing_read_only(cas_path)

    fresh = load_joint_simulation_result(
        result_ref,
        store=fresh_store,
        expected_request=request,
        expected_world_model_record_content_hash=request.world_model_record.content_hash,
        expected_atom_ids=result.atom_ids,
        expected_selected_outcomes=request.selected_outcomes,
        expected_receipt_payload_hash=result.receipt.payload_hash,
    )

    assert fresh.engine_decisions == result.engine_decisions
    assert [row.model_dump(mode="json") for row in fresh.trajectories] == [
        row.model_dump(mode="json") for row in result.trajectories
    ]
    assert fresh.physical_work_observations == result.physical_work_observations
    assert fresh.trajectory_for("joint", fresh.atom_ids).points[-1].outcomes == {
        "final_queue_length": 3.0
    }
    assert _joint_simulation_port_outcome(fresh, request=request)[0] == "joint_simulated"
    status, historical_blockers = _joint_simulation_port_outcome(fresh)
    assert status == "joint_simulated"
    assert "n5_execution_request_provenance_not_established" in historical_blockers
    assert "simulation_only_k_sim_not_world_evidence" in historical_blockers

    changed_plan = supported.model_copy(
        update={"coupled_params": {**supported.coupled_params, "capacity": 1.0}}
    )
    changed_atom = _atom(
        intervention_id=request.intervention_atoms[0].intervention_id,
        causal_variable="agents.income",
        engine_variable="income_delta",
        value=2.0,
        world_model_record_ref=request.world_model_record_ref,
    )
    changed_world = request.world_model_record.model_copy(
        update={
            "simulation_model_ref": request.world_model_record.simulation_model_ref.model_copy(
                update={"model_id": "another-coupled-world-model"}
            )
        }
    )
    changed_world_hash = world_model_record_content_hash(changed_world)
    changed_world = type(changed_world).model_validate(
        {
            **changed_world.model_dump(mode="python"),
            "world_model_record_id": (
                f"world_model_record_{changed_world_hash.removeprefix('sha256:')[:16]}"
            ),
            "content_hash": changed_world_hash,
        }
    )
    changed_requests = {
        "seed": request.model_copy(update={"seed": request.seed + 1}),
        "same-triple-plan": request.model_copy(update={"engine_plan": (rejected, changed_plan)}),
        "same-id-atom": request.model_copy(
            update={"intervention_atoms": (changed_atom, *request.intervention_atoms[1:])}
        ),
        "model": request.model_copy(
            update={
                "world_model_record_ref": changed_world.world_model_record_id,
                "world_model_record": changed_world,
                "intervention_atoms": _request(record=changed_world).intervention_atoms,
            }
        ),
        "outcome": request.model_copy(update={"selected_outcomes": ("completed_count",)}),
        "horizon": request.model_copy(update={"horizon": HorizonSpec(start=0, end=2, step=1)}),
    }
    assert changed_plan.objective_ref == supported.objective_ref
    assert changed_plan.engine_kind == supported.engine_kind
    assert changed_atom.intervention_id == request.intervention_atoms[0].intervention_id
    for binding, changed_request in changed_requests.items():
        status, blockers = _joint_simulation_port_outcome(fresh, request=changed_request)
        assert status == "simulation_blocked", binding
        assert "selected_plan_execution_binding_missing" in blockers, binding
        with pytest.raises(
            GenerationCycleError, match="joint_simulation_result_execution_binding_invalid"
        ):
            load_joint_simulation_result(
                result_ref, store=fresh_store, expected_request=changed_request
            )

    # The foreign profile exists in this store, and its bytes/receipt are
    # consistent. Neither that profile nor its foreign work spec authorizes
    # this result's selected request.
    assert fresh_store.get_bytes(foreign_manifest_ref) == fresh_store.get_bytes(forged_ref)
    foreign_profile_ref = result_ref.model_copy(
        update={"manifest_profile_sha256": foreign_manifest_ref.manifest_profile_sha256}
    )
    with pytest.raises(GenerationCycleError, match="joint_simulation_result_unavailable"):
        load_joint_simulation_result(
            foreign_profile_ref, store=fresh_store, expected_request=request
        )
    with pytest.raises(
        GenerationCycleError, match="joint_simulation_result_execution_binding_invalid"
    ):
        load_joint_simulation_result(forged_ref, store=fresh_store, expected_request=request)


def test_n8_refuses_other_atom_when_candidate_has_only_canonical_atom(tmp_path: Any) -> None:
    """N8 compares the real single-atom shape even when no execution owner is available."""
    from types import SimpleNamespace

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.quality.generation_cycle import (
        SimulationPortObservation,
        _conditional_simulation_value_observation,
        persist_joint_simulation_result,
    )

    request = _single_step_request()
    result = JointSimulationHorizonController().run(request)
    store = FileSystemCAS(tmp_path / "wrong-atom-n8")
    result_ref = persist_joint_simulation_result(result, store=store)
    candidate = SimpleNamespace(candidate_id="candidate-one", atom=request.intervention_atoms[0])
    problem = SimpleNamespace(
        outcome_of_interest=SimpleNamespace(target_variable=request.selected_outcomes[0])
    )
    observation = SimulationPortObservation(
        candidate_id=candidate.candidate_id,
        status="joint_simulated",
        simulation_ref=result.receipt.payload_hash,
        simulation_result_ref=result_ref,
        world_model_record=request.world_model_record,
        k_world_ref_before=request.world_model_record.content_hash,
        k_world_ref_after=request.world_model_record.content_hash,
        authority_blockers=("simulation_only_k_sim_not_world_evidence",),
    )
    value = _conditional_simulation_value_observation(
        candidate=candidate, simulation=observation, problem=problem, artifact_store=store
    )
    assert value is not None
    assert value.status == "value_blocked"
    assert "joint_simulation_result_atom_binding_mismatch" in value.authority_blockers
