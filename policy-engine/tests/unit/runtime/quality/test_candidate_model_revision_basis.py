"""Real source/model owner controls for the bounded coefficient component.

These tests never manufacture an action, intent, evaluation basis or N5 result.
They establish component replay, not a native second research step or authority.
The controlled WDI unemployment level is an outcome baseline; its coefficient
is a separately declared, ungrounded model assumption.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from polisyos.core import artifacts
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.ir import prepare_ncm_spec_selected_values
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.acquisition_model_transition import (
    _CandidateModelSelection,
    _is_coefficient_only_native_change,
    _native_mapping,
    _read_selected_candidate_coefficient_pair,
)
from polisyos.runtime.quality.candidate_source_basis import prepare_candidate_source_basis_values
from polisyos.runtime.quality.cycle_substrate import (
    ConfiguredCandidateSimulationContextAdmissionOwner,
)
from polisyos.runtime.quality.data_state_substrate import build_candidate_acquisition_world
from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes
from tests.unit.runtime.quality.test_candidate_acquisition_world import (
    CELL_ID,
    TENANT_ID,
    TRANSACTION_TIME,
)
from tests.unit.runtime.quality.test_candidate_source_basis import (
    _case_with_explicit_empty_prior,
    _files,
    _inputs,
)

if TYPE_CHECKING:
    from polisyos.runtime.quality.world_model_record import WorldModelRecord
    from tests.unit.runtime.quality.test_candidate_acquisition_world import _CandidateWorldCase

_RUN = "candidate-coefficient-component-run"


def _facets(values: object) -> dict[str, object]:
    return _native_mapping(json.loads(exact_n5_content_bytes(values)))


def test_candidate_model_classifier_replays_source_and_refuses_nonmodel_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every actual nonmodel facet remains decisive despite a coefficient change."""
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _case_with_explicit_empty_prior(tmp_path, monkeypatch)
        old_inputs = _inputs(case, coefficient=0.5)
        new_inputs = _inputs(case, coefficient=0.75)
        old = prepare_candidate_source_basis_values(
            store=case.store, problem=case.problem, inputs=old_inputs
        )
        new = prepare_candidate_source_basis_values(
            store=case.store, problem=case.problem, inputs=new_inputs
        )
        assert old.predicate_provenance == new.predicate_provenance == "recomputed"
        assert old.reason_codes == new.reason_codes == ()
        assert old_inputs.candidate_source_ref == new_inputs.candidate_source_ref
        assert old.effective_values["foundry_state"] == new.effective_values["foundry_state"]
        assert (
            old.effective_values["n5_request_values"] == new.effective_values["n5_request_values"]
        )
        assert old.prospective_model is not None and new.prospective_model is not None
        baseline = old.prospective_model.n5_config.baseline_state["global.unemployment_rate"]
        for values, coefficient in ((old.effective_values, 0.5), (new.effective_values, 0.75)):
            assert values["declared_model"]["outcome_baseline"] == baseline
            assert values["declared_model"]["outcome_per_target_unit"] == coefficient
            assert values["candidate_source"]["scientific_authority"]["independence"] == (
                "not_established"
            )
            assert not values["candidate_source"]["scientific_authority"]["publication_authority"]
        assert baseline not in (0.5, 0.75)
        before, after = _facets(old.effective_values), _facets(new.effective_values)
        assert _is_coefficient_only_native_change(before, after)
        assert not _is_coefficient_only_native_change(before, before)
        for name in after.keys() - {"declared_model", "selected_native_ncm"}:
            drift = {**after, name: {"unreconciled_changed_facet": name}}
            assert not _is_coefficient_only_native_change(before, drift), name


def _admit_model(
    case: _CandidateWorldCase,
    world: WorldModelRecord,
    *,
    coefficient: float,
    job_id: str,
    noise_stddev: float | None = None,
) -> _CandidateModelSelection:
    """Use the real configured context owner to emit selected declaration/NCM views."""
    inputs = _inputs(case, coefficient=coefficient)
    declaration = inputs.original_model_declaration
    if noise_stddev is not None:
        payload = declaration.model_dump(mode="json", exclude={"content_hash"})
        payload["outcome_noise_stddev"] = noise_stddev
        declaration = type(declaration).model_validate(
            {**payload, "content_hash": gy_content_hash(payload)}
        )
    offer = ConfiguredCandidateSimulationContextAdmissionOwner(
        profiles=(inputs.configured_profile,),
        model_declarations=(declaration,),
        store=case.store,
    ).admit_context_for_acquired_world(
        problem=case.problem,
        profile_selection_ref=case.binding.profile_selection_ref,
        world_model_record=world,
        job_id=job_id,
        run_id=_RUN,
        tenant_id=TENANT_ID,
        cell_id=CELL_ID,
        additional_authority_denials=case.source_case.source.limitations,
    )
    assert set(case.source_case.source.limitations).issubset(offer.context.may_not_use_for)
    return _CandidateModelSelection(
        offer.profile, offer.model_declaration_ref, offer.ncm_ref, job_id
    )


def test_selected_coefficient_reader_reopens_real_owner_and_refuses_profile_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exact selected owners are mandatory even when equal bytes/default views exist."""
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _case_with_explicit_empty_prior(tmp_path, monkeypatch)
        built = build_candidate_acquisition_world(
            case.store,
            problem=case.problem,
            base_world_model=case.base.record,
            substrate_registry=case.substrate_registry,
            substrate_registry_artifact_ref=case.substrate_registry_ref,
            materialization=case.materialization,
            workspace_dir=tmp_path / "actual-candidate-world",
            transaction_time=TRANSACTION_TIME,
            authority=case.source_case.authority,
        )
        world = built.world_model.record
        old = _admit_model(case, world, coefficient=0.5, job_id="model-old")
        new = _admit_model(case, world, coefficient=0.75, job_id="model-new")
        retry = _admit_model(case, world, coefficient=0.5, job_id="model-retry")
        noise = _admit_model(case, world, coefficient=0.75, job_id="model-noise", noise_stddev=0.02)
        reader = artifacts.FileSystemCAS.open_existing_read_only(case.store.root)

        def read(selected: _CandidateModelSelection) -> tuple[object, object]:
            return _read_selected_candidate_coefficient_pair(
                artifact_store=reader,
                previous=old,
                selected=selected,
                run_id=_RUN,
                tenant_id=TENANT_ID,
                cell_id=CELL_ID,
            )

        before = _files(case.store.root)
        first = read(new)
        second = read(new)
        assert tuple(prepare_ncm_spec_selected_values(ncm).value_bytes for ncm in first) == (
            tuple(prepare_ncm_spec_selected_values(ncm).value_bytes for ncm in second)
        )
        assert prepare_ncm_spec_selected_values(first[0]).value_bytes != (
            prepare_ncm_spec_selected_values(first[1]).value_bytes
        )
        assert not hasattr(reader, "put_bytes")
        assert _files(case.store.root) == before

        # Another producer occurrence with the same coefficient/scalar is not
        # a coefficient change or evidence of an independent scientific sample.
        assert retry.declaration_ref.artifact_id == old.declaration_ref.artifact_id
        assert retry.declaration_ref.manifest_profile_sha256 != (
            old.declaration_ref.manifest_profile_sha256
        )
        for unsupported in (retry, noise):
            with pytest.raises(
                ValueError, match="candidate_source_model_revision_coefficient_mismatch"
            ):
                read(unsupported)

        for name in ("declaration_ref", "ncm_ref"):
            unselected = getattr(new, name).model_copy(update={"manifest_profile_sha256": None})
            with pytest.raises(
                ValueError, match="candidate_source_model_revision_selected_model_ref_required"
            ):
                read(replace(new, **{name: unselected}))
        with pytest.raises(ValueError, match="ncm_owner_profile_mismatch"):
            read(replace(new, ncm_ref=old.ncm_ref))
        with pytest.raises(ValueError, match="model_declaration_owner_profile_mismatch"):
            read(replace(new, job_id=old.job_id))

        # Same payload bytes under a foreign selected producer remain a real
        # CAS sibling; keeping the original model/NCM markers cannot admit it.
        manifest = case.store.get_manifest(new.declaration_ref)
        foreign = case.store.put_bytes(
            case.store.get_bytes(new.declaration_ref),
            artifacts.ArtifactWriteOptions(
                kind=new.declaration_ref.kind,
                media_type=new.declaration_ref.media_type,
                schema=manifest.artifact_schema,
                canon=manifest.canon,
                inputs=manifest.inputs,
                governance=manifest.governance,
                tenant_context=manifest.tenant_context,
                producer=artifacts.ProducerInfo(component="test.foreign-model-view", version="1"),
            ),
            return_selected_profile=True,
        )
        assert foreign.artifact_id == new.declaration_ref.artifact_id
        assert foreign.manifest_profile_sha256 != new.declaration_ref.manifest_profile_sha256
        with pytest.raises(ValueError, match="model_declaration_owner_profile_mismatch"):
            read(replace(new, declaration_ref=foreign))
        assert read(new)
