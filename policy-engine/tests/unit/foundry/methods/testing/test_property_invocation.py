from __future__ import annotations

from unittest.mock import Mock

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.bayesian.gp import GaussianProcessRegressionEstimator
from polisyos.foundry.methods.catalog.microsim.calibration import ReweightingCalibrationEstimator
from polisyos.foundry.methods.catalog.microsim.protocols import SurveyMicroData
from polisyos.foundry.methods.catalog.microsim.static import StaticMicrosimEstimator
from polisyos.foundry.methods.catalog.simulation.dynamics import SIRCompartmentalEstimator
from polisyos.foundry.methods.exceptions import MethodContractError
from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method


def test_property_invocation_dispatches_real_nested_result() -> None:
    result = invoke_property_method(
        dispatcher=MethodDispatcher(enable_runtime_selection=False),
        method_class=SIRCompartmentalEstimator,
        state={"susceptible": 990.0, "infected": 10.0, "recovered": 0.0},
        params={"beta": 0.35, "gamma": 0.1, "n_steps": 8},
        seed=7,
    )

    assert result.output["result"]["final_state"]
    trajectory = np.asarray(result.output["result"]["trajectory"], dtype=float)
    assert trajectory.shape == (8, 3)
    assert np.isfinite(trajectory).all()
    np.testing.assert_allclose(trajectory.sum(axis=1), 1000.0, rtol=1e-6)


@pytest.mark.parametrize("invalid_state", ["missing", "wrong_rank", "extra"])
def test_invalid_declared_inputs_fail_before_method_body(invalid_state: str) -> None:
    spy = Mock()

    class SpyMethod:
        signature = GaussianProcessRegressionEstimator.signature
        pure_step = staticmethod(spy)

    features = np.ones((3, 1), dtype=float)
    target = np.ones(3, dtype=float)
    if invalid_state == "missing":
        state = {"features": features}
    elif invalid_state == "wrong_rank":
        state = {"features": np.ones(3, dtype=float), "target": target}
    else:
        state = {"features": features, "target": target, "undeclared": np.ones(1)}

    with pytest.raises(MethodContractError):
        invoke_property_method(
            dispatcher=MethodDispatcher(enable_runtime_selection=False),
            method_class=SpyMethod,
            state=state,
            params={},
            seed=3,
        )

    spy.assert_not_called()



def test_explicit_bound_inputs_use_microsim_owner_materializers() -> None:
    dispatcher = MethodDispatcher(enable_runtime_selection=False)
    survey = SurveyMicroData(
        market_income=np.asarray([4000.0, 12000.0, 22000.0, 40000.0]),
        weights=np.asarray([1.0, 1.5, 1.1, 0.9]),
    )
    calibration = invoke_property_method(
        dispatcher=dispatcher,
        method_class=ReweightingCalibrationEstimator,
        state=survey,
        bound_inputs={"market_income": survey.market_income, "weights": survey.weights},
        params={"target_total_weight": 5.0, "target_mean_income": 18000.0},
        seed=79,
    )
    calibrated_weights = np.asarray(calibration.output["weights"], dtype=float)
    assert calibrated_weights.shape == survey.weights.shape

    static_fallback = survey.model_copy(
        update={
            "microsim_calibration_report": calibration.output["microsim_calibration_report"],
            "microsim_calibration_report_ref": calibration.output[
                "microsim_calibration_report_ref"
            ],
        }
    )
    simulated = invoke_property_method(
        dispatcher=dispatcher,
        method_class=StaticMicrosimEstimator,
        state=static_fallback,
        bound_inputs={"weights": calibrated_weights},
        params={},
        seed=83,
    )

    assert simulated.output["result"].weighted_mean_disposable_income > 0.0
    assert simulated.output["uncertainty_envelope"] is not None


@pytest.mark.parametrize("invalid_inputs", ["wrong_rank", "extra"])
def test_invalid_explicit_bound_inputs_fail_before_materializer_or_body(
    invalid_inputs: str,
) -> None:
    body_spy = Mock()
    materializer_spy = Mock()

    class SpyMethod:
        signature = GaussianProcessRegressionEstimator.signature
        pure_step = staticmethod(body_spy)
        materialize_input = staticmethod(materializer_spy)

    features = np.ones((3, 1), dtype=float)
    target = np.ones(3, dtype=float)
    if invalid_inputs == "wrong_rank":
        bound_inputs = {"features": np.ones(3, dtype=float), "target": target}
    else:
        bound_inputs = {"features": features, "target": target, "undeclared": np.ones(1)}

    with pytest.raises(MethodContractError):
        invoke_property_method(
            dispatcher=MethodDispatcher(enable_runtime_selection=False),
            method_class=SpyMethod,
            state={},
            bound_inputs=bound_inputs,
            params={},
            seed=3,
        )

    materializer_spy.assert_not_called()
    body_spy.assert_not_called()
