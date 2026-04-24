from __future__ import annotations

import numpy as np

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.survey.protocols import SAEResult
from polisyos.ir.analytics.dependence_structure import load_dependence_structure


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


def _chain_graph(n_areas: int) -> dict[str, object]:
    weights = np.zeros((n_areas, n_areas), dtype=float)
    for idx in range(n_areas - 1):
        weights[idx, idx + 1] = 1.0
        weights[idx + 1, idx] = 1.0
    return {
        "graph_id": "policy_chain",
        "family": "CAR",
        "W": weights.tolist(),
        "metadata": {"role": "spatial"},
    }


def _frontier_state() -> dict[str, object]:
    n_areas = 8
    area_ids = [f"area_{idx}" for idx in range(n_areas)]
    return {
        "y_direct": np.array([0.8, 1.0, 1.2, 1.4, 2.8, 3.0, 3.2, 3.4], dtype=float),
        "X": np.ones((n_areas, 1), dtype=float),
        "sampling_var": np.full(n_areas, 0.15, dtype=float),
        "policy_indicator": np.array([0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0], dtype=float),
        "graph": _chain_graph(n_areas),
        "frontier_edges": [("area_3", "area_4", True)],
        "area_ids": area_ids,
    }


class TestCausalFrontierFayHerriot:
    def test_registered(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry, "survey.estimation.causal_frontier_fay_herriot@1.0.0"
        )
        assert method is not None

    def test_boundary_cut_exposes_positive_leakage(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry, "survey.estimation.causal_frontier_fay_herriot@1.0.0"
        )
        result = method.pure_step(
            _frontier_state(),
            {"lambda_spatial": 25.0, "component_ridge": 1e-4},
        )["result"]

        assert isinstance(result, SAEResult)
        diagnostics = result.statistics["diagnostics"]
        assert diagnostics["blr"] > 0.0
        assert result.statistics["tau"] > result.statistics["baseline_unrestricted"]["tau"]
        assert diagnostics["frontier_edges_active"] == 1
        assert diagnostics["component_count"] == 2
        assert result.statistics["component_ids"] == [0, 0, 0, 0, 1, 1, 1, 1]
        assert result.statistics["borrow_strength_neighbors"] == [1, 2, 2, 1, 1, 2, 2, 1]

    def test_supports_named_frontier_edges_and_persists_artifacts(
        self, isolated_registry, tmp_path
    ) -> None:
        method = _method_or_skip(
            isolated_registry, "survey.estimation.causal_frontier_fay_herriot@1.0.0"
        )
        store = FileSystemCAS(tmp_path / "cas")
        result = method.pure_step(
            _frontier_state(),
            {
                "lambda_spatial": 20.0,
                "component_ridge": 1e-4,
                "artifact_store": store,
            },
        )["result"]

        assert result.dependence_ref is not None
        assert result.quality_certificate_ref is not None
        loaded = load_dependence_structure(store, result.dependence_ref)
        assert loaded.regime == "areal"
        assert loaded.source_method == "survey.estimation.causal_frontier_fay_herriot"

    def test_spillover_exposure_is_carried_through_when_present(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry, "survey.estimation.causal_frontier_fay_herriot@1.0.0"
        )
        state = _frontier_state()
        state["spillover_exposure"] = np.array(
            [0.0, 0.2, 0.4, 0.8, 0.8, 0.4, 0.2, 0.0], dtype=float
        )
        result = method.pure_step(
            state,
            {"lambda_spatial": 10.0, "component_ridge": 1e-4},
        )["result"]

        assert result.statistics["spillover_gamma"] is not None
        assert result.statistics["diagnostics"]["spillover_term_included"] is True
