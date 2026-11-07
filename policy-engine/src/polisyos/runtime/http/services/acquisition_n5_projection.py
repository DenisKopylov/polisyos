"""Shared finite projection of owner-resolved N5 candidate results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core.artifacts import (
    ArtifactOwnershipError,
    ArtifactRef,
    read_core_manifest_profile,
)
from polisyos.core.contracts.runtime import RunCandidateSimulationN5ResultBody

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactManifest, CoreJSONArtifactStore
    from polisyos.runtime.quality.generation_source import N4CandidateScenarioSourceRecordV3
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationResult


class SelectedN5ScopeNotEstablishedError(ValueError):
    """The selected N5 result has no declared tenant and cell binding."""


def read_selected_n5_result_manifest(
    store: CoreJSONArtifactStore,
    ref: ArtifactRef,
    *,
    tenant_id: str,
    cell_id: str,
) -> ArtifactManifest:
    """Reopen the exact result manifest and enforce its tenant and cell scope."""
    manifest = read_core_manifest_profile(store, ref)[0]
    scope = manifest.tenant_context
    if scope is None:
        raise SelectedN5ScopeNotEstablishedError("generic_n5_result_scope_not_established")
    if (scope.tenant_id, scope.cell_id) != (tenant_id, cell_id):
        raise ArtifactOwnershipError("selected N5 result belongs to another tenant or cell")
    return manifest


def build_candidate_n5_result_body(
    *,
    store: CoreJSONArtifactStore,
    ref: ArtifactRef,
    result: JointSimulationResult,
    source: N4CandidateScenarioSourceRecordV3,
    tenant_id: str,
    cell_id: str,
    authority_purpose: str,
) -> RunCandidateSimulationN5ResultBody:
    """Project owner-resolved candidate N5 numbers and their declared units."""
    manifest = read_selected_n5_result_manifest(
        store,
        ref,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    return RunCandidateSimulationN5ResultBody.model_validate(
        {
            **n5_numerical_body_payload(
                ref=ref,
                manifest=manifest,
                result=result,
                authority_purpose=authority_purpose,
            ),
            **n5_declared_candidate_units(source, result),
        }
    )


def n5_numerical_body_payload(
    *,
    ref: ArtifactRef,
    manifest: ArtifactManifest,
    result: JointSimulationResult,
    authority_purpose: str,
) -> dict[str, object]:
    """Project finite numerical fields without changing their producer or purpose."""
    if ref.manifest_profile_sha256 is None or manifest.artifact_schema is None:
        raise ValueError("candidate_n5_result_body_selected_manifest_view_not_established")
    return {
        "artifact_ref": ref,
        "artifact_schema_name": manifest.artifact_schema.name,
        "artifact_schema_version": manifest.artifact_schema.version,
        "result_schema_version": result.schema_version,
        "selected_manifest_profile_sha256": ref.manifest_profile_sha256,
        "world_model_record_ref": result.world_model_record_ref,
        "world_model_record_content_hash": result.world_model_record_content_hash,
        "atom_ids": result.atom_ids,
        "selected_outcomes": result.selected_outcomes,
        "horizon": result.horizon.model_dump(mode="python"),
        "trajectories": tuple(
            {
                "run_level": trajectory.run_level,
                "atom_ids": trajectory.atom_ids,
                "points": tuple(
                    {
                        "step": point.step,
                        "outcomes": point.outcomes,
                        "effects": point.effect,
                    }
                    for point in trajectory.points
                ),
            }
            for trajectory in result.trajectories
        ),
        "uncertainty_kind": result.uncertainty_kind,
        "authority_purpose": authority_purpose,
        "candidate_status": "candidate_unverified",
        "currentness_status": "not_established",
        "publication_authority": False,
    }


def n5_declared_candidate_units(
    source: N4CandidateScenarioSourceRecordV3, result: JointSimulationResult
) -> dict[str, object]:
    """Project units from the actual selected declaration already reopened by N5."""
    declaration = source.model_declaration
    if set(result.selected_outcomes) != {declaration.outcome_variable}:
        raise ValueError("candidate_n5_public_outcome_unit_binding_mismatch")
    return {
        "outcome_units": {declaration.outcome_variable: declaration.outcome_unit_id},
        "unit_provenance": "declared_candidate_model",
        "model_declaration_ref": source.model_declaration_ref,
    }
