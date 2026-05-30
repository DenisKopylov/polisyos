from __future__ import annotations

import numpy as np
import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.microsim.inverse import InverseBehavioralCalibrationEstimator
from polisyos.foundry.methods.catalog.microsim.static import StaticMicrosimEstimator
from polisyos.foundry.methods.microsim import SurveyMicroData, ensure_microsim_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.microsim_calibration import load_microsim_calibration_report
from polisyos.ir.registry.refs import MicrosimCalibrationReportRef


def _inverse_method():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("microsim.calibration.inverse_behavioral_calibration@1.0.0")
    return dispatcher, method_cls


def test_inverse_behavioral_calibration_recovers_curvature_with_interior_support() -> None:
    dispatcher, method_cls = _inverse_method()

    true_curvature = 2.0
    policy_shifter = np.linspace(1.0, 6.0, 24, dtype=float)
    observed_choice = policy_shifter / true_curvature
    survey = SurveyMicroData(
        market_income=observed_choice,
        weights=np.ones_like(observed_choice),
        instrument_z=policy_shifter,
    )

    fitted = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=survey,
        params={
            "known_upper_bound": 10.0,
            "bootstrap_reps": 16,
        },
        seed=401,
    )

    result = fitted.output["result"]
    report = fitted.output["microsim_calibration_report"]
    assert result.identified_object == "objective_params"
    assert result.identifiability_status == "identified"
    assert abs(result.objective_params["curvature"] - true_curvature) < 1e-10
    assert report["decision"] == "pass"
    assert report["can_run_microsim"] is True


def test_inverse_behavioral_calibration_returns_bounds_only_without_interior_support() -> None:
    dispatcher, method_cls = _inverse_method()

    policy_shifter = np.linspace(2.0, 5.0, 20, dtype=float)
    observed_choice = np.ones_like(policy_shifter)
    survey = SurveyMicroData(
        market_income=observed_choice,
        weights=np.ones_like(observed_choice),
        instrument_z=policy_shifter,
    )

    fitted = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=survey,
        params={
            "known_upper_bound": 1.0,
            "bootstrap_reps": 16,
        },
        seed=403,
    )

    result = fitted.output["result"]
    report = fitted.output["microsim_calibration_report"]
    assert result.identified_object == "bounds_only"
    assert result.identifiability_status == "sloppy"
    assert result.identified_set is not None
    assert "curvature" in result.identified_set.parameter_bounds
    assert report["decision"] == "warn"
    assert report["can_run_microsim"] is True


def test_inverse_behavioral_calibration_marks_manual_override_as_non_identified() -> None:
    dispatcher, method_cls = _inverse_method()

    policy_shifter = np.linspace(1.0, 3.0, 18, dtype=float)
    observed_choice = np.full(policy_shifter.shape[0], 1.5, dtype=float)
    survey = SurveyMicroData(
        market_income=observed_choice,
        weights=np.ones_like(observed_choice),
        instrument_z=policy_shifter,
    )

    fitted = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=survey,
        params={
            "manual_curvature": 1.75,
            "bootstrap_reps": 0,
        },
        seed=405,
    )

    result = fitted.output["result"]
    report = fitted.output["microsim_calibration_report"]
    assert result.identified_object == "manual_override_required"
    assert result.identifiability_status == "non_identified"
    assert result.objective_params["curvature"] == 1.75
    assert report["decision"] == "warn"


def test_inverse_behavioral_calibration_accepts_track11_nested_config() -> None:
    true_curvature = 2.0
    policy_shifter = np.linspace(1.0, 6.0, 24, dtype=float)
    observed_choice = policy_shifter / true_curvature
    survey = SurveyMicroData(
        market_income=observed_choice,
        weights=np.ones_like(observed_choice),
        instrument_z=policy_shifter,
    )

    fitted = InverseBehavioralCalibrationEstimator.pure_step(
        survey,
        {
            "declared_feasibility": {
                "family": "convex.kkt.box_interval",
                "known_upper_bound": 10.0,
                "normalization": "l2_unit_with_sign_anchor",
            },
            "objective_basis": {
                "basis_name": "labor_supply_quadratic_v1",
                "terms": ["0.5*x^2", "-a*x"],
            },
            "estimator_config": {
                "mode": "point_or_set",
                "solver": "smoothed_kkt_gmm",
                "bootstrap_reps": 8,
                "multi_start": 8,
            },
            "__seed__": 411,
        },
    )

    result = fitted["result"]
    assert result.objective_family == "labor_supply_quadratic_v1"
    assert result.constraint_family == "convex.kkt.box_interval"
    assert result.identified_object == "objective_params"
    assert result.identified_set_summary is not None
    assert abs(result.objective_params["curvature"] - true_curvature) < 1e-8
    assert result.metadata["mode"] == "point_or_set"


def test_inverse_behavioral_calibration_smooths_repeated_cross_section_cells() -> None:
    true_curvature = 2.0
    levels = np.linspace(1.0, 6.0, 6, dtype=float)
    policy_shifter = np.repeat(levels, 6)
    true_choice = policy_shifter / true_curvature
    noise = np.tile(np.array([-0.06, -0.03, 0.01, 0.02, 0.04, 0.02], dtype=float), levels.size)
    observed_choice = true_choice + noise
    repeat_measure = true_choice - noise
    period_id = np.repeat(np.arange(levels.size), 6)
    survey = SurveyMicroData(
        market_income=observed_choice,
        weights=np.ones_like(observed_choice),
        instrument_z=policy_shifter,
        period_id=period_id,
        income_repeat_measure=repeat_measure,
    )

    fitted = InverseBehavioralCalibrationEstimator.pure_step(
        survey,
        {
            "known_upper_bound": 10.0,
            "estimator_config": {
                "aggregation": "auto",
                "repeat_blend": 0.5,
                "bootstrap_reps": 8,
            },
            "__seed__": 413,
        },
    )

    result = fitted["result"]
    assert result.regime == "repeated_cross_section"
    assert result.diagnostics["denoising_used"] is True
    assert result.diagnostics["aggregation_strategy"] == "weighted_cells"
    assert result.diagnostics["n_cells"] == levels.size
    assert abs(result.objective_params["curvature"] - true_curvature) < 1e-8


def test_inverse_behavioral_calibration_separates_never_binding_latent_constraint() -> None:
    true_curvature = 2.0
    policy_shifter = np.linspace(1.0, 6.0, 24, dtype=float)
    observed_choice = policy_shifter / true_curvature
    survey = SurveyMicroData(
        market_income=observed_choice,
        weights=np.ones_like(observed_choice),
        instrument_z=policy_shifter,
    )

    fitted = InverseBehavioralCalibrationEstimator.pure_step(
        survey,
        {
            "declared_feasibility": {"estimate_upper_bound": True},
            "bootstrap_reps": 8,
            "__seed__": 415,
        },
    )

    result = fitted["result"]
    report = fitted["microsim_calibration_report"]
    assert result.identified_object == "objective_params"
    assert result.identifiability_status == "sloppy"
    assert result.constraint_params == {}
    assert result.identified_set is not None
    assert "upper_bound" in result.identified_set.parameter_bounds
    assert "latent_constraint_not_point_identified" in result.diagnostics["warnings"]
    assert report["decision"] == "warn"


def test_inverse_behavioral_calibration_supports_set_only_mode() -> None:
    true_curvature = 2.0
    policy_shifter = np.linspace(1.0, 6.0, 24, dtype=float)
    observed_choice = policy_shifter / true_curvature
    survey = SurveyMicroData(
        market_income=observed_choice,
        weights=np.ones_like(observed_choice),
        instrument_z=policy_shifter,
    )

    fitted = InverseBehavioralCalibrationEstimator.pure_step(
        survey,
        {
            "known_upper_bound": 10.0,
            "mode": "set_only",
            "bootstrap_reps": 0,
        },
    )

    result = fitted["result"]
    report = fitted["microsim_calibration_report"]
    assert result.identified_object == "bounds_only"
    assert result.identifiability_status == "sloppy"
    assert result.identified_set is not None
    assert result.identified_set_summary is not None
    assert abs(result.objective_params["curvature"] - true_curvature) < 1e-8
    assert "set_only_mode_returning_identified_set" in result.diagnostics["warnings"]
    assert report["decision"] == "warn"


def test_inverse_behavioral_calibration_supports_diagnostics_only_mode() -> None:
    policy_shifter = np.linspace(1.0, 6.0, 24, dtype=float)
    observed_choice = policy_shifter / 2.0
    survey = SurveyMicroData(
        market_income=observed_choice,
        weights=np.ones_like(observed_choice),
        instrument_z=policy_shifter,
    )

    fitted = InverseBehavioralCalibrationEstimator.pure_step(
        survey,
        {
            "known_upper_bound": 10.0,
            "mode": "diagnostics_only",
            "bootstrap_reps": 0,
        },
    )

    result = fitted["result"]
    report = fitted["microsim_calibration_report"]
    assert result.identified_object == "not_identified"
    assert result.objective_params == {}
    assert "diagnostics_only_no_operational_estimate" in result.diagnostics["block_reasons"]
    assert report["decision"] == "block"


def test_inverse_behavioral_calibration_blocks_wrong_model_class() -> None:
    policy_shifter = np.linspace(1.0, 20.0, 30, dtype=float)
    observed_choice = np.where(np.arange(policy_shifter.size) % 2 == 0, 1.0, 5.0)
    survey = SurveyMicroData(
        market_income=observed_choice,
        weights=np.ones_like(observed_choice),
        instrument_z=policy_shifter,
    )

    fitted = InverseBehavioralCalibrationEstimator.pure_step(
        survey,
        {
            "known_upper_bound": 10.0,
            "fit_loss_block_threshold": 0.01,
            "bootstrap_reps": 0,
        },
    )

    result = fitted["result"]
    report = fitted["microsim_calibration_report"]
    assert result.identified_object == "not_identified"
    assert result.objective_params == {}
    assert "wrong_model_class_or_large_optimality_gap" in result.diagnostics["block_reasons"]
    assert report["decision"] == "block"
    assert report["can_run_microsim"] is False


def test_inverse_calibration_report_gates_static_microsim() -> None:
    true_curvature = 2.0
    policy_shifter = np.linspace(1.0, 6.0, 24, dtype=float)
    observed_choice = policy_shifter / true_curvature
    survey = SurveyMicroData(
        market_income=observed_choice,
        weights=np.ones_like(observed_choice),
        instrument_z=policy_shifter,
    )

    fitted = InverseBehavioralCalibrationEstimator.pure_step(
        survey,
        {
            "known_upper_bound": 10.0,
            "bootstrap_reps": 0,
        },
    )
    certified_survey = SurveyMicroData(
        market_income=observed_choice,
        weights=np.ones_like(observed_choice),
        microsim_calibration_report=fitted["microsim_calibration_report"],
    )
    static = StaticMicrosimEstimator.pure_step(certified_survey, {})
    assert static["result"].metadata["microsim_calibration_decision"] == "pass"

    blocked_survey = SurveyMicroData(
        market_income=observed_choice,
        weights=np.ones_like(observed_choice),
        microsim_calibration_report={
            **fitted["microsim_calibration_report"],
            "decision": "block",
            "can_run_microsim": False,
            "compatibility_status": "incompatible",
            "blocking_reasons": ["test_block"],
        },
    )
    with pytest.raises(ValueError, match="static_microsim refused to run"):
        StaticMicrosimEstimator.pure_step(blocked_survey, {})


def test_inverse_calibration_persists_replayable_gate_report(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    true_curvature = 2.0
    policy_shifter = np.linspace(1.0, 6.0, 24, dtype=float)
    observed_choice = policy_shifter / true_curvature
    survey = SurveyMicroData(
        market_income=observed_choice,
        weights=np.ones_like(observed_choice),
        instrument_z=policy_shifter,
    )

    fitted = InverseBehavioralCalibrationEstimator.pure_step(
        survey.model_dump(mode="python"),
        {
            "artifact_store": store,
            "known_upper_bound": 10.0,
            "bootstrap_reps": 0,
        },
    )

    ref_payload = fitted["microsim_calibration_report_ref"]
    assert ref_payload is not None
    loaded = load_microsim_calibration_report(
        store,
        MicrosimCalibrationReportRef.model_validate(ref_payload),
    ).model_dump(mode="json")
    assert loaded["decision"] == fitted["microsim_calibration_report"]["decision"]
    assert loaded["reason_code"] == fitted["microsim_calibration_report"]["reason_code"]
