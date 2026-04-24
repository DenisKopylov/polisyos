"""Runtime service for mobility estimation and report retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import numpy as np

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.foundry.methods.catalog.distributional.mobility import (
    AttritionAdjustedMobilityMatrixEstimator,
    MobilityMatrixEstimator,
    RefreshmentSampleMobilityEstimator,
    SequentialIPCWLifetimeMobilityEstimator,
)
from polisyos.ir.analytics.mobility import MobilityReport, load_mobility_report
from polisyos.ir.analytics.partial_identification import (
    BoundsBundle,
    build_mobility_bounds_bundle,
    load_bounds_bundle,
    persist_bounds_bundle,
)
from polisyos.ir.artifacts import ArtifactID as IRArtifactID
from polisyos.ir.refs import BoundsBundleRef, MobilityReportRef

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.contracts.runtime import MobilityBoundsRequest, MobilityEstimateRequest


class _MobilityEstimator(Protocol):
    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]: ...


class MobilityService:
    """Runtime-facing orchestration layer for mobility estimation and retrieval."""

    def __init__(self, *, store: Any) -> None:
        self._store = store

    def estimate(
        self,
        request: MobilityEstimateRequest,
    ) -> tuple[MobilityReport, ArtifactRef | None, ArtifactRef | None]:
        state = self._request_state(request)
        if request.persist_artifact:
            state["artifact_store"] = self._store
        params: dict[str, Any] = {
            "n_classes": request.n_classes,
            "estimator": request.estimator,
            "positivity_floor": request.positivity_floor,
            "compute_bounds": request.compute_bounds,
            "monotone": request.monotone,
            **dict(request.metadata),
        }
        if request.panel_length is not None:
            params["panel_length"] = request.panel_length
        if request.waves_used:
            params["waves_used"] = request.waves_used
        method: type[_MobilityEstimator]
        if request.mode == "complete_case":
            method = MobilityMatrixEstimator
            params = {"n_classes": request.n_classes}
        elif request.mode == "attrition_adjusted":
            method = AttritionAdjustedMobilityMatrixEstimator
        elif request.mode == "sequential_attrition_adjusted":
            method = SequentialIPCWLifetimeMobilityEstimator
        elif request.mode == "refreshment_anchored":
            method = RefreshmentSampleMobilityEstimator
            params = {
                "n_classes": request.n_classes,
                "compute_bounds": request.compute_bounds,
                "monotone": request.monotone,
                **dict(request.metadata),
            }
            if request.waves_used:
                params["waves_used"] = request.waves_used
        else:  # pragma: no cover - Pydantic prevents this
            raise ValueError(f"unsupported mobility mode: {request.mode}")

        result = method.pure_step(state, params)
        report = result["result"]
        report_ref = self._artifact_ref_from_payload(result.get("mobility_report_ref"))
        bounds_ref = (
            None
            if report.bounds.bundle_ref is None
            else self._artifact_ref_from_payload(report.bounds.bundle_ref.model_dump(mode="json"))
        )
        return report, report_ref, bounds_ref

    def compute_bounds(
        self,
        request: MobilityBoundsRequest,
    ) -> tuple[BoundsBundle, ArtifactRef | None, dict[str, list[float]], dict[str, list[float]]]:
        observed_joint = np.asarray(request.observed_joint_matrix, dtype=float)
        row_marginals = np.asarray(request.row_marginals, dtype=float)
        column_marginals = (
            None
            if request.column_marginals is None
            else np.asarray(request.column_marginals, dtype=float)
        )
        bundle, cell_lower, cell_upper, summary_bounds = build_mobility_bounds_bundle(
            observed_joint,
            row_marginals,
            column_marginals=column_marginals,
            headline_metric=request.headline_metric,
            metadata=dict(request.metadata),
        )
        bounds_ref = None
        if request.persist_artifact:
            bounds_ref = persist_bounds_bundle(self._store, bundle)
        cell_bounds = {
            f"{row},{col}": [float(cell_lower[row, col]), float(cell_upper[row, col])]
            for row in range(cell_lower.shape[0])
            for col in range(cell_lower.shape[1])
        }
        summary_payload = {
            key: [float(value[0]), float(value[1])] for key, value in summary_bounds.items()
        }
        return bundle, self._artifact_ref_from_typed(bounds_ref), cell_bounds, summary_payload

    def load_report(self, artifact_id: ArtifactID) -> tuple[MobilityReport, ArtifactRef]:
        manifest = self._store.get_manifest(artifact_id)
        if manifest.kind != "ir.mobility_report":
            raise ValueError("artifact is not an ir.mobility_report")
        ref = MobilityReportRef(
            artifact_id=IRArtifactID.model_validate(artifact_id.root),
            kind="ir.mobility_report",
            media_type=manifest.media_type,
        )
        report = load_mobility_report(self._store, ref)
        return report, self._required_artifact_ref_from_typed(ref)

    def load_bounds_for_report(
        self,
        artifact_id: ArtifactID,
    ) -> tuple[BoundsBundle, ArtifactRef, ArtifactRef]:
        report, report_ref = self.load_report(artifact_id)
        if report.bounds.bundle_ref is None:
            raise FileNotFoundError("mobility report has no linked bounds bundle")
        bundle = load_bounds_bundle(self._store, report.bounds.bundle_ref)
        return bundle, report_ref, self._required_artifact_ref_from_typed(report.bounds.bundle_ref)

    def load_diagnostics(
        self,
        artifact_id: ArtifactID,
    ) -> tuple[dict[str, Any], ArtifactRef]:
        report, report_ref = self.load_report(artifact_id)
        return report.diagnostics.model_dump(mode="json"), report_ref

    @staticmethod
    def _artifact_ref_from_typed(
        ref: MobilityReportRef | BoundsBundleRef | None,
    ) -> ArtifactRef | None:
        if ref is None:
            return None
        return ArtifactRef.model_validate(ref.model_dump(mode="json"))

    @staticmethod
    def _required_artifact_ref_from_typed(ref: MobilityReportRef | BoundsBundleRef) -> ArtifactRef:
        return ArtifactRef.model_validate(ref.model_dump(mode="json"))

    @staticmethod
    def _artifact_ref_from_payload(payload: dict[str, Any] | None) -> ArtifactRef | None:
        if payload is None:
            return None
        return ArtifactRef.model_validate(payload)

    @staticmethod
    def _request_state(request: MobilityEstimateRequest) -> dict[str, Any]:
        state: dict[str, Any] = {
            "origin_classes": request.origin_classes,
            "destination_classes": [
                (-1 if value is None else value) for value in request.destination_classes
            ],
        }
        if request.retention_indicators is not None:
            state["retention_indicators"] = request.retention_indicators
        if request.retention_indicators_by_wave is not None:
            state["retention_indicators_by_wave"] = request.retention_indicators_by_wave
        if request.attrition_features is not None:
            state["attrition_features"] = request.attrition_features
        if request.attrition_features_by_wave is not None:
            state["attrition_features_by_wave"] = request.attrition_features_by_wave
        if request.sample_weights is not None:
            state["sample_weights"] = request.sample_weights
        if request.retention_probabilities is not None:
            state["retention_probabilities"] = request.retention_probabilities
        if request.retention_probabilities_by_wave is not None:
            state["retention_probabilities_by_wave"] = request.retention_probabilities_by_wave
        if request.destination_marginals is not None:
            state["destination_marginals"] = request.destination_marginals
        if request.refreshment_destination_classes is not None:
            state["refreshment_destination_classes"] = request.refreshment_destination_classes
        if request.refreshment_weights is not None:
            state["refreshment_weights"] = request.refreshment_weights
        if request.feature_names:
            state["feature_names"] = request.feature_names
        return state


__all__ = ["MobilityService"]
