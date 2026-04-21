from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods import MethodComposer, execute_heterogeneous_chain
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.causal import PanelObservationalData
from polisyos.foundry.methods.econometrics import PanelData
from polisyos.foundry.methods.microsim import SurveyMicroData
from polisyos.foundry.methods.ml import TabularData
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _panel_iv_data() -> PanelData:
    rng = np.random.default_rng(411)
    n_obs = 64
    z = rng.normal(size=(n_obs, 2))
    controls = rng.normal(size=(n_obs, 2))
    endogenous = 0.7 * z[:, [0]] - 0.3 * z[:, [1]] + 0.2 * controls[:, [0]] + rng.normal(scale=0.3, size=(n_obs, 1))
    exog = np.column_stack([endogenous, controls])
    beta = np.array([1.8, 0.5, -0.2])
    y = exog @ beta + rng.normal(scale=0.35, size=n_obs)
    return PanelData(
        dependent=y,
        exog=exog,
        entity_ids=np.repeat(np.arange(16), 4),
        time_ids=np.tile(np.arange(4), 16),
        instrument_ids=z,
    )


def _tabular_data() -> TabularData:
    rng = np.random.default_rng(413)
    x = rng.normal(size=(96, 4))
    y = 0.6 + 1.4 * x[:, 0] - 0.5 * x[:, 1] + 0.25 * x[:, 2] + rng.normal(scale=0.2, size=96)
    return TabularData(features=x, target=y, feature_names=["x0", "x1", "x2", "x3"])


def _survey_data() -> SurveyMicroData:
    return SurveyMicroData(
        market_income=np.array([4000.0, 9000.0, 18000.0, 26000.0, 42000.0]),
        weights=np.array([1.0, 1.3, 0.9, 1.1, 0.8]),
    )


def _survey_data_with_categories() -> SurveyMicroData:
    incomes = np.array([4000.0, 9000.0, 18000.0, 26000.0], dtype=float)
    feature_pattern = np.array(
        [
            ["north", "single"],
            ["north", "family"],
            ["south", "single"],
            ["south", "family"],
        ],
        dtype=object,
    )
    return SurveyMicroData(
        market_income=np.tile(incomes, 25),
        weights=np.ones(100, dtype=float),
        features=np.tile(feature_pattern, (25, 1)),
        feature_names=["region", "family_type"],
    )


def _causal_panel() -> PanelObservationalData:
    return PanelObservationalData(
        outcome=np.array(
            [
                [1.0, 1.04, 1.09, 1.16, 1.24, 1.31],
                [0.98, 1.01, 1.05, 1.10, 1.14, 1.19],
                [1.03, 1.08, 1.12, 1.22, 1.35, 1.42],
                [1.01, 1.05, 1.10, 1.20, 1.33, 1.41],
            ]
        ),
        treatment=np.array([0, 0, 1, 1]),
        time_treatment=3,
        treatment_timing=np.array([-1, -1, 3, 3]),
        unit_ids=np.arange(4),
        time_index=np.arange(6),
    )


def test_end_to_end_econometrics_diagnostic_to_iv_chain() -> None:
    pytest.importorskip("statsmodels")
    pytest.importorskip("linearmodels")

    ensure_all_methods_registered()
    composer = MethodComposer(registry=MethodRegistry.get_instance())
    weak_iv = composer.add("econometrics.diagnostics.weak_iv_test@1.0.0", n_endogenous=1)
    iv = composer.add("econometrics.iv.two_stage_least_squares@1.0.0", n_endogenous=1)
    composer.connect(weak_iv, iv)

    result = execute_heterogeneous_chain(composer.build(), state=_panel_iv_data(), seed=419)
    final_output = result.node_results[-1][1].output

    assert final_output["result"].method_name == "iv_2sls"
    assert final_output["uncertainty_envelope"] is not None


def test_end_to_end_ml_prediction_to_uncertainty_chain() -> None:
    pytest.importorskip("sklearn")

    ensure_all_methods_registered()
    composer = MethodComposer(registry=MethodRegistry.get_instance())
    predictor = composer.add("ml.regression.elastic_net@1.0.0")
    conformal = composer.add("ml.uncertainty.conformal_prediction@1.0.0", alpha=0.1)
    composer.connect(predictor, conformal, {"result": "prediction_result"})

    result = execute_heterogeneous_chain(composer.build(), state=_tabular_data(), seed=421)
    final_output = result.node_results[-1][1].output

    assert final_output["result"].method_name == "conformal_prediction"
    assert final_output["result"].coverage is not None


def test_end_to_end_microsim_calibration_to_static_chain() -> None:
    ensure_all_methods_registered()
    composer = MethodComposer(registry=MethodRegistry.get_instance())
    calibration = composer.add(
        "microsim.calibration.reweighting_calibration@1.0.0",
        target_total_weight=5.5,
        target_mean_income=17000.0,
    )
    microsim = composer.add("microsim.static.static_microsim@1.0.0")
    composer.connect(calibration, microsim, {"weights": "weights"})

    result = execute_heterogeneous_chain(composer.build(), state=_survey_data(), seed=431)
    final_output = result.node_results[-1][1].output

    assert final_output["result"].weighted_mean_disposable_income > 0.0
    assert final_output["uncertainty_envelope"] is not None


def test_end_to_end_microsim_raking_calibration_to_static_chain() -> None:
    ensure_all_methods_registered()
    composer = MethodComposer(registry=MethodRegistry.get_instance())
    calibration = composer.add(
        "microsim.calibration.reweighting_calibration@1.0.0",
        target_total_weight=100.0,
        raking_targets={
            "region": {"north": 60.0, "south": 40.0},
            "family_type": {"single": 40.0, "family": 60.0},
        },
    )
    microsim = composer.add("microsim.static.static_microsim@1.0.0")
    composer.connect(calibration, microsim, {"weights": "weights"})

    result = execute_heterogeneous_chain(composer.build(), state=_survey_data_with_categories(), seed=437)
    calibration_output = result.node_results[0][1].output
    final_output = result.node_results[-1][1].output

    assert calibration_output["diagnostics"].decision == "pass"
    assert calibration_output["result"].metadata["solver"] == "rake_ipf"
    assert final_output["result"].weighted_mean_disposable_income > 0.0
    assert final_output["uncertainty_envelope"] is not None


def test_end_to_end_causal_parallel_trends_to_staggered_did_chain() -> None:
    pytest.importorskip("statsmodels")

    ensure_all_methods_registered()
    composer = MethodComposer(registry=MethodRegistry.get_instance())
    diagnostic = composer.add("causal.diagnostics.parallel_trends_check@1.0.0", alpha=0.1)
    did = composer.add(
        "causal.inference.did.staggered@1.0.0",
        n_bootstrap=64,
        confidence_level=0.9,
    )
    composer.connect(diagnostic, did)

    result = execute_heterogeneous_chain(composer.build(), state=_causal_panel(), seed=433)
    did_result = result.node_results[-1][1]

    assert did_result.slot_outputs["result"].status.value == "success"
    assert did_result.slot_outputs["uncertainty_envelope"] is not None
