"""Tests for SensitivityBridge."""

from __future__ import annotations

import pytest

SALib = pytest.importorskip("SALib", reason="SALib not installed")

from polisyos.scientist.autotune.sensitivity_bridge import SensitivityBridge


class TestSensitivityBridge:
    def test_morris_bridge(self):
        bridge = SensitivityBridge()
        bounds = [
            {"name": "x1", "lower": 0.0, "upper": 1.0},
            {"name": "x2", "lower": 0.0, "upper": 1.0},
        ]

        def evaluator(params: dict) -> float:
            return params["x1"] * 2 + params["x2"] * 0.1

        result = bridge.analyze_search_space(
            bounds,
            evaluator,
            method="morris",
            n_trajectories=4,
            n_levels=4,
        )
        assert "ranking" in result
        assert len(result["ranking"]) == 2
        assert result["method"] == "morris"

    def test_sobol_bridge(self):
        bridge = SensitivityBridge()
        bounds = [
            {"name": "a", "lower": 0.0, "upper": 1.0},
            {"name": "b", "lower": 0.0, "upper": 1.0},
        ]

        def evaluator(params: dict) -> float:
            return params["a"] ** 2 + params["b"]

        result = bridge.analyze_search_space(
            bounds,
            evaluator,
            method="sobol",
            n_trajectories=8,
        )
        assert "ranking" in result
        assert result["method"] == "sobol"

    def test_empty_space(self):
        bridge = SensitivityBridge()
        result = bridge.analyze_search_space([], lambda p: 0.0)
        assert result["ranking"] == []

    def test_ranking_has_all_params(self):
        bridge = SensitivityBridge()
        bounds = [
            {"name": "p1", "lower": 0.0, "upper": 10.0},
            {"name": "p2", "lower": -5.0, "upper": 5.0},
            {"name": "p3", "lower": 0.0, "upper": 1.0},
        ]
        result = bridge.analyze_search_space(
            bounds,
            lambda p: sum(p.values()),
            method="morris",
            n_trajectories=4,
        )
        assert set(result["ranking"]) == {"p1", "p2", "p3"}
