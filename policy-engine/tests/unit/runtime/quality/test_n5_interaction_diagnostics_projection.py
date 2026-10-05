"""Behavioral evidence for the persisted N5 interaction read projection."""

from __future__ import annotations

from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    JointSimulationHorizonController,
    project_joint_simulation_coverage,
)
from tests.unit.runtime.quality.test_joint_simulation_horizon import (
    _atom,
    _ncm_with_cross_term,
    _request,
)


def test_persisted_n5_projection_recomputes_missing_horizon_and_interaction_orders() -> None:
    """Observed step zero stays inspectable while the requested horizon remains incomplete."""

    result = JointSimulationHorizonController().run(_request())

    projection = project_joint_simulation_coverage(result)

    assert projection.status == "incomplete"
    assert projection.expected_steps == (0, 1, 2, 3)
    assert projection.checked_interaction_orders == ()
    assert projection.stored_checked_interaction_orders == ()
    joint = next(item for item in projection.trajectories if item.run_level == "joint")
    assert joint.observed_steps == (0,)
    assert joint.missing_steps == (1, 2, 3)
    assert joint.extra_steps == ()
    assert joint.duplicate_steps == ()
    assert joint.selected_outcomes_complete is True
    assert result.trajectories
    assert result.uncertainty_kind == "K_sim"


def test_complete_additive_three_atom_projection_preserves_candidate_work() -> None:
    """A complete N5 result remains visible and can establish all three interaction orders."""

    request = _request()
    third_atom = _atom(
        intervention_id="labor_support",
        causal_variable="firms.labor_count",
        engine_variable="labor_count_delta",
        value=1.0,
        world_model_record_ref=request.world_model_record_ref,
        mechanism_kind="labor_market",
        mechanism_variables=("firms.labor_count",),
    )
    ncm = _ncm_with_cross_term()
    additive_equation = next(
        equation
        for equation in ncm.structural_equations
        if equation.variable == "firm_survival"
    ).model_copy(
        update={
            "equation_params": {
                "noise_expression": (
                    "1.0 + (2.0 * income_delta) + (3.0 * balance_delta) + u"
                )
            }
        }
    )
    additive_ncm = ncm.model_copy(
        update={
            "structural_equations": [
                additive_equation
                if equation.variable == "firm_survival"
                else equation
                for equation in ncm.structural_equations
            ]
        }
    )
    plan = request.engine_plan[0].model_copy(
        update={
            "ncm_spec": additive_ncm,
            "variable_map": {
                **request.engine_plan[0].variable_map,
                "firms.labor_count": "labor_count_delta",
            },
        }
    )
    three_atom_request = request.model_copy(
        update={
            "intervention_atoms": (*request.intervention_atoms, third_atom),
            "baseline_state": {
                **request.baseline_state,
                "labor_count_delta": 0.0,
            },
            "horizon": HorizonSpec(start=0, end=0, step=1),
            "engine_plan": (plan,),
        }
    )

    result = JointSimulationHorizonController().run(three_atom_request)
    projection = project_joint_simulation_coverage(result)

    assert projection.status == "complete"
    assert projection.expected_steps == (0,)
    assert projection.checked_interaction_orders == (1, 2, 3)
    assert result.feedback_classification.numeric_interaction == "additive"
    assert all(item.observed_steps == (0,) for item in projection.trajectories)
    assert all(not item.missing_steps for item in projection.trajectories)
