from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.policy.mcda import (
    AHPEstimator,
    ELECTREEstimator,
    TOPSISEstimator,
)


class TestTOPSIS:
    def test_ranking(self):
        dm = np.array([
            [250, 16, 12],
            [200, 20, 8],
            [300, 12, 16],
        ])
        weights = np.array([0.5, 0.3, 0.2])
        is_benefit = np.array([False, True, True])  # cost, benefit, benefit
        state = {"decision_matrix": dm, "weights": weights, "is_benefit": is_benefit}
        result = TOPSISEstimator.pure_step(state, {})["result"]
        assert len(result["closeness_coefficients"]) == 3
        assert len(result["ranking"]) == 3
        assert result["best_alternative"] in [0, 1, 2]

    def test_identical_alternatives(self):
        dm = np.array([[10, 20], [10, 20]])
        weights = np.array([0.5, 0.5])
        is_benefit = np.array([True, True])
        state = {"decision_matrix": dm, "weights": weights, "is_benefit": is_benefit}
        result = TOPSISEstimator.pure_step(state, {})["result"]
        assert result["closeness_coefficients"][0] == pytest.approx(
            result["closeness_coefficients"][1]
        )


class TestAHP:
    def test_consistent_matrix(self):
        # Perfectly consistent 3x3
        matrix = np.array([
            [1, 3, 5],
            [1 / 3, 1, 5 / 3],
            [1 / 5, 3 / 5, 1],
        ])
        state = {"pairwise_matrix": matrix}
        result = AHPEstimator.pure_step(state, {"cr_threshold": 0.1})["result"]
        assert result["is_consistent"] is True
        assert result["consistency_ratio"] < 0.1
        assert len(result["priority_weights"]) == 3
        assert sum(result["priority_weights"]) == pytest.approx(1.0)

    def test_inconsistent_matrix(self):
        matrix = np.array([
            [1, 9, 1 / 9],
            [1 / 9, 1, 9],
            [9, 1 / 9, 1],
        ])
        state = {"pairwise_matrix": matrix}
        result = AHPEstimator.pure_step(state, {"cr_threshold": 0.1})["result"]
        assert result["is_consistent"] is False


class TestELECTRE:
    def test_outranking(self):
        dm = np.array([
            [80, 90, 600],
            [65, 58, 200],
            [83, 60, 400],
        ])
        weights = np.array([0.4, 0.3, 0.3])
        is_benefit = np.array([True, True, False])
        state = {"decision_matrix": dm, "weights": weights, "is_benefit": is_benefit}
        result = ELECTREEstimator.pure_step(
            state, {"concordance_threshold": 0.6, "discordance_threshold": 0.4}
        )["result"]
        assert len(result["kernel"]) >= 1
        assert len(result["concordance_matrix"]) == 3
        assert len(result["discordance_matrix"]) == 3
