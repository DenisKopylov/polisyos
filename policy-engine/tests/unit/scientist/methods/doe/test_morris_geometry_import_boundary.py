from __future__ import annotations

import builtins
from importlib.util import resolve_name
from types import ModuleType

import numpy as np
import pytest

from polisyos.scientist.methods.doe import (
    SensitivityPlan as PublicSensitivityPlan,
)
from polisyos.scientist.methods.doe import (
    SensitivityUncertaintyConfig as PublicSensitivityUncertaintyConfig,
)
from polisyos.scientist.methods.doe.designs import (
    ParameterSpec,
    SensitivityPlan,
    _build_salib_problem,
)
from polisyos.scientist.methods.doe.morris_geometry import _validate_morris_plan_samples
from polisyos.scientist.methods.doe.uncertainty import SensitivityUncertaintyConfig


def test_morris_geometry_uses_resolved_problem_without_designs_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shared geometry validator consumes resolved inputs without importing its model owner."""
    assert PublicSensitivityPlan is SensitivityPlan
    assert PublicSensitivityUncertaintyConfig is SensitivityUncertaintyConfig

    plan = SensitivityPlan(
        parameter_specs=[
            ParameterSpec(name="x", lower_bound=0.0, upper_bound=1.0),
            ParameterSpec(name="y", lower_bound=0.0, upper_bound=1.0),
        ],
        n_trajectories=1,
    )
    problem, _ = _build_salib_problem(plan)
    samples = np.array([[0.0, 0.0], [2.0 / 3.0, 0.0], [2.0 / 3.0, 2.0 / 3.0]])
    original_import = builtins.__import__

    def reject_geometry_to_designs_import(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] | list[str] = (),
        level: int = 0,
    ) -> ModuleType:
        package = globals.get("__package__") if globals is not None else None
        target = (
            resolve_name("." * level + name, package)
            if level and isinstance(package, str)
            else name
        )
        if (
            globals is not None
            and globals.get("__name__") == "polisyos.scientist.methods.doe.morris_geometry"
            and target == "polisyos.scientist.methods.doe.designs"
        ):
            raise AssertionError("geometry validation imported the plan-model module")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", reject_geometry_to_designs_import)

    _validate_morris_plan_samples(plan, samples, problem)

    invalid = samples.copy()
    invalid[1, 1] = 1.0 / 3.0
    with pytest.raises(ValueError, match="exactly one coordinate"):
        _validate_morris_plan_samples(plan, invalid, problem)
