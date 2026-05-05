from __future__ import annotations

from polisyos.foundry.calibration.report import (
    CalibrationReport,
    CalibrationUncertainty,
)
from polisyos.foundry.calibration.uncertainty_adapter import (
    envelope_from_calibration_param,
    envelopes_from_calibration,
    summarize_bayesian_calibration_posterior,
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
    assert env.interval_semantics == IntervalSemantics.HEURISTIC_RANGE
    assert env.is_heuristic_ci is True
    assert env.gate_eligible is False
    assert env.confidence_level is None
    assert env.metadata["requested_confidence_level"] == 0.95


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


def test_summarize_bayesian_calibration_posterior_supports_emulator_diagnostics() -> None:
    summary = summarize_bayesian_calibration_posterior(
        {
            "node.tax_rate": [0.21, 0.24, 0.25, 0.23, 0.22],
            "node.transfer": [1.1, 1.0, 1.2, 1.05, 0.98],
        },
        credible_mass=0.9,
        emulator_diagnostics={
            "emulator_name": "gp_surrogate",
            "emulator_noise_std": {"node.tax_rate": 0.01},
        },
        posterior_diagnostics={"r_hat_max": 1.01},
    )

    assert summary.posterior_means["node.tax_rate"] > 0.0
    assert (
        summary.parameter_envelopes["node.tax_rate"].interval_semantics
        == IntervalSemantics.CREDIBLE_INTERVAL
    )
    assert summary.parameter_envelopes["node.tax_rate"].source == UncertaintySource.CALIBRATION
    assert summary.diagnostics["calibration_mode"] == "bayesian_emulator"
    assert summary.uncertainty_decomposition["node.tax_rate"]["aleatoric"] is not None
