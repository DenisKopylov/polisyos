"""Property-based tests for survey design and estimation methods."""

from __future__ import annotations

import numpy as np
from hypothesis import HealthCheck, given, settings

from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method
from tests.unit.foundry.methods.testing.strategies import survey_strategy


def _run(registry, dispatcher, state):
    method = registry.get("survey.design.complex_survey@1.0.0")
    return invoke_property_method(
        dispatcher=dispatcher,
        method_class=method,
        state=state,
        bound_inputs=state,
        params={},
        seed=17,
    ).output["result"]


def _clusters_within_strata(strata):
    clusters = np.empty(strata.shape, dtype=int)
    next_id = 0
    for stratum in np.unique(strata):
        indices = np.flatnonzero(strata == stratum)
        local_ids = np.arange(indices.size, dtype=int) // 2
        clusters[indices] = next_id + local_ids
        next_id += int(local_ids.max()) + 1
    return clusters


class TestComplexSurveyProperties:
    @given(data=survey_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_weighted_mean_in_range(self, data, isolated_registry, property_method_dispatcher):
        """The design-weighted mean lies within the observed outcome support."""
        outcome = np.asarray(data["outcome"], dtype=float)
        strata = np.asarray(data["strata_id"], dtype=int)
        state = {
            "y": outcome,
            "weights": np.asarray(data["weights"], dtype=float),
            "strata": strata,
            "clusters": _clusters_within_strata(strata),
        }
        result = _run(isolated_registry, property_method_dispatcher, state)
        mean = float(result["weighted_mean"])
        assert np.isfinite(mean)
        assert float(np.min(outcome)) - 1e-6 <= mean <= float(np.max(outcome)) + 1e-6

    @given(data=survey_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_se_non_negative(self, data, isolated_registry, property_method_dispatcher):
        """The complex-design standard error is non-negative."""
        strata = np.asarray(data["strata_id"], dtype=int)
        state = {
            "y": np.asarray(data["outcome"], dtype=float),
            "weights": np.asarray(data["weights"], dtype=float),
            "strata": strata,
            "clusters": _clusters_within_strata(strata),
        }
        result = _run(isolated_registry, property_method_dispatcher, state)
        standard_error = float(result["standard_error"])
        assert np.isfinite(standard_error)
        assert standard_error >= 0.0


class TestRakingProperties:
    @given(data=survey_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_raking_weights_positive(self, data, isolated_registry, property_method_dispatcher):
        """Raked weights stay positive and reproduce the supplied stratum totals."""
        weights = np.asarray(data["weights"], dtype=float)
        strata = np.asarray(data["strata_id"], dtype=int)
        strata_matrix = np.eye(int(data["n_strata"]), dtype=float)[strata]
        parity_matrix = np.eye(2, dtype=float)[np.arange(weights.size) % 2]
        categories = np.column_stack((strata_matrix, parity_matrix))
        strata_targets = strata_matrix.T @ weights
        parity_targets = parity_matrix.T @ weights
        transfer = 0.1 * float(np.min(parity_targets))
        targets = np.concatenate(
            (strata_targets, parity_targets + np.array([transfer, -transfer], dtype=float))
        )
        state = {"sample_weights": weights, "category_matrix": categories, "target_totals": targets}
        result = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=isolated_registry.get("survey.weighting.raking@1.0.0"),
            state=state,
            bound_inputs=state,
            params={},
            seed=17,
        ).output["result"]
        raked = np.asarray(result["calibrated_weights"], dtype=float)
        assert result["converged"] is True
        assert np.all(np.isfinite(raked))
        assert np.all(raked > 0.0)
        assert not np.allclose(raked, weights)
        achieved = np.asarray(result["achieved_totals"], dtype=float)
        n_strata = int(data["n_strata"])
        np.testing.assert_allclose(achieved[:n_strata], targets[:n_strata], atol=1e-6)
        np.testing.assert_allclose(achieved[n_strata:], targets[n_strata:], atol=1e-6)
