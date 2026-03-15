from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.microsim import (
    SurveyMicroData,
    ensure_microsim_methods_registered,
)
from polisyos.foundry.methods.registry import MethodRegistry


def test_reweighting_and_static_microsim_run() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    state = SurveyMicroData(
        market_income=np.array([4000.0, 12000.0, 22000.0, 40000.0]),
        weights=np.array([1.0, 1.5, 1.1, 0.9]),
    )

    calibration_cls = registry.get("microsim.calibration.reweighting_calibration@1.0.0")
    calibration_result = dispatcher.dispatch(
        method_class=calibration_cls,
        signature=calibration_cls.signature,
        state=state,
        params={"target_total_weight": 5.0, "target_mean_income": 18000.0},
        seed=79,
    )
    new_weights = np.asarray(calibration_result.output["weights"], dtype=float)
    assert new_weights.shape == state.weights.shape

    static_cls = registry.get("microsim.static.static_microsim@1.0.0")
    static_state = state.model_copy(update={"weights": new_weights})
    static_result = dispatcher.dispatch(
        method_class=static_cls,
        signature=static_cls.signature,
        state=static_state,
        params={},
        seed=83,
    )

    assert static_result.output["result"].weighted_mean_disposable_income > 0.0
    assert static_result.output["uncertainty_envelope"] is not None
