"""Candidate comparisons retain actual selected artifact views and owner values.

This is an owner component control; it does not execute N5 or authorize a
candidate route or terminal.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    FileSystemCAS,
    ProducerInfo,
    artifact_ref_identity_key,
)
from polisyos.core.contracts.foundry import StateSnapshotRef
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.data_plane import load_input_bindings
from polisyos.foundry.execute import put_state_snapshot
from polisyos.runtime.quality.acquisition_evaluation import (
    _candidate_model_values_same,
    _candidate_ref_same,
)
from polisyos.runtime.quality.candidate_source_basis import prepare_candidate_source_basis_values
from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes
from polisyos.runtime.quality.world_model_record import world_model_artifact_views
from tests.unit.runtime.quality.test_candidate_acquisition_world import CELL_ID, TENANT_ID
from tests.unit.runtime.quality.test_candidate_source_basis import (
    _case_with_explicit_empty_prior,
    _inputs,
)


class _AdditionalMeaningSnapshotRef(StateSnapshotRef):
    custody_note: str


def _foreign_view(store: FileSystemCAS, ref: ArtifactRef) -> ArtifactRef:
    manifest = store.get_manifest(ref)
    return store.put_bytes(
        store.get_bytes(ref),
        ArtifactWriteOptions(
            kind=ref.kind,
            media_type=ref.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            inputs=manifest.inputs,
            governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            producer=ProducerInfo(component="test.foreign-state-owner", version="1"),
        ),
        return_selected_profile=True,
    )


def test_candidate_reference_comparison_replays_actual_snapshot_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _case_with_explicit_empty_prior(tmp_path, monkeypatch)
        inputs = _inputs(case)
        profile = inputs.configured_profile
        context = profile.context_inputs
        world = context.world_model_record
        views = world_model_artifact_views(world)
        bindings = load_input_bindings(case.store, views.input_bindings_ref)
        produced_state = bindings.bound_state_snapshot_ref
        assert type(produced_state) is StateSnapshotRef
        assert type(views.bound_state_snapshot_ref) is ArtifactRef
        assert artifact_ref_identity_key(produced_state) == artifact_ref_identity_key(
            views.bound_state_snapshot_ref
        )
        assert case.store.verify(produced_state).ok
        assert _candidate_ref_same(produced_state, views.bound_state_snapshot_ref)

        # The WMR owner normalizes this same producer-issued ref to ArtifactRef.
        # Restore the typed producer view inside the same complete input, not a
        # different model, and compare both actual candidate preparations.
        assert world.artifact_views is not None
        typed_views = world.artifact_views.model_copy(
            update={"bound_state_snapshot_ref": produced_state}
        )
        typed_world = world.model_copy(update={"artifact_views": typed_views})
        typed_context = context.model_copy(update={"world_model_record": typed_world})
        typed_profile = profile.model_copy(update={"context_inputs": typed_context})
        typed_inputs = inputs.model_copy(update={"configured_profile": typed_profile})
        assert _candidate_model_values_same(inputs, typed_inputs)
        plain_result = prepare_candidate_source_basis_values(
            store=case.store, problem=case.problem, inputs=inputs
        )
        typed_result = prepare_candidate_source_basis_values(
            store=case.store, problem=case.problem, inputs=typed_inputs
        )
        assert (
            plain_result.predicate_provenance == typed_result.predicate_provenance == "recomputed"
        )
        assert exact_n5_content_bytes(plain_result.effective_values) == exact_n5_content_bytes(
            typed_result.effective_values
        )

        foreign = _foreign_view(case.store, produced_state)
        assert foreign.artifact_id == produced_state.artifact_id
        assert artifact_ref_identity_key(foreign) != artifact_ref_identity_key(produced_state)
        foreign_views = world.artifact_views.model_copy(
            update={"bound_state_snapshot_ref": foreign}
        )
        foreign_world = world.model_copy(update={"artifact_views": foreign_views})
        foreign_context = context.model_copy(update={"world_model_record": foreign_world})
        foreign_profile = profile.model_copy(update={"context_inputs": foreign_context})
        foreign_inputs = inputs.model_copy(update={"configured_profile": foreign_profile})
        assert not _candidate_model_values_same(inputs, foreign_inputs)
        refused = prepare_candidate_source_basis_values(
            store=case.store, problem=case.problem, inputs=foreign_inputs
        )
        assert refused.predicate_provenance == "not_established"
        assert refused.reason_codes

        # A distinct newly selected snapshot verifies the non-null-profile
        # branch against a same-bytes foreign manifest as well.
        selected = put_state_snapshot(
            case.store,
            state={"controlled.slot": np.array([0.5], dtype=np.float64)},
            return_selected_profile=True,
        )
        assert type(selected) is StateSnapshotRef
        assert selected.manifest_profile_sha256 is not None
        same_view = ArtifactRef.model_validate(selected.model_dump(mode="python"))
        sibling = _foreign_view(case.store, selected)
        assert sibling.artifact_id == selected.artifact_id
        assert sibling.manifest_profile_sha256 != selected.manifest_profile_sha256
        assert _candidate_ref_same(selected, same_view)
        assert not _candidate_ref_same(selected, sibling)
        assert not _candidate_ref_same(
            selected, same_view.model_copy(update={"kind": "other.kind"})
        )
        assert not _candidate_ref_same(
            selected, same_view.model_copy(update={"media_type": "application/octet-stream"})
        )
        extended = _AdditionalMeaningSnapshotRef.model_validate(
            {**selected.model_dump(mode="python"), "custody_note": "new-owner-meaning"}
        )
        assert not _candidate_ref_same(selected, extended)
