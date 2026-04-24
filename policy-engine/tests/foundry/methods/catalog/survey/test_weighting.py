from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.survey import ensure_survey_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestHorvitzThompson:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.weighting.horvitz_thompson@1.0.0")
        state = {
            "values": np.array([10.0, 20.0, 30.0, 40.0, 50.0]),
            "inclusion_probabilities": np.array([0.2, 0.3, 0.5, 0.4, 0.6]),
        }
        result = method.pure_step(state, {})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.weighting.horvitz_thompson@1.0.0")
        rng = np.random.default_rng(42)
        state = {
            "values": rng.normal(100, 10, size=20),
            "inclusion_probabilities": rng.uniform(0.1, 0.9, size=20),
        }
        result = method.pure_step(state, {})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))


class TestRakeIPF:
    def test_converges_with_grouped_margins(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.weighting.rake_ipf@1.0.0")
        base_pattern = np.array(
            [
                [1.0, 0.0, 1.0, 0.0],  # female, north
                [1.0, 0.0, 0.0, 1.0],  # female, south
                [0.0, 1.0, 1.0, 0.0],  # male, north
                [0.0, 1.0, 0.0, 1.0],  # male, south
            ]
        )
        state = {
            "base_weights": np.ones(100, dtype=float),
            "category_matrix": np.tile(base_pattern, (25, 1)),
            "target_totals": np.array([55.0, 45.0, 60.0, 40.0], dtype=float),
            "margin_ids": np.array([0, 0, 1, 1], dtype=int),
            "margin_names_by_category": ("sex", "sex", "region", "region"),
            "category_labels": ("female", "male", "north", "south"),
        }
        result = method.pure_step(state, {})

        diagnostics = result["diagnostics"]
        achieved = result["result"]["achieved_totals"]

        assert diagnostics.converged is True
        assert diagnostics.decision == "pass"
        assert diagnostics.stop_reason == "converged_exact"
        assert np.allclose(
            np.array(
                [
                    achieved["sex=female"],
                    achieved["sex=male"],
                    achieved["region=north"],
                    achieved["region=south"],
                ]
            ),
            state["target_totals"],
            atol=1e-6,
        )

    def test_blocks_structural_zero(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.weighting.rake_ipf@1.0.0")
        state = {
            "base_weights": np.array([1.0, 1.0, 1.0], dtype=float),
            "category_matrix": np.array(
                [
                    [1.0, 0.0],
                    [1.0, 0.0],
                    [1.0, 0.0],
                ]
            ),
            "target_totals": np.array([2.0, 1.0], dtype=float),
            "margin_ids": np.array([0, 0], dtype=int),
            "margin_names_by_category": ("sex", "sex"),
            "category_labels": ("female", "male"),
        }
        result = method.pure_step(state, {})

        diagnostics = result["diagnostics"]
        assert diagnostics.decision == "block"
        assert diagnostics.stop_reason == "structural_zero"
        assert diagnostics.structural_zero_count == 1

    def test_auto_collapses_sparse_categories(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.weighting.rake_ipf@1.0.0")
        state = {
            "base_weights": np.ones(100, dtype=float),
            "category_matrix": np.column_stack(
                [
                    np.array([1.0] * 88 + [0.0] * 12),
                    np.array([0.0] * 88 + [1.0] * 6 + [0.0] * 6),
                    np.array([0.0] * 94 + [1.0] * 6),
                ]
            ),
            "target_totals": np.array([76.0, 12.0, 12.0], dtype=float),
            "margin_ids": np.array([0, 0, 0], dtype=int),
            "margin_names_by_category": ("age_band", "age_band", "age_band"),
            "category_labels": ("adult", "teen", "senior"),
        }

        result = method.pure_step(state, {})

        diagnostics = result["diagnostics"]
        assert diagnostics.decision == "warn"
        assert diagnostics.stop_reason == "fallback_collapsed_categories"
        assert diagnostics.fallback_used == "collapsed_categories"
        assert set(diagnostics.target_totals) == {"age_band=adult", "age_band=__collapsed__"}

    def test_dispatch_artifacts_include_fallback_attempts(self) -> None:
        MethodRegistry.reset_instance()
        MethodDispatcher.reset_instance()
        ensure_survey_methods_registered()
        registry = MethodRegistry.get_instance()
        dispatcher = MethodDispatcher.get_instance()
        method = registry.get("survey.weighting.rake_ipf@1.0.0")
        state = {
            "base_weights": np.ones(100, dtype=float),
            "category_matrix": np.column_stack(
                [
                    np.r_[np.ones(50, dtype=float), np.zeros(50, dtype=float)],
                    np.r_[np.zeros(50, dtype=float), np.ones(50, dtype=float)],
                ]
            ),
            "target_totals": np.array([90.0, 10.0], dtype=float),
            "margin_ids": np.array([0, 0], dtype=int),
            "margin_names_by_category": ("sex", "sex"),
            "category_labels": ("female", "male"),
        }

        result = dispatcher.dispatch(
            method_class=method,
            signature=method.signature,
            state=state,
            params={},
            seed=19,
        )

        fallback_summary = result.artifacts["fallback_summary"]
        attempt_names = {item["name"] for item in fallback_summary["attempts"]}
        assert {"exact", "bounded_logit", "penalized"} <= attempt_names
        assert result.artifacts["raking_diagnostics"]["decision"] == "warn"
        assert "raking_fallback_used" not in result.warnings
