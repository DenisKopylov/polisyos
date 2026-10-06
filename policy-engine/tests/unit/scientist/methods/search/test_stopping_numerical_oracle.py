"""Objective-scale plateau witnesses independent of the runtime predicate."""

from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.scientist.methods.search.objective import OptimizationDirection
from polisyos.scientist.methods.search.stopping import ImprovementPlateau


@pytest.mark.parametrize(
    ("direction", "historical", "recent", "expected"),
    [
        ("minimize", "0", "1", True),
        ("minimize", "0", "-1", False),
        ("minimize", "0", "-0.01", True),
        ("minimize", "0", "-0.0101", False),
        ("minimize", "0.005", "-0.001", True),
        ("minimize", "100", "99", True),
        ("minimize", "100", "98", False),
        ("maximize", "0", "-1", True),
        ("maximize", "0", "1", False),
        ("maximize", "0", "0.01", True),
        ("maximize", "0", "0.0101", False),
        ("maximize", "-0.005", "0.001", True),
        ("maximize", "-100", "-99", True),
        ("maximize", "-100", "-98", False),
    ],
)
def test_plateau_matches_declared_unit_decimal_oracle(
    direction: str, historical: str, recent: str, expected: bool
) -> None:
    old, new = Decimal(historical), Decimal(recent)
    gain = old - new if direction == "minimize" else new - old
    tolerance = max(Decimal("0.01"), Decimal("0.01") * abs(old))
    assert (gain <= tolerance) is expected
    criterion = ImprovementPlateau(
        patience=2,
        objective_unit="objective_points",
        direction=OptimizationDirection(direction),
    )
    result = criterion.check(
        [
            {"objective_value": float(old)},
            {"objective_value": float(new)},
            {"objective_value": float(new)},
        ],
        {},
    )
    assert result.should_stop is expected
    assert result.details["gain"] == pytest.approx(float(gain))
    assert result.details["tolerance"] == pytest.approx(float(tolerance))
    assert result.details["objective_unit"] == "objective_points"
    assert result.details["profile_version"] == "1.0"


def test_unit_conversion_also_scales_absolute_tolerance() -> None:
    verdicts = []
    for scale, unit in [(1.0, "points"), (1000.0, "millipoints")]:
        criterion = ImprovementPlateau(
            patience=2, objective_unit=unit, absolute_tolerance=0.01 * scale
        )
        verdicts.append(
            criterion.check(
                [{"objective_value": 0.005 * scale}] + [{"objective_value": -0.001 * scale}] * 2,
                {},
            ).should_stop
        )
    assert verdicts == [True, True]


def test_custom_coefficients_use_their_declared_tolerance() -> None:
    # Version 1.0 specifies the formula, not equivalence of custom coefficients.
    criterion = ImprovementPlateau(
        patience=2, objective_unit="points", min_improvement=0.03, absolute_tolerance=0.02
    )
    result = criterion.check([{"objective_value": value} for value in [100.0, 98.0, 98.0]], {})
    assert result.should_stop  # Physical gain 2 points is within 3 points.
    assert result.details["gain"] == 2.0
    assert result.details["tolerance"] == 3.0
    assert result.details["relative_tolerance"] == 0.03
    assert result.details["absolute_tolerance"] == 0.02


@pytest.mark.parametrize("bad", [None, "1.0", True, float("nan"), float("inf")])
def test_present_invalid_observation_cannot_establish_plateau(bad: object) -> None:
    result = ImprovementPlateau(patience=2, objective_unit="points").check(
        [{"objective_value": 1.0}, {"objective_value": 1.0}, {"objective_value": bad}], {}
    )
    assert not result.should_stop
    assert result.details["adequacy_status"] == "not_established"


def test_absent_observation_does_not_shorten_plateau_basis() -> None:
    result = ImprovementPlateau(patience=2, objective_unit="points").check(
        [{"objective_value": 1.0}, {}, {"objective_value": 1.0}] * 2, {}
    )
    assert not result.should_stop


def test_declared_plateau_stops_native_controller_and_preserves_best() -> None:
    from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
    from polisyos.scientist.methods.search.objective import CompositeObjective, GDPGrowthObjective

    class GDPStream:
        def generate(self, history: list, current_best: dict | None, context: dict) -> dict:
            return {"gdp": -0.005 if not history else 0.001, "semantic": {"interventions": []}}

    controller = SearchController(
        config=SearchConfig(
            stopping=ImprovementPlateau(patience=2, objective_unit="GDP growth rate"),
            objective=CompositeObjective([GDPGrowthObjective()]),
        ),
        candidate_generator=GDPStream(),
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"gdp_change": candidate["gdp"]},
            "feedback": {"verdict": "APPROVE"},
        },
    )
    result = controller.run({})
    assert result.iterations_completed == 3
    assert "plateau" in result.stopping_reason.lower()
    assert result.best_candidate["gdp"] == 0.001
    assert result.best_objective == -0.001
