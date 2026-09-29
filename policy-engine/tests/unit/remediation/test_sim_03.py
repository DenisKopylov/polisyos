"""Test-first witnesses for the SIM-03 estimation and joint-run contracts.

The tests deliberately exercise the observable seams for B19/B21/B23/B25/B26.
They remain an N/C-exclusive profile because the shared joint-simulation
fixture imports the native registry and numerical stack.
"""

from __future__ import annotations

from typing import Any

import pytest

from polisyos.foundry.coupling.estimation import (
    calibrate_coupled_smm,
    paired_monte_carlo_effect,
    summary_distance,
)
from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationControllerError,
    JointSimulationHorizonController,
    SimulationTrajectory,
    TrajectoryPoint,
    _checked_interaction_orders,
    _higher_order_residuals,
    _interaction_coverage,
)
from tests.unit.runtime.quality.test_joint_simulation_horizon import _atom, _request


def _request_with_atom_count(count: int) -> Any:
    """Build a controlled NCM request with a single explicitly requested step."""

    if count not in {2, 3, 4}:
        raise ValueError("SIM-03 fixture supports two through four atoms")
    request = _request()
    world_ref = request.world_model_record.world_model_record_id
    additions = (
        (
            "third_atom",
            "firms.labor_count",
            "labor_count_delta",
            "labor_market",
            (
                "agents.employer_id",
                "agents.is_employed",
                "agents.income",
                "firms.labor_count",
            ),
        ),
        (
            "fourth_atom",
            "agents.employer_id",
            "employer_delta",
            "labor_market",
            (
                "agents.employer_id",
                "agents.is_employed",
                "agents.income",
                "agents.employer_id",
            ),
        ),
    )
    atoms = list(request.intervention_atoms)
    variable_map = dict(request.engine_plan[0].variable_map)
    for atom_id, causal_variable, engine_variable, kind, mechanism_variables in additions[: count - 2]:
        atoms.append(
            _atom(
                intervention_id=atom_id,
                causal_variable=causal_variable,
                engine_variable=engine_variable,
                value=1.0,
                world_model_record_ref=world_ref,
                mechanism_kind=kind,
                mechanism_variables=mechanism_variables,
            )
        )
        variable_map[causal_variable] = engine_variable
    ncm_spec = request.engine_plan[0].ncm_spec
    if count == 4:
        ncm_spec = ncm_spec.model_copy(
            update={"endogenous_vars": [*ncm_spec.endogenous_vars, "employer_delta"]}
        )
    plan = request.engine_plan[0].model_copy(
        update={"variable_map": variable_map, "ncm_spec": ncm_spec}
    )
    return request.model_copy(
        update={
            "intervention_atoms": tuple(atoms),
            "engine_plan": (plan,),
            "baseline_state": {"firm_survival": 0.0},
            "horizon": request.horizon.model_copy(update={"start": 0, "end": 0}),
        }
    )


def test_summary_distance_requires_one_declared_metric_set() -> None:
    """B25: a missing required moment cannot be treated as a zero-distance fit."""

    with pytest.raises(ValueError, match="required summary moments"):
        summary_distance(
            {"easy": 0.0},
            {"easy": 0.0, "hard": 100.0},
            required_moment_names=("easy", "hard"),
        )


def test_smm_missing_required_moment_cannot_win_calibration() -> None:
    """B25: removing a difficult required moment never improves SMM selection."""

    def runner(params: dict[str, float], seed: int | None) -> dict[str, float]:
        del seed
        if params["candidate"] == 0.0:
            return {"easy": 0.0}
        return {"easy": 0.0, "hard": 99.0}

    result = calibrate_coupled_smm(
        {"candidate": (0.0, 1.0)},
        runner,
        {"easy": 0.0, "hard": 100.0},
        required_moment_names=("easy", "hard"),
        seeds=(11, 13),
    )

    assert result.best_params == {"candidate": 1.0}
    missing = next(item for item in result.evaluated if item["params"] == {"candidate": 0.0})
    assert missing["loss"] == float("inf")
    assert missing["missing_moments"] == ("hard",)
    assert missing["moment_counts"] == {"easy": 2, "hard": 0}


def test_smm_all_incomparable_candidates_are_explicitly_blocked() -> None:
    """B25: all-infinite loss cannot select the first parameter combination."""

    result = calibrate_coupled_smm(
        {"candidate": (0.0, 1.0)},
        lambda params, seed: {"easy": float(params["candidate"])},
        {"easy": 0.0, "hard": 100.0},
        required_moment_names=("easy", "hard"),
        seeds=(11, 13),
    )

    assert result.best_params is None
    assert result.best_loss == float("inf")
    assert result.comparison_status == "no_comparable"
    assert result.status == "blocked"


def test_single_paired_draw_has_unestimated_standard_error() -> None:
    """B21: one stochastic draw cannot claim a measured zero standard error."""

    result = paired_monte_carlo_effect(
        lambda seed: {"welfare": float(seed)},
        lambda seed: {"welfare": float(seed + 2)},
        seeds=(7,),
        metric_names=("welfare",),
    )

    assert result.n_replications == 1
    assert result.standard_errors["welfare"] is None
    assert result.standard_error_status["welfare"] == "standard_error_not_estimated"


def test_paired_replicates_require_distinct_seeds() -> None:
    """B21: duplicate seeds are not independent replications."""

    with pytest.raises(ValueError, match="seeds must be unique"):
        paired_monte_carlo_effect(
            lambda seed: {"welfare": float(seed)},
            lambda seed: {"welfare": float(seed + 1)},
            seeds=(7, 7),
            metric_names=("welfare",),
        )


def test_joint_request_runs_each_requested_replication_with_distinct_seeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B21: request-level replication count and seed schedule reach the runner."""

    calls: list[int] = []

    def counted(state: Any, params: Any) -> dict[str, Any]:
        query = state["ncm_query_data"]
        calls.append(int(params["__seed__"]))
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {
                        "world_index": 0,
                        "firm_survival": {"mean": float(len(query.interventions))},
                    }
                ]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(counted))
    request = _request().model_copy(update={"seed": 17, "replications": 2})
    result = JointSimulationHorizonController().run(request)

    assert len(calls) == 6
    assert calls.count(17) == 3
    assert calls.count(18) == 3
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[0].engine_state["replication_count"] == 2
    assert joint.points[0].engine_state["replication_seeds"] == [17, 18]
    assert result.diagnostics["requested_replications"] == 2
    assert result.diagnostics["replication_seeds"] == [17, 18]


def test_ncm_evidence_none_and_explicit_empty_are_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B19: explicit empty evidence must not truthiness-fallback to baseline."""

    observed: list[dict[str, float]] = []

    def counted(state: Any, params: Any) -> dict[str, Any]:
        del params
        query = state["ncm_query_data"]
        observed.append(dict(query.evidence))
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {"world_index": 0, "firm_survival": {"mean": 1.0}}
                ]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(counted))
    controller = JointSimulationHorizonController()
    controller.run(_request().model_copy(update={"evidence_state": None}))
    controller.run(_request().model_copy(update={"evidence_state": {}}))

    assert observed[0] == {
        "income_delta": 0.0,
        "balance_delta": 0.0,
        "firm_survival": 1.0,
    }
    assert observed[3] == {}


def test_physical_run_ref_binds_effective_evidence_and_source_mode() -> None:
    """B23: cache identity includes effective NCM evidence and its source mode."""

    controller = JointSimulationHorizonController()
    baseline = {
        "income_delta": 0.0,
        "balance_delta": 0.0,
        "firm_survival": 1.0,
    }
    implicit_baseline = controller.run(
        _request().model_copy(update={"baseline_state": baseline, "evidence_state": None})
    )
    explicit_empty = controller.run(
        _request().model_copy(update={"baseline_state": baseline, "evidence_state": {}})
    )
    changed_baseline = controller.run(
        _request().model_copy(
            update={
                "baseline_state": {**baseline, "income_delta": 9.0},
                "evidence_state": None,
            }
        )
    )

    def joint_ref(result: Any) -> str:
        return result.trajectory_for(
            "joint", ("income_subsidy", "balance_grant")
        ).diagnostics["physical_run_ref"]

    refs = {
        joint_ref(implicit_baseline),
        joint_ref(explicit_empty),
        joint_ref(changed_baseline),
    }
    assert len(refs) == 3


def test_three_atom_controller_reports_real_higher_order_residual_and_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B26: a real three-atom run exposes order-three non-additivity."""

    expected_joint = {
        "income_delta": 1.0,
        "balance_delta": 1.0,
        "labor_count_delta": 1.0,
    }
    observed_interventions: list[dict[str, float]] = []

    def triple_only(state: Any, params: Any) -> dict[str, Any]:
        del params
        query = state["ncm_query_data"]
        observed_interventions.append(dict(query.interventions[0]))
        value = 1.0 if query.interventions == [expected_joint] else 0.0
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {"world_index": 0, "firm_survival": {"mean": value}}
                ]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(triple_only))
    request = _request_with_atom_count(3)
    request = request.model_copy(update={"baseline_state": {"firm_survival": 0.0}})

    result = JointSimulationHorizonController().run(request)

    assert len(observed_interventions) == 7
    assert observed_interventions.count(expected_joint) == 1
    assert result.higher_order_residuals == {"firm_survival": {0: 1.0}}
    assert result.feedback_classification.numeric_interaction == "non_additive"
    assert result.feedback_classification.checked_interaction_orders == (1, 2, 3)
    assert result.diagnostics["checked_interaction_orders"] == [1, 2, 3]


def test_complete_additive_three_atom_basis_remains_additive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B26 preserving control: complete singles/pairs/joint support additivity."""

    def additive_outcome(state: Any, params: Any) -> dict[str, Any]:
        del params
        intervention = state["ncm_query_data"].interventions[0]
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {
                        "world_index": 0,
                        "firm_survival": {"mean": float(sum(intervention.values()))},
                    }
                ]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(additive_outcome))

    result = JointSimulationHorizonController().run(_request_with_atom_count(3))

    assert result.feedback_classification.numeric_interaction == "additive"
    assert result.feedback_classification.checked_interaction_orders == (1, 2, 3)
    assert result.higher_order_residuals == {"firm_survival": {0: 0.0}}
    assert "interaction_evidence_incomplete" not in result.feedback_classification.limitations


def test_missing_pair_basis_is_unsupported_not_false_additivity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B26: every requested pair is required before an additive conclusion."""

    def fixed_outcome(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {"world_index": 0, "firm_survival": {"mean": 0.0}}
                ]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fixed_outcome))
    request = _request_with_atom_count(3)
    runners = dict(JointSimulationHorizonController()._engine_runners())
    original = runners["ncm_parallel_worlds"]

    def omit_one_pair(*args: Any, **kwargs: Any) -> tuple[SimulationTrajectory, ...]:
        trajectories = original(*args, **kwargs)
        return tuple(
            item
            for item in trajectories
            if not (
                item.run_level == "pairwise"
                and set(item.atom_ids) == {"income_subsidy", "third_atom"}
            )
        )

    controller = JointSimulationHorizonController()
    monkeypatch.setattr(
        controller,
        "_engine_runners",
        lambda: {**runners, "ncm_parallel_worlds": omit_one_pair},
    )

    result = controller.run(request)

    assert result.feedback_classification.numeric_interaction == "unsupported"
    assert "interaction_evidence_incomplete" in result.feedback_classification.limitations
    assert "eligible_joint_engine_missing" not in result.feedback_classification.limitations
    assert result.feedback_classification.checked_interaction_orders == (1,)
    assert result.higher_order_residuals == {}


@pytest.mark.parametrize("mutation", ["selected_outcome", "static_horizon_step"])
def test_selected_outcome_and_engine_horizon_are_part_of_the_basis(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B26: valid markers cannot replace outcome or engine-step coverage."""

    def fixed_outcome(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {"world_index": 0, "firm_survival": {"mean": 0.0}}
                ]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fixed_outcome))
    request = _request_with_atom_count(3)
    runners = dict(JointSimulationHorizonController()._engine_runners())
    original = runners["ncm_parallel_worlds"]

    def corrupt_joint_point(*args: Any, **kwargs: Any) -> tuple[SimulationTrajectory, ...]:
        trajectories = list(original(*args, **kwargs))
        joint_index = next(
            index for index, item in enumerate(trajectories) if item.run_level == "joint"
        )
        joint = trajectories[joint_index]
        point = joint.points[0]
        if mutation == "selected_outcome":
            point = point.model_copy(update={"outcomes": {}, "effect": {}})
        else:
            point = point.model_copy(update={"step": 1})
        trajectories[joint_index] = joint.model_copy(update={"points": (point,)})
        return tuple(trajectories)

    controller = JointSimulationHorizonController()
    monkeypatch.setattr(
        controller,
        "_engine_runners",
        lambda: {**runners, "ncm_parallel_worlds": corrupt_joint_point},
    )

    result = controller.run(request)

    assert result.feedback_classification.numeric_interaction == "unsupported"
    assert "interaction_evidence_incomplete" in result.feedback_classification.limitations
    assert "eligible_joint_engine_missing" not in result.feedback_classification.limitations
    assert result.feedback_classification.checked_interaction_orders == (1, 2)
    assert result.higher_order_residuals == {}


def test_static_ncm_multi_step_horizon_is_limited_not_additive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B26: preserve a static candidate run but limit incomplete horizon claims."""

    calls: list[None] = []

    def fixed_outcome(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        calls.append(None)
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {"world_index": 0, "firm_survival": {"mean": 0.0}}
                ]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fixed_outcome))
    request = _request_with_atom_count(2)
    request = request.model_copy(
        update={
            "horizon": request.horizon.model_copy(update={"end": 3})
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert request.horizon.steps() == (0, 1, 2, 3)
    assert result.engine_decisions[0].decision == "selected"
    assert result.engine_decisions[0].temporal_capability == "static"
    assert result.trajectories
    assert calls
    assert all(
        tuple(point.step for point in trajectory.points) == (0,)
        for trajectory in result.trajectories
    )
    assert result.feedback_classification.numeric_interaction == "unsupported"
    assert "interaction_evidence_incomplete" in result.feedback_classification.limitations
    assert "eligible_joint_engine_missing" not in result.feedback_classification.limitations
    assert any(
        issue.startswith("horizon_incomplete:")
        for issue in result.diagnostics["interaction_evidence_issues"]
    )


def test_static_ncm_single_step_horizon_remains_additive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B26: a genuinely single-point NCM request retains its measured result."""

    def fixed_outcome(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {"world_index": 0, "firm_survival": {"mean": 0.0}}
                ]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fixed_outcome))
    request = _request_with_atom_count(2)

    result = JointSimulationHorizonController().run(request)

    assert request.horizon.steps() == (0,)
    assert result.engine_decisions[0].decision == "selected"
    assert result.feedback_classification.numeric_interaction == "additive"
    assert result.feedback_classification.checked_interaction_orders == (1, 2)


def test_four_atom_cancellation_is_bounded_aggregate_not_additive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B26: pairwise plus aggregate order-three evidence cannot resolve cancellation."""

    def cancel_at_joint(state: Any, params: Any) -> dict[str, Any]:
        del params
        intervention = state["ncm_query_data"].interventions[0]
        value = (
            intervention.get("income_delta", 0.0)
            * intervention.get("balance_delta", 0.0)
            * intervention.get("labor_count_delta", 0.0)
            * (1.0 - intervention.get("employer_delta", 0.0))
        )
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {"world_index": 0, "firm_survival": {"mean": value}}
                ]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(cancel_at_joint))
    request = _request_with_atom_count(4).model_copy(
        update={"baseline_state": {"firm_survival": 0.0}}
    )

    result = JointSimulationHorizonController().run(request)

    assert result.feedback_classification.numeric_interaction == "unsupported"
    assert result.feedback_classification.checked_interaction_orders == (1, 2)
    assert result.higher_order_residuals == {"firm_survival": {0: 0.0}}
    assert any(
        "aggregate_order_3_plus" in limitation
        for limitation in result.feedback_classification.limitations
    )
    assert "eligible_joint_engine_missing" not in result.feedback_classification.limitations


def test_joint_simulation_requires_explicit_selected_outcome_baseline() -> None:
    """B19: missing comparator state must not silently become numeric zero."""

    request = _request().model_copy(update={"baseline_state": {}})

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(request)

    assert raised.value.code == "baseline_state_missing_for_outcome"


def test_explicit_comparator_makes_equal_scenarios_zero_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B19: a measured comparator, not zero, defines the effect origin."""

    def fixed_outcome(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {"world_index": 0, "firm_survival": {"mean": 100.0}},
                ],
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fixed_outcome))
    request = _request().model_copy(
        update={"baseline_state": {"firm_survival": 100.0}},
    )

    result = JointSimulationHorizonController().run(request)

    assert all(
        point.effect == {"firm_survival": 0.0}
        for trajectory in result.trajectories
        for point in trajectory.points
    )


def test_joint_simulation_reuses_physical_spec_across_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B23: the joint role reuses its identical pair calculation."""

    original = NCMEngineMethod.pure_step
    calls: list[dict[str, Any]] = []

    def counted(state: Any, params: Any) -> dict[str, Any]:
        calls.append(dict(params))
        return original(state, params)

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(counted))
    result = JointSimulationHorizonController().run(_request())

    assert len(calls) == 3
    pair_ref = result.trajectory_for("pairwise", ("income_subsidy", "balance_grant")).diagnostics[
        "physical_run_ref"
    ]
    joint_ref = result.trajectory_for("joint", ("income_subsidy", "balance_grant")).diagnostics[
        "physical_run_ref"
    ]
    assert pair_ref == joint_ref


def test_joint_residual_keeps_higher_order_interaction_visible() -> None:
    """B26: zero pairwise terms do not prove global additivity."""

    request = _request_with_atom_count(3).model_copy(
        update={"selected_outcomes": ("y",), "baseline_state": {"y": 0.0}}
    )
    atoms = tuple(atom.intervention_id for atom in request.intervention_atoms)
    trajectories = [
        SimulationTrajectory(
            run_level="individual",
            atom_ids=(atom,),
            engine_kind="method_registry_estimator",
            method_fqn="tests.sim03",
            objective_ref="objective://sim03",
            points=(TrajectoryPoint(step=0, outcomes={"y": 0.0}, effect={"y": 0.0}),),
        )
        for atom in atoms
    ]
    trajectories.extend(
        SimulationTrajectory(
            run_level="pairwise",
            atom_ids=pair,
            engine_kind="method_registry_estimator",
            method_fqn="tests.sim03",
            objective_ref="objective://sim03",
            points=(TrajectoryPoint(step=0, outcomes={"y": 0.0}, effect={"y": 0.0}),),
        )
        for pair in ((atoms[0], atoms[1]), (atoms[0], atoms[2]), (atoms[1], atoms[2]))
    )
    trajectories.append(
        SimulationTrajectory(
            run_level="joint",
            atom_ids=atoms,
            engine_kind="method_registry_estimator",
            method_fqn="tests.sim03",
            objective_ref="objective://sim03",
            points=(TrajectoryPoint(step=0, outcomes={"y": 1.0}, effect={"y": 1.0}),),
        )
    )

    coverage = _interaction_coverage(request, trajectories)
    residuals = _higher_order_residuals(request, coverage)

    assert residuals == {"y": {0: 1.0}}


def test_checked_interaction_orders_include_pairwise_two_atom_run() -> None:
    """B26: a two-atom pairwise run is evidence for orders one and two."""

    request = _request_with_atom_count(2).model_copy(
        update={"selected_outcomes": ("y",), "baseline_state": {"y": 0.0}}
    )
    atoms = tuple(atom.intervention_id for atom in request.intervention_atoms)
    trajectories = [
        SimulationTrajectory(
            run_level="individual",
            atom_ids=(atom,),
            engine_kind="method_registry_estimator",
            method_fqn="tests.sim03",
            objective_ref="objective://sim03",
            points=(TrajectoryPoint(step=0, outcomes={"y": 0.0}, effect={"y": 0.0}),),
        )
        for atom in atoms
    ]
    trajectories.append(
        SimulationTrajectory(
            run_level="pairwise",
            atom_ids=atoms,
            engine_kind="method_registry_estimator",
            method_fqn="tests.sim03",
            objective_ref="objective://sim03",
            points=(TrajectoryPoint(step=0, outcomes={"y": 0.0}, effect={"y": 0.0}),),
        )
    )

    coverage = _interaction_coverage(request, trajectories)
    assert _checked_interaction_orders(request, coverage) == (1, 2)
