"""Property-based tests for validation methods."""

from __future__ import annotations

import sys

import numpy as np
import pytest

try:
    from hypothesis import HealthCheck, given, settings

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
sys.path.insert(0, "src")

from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method
from tests.unit.foundry.methods.testing.strategies import cross_section_strategy


def _invoke(
    isolated_registry,
    property_method_dispatcher,
    fqn: str,
    state: dict,
    *,
    seed: int = 42,
):
    return invoke_property_method(
        dispatcher=property_method_dispatcher,
        method_class=isolated_registry.get(fqn),
        state=state,
        bound_inputs=state,
        params={},
        seed=seed,
    ).output


def _fold_scores(outcome: np.ndarray, n_folds: int = 3) -> np.ndarray:
    """Produce explicit finite fold-score inputs for the aggregation contract."""
    return np.asarray(
        [
            np.sqrt(np.mean(np.square(chunk)))
            for chunk in np.array_split(np.asarray(outcome, dtype=float), n_folds)
        ],
        dtype=float,
    )


class TestCrossValidationProperties:
    @given(data=cross_section_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_cv_output_finite(self, data, isolated_registry, property_method_dispatcher):
        scores = _fold_scores(data["outcome"])
        state = {"fold_scores": scores}
        output = _invoke(
            isolated_registry,
            property_method_dispatcher,
            "validation.model.cross_validation@1.0.0",
            state,
        )
        result = output["result"]

        assert result["n_folds"] == 3
        assert np.isfinite(result["mean_score"])
        assert np.isfinite(result["std_score"])
        assert np.isfinite(result["ci_lower"])
        assert np.isfinite(result["ci_upper"])
        assert result["mean_score"] == pytest.approx(float(np.mean(scores)))

    @given(data=cross_section_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_cv_deterministic(self, data, isolated_registry, property_method_dispatcher):
        """The fold-score aggregator is deterministic for an unchanged request."""
        state = {"fold_scores": _fold_scores(data["outcome"])}
        fqn = "validation.model.cross_validation@1.0.0"
        first = _invoke(isolated_registry, property_method_dispatcher, fqn, state)
        second = _invoke(isolated_registry, property_method_dispatcher, fqn, state)

        assert first["result"] == second["result"]


class TestNormalScoresProperties:
    @given(data=cross_section_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_normal_scores_output_finite(self, data, isolated_registry, property_method_dispatcher):
        observations = np.asarray(data["outcome"], dtype=float)
        state = {
            "observations": observations,
            "predictive_mean": np.zeros_like(observations),
            "predictive_std": np.ones_like(observations),
        }
        output = _invoke(
            isolated_registry,
            property_method_dispatcher,
            "validation.probabilistic.normal_scores@1.0.0",
            state,
        )
        result = output["result"]

        assert np.isfinite(result["mean_log_score"])
        assert np.isfinite(result["mean_crps"])
        assert result["mean_crps"] >= 0.0

    @given(data=cross_section_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_scores_bounded(self, data, isolated_registry, property_method_dispatcher):
        """A centered Gaussian forecast has lower CRPS than a unit-shifted forecast."""
        observations = np.asarray(data["outcome"], dtype=float)
        std = np.ones_like(observations)
        fqn = "validation.probabilistic.normal_scores@1.0.0"
        centered_state = {
            "observations": observations,
            "predictive_mean": observations,
            "predictive_std": std,
        }
        shifted_state = {
            "observations": observations,
            "predictive_mean": observations + 1.0,
            "predictive_std": std,
        }
        centered = _invoke(isolated_registry, property_method_dispatcher, fqn, centered_state)[
            "result"
        ]
        shifted = _invoke(isolated_registry, property_method_dispatcher, fqn, shifted_state)[
            "result"
        ]

        assert np.isfinite(centered["mean_crps"])
        assert centered["mean_crps"] >= 0.0
        assert centered["mean_crps"] < shifted["mean_crps"]
