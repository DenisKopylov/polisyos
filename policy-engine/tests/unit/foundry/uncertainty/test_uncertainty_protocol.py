from __future__ import annotations

import math
import sys
from decimal import Decimal, localcontext
from typing import cast

import pytest

from polisyos.foundry.uncertainty.protocol import (
    UncertaintyDecomposition,
    gaussian_uncertainty_envelope,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintySource,
)


def test_gaussian_uncertainty_envelope_builds_statistical_interval() -> None:
    envelope = gaussian_uncertainty_envelope(
        point_estimate=1.5,
        std=0.2,
        confidence_level=0.9,
        source=UncertaintySource.CALIBRATION,
        distribution_family=DistributionFamily.NORMAL,
        propagation_method=PropagationMethod.MONTE_CARLO,
        metadata={"metric": "policy_loss"},
    )

    assert envelope.point_estimate == 1.5
    assert envelope.interval_semantics == IntervalSemantics.CREDIBLE_INTERVAL
    assert envelope.metadata["metric"] == "policy_loss"
    assert envelope.ci_lower < envelope.point_estimate < envelope.ci_upper


def test_uncertainty_decomposition_combines_epistemic_and_aleatoric_components() -> None:
    decomposition = UncertaintyDecomposition.from_gaussian_components(
        metric_id="policy_loss",
        point_estimate=2.0,
        confidence_level=0.95,
        epistemic_std=0.3,
        aleatoric_std=0.4,
        source=UncertaintySource.CALIBRATION,
        distribution_family=DistributionFamily.BAYESIAN,
        propagation_method=PropagationMethod.MONTE_CARLO,
        metadata={"method": "posterior_predictive"},
    )

    assert decomposition.metric_id == "policy_loss"
    assert decomposition.epistemic is not None
    assert decomposition.aleatoric is not None
    assert decomposition.total.ci_width >= decomposition.epistemic.ci_width
    assert decomposition.total.metadata["component"] == "total"
    assert decomposition.as_dict()["diagnostics"]["total_std"] > 0.0


def test_secondary_gaussian_components_preserve_explicit_limitations() -> None:
    """A caller-only approximation cannot acquire authority via a secondary envelope."""
    decomposition = UncertaintyDecomposition.from_gaussian_components(
        metric_id="theta",
        point_estimate=0.0,
        confidence_level=0.9,
        epistemic_std=1.0,
        aleatoric_std=0.2,
        interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
        is_heuristic_ci=True,
        gate_eligible=False,
        metadata={
            "sample_binding_status": "caller_input_only",
            "approximation": "gaussian_components",
        },
    )

    assert decomposition.diagnostics["total_std"] ** 2 == pytest.approx(1.0**2 + 0.2**2)
    for envelope in (decomposition.total, decomposition.epistemic, decomposition.aleatoric):
        assert envelope is not None
        assert envelope.interval_semantics is IntervalSemantics.HEURISTIC_RANGE
        assert envelope.confidence_level is None
        assert envelope.is_heuristic_ci is True
        assert envelope.gate_eligible is False
        assert envelope.metadata["sample_binding_status"] == "caller_input_only"
        assert envelope.metadata["approximation"] == "gaussian_components"


def test_gaussian_helper_rejects_heuristic_gate_promotion() -> None:
    """An internally inconsistent request cannot turn a heuristic into a gate."""
    with pytest.raises(ValueError, match="heuristic intervals"):
        gaussian_uncertainty_envelope(
            point_estimate=0.0,
            std=0.2,
            confidence_level=0.9,
            source=UncertaintySource.CALIBRATION,
            interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
            is_heuristic_ci=True,
            gate_eligible=True,
        )


@pytest.mark.parametrize(
    "semantics",
    [IntervalSemantics.DETERMINISTIC_BOUNDS, cast("IntervalSemantics", "deterministic_bounds")],
    ids=["enum", "raw-wire-string"],
)
def test_gaussian_quantiles_cannot_be_mislabeled_deterministic_bounds(
    semantics: IntervalSemantics,
) -> None:
    """A finite Gaussian quantile is not a hard bound on its unbounded law."""
    with pytest.raises(ValueError, match="deterministic bounds"):
        gaussian_uncertainty_envelope(
            point_estimate=0.0,
            std=1.0,
            confidence_level=0.95,
            source=UncertaintySource.CALIBRATION,
            interval_semantics=semantics,
        )


@pytest.mark.parametrize(
    "semantics",
    [IntervalSemantics.DETERMINISTIC_BOUNDS, cast("IntervalSemantics", "deterministic_bounds")],
    ids=["enum", "raw-wire-string"],
)
def test_gaussian_decomposition_cannot_emit_false_deterministic_bounds(
    semantics: IntervalSemantics,
) -> None:
    """The decomposition shares the same semantic guard as its component builder."""
    with pytest.raises(ValueError, match="deterministic bounds"):
        UncertaintyDecomposition.from_gaussian_components(
            metric_id="theta",
            point_estimate=0.0,
            confidence_level=0.95,
            epistemic_std=1.0,
            aleatoric_std=0.0,
            interval_semantics=semantics,
        )


@pytest.mark.parametrize(
    ("epistemic", "aleatoric"),
    [(1e155, 2e155), (1e-200, 2e-200)],
    ids=["large-finite", "small-nonzero"],
)
def test_gaussian_decomposition_preserves_representable_scale_and_bounds(
    epistemic: float, aleatoric: float
) -> None:
    """An independent decimal oracle distinguishes overflow or erased positive spread."""
    with localcontext() as context:
        context.prec = 120
        expected_std = (
            Decimal.from_float(epistemic) ** 2 + Decimal.from_float(aleatoric) ** 2
        ).sqrt()
        # Standard-normal 95th percentile, independent of the implementation's inverse CDF.
        expected_upper = expected_std * Decimal("1.6448536269514722")
    decomposition = UncertaintyDecomposition.from_gaussian_components(
        metric_id="theta",
        point_estimate=0.0,
        confidence_level=0.9,
        epistemic_std=epistemic,
        aleatoric_std=aleatoric,
    )
    assert decomposition.diagnostics["total_std"] == pytest.approx(
        float(expected_std), rel=2e-15, abs=0
    )
    assert decomposition.total.ci_lower < 0.0 < decomposition.total.ci_upper
    assert math.isfinite(decomposition.total.ci_upper)
    assert decomposition.total.ci_upper == pytest.approx(float(expected_upper), rel=2e-15, abs=0)


def test_gaussian_helper_preserves_representable_small_nonzero_interval() -> None:
    envelope = gaussian_uncertainty_envelope(
        point_estimate=0.0,
        std=1e-13,
        confidence_level=0.95,
        source=UncertaintySource.CALIBRATION,
    )
    assert envelope.ci_lower < 0.0 < envelope.ci_upper


def test_gaussian_helper_refuses_unrepresentable_nonzero_interval() -> None:
    with pytest.raises(ValueError, match="cannot represent"):
        gaussian_uncertainty_envelope(
            point_estimate=1e300,
            std=1.0,
            confidence_level=0.95,
            source=UncertaintySource.CALIBRATION,
        )


def test_gaussian_decomposition_refuses_quantile_outside_binary64() -> None:
    with localcontext() as context:
        context.prec = 120
        sigma = Decimal.from_float(1.3e308)
        assert sigma < Decimal.from_float(sys.float_info.max)
        assert sigma * Decimal("1.959963984540054") > Decimal.from_float(sys.float_info.max)
    with pytest.raises(ValueError, match="finite"):
        UncertaintyDecomposition.from_gaussian_components(
            metric_id="theta",
            point_estimate=0.0,
            confidence_level=0.95,
            epistemic_std=1.3e308,
            aleatoric_std=0.0,
        )


def test_gaussian_zero_variance_remains_valid() -> None:
    envelope = gaussian_uncertainty_envelope(
        point_estimate=1.0,
        std=0.0,
        confidence_level=0.95,
        source=UncertaintySource.CALIBRATION,
    )
    assert envelope.confidence_interval == (1.0, 1.0)


@pytest.mark.parametrize(
    "value", [math.inf, -math.inf, math.nan], ids=["positive", "negative", "nan"]
)
@pytest.mark.parametrize("target", ["envelope", "epistemic", "aleatoric"])
def test_gaussian_nonfinite_scales_cannot_become_zero_variance(value: float, target: str) -> None:
    if target == "envelope":
        with pytest.raises(ValueError, match="finite"):
            gaussian_uncertainty_envelope(
                point_estimate=0.0,
                std=value,
                confidence_level=0.95,
                source=UncertaintySource.CALIBRATION,
            )
    else:
        with pytest.raises(ValueError, match="finite"):
            UncertaintyDecomposition.from_gaussian_components(
                metric_id="theta",
                point_estimate=0.0,
                confidence_level=0.95,
                epistemic_std=value if target == "epistemic" else 0.0,
                aleatoric_std=value if target == "aleatoric" else 0.0,
            )


def test_gaussian_decomposition_keeps_finite_negative_legacy_clamp() -> None:
    decomposition = UncertaintyDecomposition.from_gaussian_components(
        metric_id="theta",
        point_estimate=0.0,
        confidence_level=0.95,
        epistemic_std=-1.0,
        aleatoric_std=0.2,
    )
    assert decomposition.diagnostics["epistemic_std"] == 0.0
    assert decomposition.diagnostics["total_std"] == 0.2
