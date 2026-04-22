from __future__ import annotations

import pytest

from polisyos.foundry.methods.catalog.causal.distributional_bounds import (
    ATKINSON_POSITIVITY_WARNING,
    DistributionalBoundsEngineMethod,
    GINI_UNIFORM_CERTIFICATE_WARNING,
    POINTWISE_NON_UNIFORM_WARNING,
    STOCHASTIC_DOMINANCE_OUTER_WARNING,
    lee_trimming_distributional_bounds,
    makarov_distributional_bounds,
    mtr_atkinson_distributional_bounds,
    mtr_gini_lorenz_distributional_bounds,
    mtr_headcount_distributional_bounds,
    mtr_theil_distributional_bounds,
    sd_headcount_distributional_bounds,
    sd_theil_distributional_bounds,
)
from polisyos.ir.analytics.distributional import (
    DistributionalBoundsBundle,
    DistributionalBoundUniformity,
    DistributionalFunctional,
    DistributionalDualCertificate,
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


def test_mtr_headcount_bounds_are_sharp_for_single_poverty_line() -> None:
    bundle, certificate = mtr_headcount_distributional_bounds(
        outcome=(1.0, 3.0, 2.0, 4.0),
        treatment=(1.0, 1.0, 0.0, 0.0),
        functional=DistributionalFunctional.POVERTY_HEADCOUNT,
        axis_values=(2.5,),
        target_potential_outcome="y1",
        outcome_unit="income",
    )

    assert bundle.functional is DistributionalFunctional.POVERTY_HEADCOUNT
    assert bundle.sharpness_status == "sharp"
    assert bundle.consensus_bounds is not None
    assert bundle.consensus_bounds.lower == pytest.approx((0.25,))
    assert bundle.consensus_bounds.upper == pytest.approx((0.5,))
    assert bundle.functional_parameters is not None
    assert bundle.functional_parameters.target_potential_outcome == "y1"
    assert certificate.bound_uniformity is DistributionalBoundUniformity.NOT_APPLICABLE
    assert certificate.lower_bound_witness.dual_gaps == pytest.approx((0.0,))


def test_mtr_headcount_warns_when_multiple_poverty_lines_are_only_pointwise_sharp() -> None:
    bundle, certificate = mtr_headcount_distributional_bounds(
        outcome=(1.0, 3.0, 2.0, 4.0),
        treatment=(1.0, 1.0, 0.0, 0.0),
        functional=DistributionalFunctional.POVERTY_HEADCOUNT,
        axis_values=(2.5, 3.5),
        target_potential_outcome="y0",
        outcome_unit="income",
    )

    assert bundle.sharpness_status == "outer_approx"
    assert POINTWISE_NON_UNIFORM_WARNING in bundle.warnings
    assert bundle.consensus_bounds is not None
    assert bundle.consensus_bounds.lower == pytest.approx((0.5, 0.75))
    assert bundle.consensus_bounds.upper == pytest.approx((0.75, 0.75))
    assert certificate.bound_uniformity is DistributionalBoundUniformity.POINTWISE_ONLY
    assert certificate.pointwise_not_uniform_warning is True


def test_distributional_bounds_engine_routes_mtr_headcount_payload_and_certificate() -> None:
    payload = DistributionalBoundsEngineMethod.pure_step(
        {"outcome": (1.0, 3.0, 2.0, 4.0), "treatment": (1.0, 1.0, 0.0, 0.0)},
        {
            "theorem_family": "mtr_headcount",
            "functional": "poverty_headcount",
            "axis_values": (2.5,),
            "target_potential_outcome": "y1",
        },
    )

    bundle = DistributionalBoundsBundle.model_validate(
        payload["result"]["distributional_bounds_bundle"]
    )
    certificate = DistributionalDualCertificate.model_validate(
        payload["result"]["distributional_dual_certificate_payload"]
    )
    assert bundle.method_summaries[0].method == "mtr_headcount"
    assert certificate.theorem_family == "mtr_headcount"


def test_sd_headcount_bounds_are_sharp_for_single_poverty_line() -> None:
    bundle, certificate = sd_headcount_distributional_bounds(
        outcome=(1.0, 3.0, 2.0, 4.0),
        treatment=(1.0, 1.0, 0.0, 0.0),
        functional=DistributionalFunctional.POVERTY_HEADCOUNT,
        axis_values=(2.5,),
        target_potential_outcome="y1",
        outcome_unit="income",
    )

    assert bundle.functional is DistributionalFunctional.POVERTY_HEADCOUNT
    assert bundle.sharpness_status == "sharp"
    assert bundle.consensus_bounds is not None
    assert bundle.consensus_bounds.lower == pytest.approx((0.25,))
    assert bundle.consensus_bounds.upper == pytest.approx((0.75,))
    assert certificate.theorem_family == "sd_headcount"
    assert certificate.assumption_class == "stochastic_dominance_fosd"
    assert certificate.bound_uniformity is DistributionalBoundUniformity.NOT_APPLICABLE


def test_sd_theil_requires_explicit_support_and_mean_and_stays_outer() -> None:
    bundle, certificate = sd_theil_distributional_bounds(
        outcome=(1.0, 4.0, 2.0, 6.0),
        treatment=(1.0, 1.0, 0.0, 0.0),
        functional=DistributionalFunctional.THEIL_T,
        axis_values=(1.0,),
        target_potential_outcome="y1",
        support_floor=0.0,
        support_ceiling=8.0,
        mean_floor=1.0,
        outcome_unit="income",
    )

    assert bundle.sharpness_status == "outer_approx"
    assert STOCHASTIC_DOMINANCE_OUTER_WARNING in bundle.warnings
    assert bundle.consensus_bounds is not None
    assert bundle.consensus_bounds.lower[0] >= 0.0
    assert bundle.consensus_bounds.upper[0] >= bundle.consensus_bounds.lower[0]
    assert certificate.theorem_family == "sd_theil"
    assert certificate.bound_uniformity is DistributionalBoundUniformity.POINTWISE_ONLY


def test_mtr_theil_bounds_are_sharp_with_explicit_support() -> None:
    bundle, certificate = mtr_theil_distributional_bounds(
        outcome=(1.0, 4.0, 2.0, 6.0),
        treatment=(1.0, 1.0, 0.0, 0.0),
        functional=DistributionalFunctional.THEIL_T,
        axis_values=(1.0,),
        target_potential_outcome="y1",
        support_ceiling=8.0,
        mean_floor=1.0,
        outcome_unit="income",
    )

    assert bundle.functional is DistributionalFunctional.THEIL_T
    assert bundle.sharpness_status == "sharp"
    assert bundle.consensus_bounds is not None
    assert bundle.consensus_bounds.lower[0] >= 0.0
    assert bundle.consensus_bounds.upper[0] >= bundle.consensus_bounds.lower[0]
    assert bundle.functional_parameters is not None
    assert bundle.functional_parameters.support_ceiling == pytest.approx(8.0)
    assert certificate.theorem_family == "mtr_theil"
    assert certificate.lower_bound_witness.dual_gaps == pytest.approx((0.0,))


def test_mtr_atkinson_requires_positive_support_for_log_regime() -> None:
    bundle, certificate = mtr_atkinson_distributional_bounds(
        outcome=(0.0, 4.0, 2.0, 6.0),
        treatment=(1.0, 1.0, 0.0, 0.0),
        functional=DistributionalFunctional.ATKINSON,
        axis_values=(1.0,),
        target_potential_outcome="y0",
        support_floor=0.0,
        outcome_unit="income",
    )

    assert bundle.sharpness_status == "outer_approx"
    assert ATKINSON_POSITIVITY_WARNING in bundle.warnings
    assert bundle.consensus_bounds is not None
    assert 0.0 <= bundle.consensus_bounds.lower[0] <= bundle.consensus_bounds.upper[0] <= 1.0
    assert certificate.theorem_family == "mtr_atkinson"
    assert certificate.upper_bound_witness.dual_gaps[0] > 0.0


def test_mtr_gini_never_upgrades_to_sharp_without_uniform_certificate() -> None:
    bundle, certificate = mtr_gini_lorenz_distributional_bounds(
        outcome=(1.0, 4.0, 2.0, 6.0),
        treatment=(1.0, 1.0, 0.0, 0.0),
        functional=DistributionalFunctional.GINI,
        axis_values=(1.0,),
        target_potential_outcome="y1",
        support_ceiling=8.0,
        outcome_unit="income",
    )

    assert bundle.functional is DistributionalFunctional.GINI
    assert bundle.sharpness_status == "outer_approx"
    assert GINI_UNIFORM_CERTIFICATE_WARNING in bundle.warnings
    assert bundle.consensus_bounds is not None
    assert 0.0 <= bundle.consensus_bounds.lower[0] <= bundle.consensus_bounds.upper[0] <= 1.0
    assert certificate.theorem_family == "mtr_gini_lorenz"
    assert certificate.bound_uniformity is DistributionalBoundUniformity.UNIFORM_OUTER


@pytest.mark.parametrize(
    ("family", "functional", "params", "method_name"),
    [
        (
            "mtr_theil",
            "theil_t",
            {"support_ceiling": 8.0, "mean_floor": 1.0, "target_potential_outcome": "y1"},
            "mtr_theil",
        ),
        (
            "mtr_atkinson",
            "atkinson",
            {"atkinson_epsilon": 0.5, "support_ceiling": 8.0, "target_potential_outcome": "y1"},
            "mtr_atkinson",
        ),
        (
            "mtr_gini_lorenz",
            "gini",
            {"support_ceiling": 8.0, "target_potential_outcome": "y1"},
            "mtr_gini_lorenz",
        ),
        (
            "sd_theil",
            "theil_t",
            {
                "support_floor": 0.0,
                "support_ceiling": 8.0,
                "mean_floor": 1.0,
                "target_potential_outcome": "y1",
            },
            "sd_theil",
        ),
        (
            "sd_atkinson",
            "atkinson",
            {
                "atkinson_epsilon": 0.5,
                "support_floor": 0.0,
                "support_ceiling": 8.0,
                "mean_floor": 1.0,
                "target_potential_outcome": "y1",
            },
            "sd_atkinson",
        ),
        (
            "sd_gini_lorenz",
            "gini",
            {"support_floor": 0.0, "support_ceiling": 8.0, "target_potential_outcome": "y1"},
            "sd_gini_lorenz",
        ),
    ],
)
def test_distributional_bounds_engine_routes_mtr_and_sd_inequality_families(
    family: str,
    functional: str,
    params: dict[str, float | str],
    method_name: str,
) -> None:
    payload = DistributionalBoundsEngineMethod.pure_step(
        {"outcome": (1.0, 4.0, 2.0, 6.0), "treatment": (1.0, 1.0, 0.0, 0.0)},
        {
            "theorem_family": family,
            "functional": functional,
            **params,
        },
    )

    bundle = DistributionalBoundsBundle.model_validate(
        payload["result"]["distributional_bounds_bundle"]
    )
    certificate = DistributionalDualCertificate.model_validate(
        payload["result"]["distributional_dual_certificate_payload"]
    )
    assert bundle.method_summaries[0].method == method_name
    assert certificate.theorem_family == family
