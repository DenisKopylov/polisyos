from __future__ import annotations

import pytest

from polisyos.foundry.methods.optimization import (
    AuctionReserveProblem,
    PublicReserveAuctionEstimator,
)


def _public_valuation_problem() -> AuctionReserveProblem:
    return AuctionReserveProblem(
        reserve_grid=(0.2, 0.5, 0.8),
        valuation_scenarios=(
            (
                (0.3, 0.2),
                (0.4, 0.35),
                (0.5, 0.25),
            ),
            (
                (0.9, 0.8),
                (0.95, 0.7),
                (0.85, 0.6),
            ),
        ),
        scenario_probabilities=(0.5, 0.5),
    )


def test_public_reserve_auction_prefers_public_deterministic_policy() -> None:
    payload, solver_info = PublicReserveAuctionEstimator.pure_step(
        _public_valuation_problem(),
        {"allow_mixed_policy": False},
    )

    assert payload["status"] == "optimal"
    assert payload["objective_value"] == pytest.approx(0.2666666667)
    assert payload["variables"]["recommended_reserve"] == pytest.approx(0.2)
    assert payload["metadata"]["policy_mode"] == "deterministic"
    assert payload["metadata"]["revenue_equivalence"]["holds"] is True
    assert payload["format_recommendation"]["uncertainty_regime"] in {"low", "moderate"}
    assert payload["format_recommendation"]["recommended_format"] == "second_price"
    assert payload["format_recommendation"]["reserve_visibility"] == "public"
    assert payload["ambiguity_certificate"]["overall_status"] == "pass"
    assert payload["ambiguity_certificate"]["per_constraint"][0]["constraint_class"] == "revenue"
    assert solver_info["recommended_reserve"] == pytest.approx(0.2)
    assert solver_info["recommended_format"] == "second_price"


def test_public_reserve_auction_warns_when_reserve_is_secret() -> None:
    problem = AuctionReserveProblem(
        reserve_grid=(0.2, 0.5, 0.8),
        valuation_scenarios=_public_valuation_problem().valuation_scenarios,
        scenario_probabilities=(0.5, 0.5),
        reserve_visibility="secret",
    )

    payload, _ = PublicReserveAuctionEstimator.pure_step(
        problem,
        {"allow_mixed_policy": False},
    )

    assert payload["metadata"]["revenue_equivalence"]["holds"] is False
    assert payload["format_recommendation"]["uncertainty_regime"] == "high"
    assert payload["format_recommendation"]["reserve_policy"] == "bilevel_or_sequential_analysis"
    assert payload["ambiguity_certificate"]["overall_status"] == "warn"
    revenue_diag = next(
        item
        for item in payload["ambiguity_certificate"]["diagnostics"]
        if item["test_name"] == "revenue_equivalence"
    )
    assert revenue_diag["status"] == "warn"
    recommendation_diag = next(
        item
        for item in payload["ambiguity_certificate"]["diagnostics"]
        if item["test_name"] == "auction_format_recommendation"
    )
    assert recommendation_diag["status"] == "warn"


def test_public_reserve_auction_uses_mixed_policy_when_it_improves_guarantee() -> None:
    pytest.importorskip("scipy")

    problem = AuctionReserveProblem(
        reserve_grid=(0.2, 0.8),
        scenario_revenues=((1.0, 0.0), (0.0, 1.0)),
    )
    payload, _ = PublicReserveAuctionEstimator.pure_step(problem, {"allow_mixed_policy": True})

    assert payload["status"] == "optimal"
    assert payload["metadata"]["policy_mode"] == "mixed"
    assert payload["objective_value"] == pytest.approx(0.5, rel=1e-6)
    assert payload["format_recommendation"]["uncertainty_regime"] == "high"
    assert payload["format_recommendation"]["reserve_policy"] == "public_randomized_or_maxmin"
    weights = {
        key: value
        for key, value in payload["variables"].items()
        if key.startswith("reserve_weight[")
    }
    assert len(weights) == 2
    assert sum(weights.values()) == pytest.approx(1.0)
