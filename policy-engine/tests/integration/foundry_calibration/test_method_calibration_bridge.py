from __future__ import annotations

import numpy as np
import pytest

from polisyos.calibration import evaluate_binary
from polisyos.foundry.methods.catalog.econometrics.discrete_choice import LogitEstimator

pytestmark = pytest.mark.integration


def test_foundry_method_output_feeds_calibration_diagnostics() -> None:
    features = np.array(
        [[-1.2], [-0.8], [-0.4], [0.0], [0.3], [0.7], [1.0], [1.4]],
        dtype=float,
    )
    outcomes = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 1.0], dtype=float)

    method_output = LogitEstimator.pure_step(
        {"X": features, "y": outcomes},
        {"max_iter": 50},
    )["result"]
    coefficients = np.asarray(method_output["coefficients"], dtype=float)
    design = np.column_stack([np.ones(features.shape[0]), features])
    predicted_probabilities = 1.0 / (1.0 + np.exp(-(design @ coefficients)))

    report = evaluate_binary(
        y_true=outcomes.tolist(),
        y_prob=predicted_probabilities.tolist(),
        curves={"binning": ["uniform", "quantile"], "n_bins": [4]},
        tests=["spiegelhalter"],
        uncertainty={"bootstrap": 8, "seed": 7},
    )

    assert method_output["n_obs"] == report.metrics.n_obs
    assert report.task == "binary"
    assert report.target_type == "probability"
    assert report.primary_curve == "quantile_4"
    assert report.metrics.brier is not None
    assert report.metrics.ece is not None
    assert report.metrics.intervals["brier"].low <= report.metrics.brier
    assert any(bin_.count > 0 for bin_ in report.curves["quantile_4"])
