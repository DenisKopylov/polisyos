"""Multiclass probabilistic calibration diagnostics."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from polisyos.calibration.diagnostics import evaluate_binary
from polisyos.ir.analytics.calibration_diagnostics import (
    CalibrationDiagnosticIssue,
    CalibrationDiagnosticsReport,
    CalibrationMetrics,
)
from polisyos.ir.analytics.query_validation_report import ValidationSeverity

_EPSILON = 1e-12


def evaluate_multiclass(
    *,
    y_true: Sequence[int | str],
    y_prob: Sequence[Sequence[float]],
    class_labels: Sequence[int | str] | None = None,
    metrics: Sequence[str] | None = None,
    curves: Mapping[str, Any] | None = None,
    tests: Sequence[str] | None = None,
    uncertainty: Mapping[str, Any] | None = None,
    groups: Mapping[str, Sequence[str]] | None = None,
    strict: bool = True,
    repair_strategy: str | None = None,
) -> CalibrationDiagnosticsReport:
    """Evaluate multiclass calibration via top-label and classwise diagnostics."""

    y_idx, labels = _encode_labels(y_true, class_labels=class_labels)
    prob_arr, issues, warnings, repair_log = _prepare_multiclass_inputs(
        y_prob=y_prob,
        n_obs=y_idx.size,
        class_labels=labels,
        strict=strict,
        repair_strategy=repair_strategy,
    )
    metric_ids = tuple(metrics or ("brier", "log_loss", "ece", "mce", "rmsce", "ence"))

    top_confidence = np.max(prob_arr, axis=1)
    top_pred = np.argmax(prob_arr, axis=1)
    top_correct = (top_pred == y_idx).astype(float)
    top_report = evaluate_binary(
        y_true=top_correct.tolist(),
        y_prob=top_confidence.tolist(),
        metrics=("brier", "log_loss", "ece", "mce", "rmsce", "ence"),
        curves=curves,
        tests=tests,
        uncertainty=uncertainty,
        groups=groups,
        strict=True,
    )

    one_hot = np.eye(prob_arr.shape[1], dtype=float)[y_idx]
    brier = float(np.mean(np.sum((one_hot - prob_arr) ** 2, axis=1)))
    log_loss = float(np.mean(-np.log(np.clip(prob_arr[np.arange(y_idx.size), y_idx], _EPSILON, 1.0))))
    per_class = _classwise_metrics(
        y_idx=y_idx,
        y_prob=prob_arr,
        labels=labels,
        curves=curves,
    )

    class_counts = np.bincount(y_idx, minlength=len(labels))
    issues.extend(_class_support_issues(labels=labels, class_counts=class_counts))
    issues.extend(_remap_issues(top_report.issues, prefix_path="calibration.top_label"))

    top_curves = {
        f"top_label_{curve_id}": bins
        for curve_id, bins in top_report.curves.items()
    }
    classwise_ece = [
        metrics.ece
        for metrics in per_class.values()
        if metrics.ece is not None
    ]
    metadata = {
        "class_labels": list(labels),
        "class_counts": {label: int(class_counts[index]) for index, label in enumerate(labels)},
        "top_label_accuracy": float(np.mean(top_correct)),
        "classwise_mean_ece": (
            None if not classwise_ece else float(np.mean(np.asarray(classwise_ece, dtype=float)))
        ),
        "repair_log": repair_log,
    }
    return CalibrationDiagnosticsReport(
        task="multiclass",
        target_type="probability",
        metrics=CalibrationMetrics(
            n_obs=int(y_idx.size),
            mean_predicted_score=float(np.mean(top_confidence)),
            mean_observed_rate=float(np.mean(top_correct)),
            brier=brier if "brier" in metric_ids else None,
            log_loss=log_loss if "log_loss" in metric_ids else None,
            ece=top_report.metrics.ece if "ece" in metric_ids else None,
            mce=top_report.metrics.mce if "mce" in metric_ids else None,
            rmsce=top_report.metrics.rmsce if "rmsce" in metric_ids else None,
            ence=top_report.metrics.ence if "ence" in metric_ids else None,
            intervals=dict(top_report.metrics.intervals),
        ),
        curves={key: tuple(value) for key, value in top_curves.items()},
        tests=top_report.tests,
        issues=tuple(issues),
        warnings=tuple(list(warnings) + list(top_report.warnings)),
        primary_curve=(
            None
            if top_report.primary_curve is None
            else f"top_label_{top_report.primary_curve}"
        ),
        per_class=per_class,
        per_group=dict(top_report.per_group),
        recommended_action=_recommended_action(
            top_report=top_report,
            classwise_mean_ece=metadata["classwise_mean_ece"],
        ),
        metadata=metadata,
    )


def _encode_labels(
    y_true: Sequence[int | str],
    *,
    class_labels: Sequence[int | str] | None,
) -> tuple[np.ndarray, tuple[str, ...]]:
    y_values = list(y_true)
    if not y_values:
        raise ValueError("y_true must not be empty for multiclass diagnostics")
    if class_labels is None:
        if not all(isinstance(value, (int, np.integer)) for value in y_values):
            raise ValueError("class_labels are required when y_true is not integer-encoded")
        max_label = max(int(value) for value in y_values)
        labels = tuple(str(index) for index in range(max_label + 1))
        mapping = {index: index for index in range(max_label + 1)}
    else:
        labels = tuple(str(label) for label in class_labels)
        mapping = {label: index for index, label in enumerate(class_labels)}

    indices: list[int] = []
    for value in y_values:
        key = value
        if key not in mapping:
            raise ValueError(f"Unknown multiclass label {value!r}; pass class_labels to fix ordering")
        indices.append(int(mapping[key]))
    return np.asarray(indices, dtype=int), labels


def _prepare_multiclass_inputs(
    *,
    y_prob: Sequence[Sequence[float]],
    n_obs: int,
    class_labels: Sequence[str],
    strict: bool,
    repair_strategy: str | None,
) -> tuple[np.ndarray, list[CalibrationDiagnosticIssue], tuple[str, ...], dict[str, Any]]:
    prob_arr = np.asarray(y_prob, dtype=float)
    if prob_arr.ndim != 2:
        raise ValueError("multiclass calibration expects a 2D probability matrix")
    if prob_arr.shape[0] != n_obs:
        raise ValueError("y_prob row count must match y_true length")
    if prob_arr.shape[1] != len(class_labels):
        raise ValueError("y_prob class count must match class_labels length")
    if not np.all(np.isfinite(prob_arr)):
        raise ValueError("y_prob contains non-finite values")

    issues: list[CalibrationDiagnosticIssue] = []
    warnings: list[str] = []
    repair_log: dict[str, Any] = {}

    invalid_probability = np.any((prob_arr < 0.0) | (prob_arr > 1.0))
    row_sums = np.sum(prob_arr, axis=1)
    invalid_rows = ~np.isclose(row_sums, 1.0, atol=1e-6)
    if invalid_probability or np.any(invalid_rows):
        if strict or repair_strategy != "normalize_rows":
            raise ValueError(
                "multiclass probabilities must be finite, non-negative, and sum to one when strict=True"
            )
        clipped = np.clip(prob_arr, 0.0, None)
        clipped_row_sums = np.sum(clipped, axis=1, keepdims=True)
        if np.any(clipped_row_sums <= _EPSILON):
            raise ValueError("cannot normalize multiclass rows with zero total mass")
        prob_arr = clipped / clipped_row_sums
        repair_log["row_repairs"] = int(np.sum(invalid_rows) + int(invalid_probability))
        repair_log["repair_strategy"] = repair_strategy
        warnings.append("Multiclass probability rows were normalized before diagnostics.")
        issues.append(
            CalibrationDiagnosticIssue(
                code="CALIB_INVALID_PROBABILITY_ROWS_REPAIRED",
                message="Multiclass probability rows were repaired before evaluation.",
                severity=ValidationSeverity.INFO,
                path="calibration.inputs.y_prob",
                expected="rows sum to 1 with values in [0, 1]",
                actual={
                    "rows_repaired": int(np.sum(invalid_rows)),
                    "out_of_bounds_detected": bool(invalid_probability),
                    "strategy": repair_strategy,
                },
            )
        )
    return prob_arr, issues, tuple(warnings), repair_log


def _classwise_metrics(
    *,
    y_idx: np.ndarray,
    y_prob: np.ndarray,
    labels: Sequence[str],
    curves: Mapping[str, Any] | None,
) -> dict[str, CalibrationMetrics]:
    per_class: dict[str, CalibrationMetrics] = {}
    for class_index, label in enumerate(labels):
        binary_report = evaluate_binary(
            y_true=(y_idx == class_index).astype(float).tolist(),
            y_prob=y_prob[:, class_index].tolist(),
            metrics=("brier", "log_loss", "ece", "mce", "rmsce", "ence"),
            curves=curves,
            tests=(),
            uncertainty=None,
            strict=True,
        )
        per_class[label] = binary_report.metrics
    return per_class


def _class_support_issues(
    *,
    labels: Sequence[str],
    class_counts: np.ndarray,
) -> list[CalibrationDiagnosticIssue]:
    issues: list[CalibrationDiagnosticIssue] = []
    for label, count in zip(labels, class_counts, strict=True):
        if int(count) >= 30:
            continue
        issues.append(
            CalibrationDiagnosticIssue(
                code="CALIB_CLASS_LOW_SUPPORT",
                message="One or more classes have low support for stable classwise calibration diagnostics.",
                severity=ValidationSeverity.WARNING,
                path=f"calibration.per_class.{label}.count",
                expected=">=30",
                actual=int(count),
            )
        )
    return issues


def _remap_issues(
    issues: Sequence[CalibrationDiagnosticIssue],
    *,
    prefix_path: str,
) -> list[CalibrationDiagnosticIssue]:
    remapped: list[CalibrationDiagnosticIssue] = []
    for item in issues:
        suffix = item.path.removeprefix("calibration.")
        remapped.append(
            item.model_copy(
                update={"path": prefix_path if not suffix else f"{prefix_path}.{suffix}"}
            )
        )
    return remapped


def _recommended_action(
    *,
    top_report: CalibrationDiagnosticsReport,
    classwise_mean_ece: float | None,
) -> str | None:
    if top_report.recommended_action is None and (
        classwise_mean_ece is None or classwise_mean_ece <= 0.05
    ):
        return None
    return "fit_temperature_or_classwise_isotonic"


__all__ = [
    "evaluate_multiclass",
]
