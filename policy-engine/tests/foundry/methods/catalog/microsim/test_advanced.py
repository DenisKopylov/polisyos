from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.microsim import SurveyMicroData, ensure_microsim_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


def _survey_state() -> SurveyMicroData:
    rng = np.random.default_rng(141)
    return SurveyMicroData(
        market_income=np.array([4000.0, 12000.0, 22000.0, 40000.0, 55000.0]),
        weights=np.array([1.0, 1.5, 1.1, 0.9, 0.7]),
        features=rng.normal(size=(5, 3)),
        household_ids=np.arange(5),
    )


def test_tax_behavior_imputation_and_dynamic_microsim_run() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    survey = _survey_state()

    tax_cls = registry.get("microsim.policy.tax_benefit_calculator@1.0.0")
    tax_result = dispatcher.dispatch(
        method_class=tax_cls,
        signature=tax_cls.signature,
        state=survey,
        params={},
        seed=143,
    )
    assert tax_result.output["result"].weighted_mean_disposable_income > 0.0

    behavior_cls = registry.get("microsim.behavior.behavioral_response@1.0.0")
    behavior_result = dispatcher.dispatch(
        method_class=behavior_cls,
        signature=behavior_cls.signature,
        state={
            "market_income": survey.market_income,
            "weights": survey.weights,
            "effective_tax_rate": tax_result.output["effective_tax_rate"],
        },
        params={"elasticity": 0.15},
        seed=145,
    )
    assert behavior_result.output["result"].elasticity == 0.15

    imputation_cls = registry.get("microsim.imputation.imputation_model@1.0.0")
    imputation_result = dispatcher.dispatch(
        method_class=imputation_cls,
        signature=imputation_cls.signature,
        state={
            "market_income": np.array([4000.0, np.nan, 22000.0, np.nan, 55000.0]),
            "features": survey.features,
            "weights": survey.weights,
        },
        params={"n_estimators": 50},
        seed=147,
    )
    assert np.isfinite(np.asarray(imputation_result.output["market_income"], dtype=float)).all()

    dynamic_cls = registry.get("microsim.dynamic.dynamic_microsim@1.0.0")
    dynamic_result = dispatcher.dispatch(
        method_class=dynamic_cls,
        signature=dynamic_cls.signature,
        state=survey,
        params={"n_periods": 4},
        seed=149,
    )
    assert dynamic_result.output["result"].weighted_mean_final_income > 0.0
    assert dynamic_result.output["uncertainty_envelope"] is not None
