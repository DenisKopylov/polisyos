"""Reusable authored-joint relation checks for an existing NCM run."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts import ArtifactRef, ArtifactStore, read_core_json_artifact
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.generation_cycle import JointSimulationRequest
from polisyos.runtime.quality.generation_source import GenerationSourceRepository
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleSimulationAdmissionOwner,
    GenericCycleSimulationContextHandoffV1,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    ParentJointAuthoredRelationV1,
    ParentJointCandidateSelectionV3,
    RecursiveGenerationCycleError,
    load_authored_joint_components,
)


def verify_authored_joint_relationship_order_consumer(
    *,
    store: ArtifactStore,
    relation_ref: ArtifactRef,
    request: JointSimulationRequest,
    parent_handoff: GenericCycleSimulationContextHandoffV1,
    selection: ParentJointCandidateSelectionV3,
    tenant_id: str,
    cell_id: str,
) -> ParentJointAuthoredRelationV1:
    """Replay one retained authored relation and reject a rehashed order mutation.

    Call with a fresh reader for an already-produced N5 result. This function
    only reads the selected relation and source artifacts; the negative control
    changes the in-memory selection projection and performs no N5 or CAS write.
    """
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        if not store.verify(relation_ref).ok:
            raise AssertionError("authored relation failed fresh CAS verification")
        relation = ParentJointAuthoredRelationV1.model_validate(
            read_core_json_artifact(store, relation_ref).value
        )
        replayed = load_authored_joint_components(
            store=store,
            relation_ref=relation_ref,
            source_repository=GenerationSourceRepository(store),
            parent_handoff=parent_handoff,
            admission_owner=GenericCycleSimulationAdmissionOwner(profiles=(), store=store),
            request=request,
            selection=selection,
        )

        assert relation == replayed
        assert relation.source_candidate_relationship == "alternatives"
        assert relation.selected_member_relationship == "joint_components"
        assert selection.source_candidate_relationship == "alternatives"
        assert selection.selected_member_relationship == "joint_components"
        assert relation.composition_status == selection.composition_status == "authored_candidate"
        assert relation.child_to_parent_refinement_status == "not_established"
        assert relation.world_model_record_ref == request.world_model_record_ref
        assert relation.world_model_record_content_hash == request.world_model_record.content_hash
        assert relation.profile_content_hash == parent_handoff.profile.content_hash
        assert relation.profile_selection_ref == parent_handoff.profile.profile_selection_ref
        assert request.horizon == parent_handoff.profile.n5.horizon
        assert request.seed == parent_handoff.profile.n5.seed
        assert request.replications == parent_handoff.profile.n5.replications

        materializations = relation.component_materializations
        assert tuple(item.candidate_id for item in materializations) == tuple(
            member.source_candidate_id for member in relation.members
        )
        assert tuple(item.original_atom_hash for item in materializations) == tuple(
            member.source_atom_content_hash for member in relation.members
        )
        assert tuple(item.derived_n5_atom for item in materializations) == request.intervention_atoms
        assert tuple(item.atom_id for item in request.intervention_atoms) == selection.derived_atom_ids
        assert tuple(item.content_hash for item in request.intervention_atoms) == (
            selection.derived_atom_content_hashes
        )
        assert relation.members == selection.members
        for materialization in materializations:
            slot = request.world_model_record.slot_binding(materialization.target_world_slot)
            assert slot is not None and slot.unit == materialization.unit_id
            assert (
                materialization.derived_n5_atom.problem_frame_ref
                == relation.parent_design_problem_ref
            )
            assert (
                materialization.derived_n5_atom.world_model_record_ref
                == relation.world_model_record_ref
            )

        # Rehash a fully typed permutation, then require the real relation
        # consumer to reject it against the original persisted relation.
        fields = selection.model_dump(mode="json", exclude={"content_hash"})
        for name in (
            "child_node_refs",
            "members",
            "derived_atom_ids",
            "derived_atom_content_hashes",
        ):
            fields[name] = tuple(reversed(fields[name]))
        reversed_payload_hash = gy_content_hash(fields)
        reversed_selection = ParentJointCandidateSelectionV3.model_validate(
            {**fields, "content_hash": reversed_payload_hash}
        )
        with pytest.raises(RecursiveGenerationCycleError) as refusal:
            load_authored_joint_components(
                store=store,
                relation_ref=relation_ref,
                source_repository=GenerationSourceRepository(store),
                parent_handoff=parent_handoff,
                admission_owner=GenericCycleSimulationAdmissionOwner(profiles=(), store=store),
                request=request,
                selection=reversed_selection,
            )
        assert refusal.value.code == "recursive_authored_joint_selection_replay_mismatch"

    return relation
