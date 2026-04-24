from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.uncertainty.sensitivity import compute_first_order_indices


class TestSensitivityIndices:
    def test_linear_model_sobol_indices(self) -> None:
        """For z = 2x + 3y with equal std, S_x ~ 4/13, S_y ~ 9/13."""
        rng = np.random.default_rng(42)
        n = 5000
        x = rng.normal(0, 1, n)
        y = rng.normal(0, 1, n)
        z = 2.0 * x + 3.0 * y

        indices = compute_first_order_indices(
            {"x": x, "y": y},
            z,
            ["x", "y"],
        )

        assert indices["x"] == pytest.approx(4.0 / 13.0, abs=0.05)
        assert indices["y"] == pytest.approx(9.0 / 13.0, abs=0.05)

    def test_independent_inputs_sum_to_one(self) -> None:
        """For a linear model with independent inputs, indices should sum to ~1."""
        rng = np.random.default_rng(123)
        n = 5000
        a = rng.normal(5, 2, n)
        b = rng.normal(10, 3, n)
        c = rng.normal(0, 1, n)
        output = 1.0 * a + 2.0 * b + 0.5 * c

        indices = compute_first_order_indices(
            {"a": a, "b": b, "c": c},
            output,
            ["a", "b", "c"],
        )

        total = sum(indices.values())
        assert total == pytest.approx(1.0, abs=0.05)

    def test_single_dominant_input(self) -> None:
        rng = np.random.default_rng(7)
        n = 3000
        x = rng.normal(0, 1, n)
        y = rng.normal(0, 1, n)
        output = 10.0 * x + 0.001 * y

        indices = compute_first_order_indices(
            {"x": x, "y": y},
            output,
            ["x", "y"],
        )

        assert indices["x"] > 0.99
        assert indices["y"] < 0.01

    def test_too_few_inputs_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 2 inputs"):
            compute_first_order_indices(
                {"x": np.array([1.0, 2.0])},
                np.array([1.0, 2.0]),
                ["x"],
            )
