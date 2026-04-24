from __future__ import annotations

import pytest

from polisyos.scientist.doe.designs import (
    ParameterSpec,
    SensitivityMethod,
    SensitivityPlan,
)


def test_sensitivity_plan_legacy_parameters_are_supported() -> None:
    plan = SensitivityPlan(parameters=["x", "y"], method=SensitivityMethod.MORRIS, n_trajectories=5)

    assert [spec.name for spec in plan.parameter_specs] == ["x", "y"]
    assert plan.estimated_runs == 15


def test_sensitivity_plan_guardrail_blocks_large_runs_by_default() -> None:
    with pytest.raises(ValueError, match="estimated_runs exceeds max_estimated_runs"):
        SensitivityPlan(
            parameter_specs=[
                ParameterSpec(name=f"x{i}", lower_bound=0.0, upper_bound=1.0) for i in range(8)
            ],
            method=SensitivityMethod.SOBOL,
            n_trajectories=100,
            max_estimated_runs=1000,
        )


def test_sensitivity_plan_allows_large_runs_with_override() -> None:
    plan = SensitivityPlan(
        parameter_specs=[ParameterSpec(name="x", lower_bound=0.0, upper_bound=1.0)],
        method=SensitivityMethod.SOBOL,
        n_trajectories=600,
        max_estimated_runs=500,
        allow_large_run=True,
    )
    assert plan.estimated_runs > plan.max_estimated_runs
