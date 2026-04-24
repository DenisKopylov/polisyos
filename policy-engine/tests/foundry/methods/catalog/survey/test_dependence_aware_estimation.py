from __future__ import annotations

import numpy as np

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.survey.protocols import SAEResult
from polisyos.ir.analytics.dependence_structure import load_dependence_structure


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


def _chain_graph(n: int) -> dict[str, object]:
    weights = np.zeros((n, n), dtype=float)
    for idx in range(n - 1):
        weights[idx, idx + 1] = 1.0
        weights[idx + 1, idx] = 1.0
    return {
        "graph_id": "spatial_chain",
        "family": "SAR",
        "W": weights.tolist(),
        "metadata": {"role": "spatial"},
    }


class TestDependenceAwareFayHerriot:
    def test_registered(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry, "survey.estimation.fay_herriot_dependence_aware@1.0.0"
        )
        assert method is not None

    def test_auto_mode_falls_back_without_useful_graph_signal(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry, "survey.estimation.fay_herriot_dependence_aware@1.0.0"
        )
        n_areas = 8
        x = np.column_stack([np.ones(n_areas), np.linspace(-1.0, 1.0, n_areas)])
        y = np.array([10.0, 11.1, 10.9, 12.0, 11.8, 13.1, 12.9, 14.0], dtype=float)
        sampling_var = np.full(n_areas, 0.4, dtype=float)
        result = method.pure_step(
            {
                "y_direct": y,
                "X": x,
                "sampling_var": sampling_var,
                "candidate_graphs": [
                    {
                        "graph_id": "degenerate",
                        "family": "SAR",
                        "W": np.zeros((n_areas, n_areas), dtype=float).tolist(),
                    }
                ],
            },
            {"mode": "auto", "score_threshold": 0.05},
        )["result"]
        assert isinstance(result, SAEResult)
        stats = result.statistics
        assert stats["selected_model"] == "independent"
        assert stats["variance_components"]["selected_graph_id"] is None
        assert stats["diagnostics"]["fallback_reason"] in {
            "no_identifiable_candidate_graph",
            "dependence_not_detected",
        }

    def test_auto_mode_selects_graph_when_dependence_is_strong(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry, "survey.estimation.fay_herriot_dependence_aware@1.0.0"
        )
        rng = np.random.default_rng(123)
        n_areas = 10
        x = np.ones((n_areas, 1), dtype=float)
        sampling_var = np.full(n_areas, 0.02, dtype=float)
        weights = np.asarray(_chain_graph(n_areas)["W"], dtype=float)
        row_sums = np.sum(weights, axis=1, keepdims=True)
        row_sums[row_sums == 0.0] = 1.0
        normalized = weights / row_sums
        rho = 0.8
        mean = np.full(n_areas, 4.0, dtype=float)
        latent = np.linalg.solve(
            np.eye(n_areas) - rho * normalized, rng.normal(scale=0.35, size=n_areas)
        )
        y = mean + latent + rng.normal(scale=np.sqrt(sampling_var), size=n_areas)
        result = method.pure_step(
            {
                "y_direct": y,
                "X": x,
                "sampling_var": sampling_var,
                "candidate_graphs": [_chain_graph(n_areas)],
            },
            {
                "mode": "auto",
                "score_threshold": 0.05,
                "rho_grid_size": 31,
                "tau2_grid_size": 24,
            },
        )["result"]
        stats = result.statistics
        assert stats["selected_model"] == "graph"
        assert stats["variance_components"]["selected_graph_id"] == "spatial_chain"
        assert stats["diagnostics"]["fallback_reason"] is None
        assert len(stats["estimates"]) == n_areas

    def test_heldout_logscore_can_drive_graph_selection(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry, "survey.estimation.fay_herriot_dependence_aware@1.0.0"
        )
        rng = np.random.default_rng(321)
        n_areas = 9
        x = np.ones((n_areas, 1), dtype=float)
        sampling_var = np.full(n_areas, 0.03, dtype=float)
        weights = np.asarray(_chain_graph(n_areas)["W"], dtype=float)
        row_sums = np.sum(weights, axis=1, keepdims=True)
        row_sums[row_sums == 0.0] = 1.0
        normalized = weights / row_sums
        latent = np.linalg.solve(
            np.eye(n_areas) - 0.75 * normalized, rng.normal(scale=0.30, size=n_areas)
        )
        y = 6.0 + latent + rng.normal(scale=np.sqrt(sampling_var), size=n_areas)

        result = method.pure_step(
            {
                "y_direct": y,
                "X": x,
                "sampling_var": sampling_var,
                "candidate_graphs": [_chain_graph(n_areas)],
            },
            {
                "mode": "auto",
                "criterion": "heldout_logscore",
                "rho_grid_size": 31,
                "tau2_grid_size": 24,
            },
        )["result"]
        stats = result.statistics

        assert stats["selected_model"] == "graph"
        assert stats["diagnostics"]["fallback_reason"] is None
        assert stats["diagnostics"]["selection_candidates"][1]["criterion_improvement"] > 0.0

    def test_hybrid_mode_can_collapse_to_single_kernel_safely(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry, "survey.estimation.fay_herriot_dependence_aware@1.0.0"
        )
        rng = np.random.default_rng(111)
        n_areas = 8
        x = np.ones((n_areas, 1), dtype=float)
        sampling_var = np.full(n_areas, 0.02, dtype=float)
        spatial_graph = _chain_graph(n_areas)
        admin_graph = {
            "graph_id": "admin_sparse",
            "family": "SAR",
            "W": np.zeros((n_areas, n_areas), dtype=float).tolist(),
            "metadata": {"role": "admin"},
        }
        weights = np.asarray(spatial_graph["W"], dtype=float)
        row_sums = np.sum(weights, axis=1, keepdims=True)
        row_sums[row_sums == 0.0] = 1.0
        normalized = weights / row_sums
        latent = np.linalg.solve(
            np.eye(n_areas) - 0.8 * normalized, rng.normal(scale=0.25, size=n_areas)
        )
        y = 3.5 + latent + rng.normal(scale=np.sqrt(sampling_var), size=n_areas)

        result = method.pure_step(
            {
                "y_direct": y,
                "X": x,
                "sampling_var": sampling_var,
                "candidate_graphs": [spatial_graph, admin_graph],
            },
            {
                "mode": "hybrid",
                "rho_grid_size": 25,
                "tau2_grid_size": 20,
            },
        )["result"]
        stats = result.statistics

        assert stats["selected_model"] in {"graph", "hybrid", "independent"}
        if stats["selected_model"] == "graph":
            assert stats["variance_components"]["selected_graph_id"] == "spatial_chain"
            assert stats["diagnostics"]["selection_note"] == "hybrid_collapsed_to_single_kernel"

    def test_coverage_benchmark_hook_emits_quality_certificate(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry, "survey.estimation.fay_herriot_dependence_aware@1.0.0"
        )
        rng = np.random.default_rng(2024)
        n_areas = 6
        x = np.ones((n_areas, 1), dtype=float)
        sampling_var = np.full(n_areas, 0.04, dtype=float)
        weights = np.asarray(_chain_graph(n_areas)["W"], dtype=float)
        row_sums = np.sum(weights, axis=1, keepdims=True)
        row_sums[row_sums == 0.0] = 1.0
        normalized = weights / row_sums
        latent = np.linalg.solve(
            np.eye(n_areas) - 0.7 * normalized, rng.normal(scale=0.25, size=n_areas)
        )
        y = 4.0 + latent + rng.normal(scale=np.sqrt(sampling_var), size=n_areas)

        result = method.pure_step(
            {
                "y_direct": y,
                "X": x,
                "sampling_var": sampling_var,
                "candidate_graphs": [_chain_graph(n_areas)],
            },
            {
                "mode": "auto",
                "coverage_benchmark_reps": 2,
                "coverage_bootstrap_reps": 0,
                "rho_grid_size": 21,
                "tau2_grid_size": 16,
            },
        )["result"]

        quality_certificate = result.statistics["quality_certificate"]
        assert quality_certificate["coverage_benchmark_id"].startswith("fh_dependence_benchmark_")
        assert "summary" in quality_certificate

    def test_persists_shared_dependence_ref(self, isolated_registry, tmp_path) -> None:
        method = _method_or_skip(
            isolated_registry, "survey.estimation.fay_herriot_dependence_aware@1.0.0"
        )
        store = FileSystemCAS(tmp_path / "cas")
        n_areas = 7
        x = np.column_stack([np.ones(n_areas), np.linspace(-1.0, 1.0, n_areas)])
        y = np.array([10.0, 10.7, 11.2, 11.9, 12.5, 13.0, 13.6], dtype=float)
        sampling_var = np.full(n_areas, 0.15, dtype=float)

        result = method.pure_step(
            {
                "y_direct": y,
                "X": x,
                "sampling_var": sampling_var,
                "candidate_graphs": [_chain_graph(n_areas)],
            },
            {"mode": "auto", "artifact_store": store},
        )["result"]

        assert result.dependence_ref is not None
        loaded = load_dependence_structure(store, result.dependence_ref)
        assert loaded.regime == "areal"
        assert loaded.source_method == "survey.estimation.fay_herriot_dependence_aware"
