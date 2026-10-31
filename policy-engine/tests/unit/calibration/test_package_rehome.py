"""Behavior and identity checks for the Calibration package rehome prototype."""

from __future__ import annotations

import hashlib
import inspect
import pickle
import sys
import typing
from pathlib import Path

import pytest

import polisyos.calibration as calibration
import polisyos.calibration.recalibration as recalibration
from polisyos.calibration.curve import (
    CalibrationPoint,
    CalibrationResult,
    compute_calibration_curve,
)
from polisyos.calibration.diagnostics import adapters, continuous, multiclass
from polisyos.calibration.recalibration import FittedCalibrator, fit_calibrator
from polisyos.foundry.methods.artifacts import (
    compute_source_fingerprint,
    compute_source_hash,
)


def test_root_facade_resolves_to_semantic_packages() -> None:
    assert calibration.__all__ == [
        "REFERENCE_PROFILES",
        "CalibrationPoint",
        "CalibrationResult",
        "EmpiricalCalibrationContext",
        "EmpiricalCalibrationEvidenceRef",
        "EvidenceArtifactRef",
        "apply_calibrator",
        "compare_calibrators",
        "compute_calibration_curve",
        "evaluate_binary",
        "evaluate_continuous",
        "evaluate_multiclass",
        "fit_calibrator",
        "load_continuous_evaluation",
        "load_empirical_calibration_evidence",
        "persist_continuous_evaluation",
        "persist_empirical_calibration_evidence",
        "produce_empirical_calibration_evidence",
        "to_validation_report",
    ]
    assert calibration.evaluate_continuous is continuous.evaluate_continuous
    assert calibration.persist_continuous_evaluation is continuous.persist_continuous_evaluation
    assert calibration.load_continuous_evaluation is continuous.load_continuous_evaluation
    assert calibration.evaluate_multiclass is multiclass.evaluate_multiclass
    assert calibration.to_validation_report is adapters.to_validation_report
    assert calibration.fit_calibrator is fit_calibrator
    package_root = Path(calibration.__file__).parent
    assert Path(continuous.__file__).parent == package_root / "diagnostics"
    assert Path(multiclass.__file__).parent == package_root / "diagnostics"
    assert Path(adapters.__file__).parent == package_root / "diagnostics"
    assert Path(recalibration.__file__).parent == package_root / "recalibration"
    assert Path(compute_calibration_curve.__code__.co_filename).parent == package_root / "curve"
    assert calibration.evaluate_continuous.__module__ == (
        "polisyos.calibration.diagnostics.continuous"
    )
    assert calibration.evaluate_multiclass.__module__ == (
        "polisyos.calibration.diagnostics.multiclass"
    )
    assert calibration.to_validation_report.__module__ == (
        "polisyos.calibration.diagnostics.adapters"
    )
    assert FittedCalibrator.__module__ == "polisyos.calibration.recalibration"


def test_curve_public_fqns_and_pickle_round_trip_are_preserved() -> None:
    assert CalibrationPoint.__module__ == "polisyos.calibration.curve"
    assert CalibrationResult.__module__ == "polisyos.calibration.curve"
    assert compute_calibration_curve.__module__ == "polisyos.calibration.curve"

    result = compute_calibration_curve(
        [0.0, 1.0, 2.0, 3.0],
        [[(-0.1, 0.1), (0.9, 1.1), (1.9, 2.1), (2.9, 3.1)]],
        levels=[1.0],
    )
    assert result.evaluation_status == "evaluated"
    assert result.points == [CalibrationPoint(1.0, 1.0, 4)]
    # Round-trip values created in this test only; no untrusted pickle data is read.
    assert pickle.loads(pickle.dumps(result)) == result  # noqa: S301
    point_copy = pickle.loads(pickle.dumps(result.points[0]))  # noqa: S301
    assert type(point_copy) is CalibrationPoint
    assert point_copy == result.points[0]


def test_moved_diagnostic_owners_keep_math_and_reject_invalid_inputs() -> None:
    continuous_report = calibration.evaluate_continuous(
        y_true=[0.0, 1.0, 2.0],
        intervals={0.5: [(-0.1, 0.1), (0.9, 1.1), (1.9, 2.1)]},
        strict=True,
    )
    assert continuous_report.metrics.n_obs == 3
    assert continuous_report.metrics.ece == pytest.approx(0.5)

    multiclass_report = calibration.evaluate_multiclass(
        y_true=[0, 1, 2],
        y_prob=[[0.8, 0.1, 0.1], [0.1, 0.8, 0.1], [0.1, 0.1, 0.8]],
        metrics=("brier", "log_loss", "ece"),
        tests=(),
        strict=True,
    )
    assert multiclass_report.metrics.n_obs == 3
    assert multiclass_report.metrics.brier == pytest.approx(0.06)
    with pytest.raises(ValueError, match="sum to one"):
        calibration.evaluate_multiclass(
            y_true=[0, 1], y_prob=[[0.8, 0.8], [0.2, 0.2]], tests=(), strict=True
        )

    identity = fit_calibrator(method="identity", y_true=[0, 1], scores=[0.2, 0.8])
    assert isinstance(identity, FittedCalibrator)
    assert calibration.apply_calibrator(calibrator=identity, scores=[0.2, 0.8]).tolist() == [
        0.2,
        0.8,
    ]


def test_all_public_calibration_annotations_resolve_at_runtime() -> None:
    """Resolve every class/function published by the package root facade."""
    for name in calibration.__all__:
        value = getattr(calibration, name)
        if inspect.isclass(value) or inspect.isfunction(value):
            typing.get_type_hints(value)


def test_public_calibration_classes_use_real_source_for_foundry_fingerprints() -> None:
    """Exercise Foundry's class-source APIs over every public class export."""
    fallback = "calibration-source-unavailable-in-test"
    class_exports = [
        getattr(calibration, name)
        for name in calibration.__all__
        if inspect.isclass(getattr(calibration, name))
    ]
    assert class_exports

    for public_class in class_exports:
        module = sys.modules[public_class.__module__]
        module_file = Path(module.__file__).resolve()
        source_file = Path(inspect.getsourcefile(public_class) or "").resolve()
        assert source_file.is_file()
        assert source_file == module_file
        assert f"class {public_class.__name__}" in inspect.getsource(public_class)

        source_hash = compute_source_hash(public_class, fallback_value=fallback)
        fingerprint = compute_source_fingerprint(public_class, fallback_value=fallback)
        assert source_hash != fallback
        assert fingerprint.source_hash == source_hash
        assert (
            fingerprint.module_file_sha256 == hashlib.sha256(source_file.read_bytes()).hexdigest()
        )
