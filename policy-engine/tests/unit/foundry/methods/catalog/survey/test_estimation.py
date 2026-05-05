from __future__ import annotations

import numpy as np
import pytest
from numpy.testing import assert_allclose
from polisyos.foundry.methods.catalog.survey.protocols import (
    AuxiliaryTotalUncertainty,
    CalibrationWeights,
)


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestFayHerriot:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.estimation.fay_herriot@1.0.0")
        rng = np.random.default_rng(42)
        n_areas = 20
        state = {
            "y_direct": rng.normal(50, 5, size=n_areas),
            "X": rng.normal(0, 1, size=(n_areas, 3)),
            "sampling_var": np.abs(rng.normal(1, 0.3, size=n_areas)) + 0.1,
        }
        result = method.pure_step(state, {"max_iter": 50})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.estimation.fay_herriot@1.0.0")
        state = {
            "y_direct": np.array([10.0, 20.0, 30.0, 40.0, 50.0]),
            "X": np.ones((5, 1)),
            "sampling_var": np.array([1.0, 1.0, 1.0, 1.0, 1.0]),
        }
        result = method.pure_step(state, {"max_iter": 20})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))


class TestCalibrationGREG:
    def test_zero_uncertainty_recovers_exact_calibration(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.estimation.calibration_greg@1.0.0")
        state = {
            "y": np.array([3.0, 5.0, 4.0]),
            "X": np.array([[1.0], [2.0], [1.0]]),
            "weights": np.array([2.0, 2.0, 2.0]),
            "population_totals": np.array([9.0]),
        }

        exact = method.pure_step(state, {})
        zero_uncertainty = method.pure_step(
            {
                **state,
                "auxiliary_total_uncertainty": {
                    "variance": [0.0],
                },
            },
            {},
        )

        assert isinstance(exact["calibration_weights"], CalibrationWeights)
        assert exact["result"]["constraint_mode"] == "exact"
        assert zero_uncertainty["result"]["constraint_mode"] == "exact"
        assert_allclose(exact["result"]["greg_total"], zero_uncertainty["result"]["greg_total"])
        assert_allclose(
            exact["calibration_weights"].calibrated_weights,
            zero_uncertainty["calibration_weights"].calibrated_weights,
        )
        assert_allclose(exact["calibration_weights"].control_residual, [0.0], atol=1e-10)

    def test_uncertainty_downweights_calibration_shift(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.estimation.calibration_greg@1.0.0")
        base_state = {
            "y": np.array([3.0, 5.0, 4.0]),
            "X": np.array([[1.0], [2.0], [1.0]]),
            "weights": np.array([2.0, 2.0, 2.0]),
            "population_totals": np.array([9.0]),
        }

        low = method.pure_step(
            {
                **base_state,
                "auxiliary_total_uncertainty": {
                    "source_kind": "estimated_external",
                    "target_names": ["aux_0"],
                    "variance": [0.01],
                },
            },
            {},
        )
        high = method.pure_step(
            {
                **base_state,
                "auxiliary_total_uncertainty": {
                    "source_kind": "estimated_external",
                    "target_names": ["aux_0"],
                    "variance": [4.0],
                },
            },
            {},
        )

        design_weights = base_state["weights"]
        low_weights = np.asarray(low["calibration_weights"].calibrated_weights)
        high_weights = np.asarray(high["calibration_weights"].calibrated_weights)
        low_shift = float(np.linalg.norm(low_weights - design_weights))
        high_shift = float(np.linalg.norm(high_weights - design_weights))

        assert low["result"]["constraint_mode"] == "relaxed"
        assert high["result"]["constraint_mode"] == "relaxed"
        assert high_shift < low_shift
        assert abs(high["result"]["control_residual"][0]) > abs(
            low["result"]["control_residual"][0]
        )
        assert high["result"]["variance_components"]["aux_total_uncertainty"] > 0.0

    def test_auxiliary_total_uncertainty_rejects_non_psd_covariance(self) -> None:
        with pytest.raises(ValueError, match="positive semidefinite"):
            AuxiliaryTotalUncertainty.model_validate(
                {
                    "source_kind": "estimated_external",
                    "target_names": ["aux_0"],
                    "covariance_matrix": [[-1.0]],
                }
            )

    def test_standard_errors_and_correlation_expand_to_full_covariance(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(isolated_registry, "survey.estimation.calibration_greg@1.0.0")
        state = {
            "y": np.array([5.0, 7.0, 6.0]),
            "X": np.array([[1.0, 0.0], [1.0, 1.0], [1.0, 2.0]]),
            "weights": np.array([1.0, 1.0, 1.0]),
            "population_totals": np.array([4.0, 4.0]),
            "auxiliary_total_uncertainty": {
                "source_kind": "time_series_benchmark",
                "target_names": ["intercept", "trend"],
                "standard_error": [2.0, 3.0],
                "correlation_matrix": [[1.0, 0.5], [0.5, 1.0]],
            },
        }

        result = method.pure_step(state, {})
        expected_covariance = np.array([[4.0, 3.0], [3.0, 9.0]])
        assert_allclose(
            result["calibration_weights"].uncertainty_covariance_used, expected_covariance
        )
        assert result["result"]["constraint_mode"] == "relaxed"

    def test_replicate_totals_are_supported(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.estimation.calibration_greg@1.0.0")
        state = {
            "y": np.array([3.0, 5.0, 4.0]),
            "X": np.array([[1.0], [2.0], [1.0]]),
            "weights": np.array([2.0, 2.0, 2.0]),
            "population_totals": np.array([9.0]),
            "auxiliary_total_uncertainty": {
                "source_kind": "estimated_external",
                "target_names": ["aux_0"],
                "replicate_totals": [[8.5], [9.5], [9.0], [8.75]],
            },
        }

        result = method.pure_step(state, {})
        assert result["result"]["constraint_mode"] == "relaxed"
        assert result["result"]["uncertainty_source_kind"] == "estimated_external"
        assert result["result"]["diagnostics"]["uncertainty_used_replicates"] is True
        assert result["result"]["variance_components"]["aux_total_uncertainty"] >= 0.0

    def test_q_weights_and_optional_inputs_are_reflected_in_contract(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(isolated_registry, "survey.estimation.calibration_greg@1.0.0")
        state = method.materialize_input(
            {
                "y": np.array([3.0, 5.0, 4.0]),
                "X": np.array([[1.0], [2.0], [1.0]]),
                "weights": np.array([2.0, 2.0, 2.0]),
                "population_totals": np.array([9.0]),
                "q_weights": np.array([1.0, 2.0, 1.0]),
                "sample_aux_error_cov": np.array([[0.25]]),
                "bounds": (0.5, 10.0),
                "auxiliary_total_uncertainty": {
                    "variance": [0.5],
                },
            },
            {},
        )
        result = method.pure_step(state, {})

        assert result["result"]["diagnostics"]["used_q_weights"] is True
        assert result["result"]["diagnostics"]["used_sample_aux_error_cov"] is True
        assert result["result"]["diagnostics"]["bounds_supplied"] is True
        assert_allclose(result["calibration_weights"].q_weights, [1.0, 2.0, 1.0])
        assert_allclose(result["calibration_weights"].sample_aux_error_cov, [[0.25]])
        assert result["calibration_weights"].bounds == (0.5, 10.0)
