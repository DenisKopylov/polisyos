"""CAL-06/B198 witnesses for typed Hessian scale preservation."""

from __future__ import annotations

import numpy.testing as npt
import pytest

from polisyos.foundry.calibration.report import CalibrationReport, CalibrationUncertainty
from polisyos.foundry.calibration.uncertainty_adapter import envelope_from_calibration_param
from polisyos.foundry.uncertainty.covariance import build_covariance_matrix, extract_std
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    ParametricFitCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

pytestmark = pytest.mark.unit


def _hessian_report(*, std: float | None = 1.0) -> CalibrationReport:
    uncertainty = CalibrationUncertainty(
        method="laplace",
        params=["node.rate"],
        covariance=[] if std is None else [[std**2]],
        correlation=[] if std is None else [[1.0]],
        std=[] if std is None else [std],
    )
    return CalibrationReport(
        calibrated_params={"node.rate": 0.25},
        total_loss=0.01,
        uncertainties=uncertainty,
    )


@pytest.mark.parametrize("display_level", [0.8, 0.95])
def test_hessian_envelope_carries_typed_normal_scale_without_authority_upgrade(
    display_level: float,
) -> None:
    """Changing display width must not change the conditional Hessian standard deviation."""
    envelope = envelope_from_calibration_param(
        _hessian_report(),
        "node.rate",
        confidence_level=display_level,
    )

    assert envelope is not None
    payload = envelope.distribution_payload
    assert isinstance(payload, ParametricFitCarrier)
    assert payload.family is DistributionFamily.NORMAL
    assert payload.parameters == {"mean": 0.25, "std": 1.0}
    assert extract_std(envelope) == pytest.approx(1.0)
    assert envelope.interval_semantics is IntervalSemantics.HEURISTIC_RANGE
    assert envelope.confidence_level is None
    assert envelope.is_heuristic_ci is True
    assert envelope.gate_eligible is False


def test_covariance_prefers_typed_fit_over_mutable_metadata() -> None:
    """A metadata value must not replace the typed conditional law used for covariance."""
    envelope = envelope_from_calibration_param(
        _hessian_report(),
        "node.rate",
        confidence_level=0.8,
    )
    assert envelope is not None
    envelope = envelope.model_copy(update={"metadata": {"std": 99.0}})

    covariance = build_covariance_matrix(
        ["node.rate"],
        {"node.rate": envelope},
        use_full_covariance=False,
        jitter=0.0,
    )

    npt.assert_allclose(float(covariance[0, 0]), 1.0, atol=1e-6)


def test_unsuitable_typed_fit_fails_closed_without_normal_interval_guess() -> None:
    """A non-normal carrier cannot be silently converted into a normal standard deviation."""
    envelope = UncertaintyEnvelope(
        point_estimate=0.0,
        confidence_interval=(-1.0, 1.0),
        confidence_level=None,
        distribution_family=DistributionFamily.UNIFORM,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
        is_heuristic_ci=True,
        gate_eligible=False,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.UNIFORM,
            parameters={"low": -1.0, "high": 1.0},
            support=(-1.0, 1.0),
        ),
    )

    with pytest.raises(ValueError, match="normal parametric fit"):
        extract_std(envelope)


def test_missing_hessian_std_stays_unrepresented() -> None:
    """An absent Hessian standard deviation must not receive a guessed normal carrier."""
    assert envelope_from_calibration_param(_hessian_report(std=None), "node.rate") is None
