"""Runtime service for attractor analysis and dynamical sidecar artifacts."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import (
    AttractorAnalysisRequest,
    AttractorAnalysisResult,
    AttractorAnalysisResultRef,
    AttractorSummary,
    BasinMap,
    BasinMapRef,
    ContinuationBranch,
    ContinuationBranchRef,
    FeedbackJacobianDiagnostics,
    FeedbackSolveResult,
)
from polisyos.foundry.analysis.attractors import (
    build_attractor_analysis_result,
    build_attractor_ensemble_analysis_result,
    build_feedback_attractor_analysis_result,
    load_attractor_analysis_result,
    load_basin_map,
    load_continuation_branch,
    persist_attractor_analysis_result,
    persist_basin_map,
    persist_continuation_branch,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.protocol import ArtifactStore


_ModelT = TypeVar("_ModelT", bound=BaseModel)


class AttractorAnalysisService:
    """Runtime-facing orchestration for attractor, basin, and continuation artifacts."""

    def __init__(self, *, store: ArtifactStore) -> None:
        self._store = store

    def analyze_attractors(
        self,
        request: AttractorAnalysisRequest,
    ) -> tuple[AttractorAnalysisResult, AttractorAnalysisResultRef | None, BasinMapRef | None]:
        """Run lightweight attractor analysis and optionally persist the result."""

        basin_ref: BasinMapRef | None = None
        if request.feedback_result_ref is not None:
            feedback = self._load_model(request.feedback_result_ref, FeedbackSolveResult)
            jacobian = (
                None
                if request.feedback_jacobian_diagnostics_ref is None
                else self._load_model(
                    request.feedback_jacobian_diagnostics_ref,
                    FeedbackJacobianDiagnostics,
                )
            )
            result = build_feedback_attractor_analysis_result(
                feedback,
                feedback_result_ref=request.feedback_result_ref,
                jacobian_diagnostics=jacobian,
                model_ref=request.model_ref,
                simulation_result_ref=request.simulation_result_ref,
                exec_plan_ref=request.exec_plan_ref,
            )
        elif request.trajectories:
            result, basin_map = build_attractor_ensemble_analysis_result(
                request.trajectories,
                self._variable_ids(request),
                initial_states=request.initial_states,
                seeds=request.seeds,
                parameter_point=request.parameter_point,
                model_ref=request.model_ref,
                simulation_result_ref=request.simulation_result_ref,
                exec_plan_ref=request.exec_plan_ref,
                tolerance=request.tolerance,
                rtol=request.rtol,
                window=request.window,
                max_period=request.max_period,
                stochastic_model=request.stochastic_model,
                notes=request.notes,
            )
            if request.persist_artifact:
                basin_ref = persist_basin_map(self._store, basin_map)
                result = result.model_copy(
                    update={"attractors": _attach_basin_ref(result.attractors, basin_ref)}
                )
        elif request.trajectory is not None:
            result = build_attractor_analysis_result(
                request.trajectory,
                self._variable_ids(request),
                parameter_point=request.parameter_point,
                model_ref=request.model_ref,
                simulation_result_ref=request.simulation_result_ref,
                exec_plan_ref=request.exec_plan_ref,
                tolerance=request.tolerance,
                rtol=request.rtol,
                window=request.window,
                max_period=request.max_period,
                seeds_used=len(set(request.seeds)) if request.seeds else None,
                stochastic_model=request.stochastic_model,
                largest_lyapunov=request.largest_lyapunov_exponent,
                notes=request.notes,
            )
        else:
            raise ValueError(
                "trajectory or feedback_result_ref is required; simulation_result_ref is "
                "recorded for provenance but is not yet a trajectory extraction source"
            )

        result_ref = (
            persist_attractor_analysis_result(self._store, result)
            if request.persist_artifact
            else None
        )
        return result, result_ref, basin_ref

    def load_analysis(
        self,
        artifact_id: ArtifactID,
    ) -> tuple[AttractorAnalysisResult, AttractorAnalysisResultRef]:
        """Load a persisted attractor-analysis result."""

        manifest = self._store.get_manifest(artifact_id)
        if manifest.kind != "foundry.attractor_analysis_result":
            raise ValueError("artifact is not a foundry.attractor_analysis_result")
        ref = AttractorAnalysisResultRef(
            artifact_id=artifact_id,
            media_type=manifest.media_type,
        )
        return load_attractor_analysis_result(self._store, ref), ref

    def persist_basin_map(self, basin_map: BasinMap) -> BasinMapRef:
        """Persist a basin-map sidecar artifact."""

        return persist_basin_map(self._store, basin_map)

    def load_basin_map(self, artifact_id: ArtifactID) -> tuple[BasinMap, BasinMapRef]:
        """Load a basin-map sidecar artifact."""

        manifest = self._store.get_manifest(artifact_id)
        if manifest.kind != "foundry.basin_map":
            raise ValueError("artifact is not a foundry.basin_map")
        ref = BasinMapRef(artifact_id=artifact_id, media_type=manifest.media_type)
        return load_basin_map(self._store, ref), ref

    def persist_continuation_branch(self, branch: ContinuationBranch) -> ContinuationBranchRef:
        """Persist a continuation-branch sidecar artifact."""

        return persist_continuation_branch(self._store, branch)

    def load_continuation_branch(
        self,
        artifact_id: ArtifactID,
    ) -> tuple[ContinuationBranch, ContinuationBranchRef]:
        """Load a continuation-branch sidecar artifact."""

        manifest = self._store.get_manifest(artifact_id)
        if manifest.kind != "foundry.continuation_branch":
            raise ValueError("artifact is not a foundry.continuation_branch")
        ref = ContinuationBranchRef(artifact_id=artifact_id, media_type=manifest.media_type)
        return load_continuation_branch(self._store, ref), ref

    def _load_model(self, ref: ArtifactRef, model: type[_ModelT]) -> _ModelT:
        payload = from_canonical_bytes(self._store.get_bytes(ref.artifact_id))
        return model.model_validate(payload)

    @staticmethod
    def _variable_ids(request: AttractorAnalysisRequest) -> list[str]:
        if request.variable_ids:
            return list(request.variable_ids)
        if request.state_projection is not None and request.state_projection.variables:
            return list(request.state_projection.variables)
        return []


def _attach_basin_ref(
    attractors: list[AttractorSummary],
    basin_ref: BasinMapRef,
) -> list[AttractorSummary]:
    return [
        attractor.model_copy(
            update={"basin": attractor.basin.model_copy(update={"basin_map_ref": basin_ref})}
        )
        for attractor in attractors
    ]


__all__ = ["AttractorAnalysisService"]
