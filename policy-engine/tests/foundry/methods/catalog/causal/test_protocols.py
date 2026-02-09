from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal.protocols import (
    HTEObservationalData,
    PanelObservationalData,
    RDDObservationalData,
)
from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod, EstimationStatus


def test_panel_observational_data_rejects_shape_mismatch():
    with pytest.raises(ValueError, match="Shape mismatch"):
        PanelObservationalData(
            outcome=np.zeros((2, 5)),
            treatment=np.array([1, 0, 0]),
            time_treatment=3,
        )


def test_panel_observational_data_rejects_non_binary_treatment():
    with pytest.raises(ValueError, match="binary"):
        PanelObservationalData(
            outcome=np.zeros((2, 5)),
            treatment=np.array([1, 2]),
            time_treatment=3,
        )


def test_rdd_observational_data_rejects_short_sample():
    with pytest.raises(ValueError, match="at least 20"):
        RDDObservationalData(
            outcome=np.ones(10),
            running_variable=np.linspace(-1, 1, 10),
            cutoff=0.0,
        )


def test_causal_effect_report_to_envelope_success():
    report = CausalEffectReport(
        method=CausalMethod.SYNTHETIC_CONTROL,
        status=EstimationStatus.SUCCESS,
        estimand="ATT",
        point_estimate=2.0,
        confidence_interval=(1.0, 3.0),
        confidence_level=0.95,
        inference_method="bootstrap",
        sample_size=100,
        n_treated=1,
        n_control=10,
        pre_periods=5,
        post_periods=5,
    )
    env = report.to_uncertainty_envelope()
    assert env is not None
    assert env.point_estimate == 2.0
    assert env.confidence_interval == (1.0, 3.0)


def test_causal_effect_report_to_envelope_failure_returns_non_gate_eligible_envelope():
    report = CausalEffectReport(
        method=CausalMethod.SYNTHETIC_CONTROL,
        status=EstimationStatus.NUMERICAL_FAILURE,
        status_reason="optimizer did not converge",
        estimand="ATT",
        inference_method="none",
        sample_size=100,
        n_treated=1,
        n_control=10,
        pre_periods=5,
        post_periods=5,
    )
    env = report.to_uncertainty_envelope()
    assert env is not None
    assert env.gate_eligible is False
    assert env.is_heuristic_ci is True


def test_hte_observational_data_validates_shapes():
    data = HTEObservationalData(
        outcome=np.arange(50, dtype=float),
        treatment=np.array([0, 1] * 25, dtype=int),
        covariates=np.ones((50, 3), dtype=float),
    )
    assert data.n_obs == 50
    assert data.n_features == 3


def test_hte_observational_data_rejects_non_binary_treatment():
    with pytest.raises(ValueError, match="binary"):
        HTEObservationalData(
            outcome=np.arange(50, dtype=float),
            treatment=np.arange(50, dtype=int),
            covariates=np.ones((50, 2), dtype=float),
        )
