from __future__ import annotations

import pytest

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
        assert default_view_ref.manifest_profile_sha256 is None
        selected_manifest = store.get_manifest(selected_ref)
        assert selected_manifest.canon is not None
        assert selected_manifest.canon.forbid_floats is False
        assert selected_manifest.canon.exclude_none is False
        loaded = load_ncm_spec_selected_view(
            store,
            selected_ref,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
            expected_declaration_ref=declaration_ref,
        )
        assert loaded.model_dump(mode="json") == spec.model_dump(mode="json")
        loaded_default_view = load_ncm_spec_selected_view(
            store,
            default_view_ref,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
            expected_declaration_ref=alternate_ref,
        )
        assert loaded_default_view.model_dump(mode="json") == default_view_spec.model_dump(
            mode="json"
        )

        with pytest.raises(ValueError, match="declaration_lineage_mismatch"):
            load_ncm_spec_selected_view(
                store,
                selected_ref,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
                expected_declaration_ref=alternate_ref,
            )

        stripped_selector = selected_ref.model_copy(update={"manifest_profile_sha256": None})
        with pytest.raises(ValueError, match="ncm_selected_view_manifest_mismatch"):
            load_ncm_spec_selected_view(
                store,
                stripped_selector,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
                expected_declaration_ref=declaration_ref,
            )
