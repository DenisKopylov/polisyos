from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.catalog.policy.mcda import (
    AHPEstimator,
    ELECTREEstimator,
    RankStabilityEstimator,
    RobustAHPEstimator,
    RobustELECTREEstimator,
    RobustTOPSISEstimator,
    TOPSISEstimator,
)


class TestTOPSIS:
    def test_ranking(self):
        dm = np.array(
            [
                [250, 16, 12],
                [200, 20, 8],
                [300, 12, 16],
            ]
        )
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
        matrix = np.array(
            [
                [1, 3, 5],
                [1 / 3, 1, 5 / 3],
                [1 / 5, 3 / 5, 1],
            ]
        )
        state = {"pairwise_matrix": matrix}
        result = AHPEstimator.pure_step(state, {"cr_threshold": 0.1})["result"]
        assert result["is_consistent"] is True
        assert result["consistency_ratio"] < 0.1
        assert len(result["priority_weights"]) == 3
        assert sum(result["priority_weights"]) == pytest.approx(1.0)

    def test_inconsistent_matrix(self):
        matrix = np.array(
            [
                [1, 9, 1 / 9],
                [1 / 9, 1, 9],
                [9, 1 / 9, 1],
            ]
        )
        state = {"pairwise_matrix": matrix}
        result = AHPEstimator.pure_step(state, {"cr_threshold": 0.1})["result"]
        assert result["is_consistent"] is False


class TestELECTRE:
    def test_outranking(self):
        dm = np.array(
            [
                [80, 90, 600],
                [65, 58, 200],
                [83, 60, 400],
            ]
        )
        weights = np.array([0.4, 0.3, 0.3])
        is_benefit = np.array([True, True, False])
        state = {"decision_matrix": dm, "weights": weights, "is_benefit": is_benefit}
        result = ELECTREEstimator.pure_step(
            state, {"concordance_threshold": 0.6, "discordance_threshold": 0.4}
        )["result"]
        assert len(result["kernel"]) >= 1
        assert len(result["concordance_matrix"]) == 3
        assert len(result["discordance_matrix"]) == 3


class TestRankStability:
    def test_exact_like_weight_interval_example(self):
        utility = np.array(
            [
                [0.9, 0.4],
                [0.6, 0.7],
                [0.3, 0.9],
            ],
            dtype=float,
        )
        stakeholders = [
            {
                "id": "s1",
                "meta_weight": 1.0,
                "weight_model": {
                    "type": "polytope",
                    "lower_bounds": [0.35, 0.0],
                    "upper_bounds": [0.75, 1.0],
                },
            }
        ]

        result = RankStabilityEstimator.pure_step(
            {
                "utility_matrix": utility,
                "stakeholders": stakeholders,
                "reference_weights": [0.55, 0.45],
                "alternative_ids": ["A", "B", "C"],
            },
            {"n_samples": 12000, "seed": 7},
        )["result"]

        assert result["status"] == "tiered"
        assert result["aggregate_ranking"] == ["A", "B", "C"]
        assert result["top_rank_acceptability"]["A"] == pytest.approx(0.625, abs=0.04)
        assert result["pairwise_flip_probability"]["A>B"] == pytest.approx(0.375, abs=0.04)
        assert result["expected_rank_displacement"]["A"] == pytest.approx(0.6364, abs=0.06)
        assert result["kendall_expected_normalized"] == pytest.approx(0.2538, abs=0.05)
        assert "LOW_TOP1_DOMINANCE" in result["refusal_reason_codes"]
        assert result["rank_acceptability"]["A"][0] == pytest.approx(0.625, abs=0.04)
        assert result["rank_intervals"]["A"] == [1, 3]
        assert result["ror_screen_status"] == "ran"
        assert result["pairwise_necessary"]["A>B"] is False
        assert result["pairwise_possible"]["A>B"] is True
        assert result["pairwise_margin_bounds"]["A>B"]["min"] < 0
        assert result["pairwise_margin_bounds"]["A>B"]["max"] > 0
        assert result["flip_surfaces"][0]["pair"] == "A>B"
        assert result["top_flip_pairs"]
        assert result["explanations"]

    def test_point_weights_with_missing_components_stay_stable(self):
        utility = np.array(
            [
                [1.0, np.nan, 0.5],
                [0.7, 0.7, 0.7],
            ],
            dtype=float,
        )
        stakeholders = [
            {
                "id": "s1",
                "meta_weight": 1.0,
                "weight_model": {"type": "point", "weights": [2.0, 1.0, 1.0]},
            }
        ]

        result = RankStabilityEstimator.pure_step(
            {
                "utility_matrix": utility,
                "stakeholders": stakeholders,
                "alternative_ids": ["A", "B"],
            },
            {"n_samples": 32, "seed": 0},
        )["result"]

        assert result["status"] == "full"
        assert result["aggregate_ranking"] == ["A", "B"]
        assert result["top_rank_acceptability"]["A"] == pytest.approx(1.0)
        assert result["expected_rank_displacement"]["A"] == pytest.approx(0.0)
        assert result["pairwise_credibility"]["A>B"] == pytest.approx(1.0)
        assert result["refusal_reason_codes"] == []
        assert result["ror_screen_status"] == "skipped_missing_components"

    def test_ror_screen_marks_necessary_pairs_inside_stable_interval(self):
        utility = np.array(
            [
                [0.9, 0.4],
                [0.6, 0.7],
                [0.3, 0.9],
            ],
            dtype=float,
        )
        stakeholders = [
            {
                "id": "s1",
                "weight_model": {
                    "type": "polytope",
                    "lower_bounds": [0.55, 0.0],
                    "upper_bounds": [0.75, 0.45],
                },
            }
        ]

        result = RankStabilityEstimator.pure_step(
            {
                "utility_matrix": utility,
                "stakeholders": stakeholders,
                "reference_weights": [0.60, 0.40],
                "alternative_ids": ["A", "B", "C"],
                "criteria_ids": ["benefit", "equity"],
            },
            {"n_samples": 512, "seed": 3},
        )["result"]

        assert result["ror_screen_status"] == "ran"
        assert result["pairwise_necessary"]["A>B"] is True
        assert result["pairwise_possible"]["B>A"] is False
        assert result["pairwise_margin_bounds"]["A>B"]["min"] > 0
        assert result["flip_surfaces"][0]["dominant_criteria"] == ["benefit", "equity"]


class TestRobustMCDA:
    def test_robust_topsis_reports_stability_contract(self):
        dm = np.array(
            [
                [80, 90, 600],
                [65, 58, 200],
                [83, 60, 400],
            ]
        )
        stakeholders = [
            {
                "id": "s1",
                "meta_weight": 1.0,
                "weight_model": {"type": "dirichlet", "alpha": [4.0, 3.0, 2.0]},
            }
        ]

        result = RobustTOPSISEstimator.pure_step(
            {
                "decision_matrix": dm,
                "is_benefit": [True, True, False],
                "stakeholders": stakeholders,
                "alternative_ids": ["A", "B", "C"],
            },
            {"n_samples": 256, "seed": 11},
        )["result"]

        assert result["method"] == "topsis"
        assert result["aggregate_ranking"][0] in {"A", "B", "C"}
        assert "reference_method_output" in result
        assert len(result["reference_method_output"]["closeness_coefficients"]) == 3
        assert result["ror_screen_status"] == "skipped_non_linear_method"
        assert result["pairwise_credibility"]

    def test_robust_ahp_accepts_stakeholder_pairwise_matrix(self):
        priorities = np.array(
            [
                [0.9, 0.7],
                [0.4, 0.6],
            ],
            dtype=float,
        )
        stakeholders = [
            {
                "id": "committee",
                "pairwise_matrix": [
                    [1.0, 3.0],
                    [1.0 / 3.0, 1.0],
                ],
            }
        ]

        result = RobustAHPEstimator.pure_step(
            {
                "local_priority_matrix": priorities,
                "stakeholders": stakeholders,
                "alternative_ids": ["A", "B"],
            },
            {"n_samples": 32, "seed": 0},
        )["result"]

        assert result["method"] == "ahp"
        assert result["status"] == "full"
        assert result["aggregate_ranking"] == ["A", "B"]
        assert result["top_rank_acceptability"]["A"] == pytest.approx(1.0)
        assert result["pairwise_necessary"]["A>B"] is True
        assert result["reference_method_output"]["priority_weights"] == pytest.approx([0.75, 0.25])

    def test_robust_electre_reports_reference_outranking(self):
        dm = np.array(
            [
                [80, 90, 600],
                [65, 58, 200],
                [83, 60, 400],
            ]
        )
        stakeholders = [
            {
                "id": "s1",
                "weight_model": {"type": "dirichlet", "alpha": [3.0, 3.0, 2.0]},
            }
        ]

        result = RobustELECTREEstimator.pure_step(
            {
                "decision_matrix": dm,
                "is_benefit": [True, True, False],
                "stakeholders": stakeholders,
                "alternative_ids": ["A", "B", "C"],
            },
            {
                "concordance_threshold": 0.6,
                "discordance_threshold": 0.4,
                "n_samples": 128,
                "seed": 5,
            },
        )["result"]

        assert result["method"] == "electre"
        assert result["status"] in {"full", "tiered", "refusal"}
        assert "kernel" in result["reference_method_output"]
        assert result["ror_screen_status"] == "skipped_non_linear_method"
