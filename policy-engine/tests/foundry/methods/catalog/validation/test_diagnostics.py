from __future__ import annotations

import numpy as np
import pytest


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestCrossValidation:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "validation.model.cross_validation@1.0.0")
        state = {"fold_scores": np.array([0.8, 0.85, 0.82, 0.79, 0.83])}
        result = method.pure_step(state, {})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "validation.model.cross_validation@1.0.0")
        state = {"fold_scores": np.array([0.9, 0.88, 0.91, 0.87])}
        result = method.pure_step(state, {})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))


class TestWalkForward:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "validation.model.walk_forward@1.0.0")
        state = {
            "actuals": np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
            "forecasts": np.array([1.1, 2.2, 2.8, 4.1, 5.3]),
        }
        result = method.pure_step(state, {})
        assert isinstance(result, dict)


class TestCalibrationDiagnostic:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "validation.calibration.calibration_diagnostic@1.0.0")
        state = {
            "predicted_probs": np.array([0.1, 0.4, 0.6, 0.8, 0.9]),
            "observed_outcomes": np.array([0.0, 0.0, 1.0, 1.0, 1.0]),
        }
        result = method.pure_step(state, {})
        assert isinstance(result, dict)
