from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.candidate_simulation import (
    CandidateSimulationSyntheticModelDeclarationV1,
)
from polisyos.runtime.quality.generation_source import (
    GenerationSourceRepository,
    _candidate_simulation_write_options,
)

if TYPE_CHECKING:
    from polisyos.ir.artifacts.contracts import ArtifactSelector


class _ReadOnlySelectedView:
    """Expose only the selected-view reads required by the NCM replay path."""

    def __init__(self, adapter: CoreToIRArtifactStoreAdapter) -> None:
        self._adapter = adapter

    def get_bytes(self, artifact_id: ArtifactSelector) -> bytes:
        return self._adapter.get_bytes(artifact_id)

    def get_manifest(self, artifact_id: ArtifactSelector) -> object:
        return self._adapter.get_manifest(artifact_id)

    def get_manifest_bytes(self, artifact_id: ArtifactSelector) -> bytes:
        return self._adapter.get_manifest_bytes(artifact_id)

    def verify(self, artifact_id: ArtifactSelector) -> object:
        return self._adapter.verify(artifact_id)


def _declaration(*, coefficient: float) -> CandidateSimulationSyntheticModelDeclarationV1:
    fields = {
        "schema_version": ("policyos.runtime.candidate_simulation.synthetic_model_declaration.v1"),
        "profile_config_ref": "runtime-config:candidate-simulation:fixture",
        "profile_content_hash": "sha256:" + "a" * 64,
        "profile_selection_ref": "sha256:" + "b" * 64,
        "target_world_slot": "cells.distress_score",
        "outcome_variable": "cells.output",
        "target_unit_id": "synthetic_score",
        "outcome_unit_id": "synthetic_score",
        "target_baseline": 2.0,
        "outcome_baseline": 10.0,
        "outcome_per_target_unit": coefficient,
        "outcome_noise_stddev": 0.01,
        "assumption": "declared_candidate_scm_not_empirically_grounded",
    }
    draft = CandidateSimulationSyntheticModelDeclarationV1.model_construct(
        **fields,
        content_hash="sha256:" + "0" * 64,
    )
    return CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {
            **fields,
            "content_hash": gy_content_hash(
                draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )


def test_candidate_ncm_is_derived_from_declared_baseline_and_selected_view(
    tmp_path,
) -> None:
    """NCM replay binds the exact declaration view, including nondefault CAS views."""
    from polisyos.ir.analytics.ncm import (
        candidate_ncm_spec_from_declaration,
        load_ncm_spec_selected_view,
    )

    tenant_id = "tenant-candidate-ncm"
    cell_id = "cell-candidate-ncm"
    job_id = "job-candidate-ncm"
    run_id = "run-candidate-ncm"
    store = FileSystemCAS(tmp_path / "candidate-ncm-cas")
    repository = GenerationSourceRepository(store)
    declaration = _declaration(coefficient=3.0)
    alternate_declaration = _declaration(coefficient=2.0)
    spec = candidate_ncm_spec_from_declaration(declaration)
    assert spec.structural_equations[1].equation_params["intercept"] == 4.0
    assert spec.scm_spec is not None and spec.scm_spec.fitted is False
    assert spec.markov_condition_verified is False
    assert spec.fit_method == "declared_candidate_assumption"

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        # Establish a distinct default view of the same bytes. The selected
        # candidate view below must remain resolvable by its full ArtifactRef.
        default_options = _candidate_simulation_write_options(
            kind="ir.ncm_spec",
            schema_name="ir.ncm_spec",
            schema_version="1.0",
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            source_ref=declaration.profile_content_hash,
        )
        from polisyos.ir.model_layer.canon import CanonSpec, to_canonical_bytes

        spec_bytes = to_canonical_bytes(
            spec.model_dump(mode="json"),
            CanonSpec(forbid_floats=False, exclude_none=False),
        )
        store.put_bytes(spec_bytes, default_options)
        declaration_ref = repository.persist_candidate_model_declaration(
            declaration=declaration,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        selected_ref = repository.persist_candidate_ncm_selected_view(
            ncm_spec=spec,
            declaration_ref=declaration_ref,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            profile_content_hash=declaration.profile_content_hash,
        )
        alternate_ref = repository.persist_candidate_model_declaration(
            declaration=alternate_declaration,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        default_view_spec = candidate_ncm_spec_from_declaration(alternate_declaration)
        default_view_ref = repository.persist_candidate_ncm_selected_view(
            ncm_spec=default_view_spec,
            declaration_ref=alternate_ref,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            profile_content_hash=alternate_declaration.profile_content_hash,
        )

        assert selected_ref.manifest_profile_sha256 is not None
        assert default_view_ref.manifest_profile_sha256 is not None
        from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref

        # Reproduce the authentic legacy selected-view writer path: it writes
        # the complete context but returns the default/profileless selector.
        legacy_default_options = _candidate_simulation_write_options(
            kind="ir.ncm_spec",
            schema_name="ir.ncm_spec",
            schema_version="1.0",
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            source_ref=alternate_declaration.profile_content_hash,
            input_refs=(
                input_ref_from_artifact_ref(
                    alternate_ref,
                    role="candidate_model_declaration",
                ),
            ),
        )
        legacy_default_bytes = to_canonical_bytes(
            default_view_spec.model_dump(mode="json"),
            CanonSpec(forbid_floats=False, exclude_none=False),
        )
        legacy_default_ref = store.put_bytes(legacy_default_bytes, legacy_default_options)
        assert legacy_default_ref.manifest_profile_sha256 is None
        from polisyos.ir.model_layer.canon import CanonViolation

        legacy_options = replace(
            _candidate_simulation_write_options(
                kind="ir.ncm_spec",
                schema_name="ir.ncm_spec",
                schema_version="1.0",
                job_id=job_id,
                run_id=run_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
                source_ref=declaration.profile_content_hash,
                input_refs=(
                    input_ref_from_artifact_ref(
                        declaration_ref,
                        role="candidate_model_declaration",
                    ),
                ),
            ),
            canon=None,
        )
        legacy_ref = store.put_bytes(spec_bytes, legacy_options)
        with pytest.raises(CanonViolation, match="unsupported_ir_canon_profile"):
            load_ncm_spec_selected_view(
                _ensure_ir_artifact_store(store),
                legacy_ref,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
                expected_declaration_ref=declaration_ref,
            )

        loaded = load_ncm_spec_selected_view(
            _ensure_ir_artifact_store(store),
            selected_ref,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
            expected_declaration_ref=declaration_ref,
        )
        assert loaded.model_dump(mode="json") == spec.model_dump(mode="json")
        read_only_reader = _ReadOnlySelectedView(CoreToIRArtifactStoreAdapter(store))
        assert not hasattr(read_only_reader, "put_bytes")
        loaded_from_read_only = load_ncm_spec_selected_view(
            read_only_reader,
            selected_ref,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
            expected_declaration_ref=declaration_ref,
        )
        assert loaded_from_read_only.model_dump(mode="json") == spec.model_dump(mode="json")
        loaded_default_view = load_ncm_spec_selected_view(
            _ensure_ir_artifact_store(store),
            default_view_ref,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
            expected_declaration_ref=alternate_ref,
        )
        assert loaded_default_view.model_dump(mode="json") == default_view_spec.model_dump(
            mode="json"
        )
        loaded_legacy_default_view = load_ncm_spec_selected_view(
            _ensure_ir_artifact_store(store),
            legacy_default_ref,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
            expected_declaration_ref=alternate_ref,
        )
        assert loaded_legacy_default_view.model_dump(mode="json") == default_view_spec.model_dump(
            mode="json"
        )

        with pytest.raises(ValueError, match="declaration_lineage_mismatch"):
            load_ncm_spec_selected_view(
                _ensure_ir_artifact_store(store),
                selected_ref,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
                expected_declaration_ref=alternate_ref,
            )

        stripped_selector = selected_ref.model_copy(update={"manifest_profile_sha256": None})
        with pytest.raises(ValueError, match="ncm_selected_view_manifest_mismatch"):
            load_ncm_spec_selected_view(
                _ensure_ir_artifact_store(store),
                stripped_selector,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
                expected_declaration_ref=declaration_ref,
            )


def _assert_complete_native_selected_values(prepared: object, actual: object) -> None:
    """Compare every consumed typed field, preserving native float distinctions."""
    import struct
    from enum import Enum

    from pydantic import BaseModel

    assert type(prepared) is type(actual)
    if isinstance(actual, Enum):
        _assert_complete_native_selected_values(prepared.value, actual.value)
    elif isinstance(actual, BaseModel):
        for name in type(actual).model_fields:
            _assert_complete_native_selected_values(getattr(prepared, name), getattr(actual, name))
    elif isinstance(actual, dict):
        assert prepared.keys() == actual.keys()
        for key in actual:
            _assert_complete_native_selected_values(prepared[key], actual[key])
    elif isinstance(actual, tuple | list):
        assert len(prepared) == len(actual)
        for one, other in zip(prepared, actual, strict=True):
            _assert_complete_native_selected_values(one, other)
    elif type(actual) is float:
        assert struct.pack("!d", prepared) == struct.pack("!d", actual)
    else:
        assert actual is None or type(actual) in {str, int, bool, bytes}
        assert prepared == actual


@pytest.mark.parametrize("baseline", [0.0, -0.0])
def test_selected_ncm_preparation_matches_actual_persisted_codec_bytes(tmp_path, baseline) -> None:
    from polisyos.ir.analytics.ncm import (
        candidate_ncm_spec_from_declaration,
        load_ncm_spec_selected_view,
        prepare_ncm_spec_selected_values,
    )

    store = FileSystemCAS(tmp_path / "selected-codec-cas")
    repository = GenerationSourceRepository(store)
    values = _declaration(coefficient=0.5).model_dump(mode="python", exclude={"content_hash"})
    values.update(target_baseline=baseline, outcome_baseline=baseline)
    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {**values, "content_hash": gy_content_hash(values)}
    )
    spec = candidate_ncm_spec_from_declaration(declaration)
    prepared = prepare_ncm_spec_selected_values(spec)
    with tenant_scope(None, tenant_id="tenant-codec", cell_id="cell-codec"):
        declaration_ref = repository.persist_candidate_model_declaration(
            declaration=declaration,
            job_id="job-codec",
            run_id="run-codec",
            tenant_id="tenant-codec",
            cell_id="cell-codec",
        )
        selected = repository.persist_candidate_ncm_selected_view(
            ncm_spec=spec,
            declaration_ref=declaration_ref,
            job_id="job-codec",
            run_id="run-codec",
            tenant_id="tenant-codec",
            cell_id="cell-codec",
            profile_content_hash=declaration.profile_content_hash,
        )
        reader = FileSystemCAS(tmp_path / "selected-codec-cas")
        actual = load_ncm_spec_selected_view(
            _ensure_ir_artifact_store(reader),
            selected,
            expected_tenant_id="tenant-codec",
            expected_cell_id="cell-codec",
            expected_declaration_ref=declaration_ref,
        )
        # Exact real selected bytes are the independent deciding quantity.
        assert prepared.value_bytes == reader.get_bytes(selected)
        assert prepare_ncm_spec_selected_values(actual).value_bytes == prepared.value_bytes
        _assert_complete_native_selected_values(prepared.ncm_spec, actual)
