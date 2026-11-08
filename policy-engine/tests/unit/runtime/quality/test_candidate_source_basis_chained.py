"""Compare actual successive candidate-world inputs, including their source scope."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, ProducerInfo
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.quality.candidate_acquisition_source import (
    read_candidate_acquisition_source,
)
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
class _TwoStepChain:
    case: _CandidateWorldCase
    initial: CandidateSourceBasisInputs
    first: CandidateSourceBasisValues
    first_world: CandidateAcquisitionWorldBuildResult
    owner: ConfiguredCandidateSimulationContextAdmissionOwner
    next_inputs: CandidateSourceBasisInputs
    materialized: CandidateAcquisitionDataSnapshotResult
    second_world: CandidateAcquisitionWorldBuildResult
    next_time: datetime


def _different_paths(left: object, right: object, path: str = "world") -> tuple[str, ...]:
    """Name exact differing native values without dumping source payloads."""
    if type(left) is dict and type(right) is dict:
        paths: list[str] = []
        for key in sorted(left.keys() | right.keys()):
            if key not in left or key not in right:
                paths.append(f"{path}.{key}:missing")
            else:
                paths.extend(_different_paths(left[key], right[key], f"{path}.{key}"))
        return tuple(paths)
    if type(left) is type(right) and type(left) in (tuple, list):
        if len(left) != len(right):
            return (f"{path}:length({len(left)},{len(right)})",)
        return tuple(
            item
            for index, (a, b) in enumerate(zip(left, right, strict=True))
            for item in _different_paths(a, b, f"{path}[{index}]")
        )
    if exact_n5_content_bytes(left) != exact_n5_content_bytes(right):
        return (path,)
    return ()


def _build_two_step_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, source_body: bytes | None = None
) -> _TwoStepChain:
    """Use the real source and world producers for exactly two selected worlds."""
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _case_with_explicit_empty_prior(tmp_path, monkeypatch)
        initial = _inputs(case)
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
        first = prepare_candidate_source_basis_values(
            store=case.store,
            problem=case.problem,
            inputs=initial,
            data_snapshot_ref=case.materialization.data_snapshot_ref,
            world_model_ref=first_world.world_model.record_ref,
        )
        assert first.predicate_provenance == "recomputed", first.reason_codes

        owner = ConfiguredCandidateSimulationContextAdmissionOwner(
            profiles=(initial.configured_profile,),
            model_declarations=(initial.original_model_declaration,),
            store=case.store,
        )
        latest = owner.prepare_context_for_acquired_world(
            problem=case.problem,
            profile_selection_ref=initial.slot_binding.profile_selection_ref,
            world_model_record=first_world.world_model.record,
            job_id="candidate-basis-first-action",
            run_id=case.source_case.source.run_id,
            tenant_id=TENANT_ID,
            cell_id=CELL_ID,
        )
        next_dir = tmp_path / "next-source"
        next_dir.mkdir()
        next_source_ref = _another_real_source(case, next_dir, monkeypatch, body=source_body)
        next_time = TRANSACTION_TIME + timedelta(seconds=1)
        next_inputs = CandidateSourceBasisInputs(
            configured_profile=latest.profile,
            original_model_declaration=latest.model_declaration,
            base_world_model_ref=first_world.world_model.record_ref,
            base_data_snapshot_ref=world_model_artifact_views(
                first_world.world_model.record
            ).data_snapshot_ref,
            candidate_source_ref=next_source_ref,
            slot_binding=initial.slot_binding,
            transaction_time=next_time,
        )
        materialized = materialize_candidate_acquisition_snapshot(
            case.store,
            base_data_snapshot_ref=next_inputs.base_data_snapshot_ref,
            candidate_source_ref=next_source_ref,
            slot_binding=next_inputs.slot_binding,
            workspace_dir=tmp_path / "next-data",
            transaction_time=next_time,
            authority=case.source_case.authority,
        )
        second_world = build_candidate_acquisition_world(
            case.store,
            problem=case.problem,
            base_world_model=first_world.world_model.record,
            substrate_registry=case.substrate_registry,
            substrate_registry_artifact_ref=case.substrate_registry_ref,
            materialization=materialized,
            workspace_dir=tmp_path / "next-world",
            transaction_time=next_time,
            authority=case.source_case.authority,
        )
        return _TwoStepChain(
            case=case,
            initial=initial,
            first=first,
            first_world=first_world,
            owner=owner,
            next_inputs=next_inputs,
            materialized=materialized,
            second_world=second_world,
            next_time=next_time,
        )


def test_repeated_source_uses_verified_latest_world_without_losing_scientific_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Equal selected source values can repeat without losing scientific scope.

    This is an owner-composition test, not a served action, current lease, or
    source-authority claim. No physical N5 execution is asserted.
    """
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        chain = _build_two_step_chain(tmp_path, monkeypatch)
        case = chain.case
        initial = chain.initial
        first = chain.first
        first_world = chain.first_world
        owner = chain.owner
        next_inputs = chain.next_inputs
        materialized = chain.materialized
        second_world = chain.second_world
        next_time = chain.next_time
        next_source_ref = next_inputs.candidate_source_ref
        unproved = prepare_candidate_source_basis_values(
            store=case.store,
            problem=case.problem,
            inputs=next_inputs,
            data_snapshot_ref=materialized.data_snapshot_ref,
            world_model_ref=second_world.world_model.record_ref,
        )
        assert unproved.predicate_provenance == "recomputed", unproved.reason_codes
        assert exact_n5_content_bytes(first.effective_values) != exact_n5_content_bytes(
            unproved.effective_values
        )
        predecessor = CandidateSourceBasisPredecessor(
            inputs=initial,
            data_snapshot_ref=case.materialization.data_snapshot_ref,
            world_model_ref=first_world.world_model.record_ref,
        )
        repeated = prepare_candidate_source_basis_values(
            store=case.store,
            problem=case.problem,
            inputs=next_inputs,
            data_snapshot_ref=materialized.data_snapshot_ref,
            world_model_ref=second_world.world_model.record_ref,
            predecessors=(predecessor,),
        )
        assert repeated.predicate_provenance == "recomputed", repeated.reason_codes
        differing_facets = tuple(
            sorted(
                name
                for name in first.effective_values.keys() | repeated.effective_values.keys()
                if exact_n5_content_bytes(first.effective_values.get(name))
                != exact_n5_content_bytes(repeated.effective_values.get(name))
            )
        )
        if differing_facets:
            pytest.fail(
                "\n".join(
                    (
                        f"Differing facets: {', '.join(differing_facets)}",
                        *_different_paths(
                            first.effective_values["world"], repeated.effective_values["world"]
                        ),
                    )
                ),
                pytrace=False,
            )
        assert not differing_facets

        # Equal CAS bytes under a different manifest do not supply the selected
        # prior world. The producer proof must bind the full selected profile.
        selected_world = first_world.world_model.record_ref
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
            inputs=initial,
            data_snapshot_ref=case.materialization.data_snapshot_ref,
            world_model_ref=foreign_world,
        )
        foreign = prepare_candidate_source_basis_values(
            store=case.store,
            problem=case.problem,
            inputs=next_inputs,
            predecessors=(foreign_predecessor,),
        )
        assert foreign.predicate_provenance == "not_established"
        assert foreign.reason_codes == ("candidate_source_basis_predecessor_selection_mismatch",)

        wrong_source = CandidateSourceBasisPredecessor(
            inputs=initial.model_copy(update={"candidate_source_ref": next_source_ref}),
            data_snapshot_ref=case.materialization.data_snapshot_ref,
            world_model_ref=selected_world,
        )
        forged = prepare_candidate_source_basis_values(
            store=case.store,
            problem=case.problem,
            inputs=next_inputs,
            predecessors=(wrong_source,),
        )
        assert forged.predicate_provenance == "not_established"
        assert forged.reason_codes == ("candidate_source_basis_actual_snapshot_mismatch",)

        # Two verified producer transitions followed by a third equal source
        # remain one effective input; no extra N5 execution is asserted here.
        second_predecessor = CandidateSourceBasisPredecessor(
            inputs=next_inputs,
            data_snapshot_ref=materialized.data_snapshot_ref,
            world_model_ref=second_world.world_model.record_ref,
        )
        after_second = owner.prepare_context_for_acquired_world(
            problem=case.problem,
            profile_selection_ref=initial.slot_binding.profile_selection_ref,
            world_model_record=second_world.world_model.record,
            job_id="candidate-basis-second-action",
            run_id=case.source_case.source.run_id,
            tenant_id=TENANT_ID,
            cell_id=CELL_ID,
        )
        third_dir = tmp_path / "third-source"
        third_dir.mkdir()
        third_source_ref = _another_real_source(case, third_dir, monkeypatch)
        assert third_source_ref != next_source_ref
        third_inputs = CandidateSourceBasisInputs(
            configured_profile=after_second.profile,
            original_model_declaration=after_second.model_declaration,
            base_data_snapshot_ref=materialized.data_snapshot_ref,
            base_world_model_ref=second_world.world_model.record_ref,
            candidate_source_ref=third_source_ref,
            slot_binding=initial.slot_binding,
            transaction_time=next_time + timedelta(seconds=1),
        )
        third = prepare_candidate_source_basis_values(
            store=case.store,
            problem=case.problem,
            inputs=third_inputs,
            predecessors=(predecessor, second_predecessor),
        )
        assert third.predicate_provenance == "recomputed", third.reason_codes
        assert exact_n5_content_bytes(first.effective_values) == exact_n5_content_bytes(
            third.effective_values
        )

        # Same numerical value with new source sampling/independence facts must
        # remain different; receipt identity alone is never scientific evidence.
        response = json.loads(fixture_wdi_response(UNEMPLOYMENT_PROFILE))
        response[1][0]["scientific_scope"] = {
            "sample_size": 317,
            "independence_group": "shared-modeled-panel",
            "replication_id": "replica-2",
            "reference_period": "2024-07-01/2024-12-31",
        }
        changed_dir = tmp_path / "changed-source"
        changed_dir.mkdir()
        changed_ref = _another_real_source(
            case,
            changed_dir,
            monkeypatch,
            body=json.dumps(response, sort_keys=True, separators=(",", ":")).encode(),
        )
        changed = prepare_candidate_source_basis_values(
            store=case.store,
            problem=case.problem,
            inputs=next_inputs.model_copy(update={"candidate_source_ref": changed_ref}),
            predecessors=(predecessor,),
        )
        assert changed.predicate_provenance == "recomputed", changed.reason_codes
        assert (
            changed.effective_values["candidate_source"]["raw_wdi_values"][1][0]["scientific_scope"]
            == response[1][0]["scientific_scope"]
        )
        for facet in ("foundry_state", "selected_native_ncm", "n5_request_values"):
            assert exact_n5_content_bytes(changed.effective_values[facet]) == (
                exact_n5_content_bytes(repeated.effective_values[facet])
            )
        assert exact_n5_content_bytes(repeated.effective_values) != exact_n5_content_bytes(
            changed.effective_values
        )

        # A provider release date changes the retained source occurrence even
        # when the selected WDI row and every numerical N5 input stay equal.
        # The date is source metadata, not proof that the source is current.
        release_response = json.loads(fixture_wdi_response(UNEMPLOYMENT_PROFILE))
        release_response[0]["lastupdated"] = "2026-10-09"
        release_body = json.dumps(release_response, sort_keys=True, separators=(",", ":")).encode()
        release_dir = tmp_path / "release-metadata-source"
        release_dir.mkdir()
        release_ref = _another_real_source(
            case,
            release_dir,
            monkeypatch,
            body=release_body,
        )
        assert release_ref != next_source_ref
        prior_persisted_source = read_candidate_acquisition_source(
            case.store,
            source_ref=next_source_ref,
        )
        release_persisted_source = read_candidate_acquisition_source(
            case.store,
            source_ref=release_ref,
        )
        assert release_persisted_source.raw_source_ref != prior_persisted_source.raw_source_ref

        released = prepare_candidate_source_basis_values(
            store=case.store,
            problem=case.problem,
            inputs=next_inputs.model_copy(update={"candidate_source_ref": release_ref}),
            predecessors=(predecessor,),
        )
        assert released.predicate_provenance == "recomputed", released.reason_codes
        previous_raw = repeated.effective_values["candidate_source"]["raw_wdi_values"]
        released_raw = released.effective_values["candidate_source"]["raw_wdi_values"]
        assert "lastupdated" not in previous_raw[0]
        assert released_raw[0]["lastupdated"] == "2026-10-09"
        assert released_raw[1] == previous_raw[1]
        for facet in ("foundry_state", "selected_native_ncm", "n5_request_values"):
            assert exact_n5_content_bytes(released.effective_values[facet]) == (
                exact_n5_content_bytes(repeated.effective_values[facet])
            )
        assert exact_n5_content_bytes(released.effective_values) != exact_n5_content_bytes(
            repeated.effective_values
        )
        assert released.effective_values["candidate_source"]["scientific_authority"] == {
            "observation_class": release_persisted_source.observation_class.value,
            "source_currentness": "not_established",
            "measurement_validity": "not_established",
            "independence": "not_established",
            "sample_denominator_evidence": "not_established",
            "publication_authority": False,
        }


def test_changed_scientific_source_remains_in_restored_source_ancestry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A changed intervening source is not erased when its scalar is restored."""
    response = json.loads(fixture_wdi_response(UNEMPLOYMENT_PROFILE))
    response[1][0]["scientific_scope"] = {
        "sample_size": 317,
        "independence_group": "shared-modeled-panel",
        "replication_id": "replica-2",
        "reference_period": "2024-07-01/2024-12-31",
    }
    source_body = json.dumps(response, sort_keys=True, separators=(",", ":")).encode()
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        chain = _build_two_step_chain(tmp_path, monkeypatch, source_body=source_body)
        case = chain.case
        changed_ref = chain.next_inputs.candidate_source_ref
        after_changed = chain.owner.prepare_context_for_acquired_world(
            problem=case.problem,
            profile_selection_ref=chain.initial.slot_binding.profile_selection_ref,
            world_model_record=chain.second_world.world_model.record,
            job_id="candidate-basis-changed-action",
            run_id=case.source_case.source.run_id,
            tenant_id=TENANT_ID,
            cell_id=CELL_ID,
        )
        restored_inputs = CandidateSourceBasisInputs(
            configured_profile=after_changed.profile,
            original_model_declaration=after_changed.model_declaration,
            base_data_snapshot_ref=chain.materialized.data_snapshot_ref,
            base_world_model_ref=chain.second_world.world_model.record_ref,
            candidate_source_ref=case.source_case.source_ref,
            slot_binding=chain.initial.slot_binding,
            transaction_time=chain.next_time + timedelta(seconds=1),
        )
        restored = prepare_candidate_source_basis_values(
            store=case.store,
            problem=case.problem,
            inputs=restored_inputs,
            predecessors=(
                CandidateSourceBasisPredecessor(
                    inputs=chain.initial,
                    data_snapshot_ref=case.materialization.data_snapshot_ref,
                    world_model_ref=chain.first_world.world_model.record_ref,
                ),
                CandidateSourceBasisPredecessor(
                    inputs=chain.next_inputs,
                    data_snapshot_ref=chain.materialized.data_snapshot_ref,
                    world_model_ref=chain.second_world.world_model.record_ref,
                ),
            ),
        )
        assert restored.predicate_provenance == "recomputed", restored.reason_codes
        assert exact_n5_content_bytes(chain.first.effective_values) != exact_n5_content_bytes(
            restored.effective_values
        )
        assert restored.effective_values["world"]["data"]["base_snapshot"]["source_lineage"][
            "candidate_source_ref"
        ] == changed_ref.model_dump(mode="json")
