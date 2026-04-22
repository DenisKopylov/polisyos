from __future__ import annotations

import numpy as np
import pytest


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestMultidimensionalPoverty:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.poverty.multidimensional@1.0.0")
        rng = np.random.default_rng(42)
        state = {
            "deprivation_matrix": rng.integers(0, 2, size=(50, 4)).astype(float),
            "weights": np.array([0.25, 0.25, 0.25, 0.25]),
        }
        result = method.pure_step(state, {"k_threshold": 0.33})
        assert isinstance(result, dict)


class TestOrdinalMultidimensionalPoverty:
    @staticmethod
    def _base_state() -> dict[str, np.ndarray]:
        return {
            "category_matrix": np.array(
                [
                    [1, 1, 1],
                    [2, 2, 2],
                    [1, 3, 1],
                    [3, 1, 2],
                    [4, 2, 1],
                    [3, 4, 3],
                ],
                dtype=float,
            ),
            "weights": np.array([1 / 3, 1 / 3, 1 / 3], dtype=float),
        }

    @staticmethod
    def _base_params() -> dict[str, object]:
        return {
            "category_orders": [[1, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3]],
            "deprivation_cutoffs": [2, 2, 1],
            "k_threshold": 2 / 3,
            "dimension_names": ["health", "education", "housing"],
        }

    def test_micro_example_matches_oraf_reference_values(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.poverty.ordinal_multidimensional@1.0.0")
        result = method.pure_step(self._base_state(), self._base_params())
        payload = result["result"]

        assert payload["n_poor"] == 4
        assert payload["poor_mask"] == [1, 1, 1, 0, 1, 0]
        assert payload["headcount_h"] == pytest.approx(4 / 6, rel=1e-6, abs=1e-6)
        assert payload["ordinal_adjusted_headcount_q"] == pytest.approx(0.25, rel=1e-6, abs=1e-6)
        assert payload["ordinal_intensity_a"] == pytest.approx(0.375, rel=1e-6, abs=1e-6)
        assert payload["af_m0_baseline"] == pytest.approx(0.5, rel=1e-6, abs=1e-6)
        assert payload["dimension_contributions"]["available"] is True
        assert payload["cutoff_diagnostics"]["recoding_invariance_bound"] == 0.0

    def test_monotone_recoding_leaves_oraf_unchanged(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.poverty.ordinal_multidimensional@1.0.0")
        baseline = method.pure_step(self._base_state(), self._base_params())["result"]

        recoded_state = {
            "category_matrix": np.array(
                [
                    [1, 1, 1],
                    [2, 4, 9],
                    [1, 10, 1],
                    [10, 1, 9],
                    [100, 4, 1],
                    [10, 100, 20],
                ],
                dtype=float,
            ),
            "weights": np.array([1 / 3, 1 / 3, 1 / 3], dtype=float),
        }
        recoded_params = {
            **self._base_params(),
            "category_orders": [[1, 2, 10, 100], [1, 4, 10, 100], [1, 9, 20]],
        }
        recoded = method.pure_step(recoded_state, recoded_params)["result"]

        for key in ("headcount_h", "ordinal_intensity_a", "ordinal_adjusted_headcount_q", "af_m0_baseline"):
            assert recoded[key] == pytest.approx(baseline[key], rel=1e-9, abs=1e-9)
        assert recoded["poor_mask"] == baseline["poor_mask"]
        assert recoded["severity_scores"] == pytest.approx(baseline["severity_scores"], rel=1e-9, abs=1e-9)

    def test_af_nesting_via_last_threshold_weights(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.poverty.ordinal_multidimensional@1.0.0")
        payload = method.pure_step(
            self._base_state(),
            {
                **self._base_params(),
                "threshold_weights": "af_last",
            },
        )["result"]

        assert payload["ordinal_adjusted_headcount_q"] == pytest.approx(
            payload["af_m0_baseline"],
            rel=1e-9,
            abs=1e-9,
        )
        assert payload["threshold_weights_basis"] == "af_last"

    def test_string_category_labels_are_supported(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.poverty.ordinal_multidimensional@1.0.0")
        payload = method.pure_step(
            {
                "category_matrix": np.array(
                    [
                        ["very_bad", "none", "poor"],
                        ["bad", "basic", "basic"],
                        ["very_bad", "secondary", "poor"],
                        ["good", "none", "basic"],
                    ],
                    dtype=object,
                ),
                "weights": np.array([1 / 3, 1 / 3, 1 / 3], dtype=float),
            },
            {
                "category_orders": [
                    ["very_bad", "bad", "good", "very_good"],
                    ["none", "basic", "secondary", "higher"],
                    ["poor", "basic", "adequate"],
                ],
                "deprivation_cutoffs": [2, 2, 1],
                "k_threshold": 2 / 3,
                "dimension_names": ["health", "education", "housing"],
                "return_cutoff_diagnostics": False,
            },
        )["result"]

        assert payload["n_poor"] == 3
        assert payload["poor_mask"] == [1, 1, 1, 0]
        assert payload["threshold_weights_basis"] == "equal"

    def test_legacy_gap_envelope_exposes_recoding_sensitivity(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.poverty.ordinal_multidimensional@1.0.0")
        payload = method.pure_step(
            self._base_state(),
            {
                **self._base_params(),
                "return_cutoff_diagnostics": False,
                "comparator_recodings": [
                    {
                        "name": "stretched",
                        "category_orders": [[1, 2, 10, 100], [1, 4, 10, 100], [1, 9, 20]],
                    }
                ],
            },
        )["result"]

        envelope = payload["legacy_gap_envelope"]
        assert envelope["envelope_width"] > 0.0
        assert envelope["q_gap_max"] > envelope["q_gap_min"]
        assert envelope["baseline_q_gap"] == pytest.approx(0.25, rel=1e-6, abs=1e-6)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.poverty.multidimensional@1.0.0")
        state = {
            "deprivation_matrix": np.array([[1, 0, 1], [0, 0, 0], [1, 1, 1]], dtype=float),
            "weights": np.array([0.4, 0.3, 0.3]),
        }
        result = method.pure_step(state, {"k_threshold": 0.5})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))

    def test_no_deprivation(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.poverty.multidimensional@1.0.0")
        state = {
            "deprivation_matrix": np.zeros((20, 3)),
            "weights": np.array([0.33, 0.34, 0.33]),
        }
        result = method.pure_step(state, {"k_threshold": 0.33})
        assert isinstance(result, dict)
