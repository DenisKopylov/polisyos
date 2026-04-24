from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.mobility import MobilityReport, load_mobility_report
from polisyos.ir.analytics.partial_identification import load_bounds_bundle
from polisyos.ir.refs import MobilityReportRef


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestTransitionMatrix:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry, "distributional.mobility.transition_matrix@1.0.0"
        )
        rng = np.random.default_rng(42)
        state = {
            "origin_classes": rng.integers(0, 5, size=100),
            "destination_classes": rng.integers(0, 5, size=100),
        }
        result = method.pure_step(state, {"n_classes": 5})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry, "distributional.mobility.transition_matrix@1.0.0"
        )
        state = {
            "origin_classes": np.array([0, 0, 1, 1, 2]),
            "destination_classes": np.array([0, 1, 1, 2, 2]),
        }
        result = method.pure_step(state, {"n_classes": 3})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))

    def test_persists_typed_mobility_report(self, isolated_registry, tmp_path) -> None:
        method = _method_or_skip(
            isolated_registry, "distributional.mobility.transition_matrix@1.0.0"
        )
        store = FileSystemCAS(tmp_path / "cas")
        result = method.pure_step(
            {
                "origin_classes": np.array([0, 0, 1, 1, 2]),
                "destination_classes": np.array([0, 1, 1, 2, 2]),
            },
            {"n_classes": 3, "artifact_store": store},
        )

        report = result["result"]
        ref_payload = result["mobility_report_ref"]

        assert isinstance(report, MobilityReport)
        assert ref_payload is not None
        loaded = load_mobility_report(store, MobilityReportRef.model_validate(ref_payload))
        assert loaded.analysis_type == "transition_matrix"
        assert loaded.schema_version == "2.0"
        assert loaded.summary_metrics["n_classes"] == 3

    def test_attrition_adjusted_ipcw_recovers_balanced_rows_and_persists_bounds(
        self,
        isolated_registry,
        tmp_path,
    ) -> None:
        method = _method_or_skip(
            isolated_registry,
            "distributional.mobility.transition_matrix_attrition_adjusted@1.0.0",
        )
        store = FileSystemCAS(tmp_path / "cas")

        origin = np.concatenate(
            (
                np.zeros(100, dtype=int),
                np.zeros(100, dtype=int),
                np.ones(100, dtype=int),
                np.ones(100, dtype=int),
            )
        )
        feature = np.concatenate(
            (
                np.zeros(100, dtype=float),
                np.ones(100, dtype=float),
                np.zeros(100, dtype=float),
                np.ones(100, dtype=float),
            )
        )
        destination_full = feature.astype(int)
        retained = np.concatenate(
            (
                np.r_[np.ones(90, dtype=int), np.zeros(10, dtype=int)],
                np.r_[np.ones(30, dtype=int), np.zeros(70, dtype=int)],
                np.r_[np.ones(90, dtype=int), np.zeros(10, dtype=int)],
                np.r_[np.ones(30, dtype=int), np.zeros(70, dtype=int)],
            )
        )
        destination = np.where(retained == 1, destination_full, -1)
        retention_probabilities = np.where(feature == 0.0, 0.9, 0.3)

        result = method.pure_step(
            {
                "origin_classes": origin,
                "destination_classes": destination,
                "retention_indicators": retained,
                "attrition_features": feature.reshape(-1, 1),
                "retention_probabilities": retention_probabilities,
                "artifact_store": store,
            },
            {"n_classes": 2, "estimator": "ipcw", "compute_bounds": True},
        )

        report = result["result"]
        transition_matrix = np.asarray(report.point_estimate.transition_matrix)
        np.testing.assert_allclose(transition_matrix[0], np.array([0.5, 0.5]), atol=1e-8)
        np.testing.assert_allclose(transition_matrix[1], np.array([0.5, 0.5]), atol=1e-8)
        assert report.bounds.bundle_ref is not None
        assert report.diagnostics.balance is not None
        assert report.diagnostics.balance.max_abs_smd_before is not None
        assert report.diagnostics.balance.max_abs_smd_after is not None
        assert (
            report.diagnostics.balance.max_abs_smd_after
            < report.diagnostics.balance.max_abs_smd_before
        )

        upward_bounds = report.bounds.summary_bounds["upward_rate"]
        upward_rate = float(report.point_estimate.mobility_stats["upward_rate"])
        assert upward_bounds[0] <= upward_rate <= upward_bounds[1]

        bounds_bundle = load_bounds_bundle(store, report.bounds.bundle_ref)
        assert bounds_bundle.metadata["headline_metric"] == "upward_rate"
        assert bounds_bundle.metadata["summary_bounds"]["upward_rate"] == list(upward_bounds)

    def test_sequential_ipcw_estimator_emits_sequential_attrition_report(
        self,
        isolated_registry,
        tmp_path,
    ) -> None:
        method = _method_or_skip(
            isolated_registry,
            "distributional.mobility.sequential_lifetime_transition_matrix@1.0.0",
        )
        store = FileSystemCAS(tmp_path / "cas")

        result = method.pure_step(
            {
                "origin_classes": np.array([0, 0, 1, 1]),
                "destination_classes": np.array([0, -1, 1, -1]),
                "retention_indicators_by_wave": np.array(
                    [
                        [1, 1],
                        [1, 0],
                        [1, 1],
                        [1, 0],
                    ]
                ),
                "attrition_features_by_wave": np.array(
                    [
                        [[0.0], [0.0]],
                        [[1.0], [1.0]],
                        [[0.0], [0.0]],
                        [[1.0], [1.0]],
                    ]
                ),
                "retention_probabilities_by_wave": np.array(
                    [
                        [1.0, 1.0],
                        [1.0, 0.5],
                        [1.0, 1.0],
                        [1.0, 0.5],
                    ]
                ),
                "artifact_store": store,
            },
            {"n_classes": 2, "estimator": "ipcw", "compute_bounds": True},
        )

        report = result["result"]
        assert report.analysis_type == "sequential_lifetime_transition_matrix"
        np.testing.assert_allclose(
            np.asarray(report.point_estimate.transition_matrix),
            np.array([[1.0, 0.0], [0.0, 1.0]]),
            atol=1e-8,
        )
        assert report.attrition.mechanism_assumed == "sequential_mar_given_history"
        assert report.diagnostics.sensitivity_grid["wave_2_retention_rate"] == pytest.approx(0.5)
        assert report.bounds.bundle_ref is not None

        bounds_bundle = load_bounds_bundle(store, report.bounds.bundle_ref)
        assert bounds_bundle.metadata["summary_bounds"]["immobility_rate"] == [0.5, 1.0]

    def test_refreshment_estimator_anchors_destination_marginals_and_persists_bounds(
        self,
        isolated_registry,
        tmp_path,
    ) -> None:
        method = _method_or_skip(
            isolated_registry,
            "distributional.mobility.refreshment_transition_matrix@1.0.0",
        )
        store = FileSystemCAS(tmp_path / "cas")

        result = method.pure_step(
            {
                "origin_classes": np.array([0, 0, 1, 1]),
                "destination_classes": np.array([0, -1, 1, -1]),
                "retention_indicators": np.array([1, 0, 1, 0]),
                "refreshment_destination_classes": np.array([0, 0, 1, 1]),
                "artifact_store": store,
            },
            {"n_classes": 2, "compute_bounds": True},
        )

        report = result["result"]
        assert report.analysis_type == "refreshment_transition_matrix"
        assert report.attrition.refreshment_sample is True
        assert report.attrition.mechanism_assumed == "selection_on_unobservables_refreshment"
        assert report.attrition.weight_model is not None
        assert report.attrition.weight_model.family == "additive_nonignorable_logit_refreshment"
        np.testing.assert_allclose(
            np.asarray(report.point_estimate.col_marginals),
            np.array([0.5, 0.5]),
            atol=1e-8,
        )
        transition = np.asarray(report.point_estimate.transition_matrix)
        assert transition[0, 0] > transition[0, 1]
        assert transition[1, 1] > transition[1, 0]
        assert report.bounds.sharpness_status == "sharp_with_known_marginals"
        assert report.bounds.bundle_ref is not None
        assert (
            "refreshment_additive_nonignorable_logit_structural_fit" in report.diagnostics.warnings
        )

        bounds_bundle = load_bounds_bundle(store, report.bounds.bundle_ref)
        assert bounds_bundle.metadata["summary_bounds"]["upward_rate"] == [0.0, 0.25]


class TestIntergenerationalElasticity:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry, "distributional.mobility.intergenerational_elasticity@1.0.0"
        )
        rng = np.random.default_rng(42)
        state = {
            "parent_values": np.abs(rng.normal(50, 10, size=50)) + 1.0,
            "child_values": np.abs(rng.normal(55, 12, size=50)) + 1.0,
        }
        result = method.pure_step(state, {})
        assert isinstance(result, dict)
