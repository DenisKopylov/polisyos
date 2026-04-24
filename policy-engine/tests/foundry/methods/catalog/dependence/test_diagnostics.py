from __future__ import annotations

import numpy as np


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestGraphDependenceDiagnostic:
    def test_detects_graph_local_dependence(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "dependence.diagnostic.graph_dependence@1.0.0")
        residuals = np.array([1.0, 1.1, -0.9, -1.0, 0.95, -0.85], dtype=float)
        graph = [
            {
                "graph_id": "chain",
                "family": "SAR",
                "W": [
                    [0, 1, 0, 0, 0, 0],
                    [1, 0, 1, 0, 0, 0],
                    [0, 1, 0, 1, 0, 0],
                    [0, 0, 1, 0, 1, 0],
                    [0, 0, 0, 1, 0, 1],
                    [0, 0, 0, 0, 1, 0],
                ],
            }
        ]
        result = method.pure_step(
            {"residuals": residuals, "candidate_graphs": graph},
            {"score_threshold": 0.05},
        )["result"]
        assert result.detected is True
        assert result.selected_graph_id == "chain"
        assert result.class_label == "graph_local"

    def test_reports_non_identifiable_graphs(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "dependence.diagnostic.graph_dependence@1.0.0")
        residuals = np.array([0.1, -0.1, 0.05, -0.05], dtype=float)
        graph = [
            {
                "graph_id": "degenerate",
                "family": "SAR",
                "W": np.zeros((4, 4), dtype=float).tolist(),
            }
        ]
        result = method.pure_step(
            {"residuals": residuals, "candidate_graphs": graph},
            {},
        )["result"]
        assert result.detected is False
        assert result.estimator_status == "not_identified"
        assert result.fallback_reason == "no_identifiable_candidate_graph"

    def test_exposes_pesaran_and_lm_diagnostics_when_panel_like_metadata_is_available(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(isolated_registry, "dependence.diagnostic.graph_dependence@1.0.0")
        residuals = np.array([0.9, 1.1, -0.8, -1.0, 0.7, -0.9], dtype=float)
        pseudo_panel = np.array(
            [
                [1.00, 0.95, 1.05, 0.98, 1.02],
                [0.92, 0.90, 0.88, 0.94, 0.91],
                [-0.81, -0.77, -0.84, -0.79, -0.82],
                [-0.97, -0.94, -1.02, -0.99, -0.96],
                [0.69, 0.73, 0.70, 0.74, 0.71],
                [-0.86, -0.91, -0.88, -0.90, -0.87],
            ],
            dtype=float,
        )
        graph = [
            {
                "graph_id": "chain",
                "family": "SAR",
                "W": [
                    [0, 1, 0, 0, 0, 0],
                    [1, 0, 1, 0, 0, 0],
                    [0, 1, 0, 1, 0, 0],
                    [0, 0, 1, 0, 1, 0],
                    [0, 0, 0, 1, 0, 1],
                    [0, 0, 0, 0, 1, 0],
                ],
            }
        ]
        result = method.pure_step(
            {
                "residuals": residuals,
                "candidate_graphs": graph,
                "metadata": {
                    "residual_draws": pseudo_panel,
                    "y_direct": (5.0 + residuals).tolist(),
                    "X": np.ones((6, 1), dtype=float).tolist(),
                },
            },
            {"score_threshold": 0.05},
        )["result"]
        assert result.pesaran_cd is not None
        assert result.pesaran_cd_p_value is not None
        assert result.lm_error is not None
        assert result.lm_error_p_value is not None
        assert result.lm_lag is not None
        assert result.lm_lag_p_value is not None
