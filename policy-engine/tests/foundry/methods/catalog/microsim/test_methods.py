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
    static_state = state.model_copy(
        update={
            "weights": new_weights,
            "microsim_calibration_report": calibration_result.output["microsim_calibration_report"],
            "microsim_calibration_report_ref": calibration_result.output[
                "microsim_calibration_report_ref"
            ],
        }
    )
    static_result = dispatcher.dispatch(
        method_class=static_cls,
        signature=static_cls.signature,
        state=static_state,
        params={},
        seed=83,
    )

    assert static_result.output["result"].weighted_mean_disposable_income > 0.0
    assert static_result.output["uncertainty_envelope"] is not None


def test_static_microsim_refuses_uncertified_weights() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    state = SurveyMicroData(
        market_income=np.array([4000.0, 12000.0, 22000.0, 40000.0]),
        weights=np.array([1.0, 1.5, 1.1, 0.9]),
    )

    static_cls = registry.get("microsim.static.static_microsim@1.0.0")
    try:
        dispatcher.dispatch(
            method_class=static_cls,
            signature=static_cls.signature,
            state=state,
            params={},
            seed=83,
        )
    except ValueError as exc:
        assert "requires microsim_calibration_report" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("static_microsim should refuse uncertified weights")


def test_reweighting_returns_target_compatibility_report() -> None:
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
        seed=91,
    )

    report = calibration_result.output["result"].target_compatibility
    assert report is not None
    assert report.status.value in {"compatible", "approximately_compatible"}
    assert report.test_method.value in {"none", "hansen_j"}


def test_exact_identification_does_not_force_hansen_j() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    state = SurveyMicroData(
        market_income=np.array([5000.0, 9000.0, 14000.0, 21000.0]),
        weights=np.array([1.0, 1.0, 1.0, 1.0]),
    )

    calibration_cls = registry.get("microsim.calibration.reweighting_calibration@1.0.0")
    calibration_result = dispatcher.dispatch(
        method_class=calibration_cls,
        signature=calibration_cls.signature,
        state=state,
        params={"target_total_weight": 4.0, "target_mean_income": 12250.0},
        seed=93,
    )

    report = calibration_result.output["result"].target_compatibility
    assert report is not None
    assert report.test_method.value != "hansen_j"


def test_nonlinear_target_populates_per_target_gaps() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    state = SurveyMicroData(
        market_income=np.array([4000.0, 12000.0, 22000.0, 40000.0, 55000.0]),
        weights=np.array([1.0, 1.5, 1.1, 0.9, 0.7]),
    )
    median_weight = float(np.quantile(state.weights, 0.5))

    calibration_cls = registry.get("microsim.calibration.reweighting_calibration@1.0.0")
    calibration_result = dispatcher.dispatch(
        method_class=calibration_cls,
        signature=calibration_cls.signature,
        state=state,
        params={
            "targets": [
                {
                    "name": "weight_quantile_p50",
                    "kind": "weight_quantile",
                    "quantile": 0.5,
                    "target_value": median_weight,
                }
            ],
        },
        seed=97,
    )

    report = calibration_result.output["result"].target_compatibility
    assert report is not None
    gap = {item.name: item for item in report.per_target}["weight_quantile_p50"]
    assert np.isfinite(gap.scaled_gap)
    assert gap.abs_gap >= 0.0


def test_nonlinear_gini_target_uses_bootstrap_compatibility() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    state = SurveyMicroData(
        market_income=np.array([4000.0, 12000.0, 22000.0, 40000.0, 55000.0]),
        weights=np.array([1.0, 1.5, 1.1, 0.9, 0.7]),
    )
    target_gini = 0.0
    sorted_weights = np.sort(state.weights)
    ranks = np.arange(1.0, float(sorted_weights.size) + 1.0, dtype=float)
    target_gini = float(
        (2.0 * np.sum(ranks * sorted_weights)) / (sorted_weights.size * np.sum(sorted_weights))
        - (sorted_weights.size + 1.0) / sorted_weights.size
    )

    calibration_cls = registry.get("microsim.calibration.reweighting_calibration@1.0.0")
    calibration_result = dispatcher.dispatch(
        method_class=calibration_cls,
        signature=calibration_cls.signature,
        state=state,
        params={
            "targets": [
                {"name": "weight_gini", "kind": "weight_gini", "target_value": target_gini}
            ],
            "gmm_covariance_bootstrap_reps": 8,
            "compatibility_bootstrap_reps": 16,
        },
        seed=99,
    )

    report = calibration_result.output["result"].target_compatibility
    assert report is not None
    assert report.test_method.value == "distance_bootstrap"
    gap = {item.name: item for item in report.per_target}["weight_gini"]
    assert np.isfinite(gap.scaled_gap)
    assert gap.abs_gap >= 0.0


def test_incompatible_bounds_set_reason_code() -> None:
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
        params={
            "target_total_weight": 20.0,
            "upper_bound": 1.0,
            "target_mean_income": 20000.0,
        },
        seed=101,
    )

    report = calibration_result.output["result"].target_compatibility
    assert report is not None
    assert report.status.value == "incompatible"
    assert report.reason_code.value == "BOUNDS_PRECLUDE_TARGETS"
    assert report.distance_to_feasibility > 0.0


def test_matrix_instrument_z_participates_in_dual_basis() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    state = SurveyMicroData(
        market_income=np.array([4000.0, 12000.0, 22000.0, 40000.0, 55000.0]),
        weights=np.array([1.0, 1.5, 1.1, 0.9, 0.7]),
        instrument_z=np.column_stack(
            [
                np.array([0.0, 0.0, 1.0, 1.0, 1.0]),
                np.array([1.0, 0.5, 0.0, 0.5, 1.0]),
            ]
        ),
    )

    calibration_cls = registry.get("microsim.calibration.reweighting_calibration@1.0.0")
    calibration_result = dispatcher.dispatch(
        method_class=calibration_cls,
        signature=calibration_cls.signature,
        state=state,
        params={
            "targets": [
                {
                    "name": "income_quantile_p50",
                    "kind": "income_quantile",
                    "quantile": 0.5,
                    "target_value": 22000.0,
                }
            ],
            "gmm_covariance_bootstrap_reps": 8,
            "compatibility_bootstrap_reps": 16,
        },
        seed=103,
    )

    result = calibration_result.output["result"]
    report = result.target_compatibility
    assert report is not None
    assert "instrument_z_0" in result.metadata["basis_columns"]
    assert "instrument_z_1" in result.metadata["basis_columns"]


def test_raking_targets_return_structured_compatibility() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    state = SurveyMicroData(
        market_income=np.linspace(4000.0, 48000.0, 120),
        weights=np.ones(120, dtype=float),
        features=np.array(
            ([["north", "single"]] * 30)
            + ([["north", "family"]] * 30)
            + ([["south", "single"]] * 30)
            + ([["south", "family"]] * 30),
            dtype=object,
        ),
        feature_names=["region", "family_type"],
    )

    calibration_cls = registry.get("microsim.calibration.reweighting_calibration@1.0.0")
    calibration_result = dispatcher.dispatch(
        method_class=calibration_cls,
        signature=calibration_cls.signature,
        state=state,
        params={
            "target_total_weight": 100.0,
            "raking_targets": {
                "region": {"north": 60.0, "south": 40.0},
                "family_type": {"single": 40.0, "family": 60.0},
            },
        },
        seed=107,
    )

    diagnostics = calibration_result.output["diagnostics"]
    report = calibration_result.output["result"].target_compatibility
    assert diagnostics is not None
    assert report is not None
    assert diagnostics.decision == "pass"
    assert report.status.value == "compatible"
    assert calibration_result.output["result"].metadata["solver"] == "rake_ipf"
