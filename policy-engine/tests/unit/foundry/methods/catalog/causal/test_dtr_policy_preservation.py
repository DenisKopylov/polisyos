"""Behavioral controls for preserving a fitted DTR's actual stage decisions."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError
from sklearn.linear_model import LinearRegression

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.dtr import (
    ALearningDTR,
    _fit_q_function,
    _optimal_q_action,
    _regime_from_q_models,
)
from polisyos.foundry.methods.catalog.causal.g_computation import (
    _apply_regime,
    _build_history_matrix,
    _regime_params_from_spec,
)
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.ir.analytics.dynamic_regime import (
    DynamicTreatmentRegime,
    RegimeRule,
    load_dynamic_treatment_regime,
    persist_dynamic_treatment_regime,
)


def _stage_actions(regime, treatment: np.ndarray, covariates: np.ndarray, stage: int):
    params = _regime_params_from_spec(regime)
    extras = {
        key: value
        for key, value in params.items()
        if key not in {"regime", "threshold_covariate_index", "threshold_value"}
    }
    return _apply_regime(
        _build_history_matrix(treatment, covariates, stage),
        covariates[:, stage, :],
        params["regime"],
        params["threshold_covariate_index"],
        params["threshold_value"],
        time_index=stage,
        **extras,
    )


def _fitted_stage_models():
    rng = np.random.default_rng(197)
    covariates = rng.normal(size=(80, 3, 2))
    treatment = rng.integers(0, 2, size=(80, 3)).astype(float)
    models = []
    for stage, (intercept, weights) in enumerate(
        [(0.0, (1.0, -0.4)), (0.3, (-1.2, 0.7)), (-0.5, (0.2, 1.4))]
    ):
        history = _build_history_matrix(treatment, covariates, stage)
        action = treatment[:, stage : stage + 1]
        current = covariates[:, stage, :]
        features = np.hstack([history, action, action * current])
        outcome = 0.6 * history.sum(axis=1) + action[:, 0] * (
            intercept + current @ np.asarray(weights)
        )
        models.append(_fit_q_function(features, outcome))
    return models, treatment, covariates


def test_q_regime_preserves_each_stage_on_unseen_histories() -> None:
    models, treatment, covariates = _fitted_stage_models()
    regime = _regime_from_q_models(models, covariates, treatment, n_cov=2)
    rng = np.random.default_rng(991)
    unseen_covariates = rng.normal(size=(120, 3, 2)) * 7
    unseen_treatment = rng.integers(0, 2, size=(120, 3)).astype(float)
    for stage, model in enumerate(models):
        history = _build_history_matrix(unseen_treatment, unseen_covariates, stage)
        expected = _optimal_q_action(model, history, n_cov=2)
        np.testing.assert_array_equal(
            _stage_actions(regime, unseen_treatment, unseen_covariates, stage),
            expected,
        )


@pytest.mark.parametrize("rule", ["linear_blip", "future_rule", "always_treat_typo"])
def test_unrepresented_rule_refuses_instead_of_treating_everyone(rule: str) -> None:
    with pytest.raises(ValueError):
        _apply_regime(np.zeros((2, 1)), np.zeros((2, 1)), rule)


def test_selected_q_rule_survives_persistence_and_a_fresh_reader(tmp_path) -> None:
    models, treatment, covariates = _fitted_stage_models()
    regime = _regime_from_q_models(models, covariates, treatment, n_cov=2)
    root = tmp_path / "cas"
    ref = persist_dynamic_treatment_regime(ensure_ir_artifact_store(FileSystemCAS(root)), regime)
    restored = load_dynamic_treatment_regime(ensure_ir_artifact_store(FileSystemCAS(root)), ref)
    assert restored == regime
    assert restored.schema_version == "1.1"
    for stage, model in enumerate(models):
        expected = _optimal_q_action(
            model, _build_history_matrix(treatment, covariates, stage), n_cov=2
        )
        np.testing.assert_array_equal(
            _stage_actions(restored, treatment, covariates, stage), expected
        )


def test_historical_regime_is_readable_but_its_linear_blip_is_unbound(tmp_path) -> None:
    legacy = DynamicTreatmentRegime(
        time_points=(0,),
        treatment_variables=("A_0",),
        time_varying_covariates=("L_0",),
        outcome="Y",
        rule=RegimeRule.LINEAR_BLIP,
        regime_coefficients=(1.0, -0.2),
    )
    root = tmp_path / "cas"
    ref = persist_dynamic_treatment_regime(ensure_ir_artifact_store(FileSystemCAS(root)), legacy)
    restored = load_dynamic_treatment_regime(ensure_ir_artifact_store(FileSystemCAS(root)), ref)
    assert restored == legacy
    assert restored.schema_version == "1.0"
    with pytest.raises(ValueError, match="selected decision profile"):
        _stage_actions(restored, np.zeros((2, 1)), np.zeros((2, 1, 1)), 0)


def test_q_profile_keeps_actual_floating_point_tie_and_default_action() -> None:
    model = LinearRegression()
    model.coef_ = np.asarray([1e20, 1.0, 0.0])
    model.intercept_ = 0.0
    model.n_features_in_ = 3
    covariates = np.asarray([[[1.0]], [[0.0]]])
    treatment = np.zeros((2, 1))
    regime = _regime_from_q_models([model], covariates, treatment, n_cov=1)
    # Algebraically the blip is +1 for both units. Actual Q predictions tie at
    # the large common baseline, and the producer selects action zero there.
    expected = _optimal_q_action(model, covariates[:, 0, :], n_cov=1)
    np.testing.assert_array_equal(expected, [0.0, 1.0])
    np.testing.assert_array_equal(_stage_actions(regime, treatment, covariates, 0), expected)


@pytest.mark.parametrize(
    "change",
    [
        {"stage_coefficients": ((1.0,),)},
        {"stage_coefficients": ((float("nan"), 0.0, 0.0, 0.0),)},
        {"time_points": (2,)},
        {"schema_version": "1.0"},
        {"decision_rule_profile": "unselected_profile"},
    ],
)
def test_selected_profile_refuses_invalid_layout_version_or_nonfinite_weights(change) -> None:
    model = LinearRegression()
    model.coef_ = np.asarray([0.0, 1.0, 0.0])
    model.intercept_ = 0.0
    model.n_features_in_ = 3
    regime = _regime_from_q_models([model], np.zeros((2, 1, 1)), np.zeros((2, 1)), n_cov=1)
    payload = regime.model_dump(mode="json")
    payload.update(change)
    with pytest.raises(ValidationError):
        DynamicTreatmentRegime.model_validate(payload)


def test_a_learning_keeps_opposite_actions_at_different_stages() -> None:
    rng = np.random.default_rng(67)
    treatment = rng.integers(0, 2, size=(180, 2)).astype(float)
    covariates = rng.normal(size=(180, 2, 1))
    data = DynamicTreatmentData(
        outcome=2.0 * treatment[:, 0] - 3.0 * treatment[:, 1] + covariates[:, 0, 0],
        treatment_sequence=treatment,
        covariate_sequence=covariates,
    )
    result = ALearningDTR.pure_step(data, {"n_bootstrap": 5})["dtr_result"]
    assert result.optimal_regime.rule is RegimeRule.EXPLICIT_SCHEDULE
    assert result.optimal_regime.scheduled_actions == (1, 0)
    np.testing.assert_array_equal(
        _stage_actions(result.optimal_regime, treatment, covariates, 1), np.zeros(180)
    )


def test_action_only_q_profile_preserves_constant_and_tied_stages() -> None:
    models = []
    for stage, action_coefficient in enumerate((2.0, -2.0, 0.0)):
        model = LinearRegression()
        history_width = 2 * stage + 1
        model.coef_ = np.zeros(history_width + 1)
        model.coef_[-1] = action_coefficient
        model.intercept_ = 0.0
        model.n_features_in_ = history_width + 1
        models.append(model)
    covariates = np.zeros((4, 3, 1))
    treatment = np.zeros((4, 3))
    regime = _regime_from_q_models(models, covariates, treatment)
    for stage, action in enumerate((1.0, 0.0, 0.0)):
        np.testing.assert_array_equal(
            _stage_actions(regime, treatment, covariates, stage), np.full(4, action)
        )


def test_learned_profile_refuses_conflicting_current_history_role() -> None:
    models, treatment, covariates = _fitted_stage_models()
    regime = _regime_from_q_models(models, covariates, treatment, n_cov=2)
    params = _regime_params_from_spec(regime)
    with pytest.raises(ValueError, match="history positions"):
        _apply_regime(
            _build_history_matrix(treatment, covariates, 0),
            covariates[:, 0, :] + 1.0,
            params.pop("regime"),
            params.pop("threshold_covariate_index"),
            params.pop("threshold_value"),
            time_index=0,
            **params,
        )


def test_unselected_fitted_dtype_is_not_reinterpreted_as_float64() -> None:
    model = LinearRegression()
    model.coef_ = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
    model.intercept_ = np.float32(0.0)
    model.n_features_in_ = 3
    with pytest.raises(ValueError, match="float64 fitted"):
        _regime_from_q_models([model], np.zeros((2, 1, 1)), np.zeros((2, 1)), n_cov=1)
