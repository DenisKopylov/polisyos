"""Bounded semantic evidence for the C49 plateau profile."""

from __future__ import annotations

import math

import pytest

from polisyos.scientist.methods.search.stopping import (
    ImprovementPlateau,
    PlateauToleranceProfile,
)


def _history(*values: float) -> list[dict[str, float]]:
    return [{"objective_value": value} for value in values]


@pytest.mark.parametrize(
    ("direction", "values", "should_stop"),
    [
        ("minimize", (0.0, 1.0, 1.0), True),
        ("minimize", (0.0, -1.0, -1.0), False),
        ("minimize", (0.0, 0.0, 0.0), True),
        ("maximize", (0.0, -1.0, -1.0), True),
        ("maximize", (0.0, 1.0, 1.0), False),
        ("maximize", (1.0, 1.005, 1.005), True),
    ],
)
def test_declared_profile_uses_signed_gain_in_objective_direction(
    direction: str, values: tuple[float, ...], should_stop: bool
) -> None:
    profile = PlateauToleranceProfile(
        direction=direction,  # type: ignore[arg-type]
        unit="fixture-points",
        abs_tol=0.01,
        rel_tol=0.01,
    )
    result = ImprovementPlateau(patience=2, tolerance_profile=profile).check(_history(*values), {})
    assert result.should_stop is should_stop
    if should_stop:
        assert result.details["unit"] == "fixture-points"


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_current_observation_cannot_claim_plateau(value: float) -> None:
    profile = PlateauToleranceProfile("minimize", "fixture-points", 0.01, 0.01)
    result = ImprovementPlateau(patience=2, tolerance_profile=profile).check(
        _history(0.0, value, value), {}
    )
    assert result.should_stop is False
    assert result.reason is None


def test_profile_refuses_missing_unit() -> None:
    with pytest.raises(ValueError, match="unit must be declared"):
        PlateauToleranceProfile("minimize", " ", 0.01, 0.01)


def test_legacy_caller_remains_backward_compatible() -> None:
    result = ImprovementPlateau(patience=2).check(_history(1.0, 2.0, 2.0), {})
    assert result.should_stop is True


@pytest.mark.parametrize("direction", ["unknown", "", None, True, 1])
def test_profile_refuses_unresolved_direction_before_plateau(direction: object) -> None:
    """An annotation cannot silently turn an unknown direction into minimization."""
    with pytest.raises(ValueError, match="direction must be"):
        PlateauToleranceProfile(direction, "fixture-points", 0.01, 0.01)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [True, "0.01", None, math.nan, math.inf, -0.01])
@pytest.mark.parametrize("field", ["abs_tol", "rel_tol"])
def test_profile_refuses_untyped_or_nonfinite_tolerance(field: str, value: object) -> None:
    values = {"direction": "minimize", "unit": "fixture-points", "abs_tol": 0.01, "rel_tol": 0.01}
    values[field] = value
    with pytest.raises(ValueError, match=field):
        PlateauToleranceProfile(**values)  # type: ignore[arg-type]


def test_explicit_profile_flows_through_existing_stopping_preset() -> None:
    """The real lifecycle preset carries the opt-in profile rather than a duplicate rule."""
    from polisyos.scientist.methods.search.stopping import StoppingPresets

    profile = PlateauToleranceProfile("maximize", "fixture-points", 0.01, 0.01)
    criterion = StoppingPresets.default(max_iter=10, patience=2, tolerance_profile=profile)
    result = criterion.check(_history(0.0, 1.0, 1.0), {"evaluation_iterations": 3})
    assert result.should_stop is False
    result = criterion.check(_history(0.0, -1.0, -1.0), {"evaluation_iterations": 3})
    assert result.should_stop is True
    assert "fixture-points" in (result.reason or "")


@pytest.mark.parametrize(
    "direction,within,beyond",
    [
        ("minimize", -0.005, -0.02),
        ("maximize", 0.005, 0.02),
    ],
)
def test_absolute_tolerance_controls_small_gain_from_zero(direction, within, beyond):
    profile = PlateauToleranceProfile(direction, "fixture-points", 0.01, 0.01)
    criterion = ImprovementPlateau(patience=2, tolerance_profile=profile)
    assert criterion.check(_history(0.0, within, within), {}).should_stop
    assert not criterion.check(_history(0.0, beyond, beyond), {}).should_stop
    # Regressions on either sign are not mistaken for useful progress.
    assert criterion.check(_history(0.0, -within, -within), {}).should_stop


@pytest.mark.parametrize(
    "direction,values",
    [
        ("minimize", (0.0, -0.005, -0.005)),
        ("maximize", (0.0, 0.005, 0.005)),
        ("minimize", (-1.0, -1.02, -1.02)),
        ("maximize", (-1.0, -0.98, -0.98)),
        ("minimize", (100.0, 99.5, 99.5)),
        ("maximize", (-100.0, -99.5, -99.5)),
    ],
)
def test_coherent_value_and_absolute_tolerance_scale_conversion(direction, values):
    outcomes = []
    for scale in (1.0, 1000.0):
        criterion = ImprovementPlateau(
            patience=2,
            tolerance_profile=PlateauToleranceProfile(
                direction,
                "fixture-points" if scale == 1.0 else "fixture-millipoints",
                0.01 * scale,
                0.01,
            ),
        )
        result = criterion.check(_history(*(value * scale for value in values)), {})
        outcomes.append(result.should_stop)
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize(
    "direction,baseline,within,beyond",
    [
        ("minimize", 100.0, 99.5, 98.0),
        ("maximize", 100.0, 100.5, 102.0),
        ("minimize", -100.0, -100.5, -102.0),
        ("maximize", -100.0, -99.5, -98.0),
    ],
)
def test_relative_tolerance_controls_gain_at_large_positive_or_negative_baseline(
    direction,
    baseline,
    within,
    beyond,
):
    criterion = ImprovementPlateau(
        patience=2,
        tolerance_profile=PlateauToleranceProfile(
            direction,
            "fixture-points",
            0.01,
            0.01,
        ),
    )
    assert criterion.check(_history(baseline, within, within), {}).should_stop
    assert not criterion.check(_history(baseline, beyond, beyond), {}).should_stop
