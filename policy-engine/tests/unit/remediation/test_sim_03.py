"""Test-first witnesses for the SIM-03 estimation and joint-run contracts.

The tests deliberately exercise the observable seams for B19/B21/B23/B25/B26.
They remain an N/C-exclusive profile because the shared joint-simulation
fixture imports the native registry and numerical stack.
"""

from __future__ import annotations

import copy
import itertools
import math
import os
import sys
from decimal import Decimal
from fractions import Fraction
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.foundry.coupling.estimation import (
    calibrate_coupled_smm,
    paired_monte_carlo_effect,
    summary_distance,
)
from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.ir.analytics.ncm import ExogenousSpec, StructuralEquation
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    JointSimulationControllerError,
    JointSimulationHorizonController,
    SimulationTrajectory,
    TrajectoryPoint,
    _aggregate_replicated_trajectory,
    _checked_interaction_orders,
    _higher_order_residuals,
    _interaction_coverage,
)
from tests.unit.runtime.quality.test_joint_simulation_horizon import _atom, _request

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationRequest


def _single_step_ncm_request():
    """Align the static NCM fixture with a genuinely one-point request."""
    return _request().model_copy(update={"horizon": HorizonSpec(start=0, end=0, step=1)})


def _request_with_atom_count(count: int) -> Any:
    """Build a controlled NCM request with a single explicitly requested step."""

    if count not in {2, 3, 4}:
        raise ValueError("SIM-03 fixture supports two through four atoms")
    request = _single_step_ncm_request()
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
    for (
        atom_id,
        causal_variable,
        engine_variable,
        kind,
        mechanism_variables,
    ) in additions[: count - 2]:
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


def _request_with_interaction_multiplier(
    request: JointSimulationRequest, multiplier: float
) -> JointSimulationRequest:
    """Change only the NCM plan's cross-term coefficient for a physical run."""

    plan = request.engine_plan[0]
    spec = plan.ncm_spec
    if spec is None:
        raise AssertionError("SIM-03 fixture requires its NCM plan")
    updated_equations = []
    changed = False
    old_term = "(5.0 * income_delta * balance_delta)"
    new_term = f"({multiplier:.1f} * income_delta * balance_delta)"
    for equation in spec.structural_equations:
        if equation.variable != "firm_survival":
            updated_equations.append(equation)
            continue
        parameters = dict(equation.equation_params)
        expression = parameters.get("noise_expression")
        if not isinstance(expression, str) or expression.count(old_term) != 1:
            raise AssertionError("SIM-03 cross-term fixture no longer matches its source model")
        parameters["noise_expression"] = expression.replace(old_term, new_term, 1)
        updated_equations.append(equation.model_copy(update={"equation_params": parameters}))
        changed = True
    if not changed:
        raise AssertionError("SIM-03 fixture is missing its firm-survival equation")
    updated_spec = spec.model_copy(update={"structural_equations": updated_equations})
    updated_plan = plan.model_copy(update={"ncm_spec": updated_spec})
    return request.model_copy(update={"engine_plan": (updated_plan, *request.engine_plan[1:])})


_NATIVE_ATOM_VARIABLES = (
    "income_delta",
    "balance_delta",
    "labor_count_delta",
    "employer_delta",
)


def _native_expression_request(
    expression: str,
    *,
    atom_count: int = 2,
    observed_u: float | None = 0.0,
    replications: int = 2,
    seed: int = 7,
) -> JointSimulationRequest:
    """Build a one-step actual NCM with observed roots and optional outcome evidence."""

    request = _request_with_atom_count(atom_count)
    plan = request.engine_plan[0]
    spec = plan.ncm_spec
    if spec is None:
        raise AssertionError("SIM-03 fixture requires its NCM plan")
    equations = [
        equation for equation in spec.structural_equations if equation.variable != "firm_survival"
    ]
    exogenous = list(spec.exogenous_specs)
    if atom_count == 4:
        equations.append(
            StructuralEquation(
                variable="employer_delta",
                parents=[],
                exogenous="u_employer",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {}},
            )
        )
        exogenous.append(
            ExogenousSpec(variable="u_employer", associated_endogenous="employer_delta")
        )
    equations.append(
        StructuralEquation(
            variable="firm_survival",
            parents=list(_NATIVE_ATOM_VARIABLES[:atom_count]),
            exogenous="u_survival",
            equation_type="nonlinear",
            equation_params={"noise_expression": expression},
        )
    )
    spec = spec.model_copy(update={"structural_equations": equations, "exogenous_specs": exogenous})
    plan = plan.model_copy(update={"ncm_spec": spec})
    evidence = dict.fromkeys(_NATIVE_ATOM_VARIABLES[:atom_count], 0.0)
    if observed_u is not None:
        evidence["firm_survival"] = observed_u
    return request.model_copy(
        update={
            "engine_plan": (plan,),
            "evidence_state": evidence,
            "baseline_state": {"firm_survival": observed_u if observed_u is not None else 0.0},
            "replications": replications,
            "seed": seed,
        }
    )


def _with_native_conditional_comparator(
    request: JointSimulationRequest,
) -> JointSimulationRequest:
    """Opt into the same-model, same-evidence conditional contrast profile."""

    payload = request.model_dump(mode="python")
    payload["comparator_profile"] = {
        "schema_version": "policyos.runtime.ncm_conditional_comparator_profile.v1",
        "outcome_units": {"firm_survival": "declared_firm_survival_unit"},
    }
    return type(request).model_validate(payload)


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


def test_replicate_aggregator_retains_recomputable_sampling_error() -> None:
    """B21: actual selected-engine draws bind mean, seeds and sample error."""

    first = SimulationTrajectory(
        run_level="joint",
        atom_ids=("a", "b"),
        engine_kind="method_registry_estimator",
        method_fqn="tests.sim03",
        objective_ref="objective://sim03",
        points=(TrajectoryPoint(step=0, outcomes={"y": 1.0}, effect={"y": 0.5}),),
    )
    second = first.model_copy(
        update={"points": (TrajectoryPoint(step=0, outcomes={"y": 3.0}, effect={"y": 1.5}),)}
    )

    aggregate = _aggregate_replicated_trajectory((first, second), (13, 14), "sha256:run")

    point = aggregate.points[0]
    summary = point.replication_sampling
    assert summary is not None
    assert summary.status == "estimated"
    assert summary.replicate_count == 2
    assert summary.seeds == (13, 14)
    assert point.outcomes == {"y": 2.0}
    assert point.effect == {"y": 1.0}
    assert summary.outcomes_standard_error["y"] == pytest.approx(1.0)
    assert summary.effects_standard_error["y"] == pytest.approx(0.5)
    assert [sample.outcomes["y"] for sample in summary.samples] == [1.0, 3.0]


@pytest.mark.parametrize(
    ("values", "expected_mean", "expected_error"),
    [
        ((1e308, 1e308), 1e308, 0.0),
        ((0.0, 4e-162), 2e-162, 2e-162),
        ((0.0, 2e-300), 1e-300, 1e-300),
    ],
)
def test_replicate_aggregator_preserves_finite_extreme_scale_samples(
    values: tuple[float, float], expected_mean: float, expected_error: float
) -> None:
    """Finite large means and representable tiny sampling errors stay finite."""

    def trajectory(value: float) -> SimulationTrajectory:
        return SimulationTrajectory(
            run_level="joint",
            atom_ids=("a", "b"),
            engine_kind="method_registry_estimator",
            method_fqn="tests.sim03",
            objective_ref="objective://sim03",
            points=(TrajectoryPoint(step=0, outcomes={"y": value}, effect={"y": value}),),
        )

    result = _aggregate_replicated_trajectory(
        tuple(trajectory(value) for value in values), (7, 8), "sha256:run"
    )
    point = result.points[0]
    summary = point.replication_sampling
    assert summary is not None
    assert math.isfinite(point.outcomes["y"])
    assert point.outcomes["y"] == pytest.approx(
        expected_mean, rel=8 * sys.float_info.epsilon, abs=0
    )
    assert point.effect["y"] == pytest.approx(expected_mean, rel=8 * sys.float_info.epsilon, abs=0)
    assert summary.outcomes_standard_error["y"] == pytest.approx(
        expected_error, rel=8 * sys.float_info.epsilon, abs=0
    )
    assert summary.effects_standard_error["y"] == pytest.approx(
        expected_error, rel=8 * sys.float_info.epsilon, abs=0
    )


def test_replicate_aggregator_preserves_small_mean_after_large_cancellation() -> None:
    """The actual reducer retains a small finite sum and all three source draws."""

    values = (1e308, 1.0, -1e308)
    seeds = (7, 8, 9)
    trajectories = tuple(
        SimulationTrajectory(
            run_level="joint",
            atom_ids=("a", "b"),
            engine_kind="method_registry_estimator",
            method_fqn="tests.sim03",
            objective_ref="objective://sim03",
            points=(TrajectoryPoint(step=0, outcomes={"y": value}, effect={"y": value}),),
        )
        for value in values
    )
    result = _aggregate_replicated_trajectory(trajectories, seeds, "sha256:run")
    point = result.points[0]
    summary = point.replication_sampling
    assert summary is not None and summary.seeds == seeds
    assert point.outcomes["y"] == point.effect["y"] == 1.0 / 3.0
    assert [sample.outcomes["y"] for sample in summary.samples] == list(values)
    assert [sample.effects["y"] for sample in summary.samples] == list(values)
    expected_error = 1e308 / math.sqrt(3.0)
    assert summary.outcomes_standard_error["y"] == pytest.approx(
        expected_error, rel=8 * sys.float_info.epsilon, abs=0
    )
    assert summary.effects_standard_error["y"] == pytest.approx(
        expected_error, rel=8 * sys.float_info.epsilon, abs=0
    )


def test_replicate_aggregator_refuses_incomplete_or_nonfinite_draw_sets() -> None:
    """B21: malformed supplied members cannot shrink the requested denominator."""

    first = SimulationTrajectory(
        run_level="joint",
        atom_ids=("a", "b"),
        engine_kind="method_registry_estimator",
        method_fqn="tests.sim03",
        objective_ref="objective://sim03",
        points=(TrajectoryPoint(step=0, outcomes={"y": 1.0}, effect={"y": 0.5}),),
    )
    mismatched = first.model_copy(
        update={"points": (TrajectoryPoint(step=0, outcomes={"other": 2.0}, effect={"y": 1.0}),)}
    )
    with pytest.raises(JointSimulationControllerError) as mismatch:
        _aggregate_replicated_trajectory((first, mismatched), (13, 14), "sha256:run")
    assert mismatch.value.code == "simulation_replication_output_key_mismatch"

    nonfinite = first.model_copy(
        update={
            "points": (TrajectoryPoint(step=0, outcomes={"y": float("nan")}, effect={"y": 0.5}),)
        }
    )
    with pytest.raises(JointSimulationControllerError) as invalid:
        _aggregate_replicated_trajectory((nonfinite,), (13,), "sha256:run")
    assert invalid.value.code == "simulation_replication_output_non_finite"


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
    request = _single_step_ncm_request().model_copy(update={"seed": 17, "replications": 2})
    result = JointSimulationHorizonController().run(request)

    assert len(calls) == 6
    assert calls.count(17) == 3
    assert calls.count(18) == 3
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[0].engine_state["replication_count"] == 2
    assert joint.points[0].engine_state["replication_seeds"] == [17, 18]
    summary = joint.points[0].replication_sampling
    assert summary is not None
    assert summary.status == "estimated"
    assert summary.replicate_count == 2
    assert summary.seeds == (17, 18)
    assert summary.samples[0].outcomes == summary.samples[1].outcomes
    assert all(value == 0.0 for value in summary.outcomes_standard_error.values())
    assert result.diagnostics["requested_replications"] == 2
    assert result.diagnostics["replication_seeds"] == [17, 18]


def test_replication_failure_retains_prior_role_without_partial_aggregate(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B21: retain the completed role and the cause of the next role's failure."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.quality.generation_cycle import (
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )

    original = NCMEngineMethod.pure_step
    calls: list[int] = []

    def fail_second_role_draw(state: Any, params: Any) -> dict[str, Any]:
        seed = int(params["__seed__"])
        calls.append(seed)
        output = original(state, params)
        if len(calls) == 4:
            del output["counterfactual_result"]["world_summaries"][0]["firm_survival"]["mean"]
        return output

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fail_second_role_draw))
    request = _single_step_ncm_request().model_copy(update={"seed": 17, "replications": 2})
    result = JointSimulationHorizonController().run(request)

    assert calls == [17, 18, 17, 18]
    assert result.diagnostics["physical_work_interruption"] == "n5_physical_work_failed"
    assert len(result.trajectories) == 1
    completed = result.trajectory_for("individual", ("income_subsidy",))
    summary = completed.points[0].replication_sampling
    assert summary is not None and summary.seeds == (17, 18)
    assert [sample.seed for sample in summary.samples] == [17, 18]
    assert result.feedback_classification.numeric_interaction == "unsupported"
    events = result.physical_work_observations
    assert [(event.effective_seed, event.status) for event in events] == [
        (17, "completed"),
        (18, "completed"),
        (17, "completed"),
        (18, "failed"),
    ]
    assert events[-1].error_type == "JointSimulationControllerError"
    assert events[-1].error_code == "ncm_outcome_missing"
    assert events[-1].error_context == {"outcome": "firm_survival"}

    cas_path = tmp_path / "cas"
    writer = FileSystemCAS(cas_path)
    ref = persist_joint_simulation_result(result, store=writer)
    reader = FileSystemCAS(cas_path)
    reopened = load_joint_simulation_result(ref, store=reader, expected_request=request)
    assert reopened.trajectories == result.trajectories
    assert reopened.physical_work_observations[-1].error_code == "ncm_outcome_missing"
    assert reopened.physical_work_observations[-1].error_context == {"outcome": "firm_survival"}
    assert reopened.diagnostics["physical_work_interruption"] == "n5_physical_work_failed"


def test_n5_one_draw_is_not_reported_as_zero_sampling_error() -> None:
    """B21: one selected-engine draw cannot establish a numeric standard error."""

    result = JointSimulationHorizonController().run(_single_step_ncm_request())

    assert result.schema_version == "policyos.runtime.joint_simulation_horizon.v5"
    assert result.trajectories
    assert all(
        point.replication_sampling is not None
        and point.replication_sampling.status == "standard_error_not_estimated"
        and point.replication_sampling.replicate_count == 1
        and all(
            value is None for value in point.replication_sampling.outcomes_standard_error.values()
        )
        and all(
            value is None for value in point.replication_sampling.effects_standard_error.values()
        )
        for trajectory in result.trajectories
        for point in trajectory.points
    )


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
                "world_summaries": [{"world_index": 0, "firm_survival": {"mean": 1.0}}]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(counted))
    controller = JointSimulationHorizonController()
    controller.run(_single_step_ncm_request().model_copy(update={"evidence_state": None}))
    controller.run(_single_step_ncm_request().model_copy(update={"evidence_state": {}}))

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
        _single_step_ncm_request().model_copy(
            update={"baseline_state": baseline, "evidence_state": None}
        )
    )
    explicit_empty = controller.run(
        _single_step_ncm_request().model_copy(
            update={"baseline_state": baseline, "evidence_state": {}}
        )
    )
    changed_baseline = controller.run(
        _single_step_ncm_request().model_copy(
            update={
                "baseline_state": {**baseline, "income_delta": 9.0},
                "evidence_state": None,
            }
        )
    )

    def joint_ref(result: Any) -> str:
        return result.trajectory_for("joint", ("income_subsidy", "balance_grant")).diagnostics[
            "physical_run_ref"
        ]

    refs = {
        joint_ref(implicit_baseline),
        joint_ref(explicit_empty),
        joint_ref(changed_baseline),
    }
    assert len(refs) == 3


def test_physical_run_identity_binds_seed_and_plan_and_reexecutes_each_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B23: changed inputs get new refs; the same counted witness can remove either input."""

    original = NCMEngineMethod.pure_step
    observed_seeds: list[int] = []

    def counted(state: Mapping[str, object], params: Mapping[str, object]) -> dict[str, Any]:
        observed_seeds.append(int(params["__seed__"]))
        return original(state, params)

    removal_probe = os.environ.get(_REMOVAL_PROBE_ENV)
    if removal_probe not in {None, "seed", "plan"}:
        raise ValueError("B23 removal probe must be 'seed', 'plan', or unset")
    if removal_probe is not None:
        from polisyos.runtime.quality import (
            joint_simulation_horizon as joint_simulation,
        )

        original_hash = joint_simulation.gy_content_hash
        removed_fields = {"seed", "replication_seeds"} if removal_probe == "seed" else {"plan"}

        def hash_without_selected_input(payload: object) -> str:
            if isinstance(payload, dict) and frozenset(payload) == _PHYSICAL_RUN_IDENTITY_FIELDS:
                payload = {
                    key: value for key, value in payload.items() if key not in removed_fields
                }
            return original_hash(payload)

        monkeypatch.setattr(joint_simulation, "gy_content_hash", hash_without_selected_input)

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(counted))
    request = _single_step_ncm_request().model_copy(update={"seed": 17})
    changed_seed = request.model_copy(update={"seed": 18})
    changed_plan = _request_with_interaction_multiplier(request, 6.0)
    controller = JointSimulationHorizonController()

    results = (
        controller.run(request),
        controller.run(changed_seed),
        controller.run(changed_plan),
    )

    pair = ("income_subsidy", "balance_grant")
    role_views = []
    for result in results:
        pairwise = result.trajectory_for("pairwise", pair)
        joint = result.trajectory_for("joint", pair)
        assert pairwise.diagnostics["physical_run_ref"] == joint.diagnostics["physical_run_ref"]  # noqa: S101
        assert pairwise.diagnostics["physical_run_reused"] is False  # noqa: S101
        assert joint.diagnostics["physical_run_reused"] is True  # noqa: S101
        assert pairwise.points == joint.points  # noqa: S101
        role_views.append((pairwise, joint))

    base_pair, base_joint = role_views[0]
    seed_pair, seed_joint = role_views[1]
    plan_pair, plan_joint = role_views[2]
    physical_refs = {
        base_pair.diagnostics["physical_run_ref"],
        seed_pair.diagnostics["physical_run_ref"],
        plan_pair.diagnostics["physical_run_ref"],
    }
    assert len(physical_refs) == 3  # noqa: S101
    assert base_joint.method_fqn == seed_joint.method_fqn == plan_joint.method_fqn  # noqa: S101
    assert observed_seeds == [17] * 3 + [18] * 3 + [17] * 3  # noqa: S101
    assert (  # noqa: S101
        plan_joint.points[0].outcomes["firm_survival"]
        == pytest.approx(base_joint.points[0].outcomes["firm_survival"] + 1.0)
    )
    # _run_cached_replicates owns only an invocation-local cache: these are three
    # separate controller executions, each observed reaching the Foundry method.


_REMOVAL_PROBE_ENV = "POLISYOS_SIM03_PHYSICAL_IDENTITY_REMOVAL_PROBE"
_PHYSICAL_RUN_IDENTITY_FIELDS = frozenset(
    {
        "world_model_record_ref",
        "world_model_record_content_hash",
        "engine_kind",
        "method_fqn",
        "objective_ref",
        "horizon",
        "selected_outcomes",
        "seed",
        "replications",
        "replication_seeds",
        "evidence_state",
        "evidence_source",
        "plan",
        "runtime_refs",
        "atoms",
    }
)


def test_three_atom_controller_reports_real_higher_order_residual_and_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B26: retain the stubbed third-order residual without classifying it."""

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
                "world_summaries": [{"world_index": 0, "firm_survival": {"mean": value}}]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(triple_only))
    request = _request_with_atom_count(3)
    request = request.model_copy(
        update={"baseline_state": {"firm_survival": 0.0}, "replications": 2, "seed": 41}
    )

    result = JointSimulationHorizonController().run(request)

    assert len(observed_interventions) == 14
    assert observed_interventions.count(expected_joint) == 2
    assert result.higher_order_residuals == {"firm_survival": {0: 1.0}}
    residual = result.higher_order_residual_sampling["firm_survival"][0]
    assert residual.seeds == (41, 42)
    assert [sample.effects["derived_effect"] for sample in residual.samples] == [1.0, 1.0]
    assert residual.effects_standard_error["derived_effect"] == pytest.approx(0.0)
    assert result.feedback_classification.interaction_sampling_status == "estimated"
    assert result.feedback_classification.numeric_interaction == "unsupported"
    assert result.diagnostics["interaction_numerical_tolerance"] == {"status": "not_established"}
    assert result.feedback_classification.checked_interaction_orders == (1, 2, 3)
    assert result.diagnostics["checked_interaction_orders"] == [1, 2, 3]


def test_complete_additive_three_atom_basis_remains_additive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B26: a complete stubbed additive basis stays numerically visible but unqualified."""

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

    request = _request_with_atom_count(3).model_copy(update={"replications": 2, "seed": 41})
    result = JointSimulationHorizonController().run(request)

    assert result.feedback_classification.interaction_sampling_status == "estimated"
    assert result.feedback_classification.numeric_interaction_basis == (
        "finite_checked_model_point_estimate_only"
    )
    assert result.feedback_classification.numeric_interaction == "unsupported"
    assert result.diagnostics["interaction_numerical_tolerance"] == {"status": "not_established"}
    assert result.feedback_classification.checked_interaction_orders == (1, 2, 3)
    assert result.higher_order_residuals == {"firm_survival": {0: 0.0}}
    assert "interaction_evidence_incomplete" not in result.feedback_classification.limitations


def test_shared_seed_residual_cancellation_is_unsupported_despite_zero_mean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Paired +1/-1 joint residuals do not become additive after averaging."""

    expected_joint = {
        "income_delta": 1.0,
        "balance_delta": 1.0,
        "labor_count_delta": 1.0,
    }

    def cancelling_joint(state: Any, params: Any) -> dict[str, Any]:
        query = state["ncm_query_data"]
        seed = params["__seed__"]
        value = (1.0 if seed == 41 else -1.0) if query.interventions == [expected_joint] else 0.0
        return {
            "counterfactual_result": {
                "world_summaries": [{"world_index": 0, "firm_survival": {"mean": value}}]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(cancelling_joint))
    request = _request_with_atom_count(3).model_copy(update={"replications": 2, "seed": 41})
    result = JointSimulationHorizonController().run(request)

    assert result.higher_order_residuals == {"firm_survival": {0: 0.0}}
    summary = result.higher_order_residual_sampling["firm_survival"][0]
    assert summary.seeds == (41, 42)
    assert [sample.effects["derived_effect"] for sample in summary.samples] == [1.0, -1.0]
    assert summary.effects_standard_error["derived_effect"] == pytest.approx(1.0)
    assert result.feedback_classification.interaction_sampling_status == "estimated"
    assert result.feedback_classification.numeric_interaction == "unsupported"
    assert result.feedback_classification.numeric_interaction_basis == (
        "finite_checked_model_point_estimate_only"
    )
    assert (
        "interaction_numeric_classification_unsupported"
        in (result.promotion_ready_value_packet["authority_blockers"])
    )


@pytest.mark.parametrize("atom_count", [3, 4])
def test_all_pair_and_higher_order_sample_vectors_are_seed_paired_and_order_invariant(
    atom_count: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every identified scope uses common seeds and atom order cannot change vectors."""

    request = _request_with_atom_count(atom_count).model_copy(
        update={"replications": 2, "seed": 41}
    )
    engine_variable_by_atom = {
        atom.intervention_id: request.engine_plan[0].variable_map[
            atom.causal_do_expr.assignments[0].variable
        ]
        for atom in request.intervention_atoms
    }
    atom_ids = tuple(engine_variable_by_atom)
    varying_pair = frozenset(atom_ids[:2])
    varying_variables = frozenset(engine_variable_by_atom[atom_id] for atom_id in varying_pair)
    all_variables = frozenset(engine_variable_by_atom.values())

    def paired_interactions(state: Any, params: Any) -> dict[str, Any]:
        query = state["ncm_query_data"]
        seed = params["__seed__"]
        active_variables = frozenset(query.interventions[0])
        pair_value = (1.0 if seed == 41 else -1.0) if varying_variables <= active_variables else 0.0
        higher_order_value = (
            (2.0 if seed == 41 else -2.0) if active_variables == all_variables else 0.0
        )
        value = pair_value + higher_order_value
        return {
            "counterfactual_result": {
                "world_summaries": [{"world_index": 0, "firm_survival": {"mean": value}}]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(paired_interactions))
    controller = JointSimulationHorizonController()
    original = controller.run(request)
    permuted = controller.run(
        request.model_copy(
            update={"intervention_atoms": tuple(reversed(request.intervention_atoms))}
        )
    )

    expected_pair_vectors = {
        frozenset(pair): ([1.0, -1.0] if frozenset(pair) == varying_pair else [0.0, 0.0])
        for pair in itertools.combinations(atom_ids, 2)
    }

    def pair_vectors(result: Any) -> dict[frozenset[str], list[float]]:
        return {
            frozenset(term.atom_ids): [
                sample.effects["derived_effect"]
                for sample in term.replication_sampling_by_step[0].samples
            ]
            for term in result.interaction_terms
        }

    assert pair_vectors(original) == expected_pair_vectors
    assert pair_vectors(permuted) == expected_pair_vectors
    for result in (original, permuted):
        residual = result.higher_order_residual_sampling["firm_survival"][0]
        assert residual.seeds == (41, 42)
        assert [sample.effects["derived_effect"] for sample in residual.samples] == [2.0, -2.0]
        assert residual.effects_standard_error["derived_effect"] == pytest.approx(2.0)
        assert result.feedback_classification.interaction_sampling_status == "estimated"
        assert result.feedback_classification.numeric_interaction == "unsupported"
        if atom_count == 4:
            assert "aggregate_order_3_plus_not_identified" in (
                result.feedback_classification.limitations
            )


def test_missing_pair_basis_is_unsupported_not_false_additivity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B26: every requested pair is required before an additive conclusion."""

    def fixed_outcome(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "counterfactual_result": {
                "world_summaries": [{"world_index": 0, "firm_survival": {"mean": 0.0}}]
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
                "world_summaries": [{"world_index": 0, "firm_survival": {"mean": 0.0}}]
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

    if mutation == "selected_outcome":
        with pytest.raises(ValueError, match="replication_summary_output_keys_mismatch"):
            controller.run(request)
        return

    result = controller.run(request)

    assert result.feedback_classification.numeric_interaction == "unsupported"
    assert "interaction_evidence_incomplete" in result.feedback_classification.limitations
    assert "eligible_joint_engine_missing" not in result.feedback_classification.limitations
    assert result.feedback_classification.checked_interaction_orders == (1, 2)
    assert result.higher_order_residuals == {}


def test_static_ncm_multi_step_horizon_refuses_before_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B07: actual multi-step demand cannot be satisfied by static NCM output."""

    calls: list[None] = []

    def fixed_outcome(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        calls.append(None)
        return {
            "counterfactual_result": {
                "world_summaries": [{"world_index": 0, "firm_survival": {"mean": 0.0}}]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fixed_outcome))
    request = _request_with_atom_count(2)
    request = request.model_copy(update={"horizon": request.horizon.model_copy(update={"end": 3})})

    controller = JointSimulationHorizonController()
    runner_lookups: list[None] = []

    def runner_map() -> dict[str, object]:
        runner_lookups.append(None)
        return {}

    monkeypatch.setattr(controller, "_engine_runners", runner_map)
    result = controller.run(request)

    assert request.horizon.steps() == (0, 1, 2, 3)
    assert all(
        condition not in {"multi_period", "dynamic_horizon", "dynamic_scm"}
        for condition in request.engine_plan[0].eligibility_conditions
    )
    assert result.engine_decisions[0].decision == "unsupported"
    assert result.engine_decisions[0].reason == "static_engine_cannot_ground_dynamic_horizon"
    assert result.engine_decisions[0].blockers == ("static_engine_temporal_capability",)
    assert not result.trajectories
    assert calls == []
    assert runner_lookups == []
    assert result.receipt.calibration_status == "no_run"
    assert result.diagnostics["engine_run_claimed"] is False


def test_static_ncm_single_step_horizon_remains_additive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B26: retain a single-point result without qualifying a stubbed model."""

    def fixed_outcome(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "counterfactual_result": {
                "world_summaries": [{"world_index": 0, "firm_survival": {"mean": 0.0}}]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fixed_outcome))
    request = _request_with_atom_count(2).model_copy(update={"replications": 2})

    result = JointSimulationHorizonController().run(request)

    assert request.horizon.steps() == (0,)
    assert result.engine_decisions[0].decision == "selected"
    assert result.feedback_classification.interaction_sampling_status == "estimated"
    assert result.feedback_classification.numeric_interaction == "unsupported"
    assert result.interaction_terms[0].by_step == {0: 0.0}
    assert result.diagnostics["interaction_numerical_tolerance"] == {"status": "not_established"}
    assert result.feedback_classification.checked_interaction_orders == (1, 2)
    assert (
        "interaction_evidence_incomplete"
        not in result.promotion_ready_value_packet["authority_blockers"]
    )


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
                "world_summaries": [{"world_index": 0, "firm_survival": {"mean": value}}]
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

    request = _single_step_ncm_request().model_copy(update={"baseline_state": {}})

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(request)

    assert raised.value.code == "baseline_state_missing_for_outcome"


def test_unresolved_comparator_keeps_baseline_subtraction_candidate_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B19: numeric baseline subtraction is not a bound comparator effect."""

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
    request = _single_step_ncm_request().model_copy(
        update={
            "baseline_state": {"firm_survival": 100.0},
            "comparator_refs": ("comparator://caller-supplied-unresolved",),
        },
    )

    result = JointSimulationHorizonController().run(request)

    assert all(
        point.effect == {"firm_survival": 0.0}
        for trajectory in result.trajectories
        for point in trajectory.points
    )
    assert result.diagnostics["comparator_refs_status"] == "not_established"
    assert result.diagnostics["effect_basis_status"] == "not_established"
    assert result.diagnostics["effect_basis"] == "outcome_minus_request_baseline_state"
    assert (
        "simulation_effect_basis_not_established"
        in (result.promotion_ready_value_packet["authority_blockers"])
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
    result = JointSimulationHorizonController().run(_single_step_ncm_request())

    assert len(calls) == 3
    pairwise = result.trajectory_for("pairwise", ("income_subsidy", "balance_grant"))
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert pairwise.diagnostics["physical_run_ref"] == joint.diagnostics["physical_run_ref"]  # noqa: S101
    assert pairwise.diagnostics["physical_run_reused"] is False  # noqa: S101
    assert joint.diagnostics["physical_run_reused"] is True  # noqa: S101
    assert pairwise.points == joint.points  # noqa: S101


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


def test_checked_interaction_orders_do_not_invent_pairwise_order_for_one_atom() -> None:
    """B26 R3: an empty pair-combination set is not pairwise evidence."""

    two_atom_request = _request_with_atom_count(2)
    request = two_atom_request.model_copy(
        update={
            "intervention_atoms": two_atom_request.intervention_atoms[:1],
            "selected_outcomes": ("y",),
            "baseline_state": {"y": 0.0},
        }
    )
    atom = request.intervention_atoms[0].intervention_id
    trajectories = [
        SimulationTrajectory(
            run_level="individual",
            atom_ids=(atom,),
            engine_kind="method_registry_estimator",
            method_fqn="tests.sim03",
            objective_ref="objective://sim03",
            points=(TrajectoryPoint(step=0, outcomes={"y": 0.0}, effect={"y": 0.0}),),
        )
    ]

    coverage = _interaction_coverage(request, trajectories)

    assert _checked_interaction_orders(request, coverage) == (1,)


def test_one_atom_roles_share_one_physical_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    """B23: an individual and joint role retain one shared physical run."""
    calls = []

    def fixed_output(state: Any, params: Any) -> dict[str, Any]:
        calls.append(int(params["__seed__"]))
        return {"counterfactual_result": {"world_summaries": [{"firm_survival": {"mean": 7.0}}]}}

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fixed_output))
    original = _single_step_ncm_request()
    request = original.model_copy(update={"intervention_atoms": original.intervention_atoms[:1]})
    result = JointSimulationHorizonController().run(request)
    individual = result.trajectory_for("individual", ("income_subsidy",))
    joint = result.trajectory_for("joint", ("income_subsidy",))
    assert calls == [request.seed]
    assert individual.diagnostics["physical_run_ref"] == joint.diagnostics["physical_run_ref"]
    assert individual.diagnostics["role"] == "individual"
    assert joint.diagnostics["role"] == "joint"
    assert individual.points[0].outcomes == {"firm_survival": 7.0}
    assert joint.points[0].effect == {"firm_survival": 6.0}


def test_fixed_evidence_changed_baseline_rebinds_effect_on_fresh_cas(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B23: equal raw inputs can share physical identity, never a stale projected effect."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )

    calls = []

    def fixed_output(state: Any, params: Any) -> dict[str, Any]:
        calls.append(dict(state["ncm_query_data"].evidence))
        return {"counterfactual_result": {"world_summaries": [{"firm_survival": {"mean": 7.0}}]}}

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fixed_output))
    base = _single_step_ncm_request().model_copy(update={"evidence_state": {"firm_survival": 3.0}})
    changed_baseline = base.model_copy(
        update={"baseline_state": {**base.baseline_state, "firm_survival": 2.0}}
    )
    changed_evidence = base.model_copy(update={"evidence_state": {"firm_survival": 4.0}})
    controller = JointSimulationHorizonController()
    results = tuple(
        controller.run(request) for request in (base, changed_baseline, changed_evidence)
    )
    first, second, third = [
        r.trajectory_for("joint", ("income_subsidy", "balance_grant")) for r in results
    ]
    assert len(calls) == 9
    assert first.points[0].outcomes == second.points[0].outcomes == {"firm_survival": 7.0}
    assert first.points[0].effect == {"firm_survival": 6.0}
    assert second.points[0].effect == {"firm_survival": 5.0}
    assert first.diagnostics["physical_run_ref"] == second.diagnostics["physical_run_ref"]
    assert first.diagnostics["physical_run_ref"] != third.diagnostics["physical_run_ref"]
    assert results[0].receipt.payload_hash != results[1].receipt.payload_hash
    store = FileSystemCAS(tmp_path / "cas")
    first_ref = persist_joint_simulation_result(results[0], store=store)
    second_ref = persist_joint_simulation_result(results[1], store=store)
    assert first_ref.manifest_profile_sha256 and second_ref.manifest_profile_sha256
    assert first_ref.artifact_id != second_ref.artifact_id
    reopened_first = load_joint_simulation_result(first_ref, store=store, expected_request=base)
    reopened_second = load_joint_simulation_result(
        second_ref, store=store, expected_request=changed_baseline
    )
    assert reopened_first.trajectory_for("joint", ("income_subsidy", "balance_grant")).points[
        0
    ].effect == {"firm_survival": 6.0}
    assert reopened_second.trajectory_for("joint", ("income_subsidy", "balance_grant")).points[
        0
    ].effect == {"firm_survival": 5.0}
    with pytest.raises(
        GenerationCycleError, match="joint_simulation_result_execution_binding_invalid"
    ):
        load_joint_simulation_result(first_ref, store=store, expected_request=changed_baseline)


def _native_no_op(request: JointSimulationRequest, seed: int) -> float:
    """Execute the registered NCM's baseline world at the requested seed."""
    from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData

    spec = request.engine_plan[0].ncm_spec
    assert spec is not None and request.evidence_state is not None
    assignments = dict.fromkeys(_NATIVE_ATOM_VARIABLES[: len(request.intervention_atoms)], 0.0)
    result = NCMEngineMethod.pure_step(
        {
            "ncm_query_data": NCMQueryData(
                ncm_spec=spec,
                evidence=request.evidence_state,
                interventions=[assignments],
                query_vars=["firm_survival"],
                n_samples=1,
            )
        },
        {"__seed__": seed},
    )
    return float(result["counterfactual_result"]["world_summaries"][0]["firm_survival"]["mean"])


def _persist_and_reopen_native_result(result: Any, request: Any, cas_path: Any) -> Any:
    """Round-trip the selected N5 artifact through a fresh store instance."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.quality.generation_cycle import (
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )

    writer = FileSystemCAS(cas_path)
    ref = persist_joint_simulation_result(result, store=writer)
    assert ref.manifest_profile_sha256
    reader = FileSystemCAS(cas_path)
    reopened = load_joint_simulation_result(ref, store=reader, expected_request=request)
    assert reopened.schema_version == "policyos.runtime.joint_simulation_horizon.v5"
    return reopened


def _assert_native_numeric_contract(
    result: Any,
    *,
    expression: str,
    observed_noise: float,
    parents: tuple[str, ...],
    residual_kind: str,
    expected_ideal: Fraction,
    actual_residual: float,
) -> None:
    """Compare the selected v5 arithmetic profile to an independent rational oracle."""

    projection = result.diagnostics["interaction_numerical_tolerance"]
    assert projection["status"] == "qualified"
    contract = projection["contract"]
    assert contract["schema_version"] == "policyos.runtime.ncm_interaction_numeric_contract.v1"
    assert contract["profile_version"] == "ncm_scalar_polynomial_binary64.v1"
    assert contract["scope"] == "one_step_fixed_input_additive_noise_polynomial_arithmetic_only"
    assert contract["expression"] == expression
    assert contract["outcome"] == "firm_survival"
    assert contract["outcome_unit"] == "declared_firm_survival_unit"
    assert contract["outcome_units_status"] == "declared_not_independently_grounded"
    assert contract["abduction_error_status"] == "not_established"
    assert contract["observed_noise"] == observed_noise
    assert contract["parent_names"] == list(parents)
    assert contract["atom_ids"] == list(result.atom_ids)
    assert {
        "abduction_requires_independent_verification",
        "external_units_not_grounded",
        "stochastic_inference_not_established",
    }.issubset(contract["limitations"])
    residual = next(item for item in contract["residuals"] if item["kind"] == residual_kind)
    assert residual["atom_ids"] == list(result.atom_ids)
    ideal = residual["ideal"]
    assert Fraction(ideal["numerator"], ideal["denominator"]) == expected_ideal
    bound = residual["absolute_roundoff_bound"]
    assert math.isfinite(bound) and bound >= 0.0
    assert abs(Fraction.from_float(actual_residual) - expected_ideal) <= Fraction.from_float(bound)


@pytest.mark.parametrize("observed_u", [0.0, 1.0, -1.0])
@pytest.mark.parametrize("interaction_coefficient", [4, 0])
@pytest.mark.parametrize("with_comparator", [False, True])
def test_native_integer_model_abduction_and_joint_effects(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
    observed_u: float,
    interaction_coefficient: int,
    with_comparator: bool,
) -> None:
    """Actual NCM abduction and common-seed worlds match an exact integer oracle."""
    from polisyos.foundry.methods.catalog.causal import ncm_engine

    expression = (
        "u + 2 * income_delta + 3 * balance_delta "
        f"+ {interaction_coefficient} * income_delta * balance_delta"
    )
    request = _native_expression_request(expression, observed_u=observed_u)
    if with_comparator:
        request = _with_native_conditional_comparator(request)
    expected_evidence = {"income_delta": 0.0, "balance_delta": 0.0, "firm_survival": observed_u}
    seen_abductions: list[tuple[dict[str, float], dict[str, float]]] = []
    original_abduction = ncm_engine._abduce_exogenous

    def observe_abduction(*args: Any, **kwargs: Any) -> dict[str, float]:
        abducted = original_abduction(*args, **kwargs)
        seen_abductions.append((dict(args[1]), dict(abducted)))
        return abducted

    monkeypatch.setattr(ncm_engine, "_abduce_exogenous", observe_abduction)
    baseline = _native_no_op(request, seed=7)
    result = JointSimulationHorizonController().run(request)
    reopened = _persist_and_reopen_native_result(result, request, tmp_path / "cas")

    assert baseline - observed_u == 0.0
    assert seen_abductions
    assert all(evidence == expected_evidence for evidence, _ in seen_abductions)
    assert all(abducted["firm_survival"] == observed_u for _, abducted in seen_abductions)
    first = reopened.trajectory_for("individual", ("income_subsidy",))
    second = reopened.trajectory_for("individual", ("balance_grant",))
    pair = reopened.trajectory_for("pairwise", ("income_subsidy", "balance_grant"))
    joint = reopened.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert first.points[0].outcomes["firm_survival"] - baseline == 2.0
    assert second.points[0].outcomes["firm_survival"] - baseline == 3.0
    assert joint.points[0].outcomes["firm_survival"] - baseline == 5.0 + interaction_coefficient
    assert first.points[0].effect["firm_survival"] == 2.0
    assert second.points[0].effect["firm_survival"] == 3.0
    assert joint.points[0].effect["firm_survival"] == 5.0 + interaction_coefficient
    assert reopened.interaction_terms[0].by_step == {0: float(interaction_coefficient)}
    assert pair.diagnostics["physical_run_ref"] == joint.diagnostics["physical_run_ref"]
    assert pair.points == joint.points
    assert reopened.feedback_classification.numeric_interaction == (
        ("non_additive" if interaction_coefficient else "additive")
        if with_comparator
        else "unsupported"
    )
    if with_comparator:
        _assert_native_numeric_contract(
            reopened,
            expression=expression,
            observed_noise=observed_u,
            parents=("income_delta", "balance_delta"),
            residual_kind="pairwise",
            expected_ideal=Fraction(interaction_coefficient),
            actual_residual=reopened.interaction_terms[0].by_step[0],
        )
        assert result.comparator_refs_verified is False
        assert reopened.comparator_refs_verified is True
        assert reopened.diagnostics["effect_basis_status"] == "established"
        assert reopened.diagnostics["comparator_refs_status"] == "selected_manifest_required"
        assert (
            "simulation_only_k_sim_not_world_evidence"
            in reopened.promotion_ready_value_packet["authority_blockers"]
        )
        comparator = reopened.diagnostics["ncm_conditional_comparator"]
        assert comparator["schema_version"] == "policyos.runtime.ncm_conditional_comparator.v1"
        assert comparator["estimand"] == "conditional_model_outcome_difference.v1"
        basis = comparator["request"]
        assert basis["world_model_record_content_hash"] == request.world_model_record.content_hash
        assert basis["engine_plan"] == request.engine_plan[0].model_dump(mode="json")
        assert basis["horizon"] == request.horizon.model_dump(mode="json")
        assert basis["outcome_units"] == {"firm_survival": "declared_firm_survival_unit"}
        assert basis["outcome_units_status"] == "declared_candidate_not_independently_grounded"
        assert basis["evidence_state"] == expected_evidence
        assert basis["replication_seeds"] == [7, 8]
        actual_input = comparator["input"]
        spec = request.engine_plan[0].ncm_spec
        assert spec is not None
        assert actual_input["ncm_spec"] == spec.model_dump(mode="json")
        assert actual_input["evidence"] == expected_evidence
        assert actual_input["interventions"] == [{}]
        assert actual_input["query_vars"] == ["firm_survival"]
        assert actual_input["n_samples"] == 1
        samples = comparator["result"]["samples"]
        assert [sample["seed"] for sample in samples] == [7, 8]
        assert [sample["outcomes"]["firm_survival"] for sample in samples] == [
            observed_u,
            observed_u,
        ]
        work = {event.event_id: event for event in reopened.physical_work_observations}
        for sample in samples:
            event = work[sample["physical_work_event_id"]]
            assert event.effective_seed == sample["seed"] and event.status == "completed"
        for trajectory, expected in (
            (first, 2.0),
            (second, 3.0),
            (joint, float(5 + interaction_coefficient)),
        ):
            sampling = trajectory.points[0].replication_sampling
            assert sampling is not None and sampling.seeds == (7, 8)
            assert [sample.effects["firm_survival"] for sample in sampling.samples] == [
                expected,
                expected,
            ]
            assert sampling.effects_standard_error["firm_survival"] == 0.0
    else:
        assert reopened.diagnostics["effect_basis_status"] == "not_established"
        assert reopened.diagnostics["interaction_numerical_tolerance"] == {
            "status": "not_established"
        }


def test_native_three_and_four_atom_interaction_scope(tmp_path: Any) -> None:
    """The actual model exposes a third-order term and bounds the 4+ conclusion."""
    triple_expression = "u + income_delta * balance_delta * labor_count_delta"
    triple = _with_native_conditional_comparator(
        _native_expression_request(triple_expression, atom_count=3)
    )
    result = JointSimulationHorizonController().run(triple)
    reopened = _persist_and_reopen_native_result(result, triple, tmp_path / "triple-cas")
    assert all(term.by_step == {0: 0.0} for term in reopened.interaction_terms)
    assert reopened.higher_order_residuals == {"firm_survival": {0: 1.0}}
    assert reopened.feedback_classification.checked_interaction_orders == (1, 2, 3)
    assert reopened.feedback_classification.numeric_interaction == "non_additive"
    _assert_native_numeric_contract(
        reopened,
        expression=triple_expression,
        observed_noise=0.0,
        parents=_NATIVE_ATOM_VARIABLES[:3],
        residual_kind="order_three",
        expected_ideal=Fraction(1),
        actual_residual=reopened.higher_order_residuals["firm_survival"][0],
    )

    four_expression = "u + income_delta * balance_delta * labor_count_delta * (1 - employer_delta)"
    four = _with_native_conditional_comparator(
        _native_expression_request(
            four_expression,
            atom_count=4,
        )
    )
    four_result = JointSimulationHorizonController().run(four)
    four_reopened = _persist_and_reopen_native_result(four_result, four, tmp_path / "four-cas")
    assert four_reopened.higher_order_residuals == {"firm_survival": {0: 0.0}}
    assert four_reopened.feedback_classification.numeric_interaction == "unsupported"
    assert four_reopened.feedback_classification.checked_interaction_orders == (1, 2)
    _assert_native_numeric_contract(
        four_reopened,
        expression=four_expression,
        observed_noise=0.0,
        parents=_NATIVE_ATOM_VARIABLES,
        residual_kind="aggregate_order_three_plus",
        expected_ideal=Fraction(0),
        actual_residual=four_reopened.higher_order_residuals["firm_survival"][0],
    )
    assert any(
        "aggregate_order_3_plus" in limitation
        for limitation in four_reopened.feedback_classification.limitations
    )

    # The unenumerated triple really has an effect, even though the four-way
    # joint cancels it. The controller's aggregate residual cannot rule it out.
    from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData

    spec = four.engine_plan[0].ncm_spec
    assert spec is not None and four.evidence_state is not None
    output = NCMEngineMethod.pure_step(
        {
            "ncm_query_data": NCMQueryData(
                ncm_spec=spec,
                evidence=four.evidence_state,
                interventions=[
                    {
                        "income_delta": 1.0,
                        "balance_delta": 1.0,
                        "labor_count_delta": 1.0,
                        "employer_delta": 0.0,
                    }
                ],
                query_vars=["firm_survival"],
                n_samples=1,
            )
        },
        {"__seed__": four.seed},
    )
    assert output["counterfactual_result"]["world_summaries"][0]["firm_survival"]["mean"] == 1.0


def test_native_numeric_profile_reissued_corruptions_fail_fresh_consumer(tmp_path: Any) -> None:
    """A valid reissued receipt cannot make a false profile or aggregate authoritative."""
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.ir.model_layer.canon import CanonSpec
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationResult,
        build_content_bound_simulation_receipt,
        verify_simulation_receipt,
    )

    expression = "u + income_delta * balance_delta * labor_count_delta"
    request = _with_native_conditional_comparator(
        _native_expression_request(expression, atom_count=3)
    )
    result = JointSimulationHorizonController().run(request)
    cas_path = tmp_path / "cas"
    writer = FileSystemCAS(cas_path)
    original_ref = persist_joint_simulation_result(result, store=writer)
    assert original_ref.manifest_profile_sha256
    original = load_joint_simulation_result(
        original_ref,
        store=FileSystemCAS.open_existing_read_only(cas_path),
        expected_request=request,
    )
    assert original.comparator_refs_verified is True
    assert original.feedback_classification.numeric_interaction == "non_additive"
    assert original.higher_order_residuals == {"firm_survival": {0: 1.0}}
    _assert_native_numeric_contract(
        original,
        expression=expression,
        observed_noise=0.0,
        parents=_NATIVE_ATOM_VARIABLES[:3],
        residual_kind="order_three",
        expected_ideal=Fraction(1),
        actual_residual=1.0,
    )
    original_manifest = writer.get_manifest(original_ref)
    original_payload = copy.deepcopy(result.content_bound_payload())
    verify_simulation_receipt(result.receipt, original_payload)

    for mutation in ("expression", "ideal", "bound", "aggregate"):
        payload = copy.deepcopy(original_payload)
        tolerance = payload["diagnostics"]["interaction_numerical_tolerance"]["contract"]
        residual = next(item for item in tolerance["residuals"] if item["kind"] == "order_three")
        if mutation == "expression":
            tolerance["expression"] += " * 2"
        elif mutation == "ideal":
            residual["ideal"]["numerator"] += 1
        elif mutation == "bound":
            residual["absolute_roundoff_bound"] = 1.0
        else:
            payload["higher_order_residuals"]["firm_survival"]["0"] = 0.0
            payload["feedback_classification"]["higher_order_residuals"]["firm_survival"]["0"] = 0.0
            payload["feedback_classification"]["numeric_interaction"] = "additive"
        reason = (
            "higher_order_residual_mean_recomputation_mismatch"
            if mutation == "aggregate"
            else "interaction_numeric_tolerance_recomputation_failed"
        )
        receipt = build_content_bound_simulation_receipt(
            engine_kind=result.receipt.engine_kind,
            payload=payload,
            diagnostics=payload["diagnostics"],
        )
        verify_simulation_receipt(receipt, payload)
        forged_payload = {**payload, "receipt": receipt.model_dump(mode="json")}
        with pytest.raises(ValueError, match=reason):
            JointSimulationResult.model_validate(forged_payload)

        # Keep the original exact selected comparator inputs; only the result
        # projection and its newly valid receipt differ from the proven base.
        forged_ref = writer.put_json(
            forged_payload,
            PutOptions(
                kind=original_manifest.kind,
                media_type=original_manifest.media_type,
                schema=original_manifest.artifact_schema,
                inputs=original_manifest.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True),
            return_selected_profile=True,
        )
        assert forged_ref.manifest_profile_sha256
        fresh_reader = FileSystemCAS.open_existing_read_only(cas_path)
        with pytest.raises(
            GenerationCycleError, match="joint_simulation_result_integrity_invalid"
        ) as failure:
            load_joint_simulation_result(forged_ref, store=fresh_reader, expected_request=request)
        assert failure.value.__cause__ is not None
        assert reason in str(failure.value.__cause__)


@pytest.mark.parametrize("mutation", ["mean", "standard_error"])
def test_native_unqualified_v5_reissued_tiny_aggregate_is_refused(
    tmp_path: Any, mutation: str
) -> None:
    """V5 rejects tiny forged moments while synthetic V4 retains its legacy tolerance."""
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.ir.model_layer.canon import CanonSpec
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationResult,
        build_content_bound_simulation_receipt,
        verify_simulation_receipt,
    )

    expression = "u + 4e-13 * income_delta" if mutation == "mean" else "1e-13 * u"
    request = _native_expression_request(
        expression,
        observed_u=0.0 if mutation == "mean" else None,
        replications=2 if mutation == "mean" else 3,
        seed=7,
    )
    request = request.model_copy(update={"intervention_atoms": request.intervention_atoms[:1]})
    result = JointSimulationHorizonController().run(request)
    cas_path = tmp_path / "cas"
    writer = FileSystemCAS(cas_path)
    original_ref = persist_joint_simulation_result(result, store=writer)
    original = load_joint_simulation_result(
        original_ref,
        store=FileSystemCAS.open_existing_read_only(cas_path),
        expected_request=request,
    )
    assert original.schema_version == "policyos.runtime.joint_simulation_horizon.v5"
    assert original.diagnostics["effect_basis_status"] == "not_established"
    assert original.diagnostics["interaction_numerical_tolerance"] == {"status": "not_established"}
    assert "ncm_conditional_comparator" not in original.diagnostics
    point = original.trajectory_for("individual", ("income_subsidy",)).points[0]
    summary = point.replication_sampling
    assert summary is not None
    draws = [sample.outcomes["firm_survival"] for sample in summary.samples]
    if mutation == "mean":
        assert draws == [4e-13, 4e-13]
        assert point.outcomes["firm_survival"] == point.effect["firm_survival"] == 4e-13
        reason = "replication_mean_recomputation_mismatch"
    else:
        assert len(set(draws)) == 3
        mean = math.fsum(draws) / len(draws)
        scale = max(abs(value) for value in draws)
        expected_se = scale * math.sqrt(
            math.fsum(((value - mean) / scale) ** 2 for value in draws)
            / (len(draws) * (len(draws) - 1))
        )
        assert 0.0 < expected_se < 1e-12
        assert summary.outcomes_standard_error["firm_survival"] == pytest.approx(
            expected_se, rel=32 * sys.float_info.epsilon, abs=0
        )
        reason = "replication_standard_error_recomputation_mismatch"

    original_manifest = writer.get_manifest(original_ref)
    payload = copy.deepcopy(result.content_bound_payload())
    verify_simulation_receipt(result.receipt, payload)
    for trajectory in payload["trajectories"]:
        assert trajectory["diagnostics"]["numeric_reduction_policy"] == "finite_binary64_mean.v1"
        forged_point = trajectory["points"][0]
        if mutation == "mean":
            forged_point["outcomes"]["firm_survival"] = 0.0
            forged_point["effect"]["firm_survival"] = 0.0
        else:
            forged_sampling = forged_point["replication_sampling"]
            forged_sampling["outcomes_standard_error"]["firm_survival"] = 0.0
            forged_sampling["effects_standard_error"]["firm_survival"] = 0.0
    if mutation == "mean":
        payload["marginal_effects"]["income_subsidy"]["0"]["firm_survival"] = 0.0

    def reissue_and_store(candidate: dict[str, Any], *, schema_version: str) -> Any:
        receipt = build_content_bound_simulation_receipt(
            engine_kind=result.receipt.engine_kind,
            payload=candidate,
            diagnostics=candidate["diagnostics"],
        )
        verify_simulation_receipt(receipt, candidate)
        signed = {**candidate, "receipt": receipt.model_dump(mode="json")}
        assert original_manifest.artifact_schema is not None
        ref = writer.put_json(
            signed,
            PutOptions(
                kind=original_manifest.kind,
                media_type=original_manifest.media_type,
                schema=original_manifest.artifact_schema.model_copy(
                    update={"version": schema_version}
                ),
                inputs=original_manifest.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True),
            return_selected_profile=True,
        )
        assert ref.manifest_profile_sha256
        return ref, signed

    forged_ref, forged_payload = reissue_and_store(payload, schema_version="5.0.0")
    with pytest.raises(ValueError, match=reason):
        JointSimulationResult.model_validate(forged_payload)
    with pytest.raises(
        GenerationCycleError, match="joint_simulation_result_integrity_invalid"
    ) as failure:
        load_joint_simulation_result(
            forged_ref,
            store=FileSystemCAS.open_existing_read_only(cas_path),
            expected_request=request,
        )
    assert failure.value.__cause__ is not None and reason in str(failure.value.__cause__)

    # This is a synthetic compatibility probe, not an assertion about any
    # historical artifact: V4 used an absolute tolerance for these moments.
    legacy = copy.deepcopy(payload)
    legacy["schema_version"] = "policyos.runtime.joint_simulation_horizon.v4"
    legacy["diagnostics"].pop("interaction_numerical_tolerance")
    for trajectory in legacy["trajectories"]:
        trajectory["diagnostics"].pop("numeric_reduction_policy")
    legacy_ref, legacy_payload = reissue_and_store(legacy, schema_version="4.0.0")
    assert JointSimulationResult.model_validate(legacy_payload).schema_version == (
        "policyos.runtime.joint_simulation_horizon.v4"
    )
    legacy_read = load_joint_simulation_result(
        legacy_ref, store=FileSystemCAS.open_existing_read_only(cas_path)
    )
    assert legacy_read.schema_version == "policyos.runtime.joint_simulation_horizon.v4"
    legacy_point = legacy_read.trajectory_for("individual", ("income_subsidy",)).points[0]
    assert legacy_point.replication_sampling is not None
    assert [
        sample.outcomes["firm_survival"] for sample in legacy_point.replication_sampling.samples
    ] == draws
    if mutation == "mean":
        assert legacy_point.outcomes["firm_survival"] == 0.0
    else:
        assert legacy_point.replication_sampling.outcomes_standard_error["firm_survival"] == 0.0


def test_native_scaled_model_has_declared_rounding_bound_and_mutation() -> None:
    """Decimal unit scaling uses a bounded binary64 error, not a significance rule.

    With u=0 and a,b in {0,1}, the integer inner sum is exact and at most 9.
    Representing 0.1, one multiplication and two residual subtractions are
    bounded by 8 * epsilon in output units (all magnitudes are at most 1).
    The exact decimal effects are .2, .3, .9 and .4; rel_tol is zero.
    """

    bound = 8 * sys.float_info.epsilon
    expression = (
        "u + 0.1 * (2 * income_delta + 3 * balance_delta + 4 * income_delta * balance_delta)"
    )
    request = _native_expression_request(expression)
    result = JointSimulationHorizonController().run(request)
    first = result.trajectory_for("individual", ("income_subsidy",)).points[0]
    second = result.trajectory_for("individual", ("balance_grant",)).points[0]
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant")).points[0]
    assert first.effect["firm_survival"] == pytest.approx(0.2, rel=0, abs=bound)
    assert second.effect["firm_survival"] == pytest.approx(0.3, rel=0, abs=bound)
    assert joint.effect["firm_survival"] == pytest.approx(0.9, rel=0, abs=bound)
    interaction = result.interaction_terms[0].by_step[0]
    assert interaction == pytest.approx(0.4, rel=0, abs=bound)

    changed = _native_expression_request(expression.replace("+ 4 *", "+ 4.001 *"))
    changed_result = JointSimulationHorizonController().run(changed)
    changed_interaction = changed_result.interaction_terms[0].by_step[0]
    assert changed_interaction == pytest.approx(0.4001, rel=0, abs=bound)
    assert abs(changed_interaction - interaction) > bound


@pytest.mark.parametrize("coefficient", [4, 0])
def test_native_tiny_unit_scale_preserves_interaction_classification(
    tmp_path: Any, coefficient: int
) -> None:
    """A real 4e-13 residual survives the numerical tolerance after CAS read.

    Binary64, one step, two paired seeds, evidence a=b=y=0, dimensionless a/b,
    and one declared outcome unit: y=u+1e-13*(2a+3b+k*a*b). Exact decimal
    effects are 2e-13, 3e-13 and (5+k)e-13; the interaction is k*1e-13.
    The absolute rounding bound is 8*epsilon*1e-12 output units, accounting
    for the 1e-13 representation, scaled multiplication and residual
    subtractions with magnitudes below 1e-12. It is not a significance rule.
    """

    expression = (
        "u + 1e-13 * (2 * income_delta + 3 * balance_delta "
        f"+ {coefficient} * income_delta * balance_delta)"
    )
    request = _with_native_conditional_comparator(_native_expression_request(expression))
    result = JointSimulationHorizonController().run(request)
    reopened = _persist_and_reopen_native_result(result, request, tmp_path / "cas")
    bound = 8 * sys.float_info.epsilon * 1e-12
    first = reopened.trajectory_for("individual", ("income_subsidy",)).points[0]
    second = reopened.trajectory_for("individual", ("balance_grant",)).points[0]
    joint = reopened.trajectory_for("joint", ("income_subsidy", "balance_grant")).points[0]
    assert first.effect["firm_survival"] == pytest.approx(2e-13, rel=0, abs=bound)
    assert second.effect["firm_survival"] == pytest.approx(3e-13, rel=0, abs=bound)
    assert joint.effect["firm_survival"] == pytest.approx(
        (5 + coefficient) * 1e-13, rel=0, abs=bound
    )
    interaction = reopened.interaction_terms[0]
    assert interaction.by_step[0] == pytest.approx(coefficient * 1e-13, rel=0, abs=bound)
    assert (
        interaction.replication_sampling_by_step[0].effects_standard_error["derived_effect"] == 0.0
    )
    assert reopened.feedback_classification.numeric_interaction == (
        "non_additive" if coefficient else "additive"
    )
    _assert_native_numeric_contract(
        reopened,
        expression=expression,
        observed_noise=0.0,
        parents=("income_delta", "balance_delta"),
        residual_kind="pairwise",
        expected_ideal=Fraction(coefficient, 10**13),
        actual_residual=interaction.by_step[0],
    )


@pytest.mark.parametrize("with_comparator", [False, True])
def test_native_stochastic_draws_and_seed_pairing_survive_cas(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, with_comparator: bool
) -> None:
    """Actual unobserved NCM noise distinguishes seed work from seed labels.

    Profile: binary64, one step, one backend sample per seed, seeds 7/8/9,
    observed a=b=0, unobserved y, y=u+(2+u)*a. For the actual three draws,
    64*epsilon*max(1,max(abs(u))) bounds endpoint, paired difference, mean and
    centered L2/sample-SE arithmetic in output units; it is not an inference
    threshold. A three-draw witness does not establish statistical coverage.
    """
    from polisyos.foundry.methods.catalog.causal import ncm_engine

    request = _native_expression_request(
        "u + (2 + u) * income_delta", observed_u=None, replications=3, seed=7
    )
    if with_comparator:
        request = _with_native_conditional_comparator(request)
    seeds = (7, 8, 9)
    mutation = os.environ.get("POLISYOS_SIM03_NATIVE_DRAW_MUTATION")
    if mutation not in {None, "first_seed", "replay_first", "reverse_baseline"}:
        raise ValueError("unknown SIM-03 native draw mutation")

    original_step = NCMEngineMethod.pure_step
    original_prediction = ncm_engine._predict_from_abducted
    current_seed: list[int] = []
    traces: list[tuple[int, dict[str, float], dict[str, float], dict[str, float]]] = []
    first_outputs: dict[tuple[tuple[str, float], ...], dict[str, Any]] = {}
    observed_evidence: list[dict[str, float]] = []

    def trace_prediction(
        ncm: Any,
        abducted_u: dict[str, float],
        intervention: dict[str, float],
        order: Any,
        parents_map: Any,
        warnings: Any,
    ) -> dict[str, float]:
        values = original_prediction(ncm, abducted_u, intervention, order, parents_map, warnings)
        assert len(current_seed) == 1
        traces.append((current_seed[0], dict(intervention), dict(abducted_u), dict(values)))
        return values

    def trace_step(state: Any, params: Any) -> dict[str, Any]:
        requested_seed = int(params["__seed__"])
        query = state["ncm_query_data"]
        observed_evidence.append(dict(query.evidence))
        effective_params = dict(params)
        if mutation == "first_seed":
            effective_params["__seed__"] = seeds[0]
        elif mutation == "reverse_baseline" and query.interventions == [{}]:
            # Mutate the actual comparator dispatch: baseline samples are
            # produced under reversed seeds while retaining their seed labels.
            effective_params["__seed__"] = tuple(reversed(seeds))[seeds.index(requested_seed)]
        current_seed.append(requested_seed)
        try:
            output = original_step(state, effective_params)
        finally:
            current_seed.pop()
        key = tuple(sorted(query.interventions[0].items()))
        if requested_seed == seeds[0]:
            first_outputs[key] = copy.deepcopy(output)
        elif mutation == "replay_first":
            output = copy.deepcopy(first_outputs[key])
        return output

    monkeypatch.setattr(ncm_engine, "_predict_from_abducted", trace_prediction)
    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(trace_step))
    baseline = {seed: _native_no_op(request, seed) for seed in seeds}
    result = JointSimulationHorizonController().run(request)
    reopened = _persist_and_reopen_native_result(result, request, tmp_path / "cas")
    assert reopened.diagnostics["interaction_numerical_tolerance"] == {"status": "not_established"}

    # Three explicit baselines plus three distinct physical subsets for each
    # seed. Opt-in adds three paired baselines; pairwise/joint reuse a subset.
    calls_per_seed = 5 if with_comparator else 4
    assert len(traces) == len(observed_evidence) == len(seeds) * calls_per_seed
    assert all(sum(trace[0] == seed for trace in traces) == calls_per_seed for seed in seeds)
    assert all(
        evidence == {"income_delta": 0.0, "balance_delta": 0.0} for evidence in observed_evidence
    )
    baseline_key = {"income_delta": 0.0, "balance_delta": 0.0}
    policy_key = {"income_delta": 1.0}
    baseline_traces = {
        seed: noise for seed, intervention, noise, _ in traces if intervention == baseline_key
    }
    policy_traces = {
        seed: (noise, values)
        for seed, intervention, noise, values in traces
        if intervention == policy_key
    }
    assert set(baseline_traces) == set(policy_traces) == set(seeds)
    draws = {seed: baseline_traces[seed]["firm_survival"] for seed in seeds}
    assert len(set(draws.values())) == 3
    bound = 64 * sys.float_info.epsilon * max(1.0, *(abs(value) for value in draws.values()))
    individual = reopened.trajectory_for("individual", ("income_subsidy",))
    sampling = individual.points[0].replication_sampling
    assert sampling is not None and sampling.seeds == seeds
    actual_policy = {sample.seed: sample.outcomes["firm_survival"] for sample in sampling.samples}
    for seed in seeds:
        u = draws[seed]
        noise, values = policy_traces[seed]
        assert noise["firm_survival"] == u
        assert baseline[seed] == pytest.approx(u, rel=0, abs=bound)
        assert values["firm_survival"] == pytest.approx(2.0 + 2.0 * u, rel=0, abs=bound)
        assert actual_policy[seed] == pytest.approx(2.0 + 2.0 * u, rel=0, abs=bound)

    expected_effects = [2.0 + draws[seed] for seed in seeds]
    expected_mean = math.fsum(expected_effects) / len(seeds)
    expected_se = math.sqrt(
        math.fsum((value - expected_mean) ** 2 for value in expected_effects)
        / (len(seeds) * (len(seeds) - 1))
    )
    paired = paired_monte_carlo_effect(
        lambda seed: {"firm_survival": baseline[seed]},
        lambda seed: {"firm_survival": actual_policy[seed]},
        seeds=seeds,
        metric_names=("firm_survival",),
    )
    differences = [difference["firm_survival"] for difference in paired.paired_differences]
    assert differences == pytest.approx(expected_effects, rel=0, abs=bound)
    assert paired.mean_effects["firm_survival"] == pytest.approx(expected_mean, rel=0, abs=bound)
    assert paired.standard_errors["firm_survival"] == pytest.approx(expected_se, rel=0, abs=bound)
    assert expected_se > bound
    reversed_effects = [
        actual_policy[seed] - baseline[other]
        for seed, other in zip(seeds, reversed(seeds), strict=True)
    ]
    reversed_mean = math.fsum(reversed_effects) / len(seeds)
    reversed_se = math.sqrt(
        math.fsum((value - reversed_mean) ** 2 for value in reversed_effects)
        / (len(seeds) * (len(seeds) - 1))
    )
    assert reversed_mean == pytest.approx(expected_mean, rel=0, abs=bound)
    assert abs(reversed_se - expected_se) > bound
    if with_comparator:
        assert result.comparator_refs_verified is False
        assert reopened.comparator_refs_verified is True
        assert reopened.diagnostics["effect_basis_status"] == "established"
        assert reopened.diagnostics["comparator_refs_status"] == "selected_manifest_required"
        comparator = reopened.diagnostics["ncm_conditional_comparator"]
        samples = comparator["result"]["samples"]
        assert [sample["seed"] for sample in samples] == list(seeds)
        assert [sample["outcomes"]["firm_survival"] for sample in samples] == pytest.approx(
            [draws[seed] for seed in seeds], rel=0, abs=bound
        )
        assert [sample.effects["firm_survival"] for sample in sampling.samples] == pytest.approx(
            expected_effects, rel=0, abs=bound
        )
        assert individual.points[0].effect["firm_survival"] == pytest.approx(
            expected_mean, rel=0, abs=bound
        )
        assert sampling.effects_standard_error["firm_survival"] == pytest.approx(
            expected_se, rel=0, abs=bound
        )
        interaction = reopened.interaction_terms[0]
        assert interaction.by_step[0] == pytest.approx(0.0, rel=0, abs=bound)
        interaction_se = interaction.replication_sampling_by_step[0].effects_standard_error[
            "derived_effect"
        ]
        if interaction_se is not None and interaction_se > 0.0:
            assert reopened.feedback_classification.numeric_interaction == "unsupported"
    else:
        # The legacy scalar baseline is zero, so its candidate interaction is
        # -u rather than the same-model paired interaction of zero.
        interaction = reopened.interaction_terms[0]
        interaction_sampling = interaction.replication_sampling_by_step[0]
        assert [
            sample.effects["derived_effect"] for sample in interaction_sampling.samples
        ] == pytest.approx([-draws[seed] for seed in seeds], rel=0, abs=bound)
        assert interaction_sampling.effects_standard_error["derived_effect"] == pytest.approx(
            expected_se, rel=0, abs=bound
        )
        assert reopened.feedback_classification.numeric_interaction == "unsupported"
        assert reopened.diagnostics["effect_basis_status"] == "not_established"


def test_native_stochastic_interaction_with_positive_se_stays_unsupported(tmp_path: Any) -> None:
    """Positive interaction sampling error is not a significance decision.

    Binary64, one step, seeds 7/8/9, evidence a=b=0, unobserved outcome:
    y=u+(2+u)*a+u*a*b has exact paired interaction u. The error bound
    128*epsilon*max(1,max(abs(u))) covers expression evaluation, paired
    endpoint subtraction, interaction composition, and sample mean/SE;
    it does not confer statistical significance or empirical authority.
    """

    request = _with_native_conditional_comparator(
        _native_expression_request(
            "u + (2 + u) * income_delta + u * income_delta * balance_delta",
            observed_u=None,
            replications=3,
            seed=7,
        )
    )
    result = JointSimulationHorizonController().run(request)
    reopened = _persist_and_reopen_native_result(result, request, tmp_path / "cas")
    assert reopened.diagnostics["interaction_numerical_tolerance"] == {"status": "not_established"}
    baseline = reopened.diagnostics["ncm_conditional_comparator"]["result"]["samples"]
    assert [sample["seed"] for sample in baseline] == [7, 8, 9]
    draws = [sample["outcomes"]["firm_survival"] for sample in baseline]
    assert len(set(draws)) == 3
    bound = 128 * sys.float_info.epsilon * max(1.0, *(abs(value) for value in draws))
    mean = math.fsum(draws) / len(draws)
    standard_error = math.sqrt(
        math.fsum((value - mean) ** 2 for value in draws) / (len(draws) * (len(draws) - 1))
    )
    term = reopened.interaction_terms[0]
    sampling = term.replication_sampling_by_step[0]
    assert sampling.seeds == (7, 8, 9)
    assert [sample.effects["derived_effect"] for sample in sampling.samples] == pytest.approx(
        draws, rel=0, abs=bound
    )
    assert term.by_step[0] == pytest.approx(mean, rel=0, abs=bound)
    assert sampling.effects_standard_error["derived_effect"] == pytest.approx(
        standard_error, rel=0, abs=bound
    )
    assert standard_error > bound
    assert reopened.feedback_classification.numeric_interaction == "unsupported"


@pytest.mark.parametrize("atom_count", [1, 2])
def test_native_physical_identity_and_selected_cas_binding(
    atom_count: int, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same physics shares roles locally; seed, plan and evidence stay distinct."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )

    expression = "u + 2 * income_delta + 3 * balance_delta + 4 * income_delta * balance_delta"
    base = _native_expression_request(expression, replications=1)
    changed_plan = _native_expression_request(expression.replace("+ 4 *", "+ 5 *"), replications=1)
    changed_evidence = _native_expression_request(expression, observed_u=1.0, replications=1)
    if atom_count == 1:
        base = base.model_copy(update={"intervention_atoms": base.intervention_atoms[:1]})
        changed_plan = changed_plan.model_copy(
            update={"intervention_atoms": changed_plan.intervention_atoms[:1]}
        )
        changed_evidence = changed_evidence.model_copy(
            update={"intervention_atoms": changed_evidence.intervention_atoms[:1]}
        )
    changed_seed = base.model_copy(update={"seed": 8})
    requests = (base, base, changed_seed, changed_plan, changed_evidence)
    original = NCMEngineMethod.pure_step
    calls: list[int] = []

    def observe_step(state: Any, params: Any) -> dict[str, Any]:
        calls.append(int(params["__seed__"]))
        return original(state, params)

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(observe_step))
    controller = JointSimulationHorizonController()
    results = tuple(controller.run(request) for request in requests)
    per_invocation = 1 if atom_count == 1 else 3
    assert calls == [7] * per_invocation * 2 + [8] * per_invocation + [7] * per_invocation * 2
    ids = tuple(atom.intervention_id for atom in base.intervention_atoms)
    other_role = "individual" if atom_count == 1 else "pairwise"
    joints = [result.trajectory_for("joint", ids) for result in results]
    for result, joint in zip(results, joints, strict=True):
        alias = result.trajectory_for(other_role, ids)
        assert alias.diagnostics["physical_run_ref"] == joint.diagnostics["physical_run_ref"]
        assert alias.points == joint.points
        assert alias.diagnostics["role"] == other_role
        assert joint.diagnostics["role"] == "joint"
    refs = [joint.diagnostics["physical_run_ref"] for joint in joints]
    assert refs[0] == refs[1]
    assert len({refs[0], refs[2], refs[3], refs[4]}) == 4

    cas_path = tmp_path / "cas"
    writer = FileSystemCAS(cas_path)
    artifact_refs = tuple(
        persist_joint_simulation_result(result, store=writer) for result in results
    )
    assert all(ref.manifest_profile_sha256 for ref in artifact_refs)
    reader = FileSystemCAS(cas_path)
    reopened = tuple(
        load_joint_simulation_result(ref, store=reader, expected_request=request)
        for ref, request in zip(artifact_refs, requests, strict=True)
    )
    for altered_request in (changed_seed, changed_plan, changed_evidence):
        with pytest.raises(
            GenerationCycleError, match="joint_simulation_result_execution_binding_invalid"
        ):
            load_joint_simulation_result(
                artifact_refs[0], store=reader, expected_request=altered_request
            )
    reopened_refs = [
        item.trajectory_for("joint", ids).diagnostics["physical_run_ref"] for item in reopened
    ]
    assert reopened_refs == refs


@pytest.mark.parametrize("missing_part", ["request", "input", "result"])
def test_native_conditional_comparator_selected_closure_and_mismatch_refusals(
    tmp_path: Any, missing_part: str
) -> None:
    """A fresh reader resolves every selected comparator part and rejects drift."""
    from polisyos.core.artifacts import ArtifactRef, read_core_json_artifact
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.ir.model_layer.canon import CanonSpec, to_canonical_bytes
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )

    expression = "u + 2 * income_delta + 3 * balance_delta + 4 * income_delta * balance_delta"
    request = _with_native_conditional_comparator(_native_expression_request(expression))
    result = JointSimulationHorizonController().run(request)
    cas_path = tmp_path / "cas"
    ref = persist_joint_simulation_result(result, store=FileSystemCAS(cas_path))
    assert ref.manifest_profile_sha256
    reader = FileSystemCAS(cas_path)
    reopened = load_joint_simulation_result(ref, store=reader, expected_request=request)
    record = reopened.diagnostics["ncm_conditional_comparator"]
    manifest = reader.get_manifest(ref)
    names = ("request", "input", "result")
    edges = tuple(edge for edge in manifest.inputs if edge.role.startswith("ncm_comparator_"))
    assert tuple(edge.role for edge in edges) == tuple(f"ncm_comparator_{name}" for name in names)
    for index, (name, edge) in enumerate(zip(names, edges, strict=True)):
        assert edge.manifest_profile_sha256 is not None
        part_manifest = reader.get_manifest_by_profile(
            edge.artifact_id, edge.manifest_profile_sha256
        )
        assert tuple(part_manifest.inputs) == edges[:index]
        part_ref = ArtifactRef(
            artifact_id=edge.artifact_id,
            kind=part_manifest.kind,
            media_type=part_manifest.media_type,
            manifest_profile_sha256=edge.manifest_profile_sha256,
        )
        expected = {
            "schema_version": "policyos.runtime.ncm_conditional_comparator.v1",
            "estimand": "conditional_model_outcome_difference.v1",
            "part": name,
            "value": record[name],
        }
        selected = read_core_json_artifact(reader, part_ref)
        assert selected.selected_manifest_profile_sha256 == edge.manifest_profile_sha256
        assert selected.value == expected
        assert selected.raw_payload_bytes == to_canonical_bytes(
            expected, CanonSpec(forbid_floats=False, forbid_nan_inf=True)
        )

    changed_model = _with_native_conditional_comparator(
        _native_expression_request(expression.replace("+ 4 *", "+ 5 *"))
    )
    changed_time = request.model_copy(update={"horizon": HorizonSpec(start=1, end=1, step=1)})
    changed_seed = request.model_copy(update={"seed": 9})
    changed_evidence = _with_native_conditional_comparator(
        _native_expression_request(expression, observed_u=1.0)
    )
    for altered in (changed_model, changed_time, changed_seed, changed_evidence):
        with pytest.raises(
            GenerationCycleError, match="joint_simulation_result_execution_binding_invalid"
        ):
            load_joint_simulation_result(ref, store=reader, expected_request=altered)

    edge = edges[names.index(missing_part)]
    selected_path = reader._manifest_path_for_ref(edge.artifact_id, edge.manifest_profile_sha256)
    assert not selected_path.is_symlink() and selected_path.stat().st_nlink == 1
    selected_path.unlink()
    fresh_reader = FileSystemCAS(cas_path)
    with pytest.raises(GenerationCycleError) as failure:
        load_joint_simulation_result(ref, store=fresh_reader, expected_request=request)
    assert failure.value.code in {
        "joint_simulation_comparator_unavailable",
        "joint_simulation_result_integrity_invalid",
    }


def test_native_conditional_comparator_ignores_caller_scalar_baseline(tmp_path: Any) -> None:
    """Changing an unrelated caller scalar cannot replace the paired no-op."""

    expression = "u + 2 * income_delta + 3 * balance_delta + 4 * income_delta * balance_delta"
    request = _with_native_conditional_comparator(
        _native_expression_request(expression, observed_u=1.0)
    )
    changed = request.model_copy(update={"baseline_state": {"firm_survival": 100.0}})
    controller = JointSimulationHorizonController()
    first = _persist_and_reopen_native_result(controller.run(request), request, tmp_path / "first")
    second = _persist_and_reopen_native_result(
        controller.run(changed), changed, tmp_path / "second"
    )
    ids = ("income_subsidy", "balance_grant")
    first_joint = first.trajectory_for("joint", ids)
    second_joint = second.trajectory_for("joint", ids)
    assert (
        first_joint.diagnostics["physical_run_ref"] == second_joint.diagnostics["physical_run_ref"]
    )
    assert (
        first_joint.points[0].outcomes == second_joint.points[0].outcomes == {"firm_survival": 10.0}
    )
    assert first_joint.points[0].effect == second_joint.points[0].effect == {"firm_survival": 9.0}
    for result in (first, second):
        baseline_samples = result.diagnostics["ncm_conditional_comparator"]["result"]["samples"]
        assert [item["outcomes"]["firm_survival"] for item in baseline_samples] == [1.0, 1.0]


def test_native_decimal_derived_atom_records_binary64_boundary_and_refuses_underflow(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A derived Decimal survives request binding; nonzero underflow never executes."""
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.ir.analytics.interventions import (
        InterventionContext,
        NodeIntervention,
        QueryTarget,
        VariableAssignment,
        identification_plan_for_intervention,
    )
    from polisyos.ir.linker import link_trinity
    from polisyos.ir.model_layer.canon import CanonSpec
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        _joint_simulation_port_outcome,
        load_joint_simulation_result,
        persist_joint_simulation_result,
    )
    from polisyos.runtime.quality.intervention_atom_binding import (
        build_intervention_atom_binding,
        derive_candidate_scenario_numeric_atom,
        intervention_atom_target_selector_ref,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationResult,
        build_content_bound_simulation_receipt,
        verify_simulation_receipt,
    )
    from tests.unit.runtime.quality.test_joint_simulation_horizon import (
        _bundle,
        _intervention,
        _ref,
        _registries,
    )

    base_request = _native_expression_request("u + 2 * income_delta")
    intervention = _intervention(intervention_id="decimal_income", kind="adaptive_agent")
    intervention = type(intervention).model_validate(
        {
            **intervention.model_dump(mode="python"),
            "params": {
                "observation_space": ["agents.income"],
                "action_space": {"type": "continuous", "affects": ["agents.income"]},
                "utility": "linear",
            },
        }
    )
    linked_bundle, report = link_trinity(_bundle(intervention), _registries())
    assert report.ok, [issue.model_dump(mode="json") for issue in report.issues]
    linked = linked_bundle.bindings.interventions[0]
    assert linked.writes_slots == ["agents.income"]
    causal = NodeIntervention(assignments=(VariableAssignment(variable="agents.income", value=0),))
    source = build_intervention_atom_binding(
        problem_frame_ref=_ref("a"),
        policy_spec_ref=_ref("c"),
        intervention=intervention,
        linked_intervention=linked,
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
        world_model_record_ref=base_request.world_model_record_ref,
        producer_ref="test.sim03.decimal_income",
        operator_proof_type_map={"adaptive_agent": "node"},
        mechanism_variable_map={"adaptive_agent": ("agents.income",)},
        mechanism_config_overrides={"joint_simulation_engine_variable": "income_delta"},
    )
    original_source = source.model_dump(mode="json")

    def request_for(value: Decimal | int) -> JointSimulationRequest:
        derived = derive_candidate_scenario_numeric_atom(
            source, target_world_slot="agents.income", value=value
        )
        assert derived.content_hash != source.content_hash
        expected = str(value) if isinstance(value, Decimal) else value
        assert derived.causal_do_expr.assignments[0].value == expected
        assert derived.to_node_intervention().assignments[0].value == expected
        return _with_native_conditional_comparator(
            base_request.model_copy(update={"intervention_atoms": (derived,)})
        )

    request = request_for(Decimal("0.1"))
    source_assignment = request.intervention_atoms[0].causal_do_expr.assignments[0]
    assert source_assignment.value == "0.1"
    serialized_atom = request.model_dump(mode="json")["intervention_atoms"][0]["causal_do_expr"]
    assert serialized_atom["expression_payload"]["assignments"][0]["value"] == "0.1"
    result = JointSimulationHorizonController().run(request)
    reopened = _persist_and_reopen_native_result(result, request, tmp_path / "cas")
    assert reopened.diagnostics["effect_basis_status"] == "established"
    limitation = "decimal_source_preserved_binary64_input_backend_precision_not_established"
    limitations = reopened.diagnostics["intervention_numeric_limitations"]
    assert limitation in limitations
    assert limitation in reopened.promotion_ready_value_packet["authority_blockers"]
    outcome, blockers = _joint_simulation_port_outcome(reopened, request=request)
    assert outcome == "joint_simulated" and limitation in blockers
    record = reopened.diagnostics["ncm_conditional_comparator"]
    recorded_atom = record["request"]["intervention_atoms"][0]["causal_do_expr"]
    assert recorded_atom["assignments"][0]["value"] == "0.1"
    point = reopened.trajectory_for("individual", ("decimal_income",)).points[0]
    sampling = point.replication_sampling
    assert sampling is not None and sampling.seeds == (7, 8)
    inputs = [sample.engine_state["intervention"]["income_delta"] for sample in sampling.samples]
    assert inputs == [0.1, 0.1] and all(type(value) is float for value in inputs)
    # The nearest binary64 0.1 differs from exact 1/10 by less than half an ULP.
    error = abs(Fraction.from_float(inputs[0]) - Fraction(1, 10))
    assert Fraction(0) < error <= Fraction(1, 2**57)
    assert point.outcomes == point.effect == {"firm_survival": 0.2}
    assert [sample.outcomes["firm_survival"] for sample in sampling.samples] == [0.2, 0.2]
    assert reopened.comparator_refs_verified is True

    exact_request = request_for(Decimal("0.5"))
    assert exact_request.intervention_atoms[0].causal_do_expr.assignments[0].value == "0.5"
    exact_result = JointSimulationHorizonController().run(exact_request)
    exact_read = _persist_and_reopen_native_result(exact_result, exact_request, tmp_path / "exact")
    exact_point = exact_read.trajectory_for("individual", ("decimal_income",)).points[0]
    exact_sampling = exact_point.replication_sampling
    assert exact_sampling is not None
    exact_inputs = [
        sample.engine_state["intervention"]["income_delta"] for sample in exact_sampling.samples
    ]
    assert exact_inputs == [0.5, 0.5] and all(type(value) is float for value in exact_inputs)
    assert Fraction.from_float(exact_inputs[0]) == Fraction(1, 2)
    assert exact_point.outcomes == exact_point.effect == {"firm_survival": 1.0}
    assert exact_read.comparator_refs_verified is True
    assert limitation not in (exact_read.diagnostics.get("intervention_numeric_limitations") or ())
    assert limitation not in exact_read.promotion_ready_value_packet["authority_blockers"]
    exact_outcome, exact_blockers = _joint_simulation_port_outcome(
        exact_read, request=exact_request
    )
    assert exact_outcome == "joint_simulated" and limitation not in exact_blockers

    integer_limitation = "integer_source_preserved_binary64_input_backend_precision_not_established"
    integer_runs: dict[int, tuple[JointSimulationRequest, JointSimulationResult]] = {}
    for source_value, rounded in ((2**53 + 1, True), (2**53, False)):
        integer_request = request_for(source_value)
        assignment = integer_request.intervention_atoms[0].causal_do_expr.assignments[0].value
        assert type(assignment) is int and assignment == source_value
        atom = integer_request.model_dump(mode="json")["intervention_atoms"][0]["causal_do_expr"]
        serialized = atom["expression_payload"]["assignments"][0]["value"]
        assert type(serialized) is int and serialized == source_value

        integer_result = JointSimulationHorizonController().run(integer_request)
        integer_read = _persist_and_reopen_native_result(
            integer_result, integer_request, tmp_path / f"integer_{source_value}"
        )
        assert integer_read.comparator_refs_verified is True
        comparator = integer_read.diagnostics["ncm_conditional_comparator"]
        recorded = comparator["request"]["intervention_atoms"][0]["causal_do_expr"]
        recorded_value = recorded["assignments"][0]["value"]
        assert type(recorded_value) is int and recorded_value == source_value
        integer_point = integer_read.trajectory_for("individual", ("decimal_income",)).points[0]
        integer_sampling = integer_point.replication_sampling
        assert integer_sampling is not None and integer_sampling.seeds == (7, 8)
        integer_inputs = [
            sample.engine_state["intervention"]["income_delta"]
            for sample in integer_sampling.samples
        ]
        assert integer_inputs == [float(2**53), float(2**53)]
        assert all(type(value) is float for value in integer_inputs)
        assert (int(integer_inputs[0]) != source_value) is rounded
        assert integer_point.outcomes == integer_point.effect == {"firm_survival": float(2**54)}
        integer_diagnostics = integer_read.diagnostics.get("intervention_numeric_limitations") or ()
        assert (integer_limitation in integer_diagnostics) is rounded
        assert (
            integer_limitation in integer_read.promotion_ready_value_packet["authority_blockers"]
        ) is rounded
        integer_outcome, integer_blockers = _joint_simulation_port_outcome(
            integer_read, request=integer_request
        )
        assert integer_outcome == "joint_simulated"
        assert (integer_limitation in integer_blockers) is rounded
        integer_runs[source_value] = (integer_request, integer_result)

    rounded_request, rounded_result = integer_runs[2**53 + 1]
    # Reissue content-valid results with the same selected comparator inputs;
    # request-aware replay must reconstruct each missing limitation.
    for source_result, source_request, missing, cas_name in (
        (result, request, limitation, "reissued_decimal"),
        (rounded_result, rounded_request, integer_limitation, "reissued_integer"),
    ):
        cas_path = tmp_path / cas_name
        writer = FileSystemCAS(cas_path)
        original_ref = persist_joint_simulation_result(source_result, store=writer)
        original_manifest = writer.get_manifest(original_ref)
        payload = copy.deepcopy(source_result.content_bound_payload())
        assert missing in payload["diagnostics"].pop("intervention_numeric_limitations")
        authority = payload["promotion_ready_value_packet"]["authority_blockers"]
        assert missing in authority
        payload["promotion_ready_value_packet"]["authority_blockers"] = [
            blocker for blocker in authority if blocker != missing
        ]
        receipt = build_content_bound_simulation_receipt(
            engine_kind=source_result.receipt.engine_kind,
            payload=payload,
            diagnostics=payload["diagnostics"],
        )
        verify_simulation_receipt(receipt, payload)
        signed = {**payload, "receipt": receipt.model_dump(mode="json")}
        assert (
            JointSimulationResult.model_validate(signed).diagnostics.get(
                "intervention_numeric_limitations"
            )
            is None
        )
        assert original_manifest.artifact_schema is not None
        forged_ref = writer.put_json(
            signed,
            PutOptions(
                kind=original_manifest.kind,
                media_type=original_manifest.media_type,
                schema=original_manifest.artifact_schema,
                inputs=original_manifest.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True),
            return_selected_profile=True,
        )
        assert forged_ref.manifest_profile_sha256
        with pytest.raises(
            GenerationCycleError, match="joint_simulation_result_execution_binding_invalid"
        ) as failure:
            load_joint_simulation_result(
                forged_ref,
                store=FileSystemCAS.open_existing_read_only(cas_path),
                expected_request=source_request,
            )
        assert failure.value.__cause__ is not None
        assert "selected_numeric_assignment_limitation_mismatch" in str(failure.value.__cause__)

    tiny_request = request_for(Decimal("1e-999"))
    assert tiny_request.intervention_atoms[0].causal_do_expr.assignments[0].value == "1E-999"
    assert source.model_dump(mode="json") == original_source
    original_step = NCMEngineMethod.pure_step
    calls: list[int] = []

    def observe_step(state: Any, params: Any) -> dict[str, Any]:
        calls.append(int(params["__seed__"]))
        return original_step(state, params)

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(observe_step))
    refused = JointSimulationHorizonController().run(tiny_request)
    assert calls == []
    assert refused.trajectories == ()
    assert refused.physical_work_observations == ()
    assert refused.engine_decisions[0].decision == "unsupported"
    assert refused.engine_decisions[0].reason == "intervention_assignment_underflow"
    assert refused.diagnostics["engine_run_claimed"] is False
    assert refused.diagnostics["effect_basis_status"] == "not_established"


def test_native_conditional_comparator_resolves_equal_aliases_and_refuses_conflicts(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One mapped evidence variable cannot silently receive contradictory values."""

    expression = "u + 2 * income_delta + 3 * balance_delta + 4 * income_delta * balance_delta"
    request = _with_native_conditional_comparator(_native_expression_request(expression))
    assert request.evidence_state is not None
    equal = request.model_copy(
        update={"evidence_state": {**request.evidence_state, "agents.income": 0.0}}
    )
    conflicting = request.model_copy(
        update={"evidence_state": {**request.evidence_state, "agents.income": 1.0}}
    )
    original = NCMEngineMethod.pure_step
    observed: list[dict[str, float]] = []

    def observe_step(state: Any, params: Any) -> dict[str, Any]:
        observed.append(dict(state["ncm_query_data"].evidence))
        return original(state, params)

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(observe_step))
    controller = JointSimulationHorizonController()
    result = controller.run(equal)
    reopened = _persist_and_reopen_native_result(result, equal, tmp_path / "cas")
    expected = {"income_delta": 0.0, "balance_delta": 0.0, "firm_survival": 0.0}
    assert len(observed) == 8
    assert all(evidence == expected for evidence in observed)
    assert reopened.diagnostics["ncm_conditional_comparator"]["input"]["evidence"] == expected
    assert reopened.trajectory_for("joint", ("income_subsidy", "balance_grant")).points[
        0
    ].effect == {"firm_survival": 9.0}
    assert reopened.diagnostics["effect_basis_status"] == "established"

    observed.clear()
    refused = controller.run(conflicting)
    assert observed == []
    assert refused.trajectories == ()
    assert refused.engine_decisions[0].decision != "selected"
    assert refused.engine_decisions[0].reason == "ncm_evidence_alias_conflict"
    assert refused.diagnostics["effect_basis_status"] == "not_established"


def test_native_unrepresentable_paired_difference_retains_prior_role(tmp_path: Any) -> None:
    """Finite NCM endpoints whose difference overflows retain an exact cause."""

    request = _with_native_conditional_comparator(
        _native_expression_request(
            "u + 1e308 * (2 * balance_delta - 1)", observed_u=None, replications=2, seed=7
        )
    )
    result = JointSimulationHorizonController().run(request)
    reopened = _persist_and_reopen_native_result(result, request, tmp_path / "cas")
    assert reopened.diagnostics["physical_work_interruption"] == "n5_physical_work_failed"
    assert reopened.diagnostics["effect_basis_status"] == "not_established"
    assert len(reopened.trajectories) == 1
    first = reopened.trajectory_for("individual", ("income_subsidy",))
    assert first.points[0].outcomes == {"firm_survival": -1e308}
    assert first.points[0].effect == {"firm_survival": 0.0}
    sampling = first.points[0].replication_sampling
    assert sampling is not None and sampling.seeds == (7, 8)
    assert [sample.outcomes["firm_survival"] for sample in sampling.samples] == [-1e308, -1e308]
    baseline = reopened.diagnostics["ncm_conditional_comparator"]["result"]["samples"]
    assert [item["outcomes"]["firm_survival"] for item in baseline] == [-1e308, -1e308]
    event = reopened.physical_work_observations[-1]
    assert event.status == "failed" and event.effective_seed == 7
    assert event.error_code == "ncm_effect_non_finite"
    assert event.error_context == {"outcome": "firm_survival"}
    assert reopened.feedback_classification.numeric_interaction == "unsupported"
