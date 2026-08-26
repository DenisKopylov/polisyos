"""Producer-only D4 handoff builder for Ukraine calibration governance."""

from __future__ import annotations

from .common import *

_D4_GOVERNANCE_REQUEST_OUTPUT = "d4_governance_request.json"


def build_d4_stage(config: PipelineConfig) -> StageBuildResult:
    """Emit the content-bound D4 handoff consumed by Scientist governance.

    This producer intentionally makes no calibration, governance, promotion, or
    release decision. Scientist consumes this request only after the orchestrator
    has emitted the completed D4 manifest and the verified read API has bound it.
    """

    stage_dir = _stage_dir(config.build_root, StageId.D4)
    ensure_dirs(stage_dir)
    d4_config = config.stages[StageId.D4.value]
    coverage_threshold = max(
        0.95,
        float(config.stages[StageId.D0_P0.value].coverage_threshold),
    )
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
            "coverage_threshold": coverage_threshold,
            "waived_signoff_families": [
                family.value for family in d4_config.final_signoff_waived_families
            ],
            "required_stage_manifests": {
                "d0_p0": "build_run_d0_p0.json",
                "d2": "build_run_d2.json",
                "d3": "build_run_d3.json",
            },
        },
    )
    return StageBuildResult(
        outputs={_D4_GOVERNANCE_REQUEST_OUTPUT: ArtifactRecord.from_path(request_path)},
        metrics={
            "producer_handoff_ready": True,
        },
        manifest_paths=[request_path],
    )


__all__ = ("build_d4_stage",)
