from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.econometrics.protocols import (
    CrossSectionalDependenceDiagnostic,
    EconometricDiagnosticResult,
    EconometricResult,
    PanelData,
    TimeSeriesData,
)


def test_panel_data_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="exog row count"):
        PanelData(
            dependent=np.ones(10),
            exog=np.ones((9, 2)),
            entity_ids=np.repeat(np.arange(5), 2),
            time_ids=np.tile(np.arange(2), 5),
        )


def test_panel_data_rejects_repeated_cross_section_metadata() -> None:
    with pytest.raises(ValueError, match="repeated cross-section/survey data"):
        PanelData(
            dependent=np.ones(10),
            exog=np.ones((10, 2)),
            entity_ids=np.repeat(np.arange(5), 2),
            time_ids=np.tile(np.arange(2), 5),
            metadata={"data_shape": "survey_repeated_cross_section"},
        )


def test_time_series_data_rejects_short_series() -> None:
    with pytest.raises(ValueError, match="at least 8"):
        TimeSeriesData(endog=np.arange(4, dtype=float))


def test_econometric_result_to_uncertainty_envelope() -> None:
    result = EconometricResult(
        method_name="test",
        params={"beta": 1.2},
        std_errors={"beta": 0.1},
        confidence_intervals={"beta": (1.0, 1.4)},
        p_values={"beta": 0.01},
        n_obs=100,
    )

    envelope = result.to_uncertainty_envelope("beta")
    assert envelope is not None
    assert envelope.point_estimate == 1.2
    assert envelope.confidence_interval == (1.0, 1.4)


def test_econometric_result_v2_accepts_cross_sectional_dependence_diagnostic() -> None:
    dependence = CrossSectionalDependenceDiagnostic(
        detected=True,
        class_label="factor",
        strength="strong",
        estimator_status="unsafe_for_default_inference",
        recommended_covariance="cce_reroute",
        tests=[
            EconometricDiagnosticResult(
                test_name="latent_factor_screen",
                statistic=0.61,
                passed=False,
            )
        ],
        factor_count=1,
        used_time_dummies=False,
        dependence_removed_by_time_effects=False,
        evidence={"router_version": "phase1"},
    )

    result = EconometricResult(
        method_name="test",
        params={"beta": 0.8},
        std_errors={"beta": 0.2},
        cross_sectional_dependence_diagnostic=dependence,
    )

    assert EconometricResult.contract_id == "foundry.econometrics.result.v2"
    assert result.cross_sectional_dependence_diagnostic is not None
    assert result.cross_sectional_dependence_diagnostic.class_label == "factor"
