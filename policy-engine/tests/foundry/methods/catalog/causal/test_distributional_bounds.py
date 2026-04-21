from __future__ import annotations

import pytest

from polisyos.foundry.methods.catalog.causal.distributional_bounds import (
    DistributionalBoundsEngineMethod,
    POINTWISE_NON_UNIFORM_WARNING,
    lee_trimming_distributional_bounds,
    makarov_distributional_bounds,
)
from polisyos.ir.analytics.distributional import (
    DistributionalBoundsBundle,
    DistributionalFunctional,
)


def _lee_state() -> dict[str, list[float]]:
    # Treated selected group is a mixture of 4 always responders and 2 marginal
    # responders. Control selected group is the always-responder baseline law.
    return {
        "outcome": [
            1.0,
            2.0,
            3.0,
            4.0,
            100.0,
            101.0,
            0.0,
            1.0,
            2.0,
            3.0,
            50.0,
            51.0,
        ],
        "treatment": [1.0] * 6 + [0.0] * 6,
        "selected": [1.0] * 6 + [1.0, 1.0, 1.0, 1.0, 0.0, 0.0],
    }


def test_lee_trimming_bounds_tail_delta_for_always_responders() -> None:
    state = _lee_state()

    bundle = lee_trimming_distributional_bounds(
        outcome=state["outcome"],
        treatment=state["treatment"],
        selected=state["selected"],
        functional=DistributionalFunctional.TAIL_DELTA,
        axis_values=(2.5, 50.0),
        outcome_unit="income",
    )

    assert bundle.functional is DistributionalFunctional.TAIL_DELTA
    assert bundle.sharpness_status == "outer_approx"
    assert POINTWISE_NON_UNIFORM_WARNING in bundle.warnings
    assert bundle.consensus_bounds is not None

    # True always-responder deltas:
    # t=2.5: P(Y1>2.5)=0.5, P(Y0>2.5)=0.25 -> 0.25.
    # t=50:  P(Y1>50)=0,   P(Y0>50)=0    -> 0.
    lower = bundle.consensus_bounds.lower
    upper = bundle.consensus_bounds.upper
    assert lower[0] <= 0.25 <= upper[0]
    assert lower[1] <= 0.0 <= upper[1]
    assert bundle.metadata["trim_fraction_alpha"] == pytest.approx(1.0 / 3.0)
    assert "monotone_selection_S1_ge_S0" in bundle.method_summaries[0].assumptions_used


def test_lee_trimming_quantile_shift_inverts_cdf_envelope() -> None:
    state = _lee_state()

    bundle = lee_trimming_distributional_bounds(
        outcome=state["outcome"],
        treatment=state["treatment"],
        selected=state["selected"],
        functional=DistributionalFunctional.QUANTILE_SHIFT,
        axis_values=(0.5,),
    )

    assert bundle.consensus_bounds is not None
    assert bundle.axis.axis_name == "quantile"
    assert bundle.consensus_bounds.lower == pytest.approx((1.0,))
    assert bundle.consensus_bounds.upper == pytest.approx((3.0,))


def test_lee_trimming_rejects_observed_monotonicity_violation() -> None:
    state = _lee_state()
    selected = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0] + [1.0] * 6

    with pytest.raises(ValueError, match="violate monotone_selection"):
        lee_trimming_distributional_bounds(
            outcome=state["outcome"],
            treatment=state["treatment"],
            selected=selected,
            functional=DistributionalFunctional.TAIL_DELTA,
            axis_values=(2.5,),
        )


def test_makarov_pointwise_ite_tail_risk_bounds_are_sharp_for_single_threshold() -> None:
    bundle = makarov_distributional_bounds(
        treated_outcome=(0.0, 1.0),
        control_outcome=(0.0, 1.0),
        functional=DistributionalFunctional.ITE_TAIL_RISK,
        axis_values=(0.0,),
    )

    assert bundle.functional is DistributionalFunctional.ITE_TAIL_RISK
    assert bundle.sharpness_status == "sharp"
    assert bundle.warnings == []
    assert bundle.consensus_bounds is not None
    assert bundle.consensus_bounds.lower == pytest.approx((0.5,))
    assert bundle.consensus_bounds.upper == pytest.approx((1.0,))
    assert "no_rank_invariance_or_copula_assumption" in bundle.method_summaries[0].assumptions_used


def test_makarov_multi_threshold_warns_pointwise_not_uniform() -> None:
    bundle = makarov_distributional_bounds(
        treated_outcome=(0.0, 1.0),
        control_outcome=(0.0, 1.0),
        functional=DistributionalFunctional.ITE_TAIL_RISK,
        axis_values=(0.0, 1.0),
    )

    assert bundle.sharpness_status == "outer_approx"
    assert POINTWISE_NON_UNIFORM_WARNING in bundle.warnings
    assert bundle.consensus_bounds is not None
    assert bundle.consensus_bounds.lower == pytest.approx((0.5, 0.0))
    assert bundle.consensus_bounds.upper == pytest.approx((1.0, 0.5))


def test_makarov_ite_quantile_uses_cdf_envelope_inversion() -> None:
    bundle = makarov_distributional_bounds(
        treated_outcome=(0.0, 1.0),
        control_outcome=(0.0, 1.0),
        functional=DistributionalFunctional.QUANTILE,
        axis_values=(0.5,),
    )

    assert bundle.estimand_type == "ite_quantile"
    assert bundle.consensus_bounds is not None
    assert bundle.consensus_bounds.lower == pytest.approx((-1.0,))
    assert bundle.consensus_bounds.upper == pytest.approx((0.0,))


def test_distributional_bounds_engine_routes_lee_and_makarov_payloads() -> None:
    lee_payload = DistributionalBoundsEngineMethod.pure_step(
        _lee_state(),
        {
            "theorem_family": "lee_trimming_distributional",
            "functional": "tail_probability_change",
            "axis_values": (2.5,),
        },
    )
    lee_bundle = DistributionalBoundsBundle.model_validate(
        lee_payload["result"]["distributional_bounds_bundle"]
    )
    assert lee_bundle.method_summaries[0].method == "lee_trimming_distributional"

    makarov_payload = DistributionalBoundsEngineMethod.pure_step(
        {"treated_outcome": (0.0, 1.0), "control_outcome": (0.0, 1.0)},
        {
            "theorem_family": "makarov_pointwise",
            "functional": "ite_tail_risk",
            "axis_values": (0.0,),
        },
    )
    makarov_bundle = DistributionalBoundsBundle.model_validate(
        makarov_payload["result"]["distributional_bounds_bundle"]
    )
    assert makarov_bundle.method_summaries[0].method == "makarov_pointwise"
