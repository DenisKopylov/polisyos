"""Exercise source/world prefix replay without action, terminal, or N5 authority.

The controlled inputs establish software replay only. They do not establish
candidate-experiment history, route authority, a PA2 decision, or publication.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, ProducerInfo
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.quality.candidate_source_basis import (
    CandidateSourceBasisInputs,
    CandidateSourceBasisPredecessor,
    CandidateSourceBasisValues,
    prepare_candidate_source_basis_values,
)
from polisyos.runtime.quality.cycle_substrate import (
    ConfiguredCandidateSimulationContextAdmissionOwner,
)
from polisyos.runtime.quality.data_state_substrate import (
    build_candidate_acquisition_world,
    materialize_candidate_acquisition_snapshot,
)
from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes
from polisyos.runtime.quality.world_model_record import world_model_artifact_views
from tests._helpers.lane01_wdi_profiles import UNEMPLOYMENT_PROFILE, fixture_wdi_response
from tests.unit.runtime.quality.test_candidate_acquisition_world import (
    CELL_ID,
    TENANT_ID,
    TRANSACTION_TIME,
)
from tests.unit.runtime.quality.test_candidate_source_basis import (
    _another_real_source,
    _case_with_explicit_empty_prior,
    _inputs,
)

if TYPE_CHECKING:
    from polisyos.runtime.quality.data_state_substrate import (
        CandidateAcquisitionDataSnapshotResult,
        CandidateAcquisitionWorldBuildResult,
    )
    from tests.unit.runtime.quality.test_candidate_acquisition_world import _CandidateWorldCase


@dataclass(frozen=True)
class _CandidateSourcePrefix:
    case: _CandidateWorldCase
    first_inputs: CandidateSourceBasisInputs
    first_basis: CandidateSourceBasisValues
    first_world: CandidateAcquisitionWorldBuildResult
    predecessor: CandidateSourceBasisPredecessor
    next_inputs: CandidateSourceBasisInputs
    next_materialization: CandidateAcquisitionDataSnapshotResult
    next_world: CandidateAcquisitionWorldBuildResult


def _build_candidate_source_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> _CandidateSourcePrefix:
    """Build two adjacent source/world steps through their existing real owners."""
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _case_with_explicit_empty_prior(tmp_path, monkeypatch)
        first_inputs = _inputs(case)
        first_world = build_candidate_acquisition_world(
            case.store,
            problem=case.problem,
            base_world_model=case.base.record,
            substrate_registry=case.substrate_registry,
            substrate_registry_artifact_ref=case.substrate_registry_ref,
            materialization=case.materialization,
            workspace_dir=tmp_path / "first-world",
            transaction_time=TRANSACTION_TIME,
            authority=case.source_case.authority,
        )
        first_basis = prepare_candidate_source_basis_values(
            store=case.store,
            problem=case.problem,
            inputs=first_inputs,
            data_snapshot_ref=case.materialization.data_snapshot_ref,
            world_model_ref=first_world.world_model.record_ref,
        )
        if first_basis.predicate_provenance != "recomputed":
            raise AssertionError(first_basis.reason_codes)

        owner = ConfiguredCandidateSimulationContextAdmissionOwner(
            profiles=(first_inputs.configured_profile,),
            model_declarations=(first_inputs.original_model_declaration,),
            store=case.store,
        )
        refreshed = owner.prepare_context_for_acquired_world(
            problem=case.problem,
            profile_selection_ref=first_inputs.slot_binding.profile_selection_ref,
            world_model_record=first_world.world_model.record,
            job_id="candidate-basis-first-action",
            run_id=case.source_case.source.run_id,
            tenant_id=TENANT_ID,
            cell_id=CELL_ID,
        )
        next_source_dir = tmp_path / "next-source"
        next_source_dir.mkdir()
        next_source_ref = _another_real_source(case, next_source_dir, monkeypatch)
        next_time = TRANSACTION_TIME + timedelta(seconds=1)
        first_views = world_model_artifact_views(first_world.world_model.record)
        next_inputs = CandidateSourceBasisInputs(
            configured_profile=refreshed.profile,
            original_model_declaration=refreshed.model_declaration,
            base_world_model_ref=first_world.world_model.record_ref,
            base_data_snapshot_ref=first_views.data_snapshot_ref,
            candidate_source_ref=next_source_ref,
            slot_binding=first_inputs.slot_binding,
            transaction_time=next_time,
        )
        next_materialization = materialize_candidate_acquisition_snapshot(
            case.store,
            base_data_snapshot_ref=next_inputs.base_data_snapshot_ref,
            candidate_source_ref=next_source_ref,
            slot_binding=next_inputs.slot_binding,
            workspace_dir=tmp_path / "next-data",
            transaction_time=next_time,
            authority=case.source_case.authority,
        )
        next_world = build_candidate_acquisition_world(
            case.store,
            problem=case.problem,
            base_world_model=first_world.world_model.record,
            substrate_registry=case.substrate_registry,
            substrate_registry_artifact_ref=case.substrate_registry_ref,
            materialization=next_materialization,
            workspace_dir=tmp_path / "next-world",
            transaction_time=next_time,
            authority=case.source_case.authority,
        )
        predecessor = CandidateSourceBasisPredecessor(
            inputs=first_inputs,
            data_snapshot_ref=case.materialization.data_snapshot_ref,
            world_model_ref=first_world.world_model.record_ref,
        )
        return _CandidateSourcePrefix(
            case=case,
            first_inputs=first_inputs,
            first_basis=first_basis,
            first_world=first_world,
            predecessor=predecessor,
            next_inputs=next_inputs,
            next_materialization=next_materialization,
            next_world=next_world,
        )


def test_candidate_experiment_basis_reuses_selected_source_world_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same source bytes reuse B1 only through its selected producer output."""
    prefix = _build_candidate_source_prefix(tmp_path, monkeypatch)
    case = prefix.case
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        assert prefix.next_inputs.candidate_source_ref != prefix.first_inputs.candidate_source_ref
        assert prefix.next_inputs.transaction_time > prefix.first_inputs.transaction_time
        assert prefix.next_inputs.base_world_model_ref == prefix.first_world.world_model.record_ref
        assert (
            prefix.next_inputs.base_data_snapshot_ref
            == world_model_artifact_views(prefix.first_world.world_model.record).data_snapshot_ref
        )

        without_predecessor = prepare_candidate_source_basis_values(
            store=case.store,
            problem=case.problem,
            inputs=prefix.next_inputs,
            data_snapshot_ref=prefix.next_materialization.data_snapshot_ref,
            world_model_ref=prefix.next_world.world_model.record_ref,
        )
        assert without_predecessor.predicate_provenance == "recomputed"
        assert exact_n5_content_bytes(without_predecessor.effective_values) != (
            exact_n5_content_bytes(prefix.first_basis.effective_values)
        )

        repeated = prepare_candidate_source_basis_values(
            store=case.store,
            problem=case.problem,
            inputs=prefix.next_inputs,
            data_snapshot_ref=prefix.next_materialization.data_snapshot_ref,
            world_model_ref=prefix.next_world.world_model.record_ref,
            predecessors=(prefix.predecessor,),
        )
        assert repeated.predicate_provenance == "recomputed", repeated.reason_codes
        assert repeated.effective_values == prefix.first_basis.effective_values
        assert exact_n5_content_bytes(repeated.effective_values) == exact_n5_content_bytes(
            prefix.first_basis.effective_values
        )

        changed_response = json.loads(fixture_wdi_response(UNEMPLOYMENT_PROFILE))
        scientific_scope = {
            "sample_size": 317,
            "independence_group": "shared-modeled-panel",
            "replication_id": "replica-2",
            "reference_period": "2024-07-01/2024-12-31",
        }
        changed_response[1][0]["scientific_scope"] = scientific_scope
        changed_source_dir = tmp_path / "changed-source"
        changed_source_dir.mkdir()
        changed_source_ref = _another_real_source(
            case,
            changed_source_dir,
            monkeypatch,
            body=json.dumps(changed_response, sort_keys=True, separators=(",", ":")).encode(),
        )
        changed = prepare_candidate_source_basis_values(
            store=case.store,
            problem=case.problem,
            inputs=prefix.next_inputs.model_copy(
                update={"candidate_source_ref": changed_source_ref}
            ),
            predecessors=(prefix.predecessor,),
        )
        assert changed.predicate_provenance == "recomputed", changed.reason_codes
        changed_source_values = changed.effective_values["candidate_source"]
        assert isinstance(changed_source_values, dict)
        changed_raw_values = changed_source_values["raw_wdi_values"]
        assert isinstance(changed_raw_values, list)
        changed_observation = changed_raw_values[1][0]
        assert isinstance(changed_observation, dict)
        assert changed_observation["scientific_scope"] == scientific_scope
        assert exact_n5_content_bytes(changed.effective_values) != exact_n5_content_bytes(
            repeated.effective_values
        )

        selected_world = prefix.first_world.world_model.record_ref
        selected_manifest = case.store.get_manifest(selected_world)
        foreign_world = case.store.put_bytes(
            case.store.get_bytes(selected_world),
            ArtifactWriteOptions(
                kind=selected_world.kind,
                media_type=selected_world.media_type,
                schema=selected_manifest.artifact_schema,
                producer=ProducerInfo(component="test.foreign-world-owner", version="1"),
                env=selected_manifest.env,
                inputs=selected_manifest.inputs,
                canon=selected_manifest.canon,
                governance=selected_manifest.governance,
                tenant_context=selected_manifest.tenant_context,
                same_input_closure=selected_manifest.same_input_closure,
                authority=selected_manifest.authority,
                warnings=selected_manifest.warnings,
            ),
            return_selected_profile=True,
        )
        assert foreign_world.artifact_id == selected_world.artifact_id
        assert foreign_world.manifest_profile_sha256 != selected_world.manifest_profile_sha256
        foreign_predecessor = CandidateSourceBasisPredecessor(
            inputs=prefix.first_inputs,
            data_snapshot_ref=case.materialization.data_snapshot_ref,
            world_model_ref=foreign_world,
        )
        foreign = prepare_candidate_source_basis_values(
            store=case.store,
            problem=case.problem,
            inputs=prefix.next_inputs,
            predecessors=(foreign_predecessor,),
        )
        assert foreign.predicate_provenance == "not_established"
        assert foreign.reason_codes == ("candidate_source_basis_predecessor_selection_mismatch",)
