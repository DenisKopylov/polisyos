from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.ml.shift_diagnostics import (
    ShiftDiagnosticInput,
    build_shift_diagnostic_report,
    build_shift_reference_comparison_reports,
)
from polisyos.foundry.methods.ml import ensure_ml_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_method_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _base_metadata() -> dict[str, str]:
    return {
        "model_id": "benefit-risk-model",
        "model_version": "2026.04",
        "current_window_start": "2026-04-01",
        "current_window_end": "2026-04-30",
        "generated_at": "2026-04-26T00:00:00Z",
    }


def test_shift_diagnostic_method_builds_readiness_report() -> None:
    ensure_ml_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("ml.diagnostics.shift_diagnostic@1.0.0")

    rng = np.random.default_rng(101)
    reference = np.column_stack(
        [
            rng.normal(size=220),
            rng.choice(["legacy", "standard"], size=220, p=[0.70, 0.30]),
        ]
    ).astype(object)
    current = np.column_stack(
        [
            rng.normal(loc=0.85, size=210),
            rng.choice(["standard", "new-code"], size=210, p=[0.55, 0.45]),
        ]
    ).astype(object)
    ref_predictions = 1.0 / (1.0 + np.exp(-np.asarray(reference[:, 0], dtype=float)))
    cur_predictions = 1.0 / (1.0 + np.exp(-np.asarray(current[:, 0], dtype=float)))

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state={
            **_base_metadata(),
            "reference_features": reference,
            "current_features": current,
            "feature_names": ("income", "program_code"),
            "feature_types": ("numeric", "categorical"),
            "reference_predictions": ref_predictions,
            "current_predictions": cur_predictions,
            "metadata": {"feature_importances": {"income": 1.0, "program_code": 0.4}},
        },
        params={"mmd_permutations": 5, "random_state": 9},
        seed=9,
    )

    report = result.output["shift_diagnostic_report"]
    assert report.schema_version == "foundry.shift_diagnostic.v1"
    assert report.concept_shift.status == "unassessable_until_labels"
    assert report.global_verdict in {"marginal_shift", "support_shift", "mixed_shift"}
    assert report.readiness_impact.downgrade_level >= 1
    assert report.feature_diagnostics
    assert "concept_shift_unassessable_without_labels_or_validated_proxy" in report.limitations


def test_delayed_labels_can_confirm_concept_shift_and_block_readiness() -> None:
    rng = np.random.default_rng(202)
    reference = rng.normal(size=(260, 3))
    current = rng.normal(size=(260, 3))
    reference_target = (reference[:, 0] > 0.0).astype(float)
    current_target = (current[:, 0] > 0.0).astype(float)
    reference_predictions = np.where(reference_target == 1.0, 0.90, 0.10)
    current_predictions = np.full(current.shape[0], 0.50)

    report = build_shift_diagnostic_report(
        {
            **_base_metadata(),
            "reference_features": reference,
            "current_features": current,
            "feature_names": ("x0", "x1", "x2"),
            "reference_predictions": reference_predictions,
            "current_predictions": current_predictions,
            "reference_target": reference_target,
            "current_target": current_target,
            "label_availability": "delayed",
            "label_lag_days": 45,
        },
        params={"mmd_permutations": 5, "random_state": 7},
    )

    assert report.concept_shift.status == "confirmed"
    assert report.readiness_impact.resulting_readiness == "blocked"
    assert report.readiness_impact.downgrade_level == 3
    assert any(
        detector.detector_name == "delayed_label_reweighted_loss"
        for detector in report.detector_results
    )


def test_sparse_survey_no_shift_reports_insufficient_power_not_silent_green() -> None:
    rng = np.random.default_rng(303)
    reference = rng.normal(size=(32, 2))
    current = reference.copy()

    report = build_shift_diagnostic_report(
        {
            **_base_metadata(),
            "reference_features": reference,
            "current_features": current,
            "modality": "sparse_survey",
        },
        params={"mmd_permutations": 3, "random_state": 11},
    )

    assert report.global_verdict == "insufficient_power"
    assert report.power_status == "insufficient"
    assert report.readiness_impact.resulting_readiness == "monitor"
    assert "insufficient_power_for_small_or_moderate_shift" in report.limitations


def test_four_reference_comparisons_are_executable_and_labeled() -> None:
    rng = np.random.default_rng(404)
    reference = rng.normal(size=(140, 2))
    current = rng.normal(loc=0.15, size=(140, 2))
    windows = {
        "training_vs_current": {"features": reference, "reference_id": "train-2025"},
        "validation_vs_current": {"features": reference + 0.01, "reference_id": "valid-2025"},
        "stable_recent_vs_current": {"features": current - 0.02, "reference_id": "stable-2026"},
        "seasonal_historical_vs_current": {
            "features": reference + 0.02,
            "reference_id": "seasonal-2025-04",
        },
    }
    data = ShiftDiagnosticInput(
        **_base_metadata(),
        reference_features=reference,
        current_features=current,
        reference_windows=windows,
    )

    reports = build_shift_reference_comparison_reports(
        data,
        params={"mmd_permutations": 3, "random_state": 13},
    )

    assert len(reports) == 4
    assert {report.calibration.reference_comparison_type for report in reports} == set(windows)
    assert all(report.calibration.power_summary for report in reports)


def test_schema_break_maps_to_blocked_readiness() -> None:
    rng = np.random.default_rng(505)
    reference = rng.normal(size=(120, 2))
    current = rng.normal(size=(120, 2))

    report = build_shift_diagnostic_report(
        {
            **_base_metadata(),
            "reference_features": reference,
            "current_features": current,
            "feature_names": ("age", "income"),
            "reference_schema": {
                "fields": ("age", "income"),
                "types": {"age": "int", "income": "amount"},
            },
            "current_schema": {
                "fields": ("age", "income"),
                "types": {"age": "int", "income": "percent"},
            },
        },
        params={"mmd_permutations": 3, "random_state": 15},
    )

    assert report.global_verdict == "schema_shift"
    assert report.schema_shift.severity_bucket == "severe"
    assert report.readiness_impact.resulting_readiness == "blocked"
