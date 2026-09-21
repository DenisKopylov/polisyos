"""Producer-only D4 governance handoff for the Ukraine data pipeline."""

from __future__ import annotations

from polisyos.data_forge.domains.ukraine.manifests import ArtifactRecord
from polisyos.data_forge.domains.ukraine.models import PipelineConfig, StageId
from polisyos.data_forge.kernel.io import ensure_dirs

from .common import _stage_dir, _write_json
from .contracts import StageBuildResult

_D4_GOVERNANCE_REQUEST_OUTPUT = "d4_governance_request.json"


def build_d4_stage(config: PipelineConfig) -> StageBuildResult:
    """Emit the content-bound D4 handoff consumed by Scientist governance.

    This producer intentionally makes no calibration, governance, promotion, or
    release decision. Scientist consumes this request only after the orchestrator
    has emitted the completed D4 manifest and the verified read API has bound it.
    """

    stage_dir = _stage_dir(config.build_root, StageId.D4)
    ensure_dirs(stage_dir)
    request_path = _write_json(
        stage_dir / _D4_GOVERNANCE_REQUEST_OUTPUT,
        {
            "schema_version": "policyos.data_forge.ukraine.d4_governance_request.v1",
            "authority_purpose": "producer_governance_handoff",
            "may_not_use_for": [
                "governance_admissibility",
                "release_acceptance",
                "legal_intervention_compilation",
                "method_validity",
            ],
            "required_stage_manifests": {
                "d0_p0": "build_run_d0_p0.json",
                "d2": "build_run_d2.json",
                "d3": "build_run_d3.json",
            },
        },
    )
    return StageBuildResult(
        outputs={
            _D4_GOVERNANCE_REQUEST_OUTPUT: ArtifactRecord.from_path(request_path)
        },
        metrics={
            "producer_handoff_ready": True,
        },
        manifest_paths=[request_path],
    )


__all__ = ("build_d4_stage",)
