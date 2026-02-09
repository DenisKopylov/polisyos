from __future__ import annotations

from polisyos.foundry.calibration.report import (
    CalibrationReport,
    CalibrationUncertainty,
)
from polisyos.foundry.calibration.uncertainty_adapter import (
    envelope_from_calibration_param,
    envelopes_from_calibration,
)
from polisyos.ir.analytics.uncertainty import IntervalSemantics, UncertaintySource


def test_envelope_from_calibration_param() -> None:
    report = CalibrationReport(
        calibrated_params={"node.tax_rate": 0.25},
        total_loss=0.01,
        uncertainties=CalibrationUncertainty(
            method="laplace",
            params=["node.tax_rate"],
            std=[0.05],
            covariance=[[0.0025]],
            correlation=[[1.0]],
        ),
    )
    env = envelope_from_calibration_param(report, "node.tax_rate")
    assert env is not None
    assert env.point_estimate == 0.25
    assert env.ci_lower < env.point_estimate < env.ci_upper
    assert env.source == UncertaintySource.CALIBRATION
    assert env.interval_semantics == IntervalSemantics.CONFIDENCE_INTERVAL


def test_envelope_from_calibration_param_none_when_uncertainty_missing() -> None:
    report = CalibrationReport(
        calibrated_params={"node.tax_rate": 0.25},
        total_loss=0.01,
        uncertainties=None,
    )
    assert envelope_from_calibration_param(report, "node.tax_rate") is None


def test_envelopes_from_calibration_filters_missing_std() -> None:
    report = CalibrationReport(
        calibrated_params={"node.tax_rate": 0.25, "node.vat_rate": 0.2},
        total_loss=0.01,
        uncertainties=CalibrationUncertainty(
            method="laplace",
            params=["node.tax_rate"],
            std=[0.05],
            covariance=[[0.0025]],
            correlation=[[1.0]],
        ),
    )
    envelopes = envelopes_from_calibration(report)
    assert set(envelopes.keys()) == {"node.tax_rate"}
