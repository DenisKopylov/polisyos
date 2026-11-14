"""Temporal derived snapshots reject one-period proof grafts."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
    validate_core_model_json_artifact,
)
from polisyos.core.contracts import (
    DataSnapshot,
    DataSnapshotOwnerBound,
    DerivedModelInputDataSnapshotLineage,
    data_snapshot_owner_input_requirements,
    load_model_input_obligation_set,
)
from polisyos.core.contracts.fabric import DerivedModelInputStepDataSnapshotLineage
from polisyos.core.contracts.semantic_input_binding import ResolvedDerivedInputAtStep
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.runtime.quality.data_snapshot_lineage import (
    DataSnapshotLineageError,
    validate_data_snapshot_owner_lineage,
)
from tests._helpers.registered_derived_method_input import materialize_registered_method_input_case
from tests._helpers.selected_method_input import prepare_selected_method_input_case


def _persist_snapshot(store: FileSystemCAS, snapshot: DataSnapshotOwnerBound) -> ArtifactRef:
    return store.put_json(
        snapshot,
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshotOwnerBound.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[
                input_ref_from_artifact_ref(ref, role=role)
                for ref, role in data_snapshot_owner_input_requirements(snapshot)
            ],
        ),
        return_selected_profile=True,
    )


def test_temporal_snapshot_rejects_legacy_one_period_proof_graft(tmp_path: Path) -> None:
    """A real one-period certificate cannot be relabeled as a step proof."""
    case, metadata = prepare_selected_method_input_case(
        tmp_path / "method", method_class=PeriodFlowToStock, period_step_profile=True
    )
    try:
        materialize_registered_method_input_case(case, metadata)
        batch = metadata["batch_materialization"]
        original = validate_core_model_json_artifact(
            DataSnapshot, case.store, batch.data_snapshot_ref
        )
        assert isinstance(original.source_lineage, DerivedModelInputDataSnapshotLineage)
        selected_set, _ = load_model_input_obligation_set(
            case.store, original.source_lineage.model_input_obligation_set_ref
        )
        assert selected_set.required_step_scopes is not None
        (step_scope,) = selected_set.required_step_scopes
        (selection,) = original.source_lineage.selections

        lineage = DerivedModelInputStepDataSnapshotLineage(
            base_data_snapshot_ref=original.source_lineage.base_data_snapshot_ref,
            model_input_obligation_set_ref=original.source_lineage.model_input_obligation_set_ref,
            selections=(ResolvedDerivedInputAtStep(step_scope=step_scope, selection=selection),),
        )
        original_payload = load_core_json_artifact(case.store, original.data_ref)
        compact_payload_ref = case.store.put_json(
            {"derived_inputs": original_payload["derived_inputs"]},
            PutOptions(
                kind=original.data_ref.kind,
                media_type=original.data_ref.media_type,
                schema=SchemaInfo(
                    name="polisyos.runtime.quality.DerivedModelInputPayload", version="1.1"
                ),
                inputs=list(case.store.get_manifest(original.data_ref).inputs),
            ),
            return_selected_profile=True,
        )
        temporal_snapshot = DataSnapshotOwnerBound.model_validate(
            original.model_dump(mode="python")
            | {"data_ref": compact_payload_ref, "source_lineage": lineage}
        )
        temporal_snapshot_ref = _persist_snapshot(case.store, temporal_snapshot)

        # The value, output, scope year, and target still match. Its selected
        # correspondence is 2.0, so it has no independently bound step subject.
        with pytest.raises(
            DataSnapshotLineageError,
            match="derived_model_input_temporal_scope_unexpected",
        ):
            validate_data_snapshot_owner_lineage(
                FileSystemCAS.open_existing_read_only(case.store.root),
                temporal_snapshot_ref,
                temporal_snapshot,
                candidate_only=True,
            )
    finally:
        case.close()
