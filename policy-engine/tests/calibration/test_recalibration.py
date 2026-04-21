"""Tests for calibration recalibration helpers."""
from __future__ import annotations

import numpy as np

from polisyos.calibration import (
    apply_calibrator,
    compare_calibrators,
    fit_calibrator,
)


def test_compare_calibrators_improves_over_identity_for_binary_miscalibration() -> None:
    rng = np.random.default_rng(7)
    latent = np.linspace(-2.5, 2.5, 250)
    true_prob = 1.0 / (1.0 + np.exp(-latent))
    y_true = rng.binomial(1, true_prob)
    base_prob = 1.0 / (1.0 + np.exp(-(latent * 2.0)))

    report = compare_calibrators(
        base_predictions=base_prob.tolist(),
        y_true=y_true.tolist(),
        methods=["none", "sigmoid", "temperature", "isotonic"],
        selection_metric="log_loss",
        guardrails={"delta_log_loss_min": 0.0},
        task="binary",
    )

    identity = next(entry for entry in report.entries if entry.method == "identity")
    selected = next(entry for entry in report.entries if entry.selected)

    assert report.selected_method != "identity"
    assert selected.metrics.log_loss is not None
    assert identity.metrics.log_loss is not None
    assert selected.metrics.log_loss <= identity.metrics.log_loss


def test_fit_and_apply_multiclass_temperature_returns_normalized_rows() -> None:
    logits = np.asarray(
        [
            [3.0, 0.5, -0.5],
            [0.2, 2.8, 0.1],
            [-0.2, 0.4, 2.6],
            [2.5, 0.7, -0.3],
        ],
        dtype=float,
    )
    y_true = [0, 1, 2, 0]

    calibrator = fit_calibrator(
        method="temperature",
        y_true=y_true,
        scores=logits.tolist(),
        task="multiclass",
        input_type="logit",
        class_labels=[0, 1, 2],
    )
    calibrated = apply_calibrator(calibrator=calibrator, scores=logits.tolist())

    assert calibrated.shape == logits.shape
    assert np.allclose(np.sum(calibrated, axis=1), 1.0)
