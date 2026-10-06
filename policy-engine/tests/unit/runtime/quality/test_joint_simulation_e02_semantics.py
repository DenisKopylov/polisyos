"""Focused SIM semantic witnesses for atom composition and horizon coverage."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

import polisyos.runtime.quality.joint_simulation_horizon as joint_simulation_horizon_module
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.foundry.methods.catalog.simulation.dynamics import (
    StockFlowSystemDynamicsEstimator,
)
from polisyos.ir.analytics.ncm import ExogenousSpec, NCMSpec, StructuralEquation
from polisyos.runtime.quality.joint_simulation_horizon import (
    EnginePlan,
    HorizonSpec,
    JointSimulationControllerError,
    JointSimulationHorizonController,
    JointSimulationRequest,
    SimulationTrajectory,
    TrajectoryPoint,
    _atom_subsets,
    _coupled_queue_value,
    _interaction_coverage,
    _ncm_run_once,
    _physical_run_ref,
    _required_finite_scalar,
    _run_or_reuse_physical_spec,
    _snapshot_engine_plan,
    _system_dynamics_outcomes,
)
from tests.unit.runtime.quality.test_joint_simulation_horizon import (
    _atom,
    _program_graph_plan,
    _request,
)


def _same_slot_conflict_request(*, reverse: bool = False) -> JointSimulationRequest:
    request = _request()
    world_ref = request.world_model_record.world_model_record_id
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
            causal_variable="agents.income",
            engine_variable="income_delta",
            value=2.0,
            world_model_record_ref=world_ref,
        ),
    )
    return request.model_copy(
        update={"intervention_atoms": tuple(reversed(atoms)) if reverse else atoms}
    )


def _trajectory(
    request: JointSimulationRequest,
    *,
    run_level: str,
    atom_ids: tuple[str, ...],
    steps: Sequence[int],
) -> SimulationTrajectory:
    points = tuple(
        TrajectoryPoint(
            step=step,
            outcomes=dict.fromkeys(request.selected_outcomes, 0.0),
            effect=dict.fromkeys(request.selected_outcomes, 0.0),
        )
        for step in steps
    )
    return SimulationTrajectory(
        run_level=run_level,  # type: ignore[arg-type]
        atom_ids=atom_ids,
        engine_kind="ncm_parallel_worlds",
        method_fqn="polisyos.foreign.test_ncm@1.0.0",
        objective_ref=request.engine_plan[0].objective_ref,
        points=points,
    )


def _complete_trajectories(
    request: JointSimulationRequest,
    *,
    replace_scope: tuple[str, tuple[str, ...]] | None = None,
    replacement_steps: Sequence[int] = (),
) -> list[SimulationTrajectory]:
    trajectories: list[SimulationTrajectory] = []
    for level, subset in _atom_subsets(request.intervention_atoms):
        atom_ids = tuple(atom.intervention_id for atom in subset)
        steps = request.horizon.steps()
        if replace_scope == (level, atom_ids):
            steps = replacement_steps
        trajectories.append(
            _trajectory(
                request,
                run_level=level,
                atom_ids=atom_ids,
                steps=steps,
            )
        )
    return trajectories


def test_static_engine_eligibility_uses_the_requested_grid_not_hint_strings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    controller = JointSimulationHorizonController()
    runner_calls: list[None] = []
    monkeypatch.setattr(
        controller,
        "_engine_runners",
        lambda: {
            "ncm_parallel_worlds": lambda *_args: runner_calls.append(None),
        },
    )

    result = controller.run(request)

    assert request.horizon.steps() == (0, 1, 2, 3)
    assert result.engine_decisions[0].decision == "unsupported"
    assert result.engine_decisions[0].reason == "static_engine_cannot_ground_dynamic_horizon"
    assert result.engine_decisions[0].blockers == ("static_engine_temporal_capability",)
    assert result.trajectories == ()
    assert result.receipt.calibration_status == "no_run"
    assert runner_calls == []

    one_requested_point = request.model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=3, step=4),
            "engine_plan": (
                request.engine_plan[0].model_copy(
                    update={"eligibility_conditions": ("multi_period",)}
                ),
            ),
        }
    )
    selected = controller._select_engine(one_requested_point)
    assert one_requested_point.horizon.steps() == (0,)
    assert selected.decision.decision == "selected"
    assert selected.decision.temporal_capability == "static"


@pytest.mark.parametrize("reverse", [False, True], ids=("left-right", "right-left"))
def test_conflicting_canonical_slot_writes_refuse_before_any_singleton(
    monkeypatch: pytest.MonkeyPatch,
    reverse: bool,
) -> None:
    calls: list[None] = []
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.causal.ncm_engine.NCMEngineMethod.pure_step",
        staticmethod(lambda *_args: calls.append(None)),
    )

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(_same_slot_conflict_request(reverse=reverse))

    assert raised.value.code == "intervention_assignment_conflict"
    assert calls == []


def test_engine_variable_alias_conflict_rejects_candidate_before_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _request()
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
    plan = base.engine_plan[0].model_copy(
        update={
            "variable_map": {
                **base.engine_plan[0].variable_map,
                "government.balance": "income_delta",
            }
        }
    )
    request = base.model_copy(
        update={
            "intervention_atoms": atoms,
            "horizon": HorizonSpec(start=0, end=0),
            "engine_plan": (plan,),
        }
    )
    runner_calls: list[None] = []
    controller = JointSimulationHorizonController()
    monkeypatch.setattr(
        controller,
        "_engine_runners",
        lambda: {"ncm_parallel_worlds": lambda *_args: runner_calls.append(None)},
    )

    result = controller.run(request)

    assert result.engine_decisions[0].decision == "unsupported"
    assert result.engine_decisions[0].reason == "engine_intervention_assignment_conflict"
    assert result.engine_decisions[0].blockers == ("engine_variable_conflict:income_delta",)
    assert result.trajectories == ()
    assert result.receipt.calibration_status == "no_run"
    assert runner_calls == []


@pytest.mark.parametrize(
    ("steps", "coverage_class"),
    [
        pytest.param((0, 1), "short", id="short-trailing"),
        pytest.param((0, 2, 3), "missing_internal", id="missing-middle"),
        pytest.param((2, 3), "suffix_only", id="suffix-only"),
        pytest.param((1, 0, 2, 3), "reordered", id="reordered-full-set"),
        pytest.param((0, 1, 2, 3, 4), "overlong", id="overlong"),
    ],
)
def test_interaction_coverage_requires_exact_ordered_requested_grid(
    steps: tuple[int, ...],
    coverage_class: str,
) -> None:
    request = _request()
    scope = ("joint", tuple(atom.intervention_id for atom in request.intervention_atoms))

    coverage = _interaction_coverage(
        request,
        _complete_trajectories(
            request,
            replace_scope=scope,
            replacement_steps=steps,
        ),
    )

    scope_text = ":".join((*scope[0:1], ",".join(scope[1])))
    assert any(
        issue.startswith(f"horizon_incomplete:{coverage_class}:{scope_text}")
        for issue in coverage.issues
    )
    assert scope not in coverage.complete_scopes


def test_physical_run_identity_canonicalizes_atoms_and_binds_comparator_inputs() -> None:
    request = _request().model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=0),
            "baseline_state": {"firm_survival": 0.0},
            "evidence_state": {},
        }
    )
    controller = JointSimulationHorizonController()
    selected = controller._select_engine(request)

    def identity(candidate: JointSimulationRequest) -> str:
        return _physical_run_ref(
            candidate,
            selected.plan,
            selected.decision,
            candidate.intervention_atoms,
        )

    base_ref = identity(request)
    permuted = request.model_copy(
        update={"intervention_atoms": tuple(reversed(request.intervention_atoms))}
    )
    changed_baseline = request.model_copy(
        update={"baseline_state": {"firm_survival": 1.0}}
    )
    changed_comparator = request.model_copy(
        update={"comparator_refs": ("comparator://new-observation",)}
    )

    assert identity(permuted) == base_ref
    assert identity(changed_baseline) != base_ref
    assert identity(changed_comparator) != base_ref


def test_missing_queue_and_mass_balance_output_never_becomes_numeric_zero() -> None:
    assert _coupled_queue_value({"initial_queue_length": 0.0}, 0) == 0.0
    with pytest.raises(JointSimulationControllerError) as queue_error:
        _coupled_queue_value(
            {"initial_queue_length": 0.0, "final_queue_length": 9.0},
            1,
        )
    assert queue_error.value.code == "coupled_queue_trajectory_incomplete"

    plan = EnginePlan(
        engine_kind="system_dynamics",
        objective_ref="objective://missing-mass-balance",
        variable_map={"mass_balance": "mass_balance"},
    )
    with pytest.raises(JointSimulationControllerError) as mass_error:
        _system_dynamics_outcomes(
            {},
            [0.0],
            ("mass_balance",),
            plan,
            point_is_terminal=True,
            terminal_scalar_fields=frozenset({"mass_balance"}),
        )
    assert mass_error.value.code == "system_dynamics_mass_balance_missing"
    assert _system_dynamics_outcomes(
        {"mass_balance": 0.0},
        [0.0],
        ("mass_balance",),
        plan,
        point_is_terminal=True,
        terminal_scalar_fields=frozenset({"mass_balance"}),
    ) == {"mass_balance": 0.0}


@pytest.mark.parametrize(
    ("value", "expected_code"),
    [
        pytest.param(None, "output_missing", id="null"),
        pytest.param("not-a-number", "output_non_numeric", id="malformed"),
        pytest.param(float("nan"), "output_non_finite", id="nan"),
        pytest.param(float("inf"), "output_non_finite", id="infinity"),
    ],
)
def test_shared_required_output_projection_rejects_invalid_values(
    value: object,
    expected_code: str,
) -> None:
    with pytest.raises(JointSimulationControllerError) as raised:
        _required_finite_scalar(
            value,
            field="test_output",
            missing_code="output_missing",
            malformed_code="output_non_numeric",
            non_finite_code="output_non_finite",
        )
    assert raised.value.code == expected_code


def test_shared_cache_executor_rejects_nonfinite_adapter_output() -> None:
    request = _request().model_copy(update={"horizon": HorizonSpec(start=0, end=0)})
    selected = JointSimulationHorizonController()._select_engine(request)
    atom_ids = tuple(atom.intervention_id for atom in request.intervention_atoms)
    malformed = SimulationTrajectory(
        run_level="joint",
        atom_ids=atom_ids,
        engine_kind=selected.decision.engine_kind,
        method_fqn=selected.decision.method_fqn or "foreign.method@1.0.0",
        objective_ref=selected.plan.objective_ref,
        points=(
            TrajectoryPoint(
                step=0,
                outcomes={"firm_survival": float("nan")},
                effect={"firm_survival": 0.0},
            ),
        ),
    )

    with pytest.raises(JointSimulationControllerError) as raised:
        _run_or_reuse_physical_spec(
            {},
            request,
            selected.plan,
            selected.decision,
            "joint",
            request.intervention_atoms,
            lambda *_args: malformed,
        )

    assert raised.value.code == "simulation_output_non_finite"


def test_generic_scalar_result_is_unavailable_without_terminal_binding() -> None:
    plan = EnginePlan(
        engine_kind="method_registry_estimator",
        objective_ref="objective://generic-final-scalar",
        variable_map={"mass_balance": "mass_balance"},
    )

    with pytest.raises(JointSimulationControllerError) as raised:
        _system_dynamics_outcomes(
            {"mass_balance": 11.0},
            [0.0],
            ("mass_balance",),
            plan,
            point_is_terminal=True,
        )

    assert raised.value.code == "system_dynamics_scalar_result_unbound"


def test_registered_stock_flow_mass_balance_is_terminal_only_not_broadcast() -> None:
    base = _request()
    world_ref = base.world_model_record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="income_subsidy",
            causal_variable="agents.income",
            engine_variable="exogenous_inflows.0",
            value=0.0,
            world_model_record_ref=world_ref,
        ),
        _atom(
            intervention_id="balance_grant",
            causal_variable="government.balance",
            engine_variable="exogenous_inflows.1",
            value=0.0,
            world_model_record_ref=world_ref,
        ),
    )
    plan = EnginePlan(
        engine_kind="system_dynamics",
        objective_ref="objective://stock-flow-final-mass-balance",
        variable_map={
            "agents.income": "exogenous_inflows.0",
            "government.balance": "exogenous_inflows.1",
            "mass_balance": "mass_balance",
        },
        system_dynamics_state={
            "initial_stocks": [10.0, 0.0],
            "flow_matrix": [[0.0, 0.1], [0.0, 0.0]],
            "exogenous_inflows": [0.0, 0.0],
        },
        system_dynamics_params={"dt": 1.0},
    )
    request = base.model_copy(
        update={
            "intervention_atoms": atoms,
            "selected_outcomes": ("mass_balance",),
            "baseline_state": {"mass_balance": 0.0},
            "horizon": HorizonSpec(start=0, end=3),
            "engine_plan": (plan,),
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert result.engine_decisions[0].method_fqn == "simulation.system_dynamics.stock_flow@1.0.0"
    for trajectory in result.trajectories:
        assert [point.step for point in trajectory.points] == [0, 1, 2, 3]
        assert all("mass_balance" not in point.outcomes for point in trajectory.points[:-1])
        assert "mass_balance" in trajectory.points[-1].outcomes
    assert result.feedback_classification.numeric_interaction == "unsupported"
    assert "interaction_evidence_incomplete" in result.feedback_classification.limitations
    assert any(
        issue.startswith("selected_outcome_incomplete:")
        for issue in result.diagnostics["interaction_evidence_issues"]
    )


def test_registered_stock_flow_marks_unbound_time_grid_when_dt_disagrees() -> None:
    """A dt/horizon mismatch falsifies row-index time alignment; keep it limited."""

    base = _request()
    world_ref = base.world_model_record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="income_subsidy",
            causal_variable="agents.income",
            engine_variable="exogenous_inflows.0",
            value=0.0,
            world_model_record_ref=world_ref,
        ),
        _atom(
            intervention_id="balance_grant",
            causal_variable="government.balance",
            engine_variable="exogenous_inflows.1",
            value=0.0,
            world_model_record_ref=world_ref,
        ),
    )
    plan = EnginePlan(
        engine_kind="system_dynamics",
        objective_ref="objective://unbound-time-grid",
        variable_map={
            "agents.income": "exogenous_inflows.0",
            "government.balance": "exogenous_inflows.1",
            "stock0": "stock:0",
        },
        system_dynamics_state={
            "initial_stocks": [10.0, 0.0],
            "flow_matrix": [[0.0, 0.1], [0.0, 0.0]],
            "exogenous_inflows": [0.0, 0.0],
        },
        system_dynamics_params={"dt": 1.0},
    )
    request = base.model_copy(
        update={
            "intervention_atoms": atoms,
            "selected_outcomes": ("stock0",),
            "baseline_state": {"stock0": 10.0},
            "horizon": HorizonSpec(start=0, end=6, step=2),
            "engine_plan": (plan,),
        }
    )

    result = JointSimulationHorizonController().run(request)

    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert [point.step for point in joint.points] == [0, 2, 4, 6]
    # Producer advances one dt=1 row while the adapter labels it as request step 2.
    assert [point.outcomes["stock0"] for point in joint.points] == pytest.approx(
        [10.0, 9.0, 8.1, 7.29]
    )
    assert joint.diagnostics["producer_time_grid_binding"] == "not_established"


def test_single_point_stock_flow_can_mix_initial_row_with_terminal_scalar() -> None:
    """B22 falsifier: no producer time binding distinguishes row zero from final output."""

    base = _request()
    world_ref = base.world_model_record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="income_subsidy",
            causal_variable="agents.income",
            engine_variable="exogenous_inflows.0",
            value=0.0,
            world_model_record_ref=world_ref,
        ),
        _atom(
            intervention_id="balance_grant",
            causal_variable="government.balance",
            engine_variable="exogenous_inflows.1",
            value=0.0,
            world_model_record_ref=world_ref,
        ),
    )
    plan = EnginePlan(
        engine_kind="system_dynamics",
        objective_ref="objective://single-point-initial-and-terminal-mix",
        variable_map={
            "agents.income": "exogenous_inflows.0",
            "government.balance": "exogenous_inflows.1",
            "stock0": "stock:0",
        },
        system_dynamics_state={
            "initial_stocks": [10.0, 0.0],
            "flow_matrix": [[0.0, 0.1], [0.0, 0.0]],
            "exogenous_inflows": [0.0, 0.0],
        },
        system_dynamics_params={"dt": 1.0},
    )
    request = base.model_copy(
        update={
            "intervention_atoms": atoms,
            "selected_outcomes": ("stock0", "final_stocks.0"),
            "baseline_state": {"stock0": 10.0, "final_stocks.0": 10.0},
            "horizon": HorizonSpec(start=0, end=0, step=1),
            "engine_plan": (plan,),
        }
    )

    result = JointSimulationHorizonController().run(request)

    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert request.horizon.steps() == (0,)
    assert joint.points[0].engine_state["stock_values"] == [10.0, 0.0]
    assert joint.points[0].outcomes == {"stock0": 10.0, "final_stocks.0": 9.0}
    assert joint.diagnostics["unrequested_output_points"] == 1
    assert joint.diagnostics["producer_time_grid_binding"] == "not_established"
    assert "simulation_only_k_sim_not_world_evidence" in (
        result.promotion_ready_value_packet["authority_blockers"]
    )


def test_invocation_cache_hits_and_semantic_misses_execute_the_real_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request().model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=0),
            "evidence_state": None,
        }
    )
    controller = JointSimulationHorizonController()
    selected = controller._select_engine(request)
    assert selected.decision.method_fqn is not None
    original_pure_step = NCMEngineMethod.pure_step
    engine_calls: list[tuple[int, dict[str, float]]] = []

    def counted_pure_step(state: Any, params: Any) -> dict[str, Any]:
        query = state["ncm_query_data"]
        engine_calls.append((int(params["__seed__"]), dict(query.evidence)))
        return original_pure_step(state, params)

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(counted_pure_step))
    cache: dict[str, SimulationTrajectory] = {}

    def invoke(
        candidate_request: JointSimulationRequest,
        candidate_plan: EnginePlan,
        candidate_decision: Any,
    ) -> tuple[str, SimulationTrajectory, bool]:
        def run_once(
            run_request: JointSimulationRequest,
            run_plan: EnginePlan,
            run_decision: Any,
            run_level: str,
            atoms: tuple[Any, ...],
            seed: int,
        ) -> SimulationTrajectory:
            assert run_request is not candidate_request
            assert run_plan is not candidate_plan
            assert run_decision is not candidate_decision
            assert run_decision.method_fqn is not None
            return _ncm_run_once(
                run_request,
                run_plan,
                run_decision,
                controller._registry.get(run_decision.method_fqn).pure_step,
                run_level,  # type: ignore[arg-type]
                atoms,
                seed,
            )

        return _run_or_reuse_physical_spec(
            cache,
            candidate_request,
            candidate_plan,
            candidate_decision,
            "joint",
            (candidate_request.intervention_atoms[0],),
            run_once,
        )

    base_ref, _, reused = invoke(request, selected.plan, selected.decision)
    assert not reused
    repeated_ref, _, reused = invoke(request, selected.plan, selected.decision)
    assert repeated_ref == base_ref
    assert reused
    assert len(engine_calls) == 1

    plan_variant = selected.plan.model_copy(
        update={
            "variable_map": {
                **selected.plan.variable_map,
                "firm_survival": "balance_delta",
            }
        }
    )
    variants = (
        (request.model_copy(update={"seed": request.seed + 1}), selected.plan),
        (request, plan_variant),
        (
            request.model_copy(
                update={
                    "evidence_state": {
                        "income_delta": 2.0,
                        "balance_delta": 0.0,
                        "firm_survival": 1.0,
                    }
                }
            ),
            selected.plan,
        ),
        (
            request.model_copy(
                update={
                    "baseline_state": {
                        **request.baseline_state,
                        "firm_survival": 7.0,
                    }
                }
            ),
            selected.plan,
        ),
        (
            request.model_copy(update={"comparator_refs": ("comparator://updated",)}),
            selected.plan,
        ),
    )
    distinct_refs = {base_ref}
    for expected_call_count, (candidate_request, candidate_plan) in enumerate(
        variants,
        start=2,
    ):
        physical_ref, _, reused = invoke(
            candidate_request,
            candidate_plan,
            selected.decision,
        )
        assert physical_ref not in distinct_refs
        assert not reused
        distinct_refs.add(physical_ref)
        assert len(engine_calls) == expected_call_count

    mutable_request = request.model_copy(
        update={
            "evidence_state": {
                "income_delta": 3.0,
                "balance_delta": 0.0,
                "firm_survival": 1.0,
            }
        }
    )
    snapshot_evidence = dict(mutable_request.evidence_state or {})
    mutable_cache: dict[str, SimulationTrajectory] = {}
    mutation_runs: list[SimulationTrajectory] = []

    def mutate_source_after_key(
        run_request: JointSimulationRequest,
        run_plan: EnginePlan,
        run_decision: Any,
        run_level: str,
        atoms: tuple[Any, ...],
        seed: int,
    ) -> SimulationTrajectory:
        mutable_request.evidence_state["income_delta"] = 99.0
        assert run_request.evidence_state == snapshot_evidence
        assert run_plan is not selected.plan
        assert run_decision is not selected.decision
        trajectory = _ncm_run_once(
            run_request,
            run_plan,
            run_decision,
            controller._registry.get(run_decision.method_fqn).pure_step,
            run_level,  # type: ignore[arg-type]
            atoms,
            seed,
        )
        mutation_runs.append(trajectory)
        return trajectory

    mutation_ref, _, mutation_reused = _run_or_reuse_physical_spec(
        mutable_cache,
        mutable_request,
        selected.plan,
        selected.decision,
        "joint",
        (mutable_request.intervention_atoms[0],),
        mutate_source_after_key,
    )
    assert mutation_ref not in distinct_refs
    assert not mutation_reused
    assert len(mutation_runs) == 1
    assert engine_calls[-1][1] == snapshot_evidence


def test_program_graph_cache_binds_mutated_state_with_same_cas_refs(
    tmp_path: Any,
) -> None:
    import jax.numpy as jnp

    from polisyos.core.contracts.foundry import StateSnapshotRef
    from polisyos.foundry.execute._internal.snapshots import put_state_snapshot

    first_plan = _program_graph_plan(tmp_path)
    snapshot_ref = put_state_snapshot(
        first_plan.program_store,
        state=first_plan.program_base_state,
        step=0,
    )
    snapshot_ref = StateSnapshotRef.model_validate(snapshot_ref.model_dump(mode="python"))
    first_plan = first_plan.model_copy(update={"program_base_ref": snapshot_ref})
    changed_state = first_plan.program_base_state.replace(
        agents=first_plan.program_base_state.agents.replace(
            income=jnp.asarray([2000.0, 4000.0], dtype=jnp.float32)
        )
    )
    second_plan = first_plan.model_copy(
        update={"program_base_state": changed_state}
    )
    request = _request().model_copy(
        update={
            "engine_plan": (first_plan,),
            "horizon": HorizonSpec(start=0, end=0),
            "selected_outcomes": ("mean_income",),
            "baseline_state": {"mean_income": 0.0},
        }
    )
    controller = JointSimulationHorizonController()
    decision = controller._select_program_graph_engine(first_plan)
    second_request = request.model_copy(update={"engine_plan": (second_plan,)})
    cache: dict[str, SimulationTrajectory] = {}
    observed_states: list[float] = []

    def run_once(
        run_request: JointSimulationRequest,
        run_plan: EnginePlan,
        run_decision: Any,
        run_level: str,
        atoms: tuple[Any, ...],
        seed: int,
    ) -> SimulationTrajectory:
        artifacts = joint_simulation_horizon_module.execute_program_graph(
            run_plan.program_store,
            program_ref=run_plan.program_graph_ref,
            exec_plan_ref=run_plan.exec_plan_ref,
            base_state=run_plan.program_base_state,
            mechanism_registry=run_plan.mechanism_registry,
            slot_registry=run_plan.slot_registry,
            merge_registry=run_plan.merge_registry,
            selector_field_registry=run_plan.selector_field_registry,
            constraint_registry=run_plan.constraint_registry,
            step=0,
            seed=seed,
            base_ref=run_plan.program_base_ref,
            parameter_overrides=joint_simulation_horizon_module._program_parameter_overrides(
                atoms,
                run_plan,
            ),
        )
        current_state = joint_simulation_horizon_module.apply_state_delta(
            run_plan.program_store,
            base_state=run_plan.program_base_state,
            state_delta_ref=artifacts.state_delta_ref,
            slot_registry=run_plan.slot_registry,
            merge_registry=run_plan.merge_registry,
        )
        outcomes = joint_simulation_horizon_module._program_graph_outcomes(
            current_state,
            run_request.selected_outcomes,
            run_plan,
        )
        observed_states.append(float(outcomes["mean_income"]))
        return SimulationTrajectory(
            run_level=run_level,  # type: ignore[arg-type]
            atom_ids=tuple(atom.intervention_id for atom in atoms),
            engine_kind=run_decision.engine_kind,
            method_fqn=run_decision.method_fqn,
            objective_ref=run_plan.objective_ref,
            points=(
                TrajectoryPoint(
                    step=run_request.horizon.steps()[0],
                    outcomes=outcomes,
                    effect=outcomes,
                ),
            ),
        )

    atom_subset = (request.intervention_atoms[0],)
    first_ref, first_result, reused = _run_or_reuse_physical_spec(
        cache,
        request,
        first_plan,
        decision,
        "joint",
        atom_subset,
        run_once,
    )
    assert not reused
    second_ref, second_result, reused = _run_or_reuse_physical_spec(
        cache,
        second_request,
        second_plan,
        decision,
        "joint",
        atom_subset,
        run_once,
    )

    assert first_plan.program_base_ref == second_plan.program_base_ref
    assert first_plan.program_graph_ref == second_plan.program_graph_ref
    assert first_plan.exec_plan_ref == second_plan.exec_plan_ref
    assert first_ref != second_ref
    assert not reused
    assert len(observed_states) == 2
    assert first_result.points[0].outcomes["mean_income"] == observed_states[0]
    assert second_result.points[0].outcomes["mean_income"] == observed_states[1]
    assert observed_states[0] != observed_states[1]


def test_program_graph_controller_preserves_store_handles_and_snapshots_state(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ProgramGraph run snapshots its state while reusing the owning CAS handle."""

    plan = _program_graph_plan(tmp_path)
    assert isinstance(plan.program_store, FileSystemCAS)
    snapshot = _snapshot_engine_plan(plan)
    assert snapshot.program_store is plan.program_store
    for handle in (
        "mechanism_registry",
        "slot_registry",
        "merge_registry",
        "selector_field_registry",
        "constraint_registry",
    ):
        assert getattr(snapshot, handle) is getattr(plan, handle)
    assert snapshot.program_base_state is not plan.program_base_state
    assert snapshot.program_graph_ref == plan.program_graph_ref
    assert snapshot.exec_plan_ref == plan.exec_plan_ref
    assert snapshot.program_base_ref == plan.program_base_ref

    stores: list[FileSystemCAS] = []
    base_states: list[Any] = []
    original_execute = joint_simulation_horizon_module.execute_program_graph

    def observe_execution(store: FileSystemCAS, *args: Any, **kwargs: Any) -> Any:
        stores.append(store)
        base_states.append(kwargs["base_state"])
        return original_execute(store, *args, **kwargs)

    monkeypatch.setattr(
        joint_simulation_horizon_module,
        "execute_program_graph",
        observe_execution,
    )
    request = _request().model_copy(
        update={
            "engine_plan": (plan,),
            "selected_outcomes": ("mean_income",),
            "baseline_state": {"mean_income": 0.0},
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert result.engine_decisions[0].decision == "selected"
    assert stores
    assert all(store is plan.program_store for store in stores)
    assert base_states[0] is not plan.program_base_state


def test_stock_flow_runner_does_not_fill_a_short_trajectory_with_final_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def short_stock_flow(
        state: Any,
        params: Any,
    ) -> dict[str, Any]:
        del state, params
        return {
            "result": {
                "trajectory": [[10.0, 0.0], [20.0, 0.0]],
                "final_stocks": [99.0, 99.0],
                "mass_balance": 90.0,
            }
        }

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(short_stock_flow),
    )
    base = _request()
    plan = EnginePlan(
        engine_kind="system_dynamics",
        objective_ref="objective://short-stock-flow",
        variable_map={
            "agents.income": "exogenous_inflows.0",
            "government.balance": "exogenous_inflows.1",
            "stock0": "stock:0",
        },
        system_dynamics_state={
            "initial_stocks": [10.0, 0.0],
            "flow_matrix": [[0.0, 0.0], [0.0, 0.0]],
            "exogenous_inflows": [0.0, 0.0],
        },
        system_dynamics_params={"dt": 1.0},
    )
    request = base.model_copy(
        update={
            "selected_outcomes": ("stock0",),
            "baseline_state": {"stock0": 10.0},
            "horizon": HorizonSpec(start=0, end=2),
            "engine_plan": (plan,),
        }
    )

    result = JointSimulationHorizonController().run(request)

    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert [point.step for point in joint.points] == [0, 1]
    assert [point.outcomes["stock0"] for point in joint.points] == [10.0, 20.0]
    assert all(point.outcomes["stock0"] != 99.0 for point in joint.points)
    assert any(
        issue.startswith("horizon_incomplete:short:joint:")
        for issue in result.diagnostics["interaction_evidence_issues"]
    )


def _cubic_ncm() -> NCMSpec:
    return NCMSpec(
        endogenous_vars=["x1", "x2", "x3", "y"],
        exogenous_specs=[
            ExogenousSpec(variable=f"u_{name}", associated_endogenous=name)
            for name in ("x1", "x2", "x3", "y")
        ],
        structural_equations=[
            StructuralEquation(
                variable=name,
                parents=[],
                exogenous=f"u_{name}",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {}},
            )
            for name in ("x1", "x2", "x3")
        ]
        + [
            StructuralEquation(
                variable="y",
                parents=["x1", "x2", "x3"],
                exogenous="u_y",
                equation_type="nonlinear",
                equation_params={"noise_expression": "x1 * x2 * x3 + u"},
            )
        ],
        is_acyclic=True,
        markov_condition_verified=True,
        independence_model="dag_markov",
        fit_method="symbolic",
    )


def test_real_ncm_cubic_exposes_joint_residual_with_zero_lower_order_terms() -> None:
    base = _request()
    world_ref = base.world_model_record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="income_subsidy",
            causal_variable="agents.income",
            engine_variable="x1",
            value=1.0,
            world_model_record_ref=world_ref,
        ),
        _atom(
            intervention_id="balance_grant",
            causal_variable="government.balance",
            engine_variable="x2",
            value=1.0,
            world_model_record_ref=world_ref,
        ),
        _atom(
            intervention_id="labor_market",
            causal_variable="firms.labor_count",
            engine_variable="x3",
            value=1.0,
            world_model_record_ref=world_ref,
            mechanism_kind="labor_market",
            mechanism_variables=(
                "agents.employer_id",
                "agents.is_employed",
                "agents.income",
                "firms.labor_count",
            ),
        ),
    )
    plan = base.engine_plan[0].model_copy(
        update={
            "ncm_spec": _cubic_ncm(),
            "variable_map": {
                "agents.income": "x1",
                "government.balance": "x2",
                "firms.labor_count": "x3",
                "y": "y",
            },
        }
    )
    request = base.model_copy(
        update={
            "intervention_atoms": atoms,
            "selected_outcomes": ("y",),
            "horizon": HorizonSpec(start=0, end=0),
            "baseline_state": {"y": 0.0},
            "evidence_state": {"x1": 0.0, "x2": 0.0, "x3": 0.0, "y": 0.0},
            "engine_plan": (plan,),
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert result.engine_decisions[0].method_fqn.endswith("ncm_engine@1.0.0")
    for trajectory in result.trajectories:
        expected = 1.0 if trajectory.run_level == "joint" else 0.0
        assert trajectory.points[0].outcomes["y"] == pytest.approx(expected)
    assert result.higher_order_residuals == {"y": {0: pytest.approx(1.0)}}
    assert result.feedback_classification.numeric_interaction == "non_additive"
    assert result.feedback_classification.checked_interaction_orders == (1, 2, 3)
