"""Legacy exports compare only complete finite vectors on one declared basis."""

import math
from dataclasses import replace

import pytest

from polisyos.scientist.methods.search.frontier import dominates, update_legacy_pareto_front
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection


def objectives(gdp=1.0, deficit=10.0):
    return [
        ObjectiveValue("gdp_growth", gdp, OptimizationDirection.MAXIMIZE),
        ObjectiveValue("budget_deficit", deficit, OptimizationDirection.MINIMIZE),
    ]


@pytest.mark.parametrize(
    "invalid", [math.nan, math.inf, -math.inf, False, True, None, "0", 10**400]
)
def test_unavailable_declared_coordinate_cannot_displace_or_export_a_complete_row(invalid):
    complete = update_legacy_pareto_front(
        [], candidate={"source": "measured"}, objectives=objectives()
    )
    result = update_legacy_pareto_front(
        complete, candidate={"source": "unavailable"}, objectives=objectives(2.0, invalid)
    )
    assert result == complete
    assert result[0].as_payload()["candidate"] == {"source": "measured"}


@pytest.mark.parametrize(
    "invalid", [math.nan, math.inf, -math.inf, False, True, None, "0", 10**400]
)
def test_raw_comparator_never_treats_an_unavailable_coordinate_as_dominating(invalid):
    assert dominates((-2.0, invalid), (-1.0, 10.0)) is False
    assert dominates((-1.0, 10.0), (-2.0, invalid)) is False


def test_changed_declared_axis_set_is_refused_before_export():
    complete = update_legacy_pareto_front(
        [], candidate={"source": "measured"}, objectives=objectives()
    )
    with pytest.raises(ValueError, match="objective basis"):
        update_legacy_pareto_front(
            complete, candidate={"source": "missing"}, objectives=objectives(2.0)[:1]
        )


def test_duplicate_declared_names_are_not_a_complete_vector():
    assert (
        update_legacy_pareto_front(
            [], candidate={"source": "duplicate"}, objectives=[objectives()[0], objectives(2.0)[0]]
        )
        == []
    )


def test_nonfinite_existing_payload_is_not_reexported():
    complete = update_legacy_pareto_front(
        [], candidate={"source": "measured"}, objectives=objectives()
    )
    bad = replace(complete[0], normalized_values=(-2.0, math.nan))
    assert (
        update_legacy_pareto_front(
            [bad], candidate={"source": "unavailable"}, objectives=objectives(2.0, math.nan)
        )
        == []
    )


def test_finite_directions_and_strict_ties_preserve_existing_dominance():
    assert dominates((-2.0, 8.0), (-1.0, 10.0)) is True
    assert dominates((-1.0, 10.0), (-1.0, 10.0)) is False
    complete = update_legacy_pareto_front(
        [], candidate={"source": "measured"}, objectives=objectives()
    )
    better = update_legacy_pareto_front(
        complete, candidate={"source": "better"}, objectives=objectives(2.0, 8.0)
    )
    assert len(better) == 1 and better[0].candidate == {"source": "better"}
