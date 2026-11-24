"""Typed derived snapshots replay complete candidate values without authority."""

from __future__ import annotations

import copy
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core import artifacts, derivations
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import (
    DataSnapshot,
    DerivedModelInputDataSnapshotLineage,
    data_snapshot_owner_input_requirements,
)
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.runtime.quality.data_snapshot_lineage import (
    DERIVED_MODEL_INPUT_LIMITATIONS,
    DataSnapshotLineageError,
    validate_data_snapshot_owner_lineage,
)
from tests._helpers.registered_derived_method_input import materialize_registered_method_input_case
from tests._helpers.selected_method_input import prepare_selected_method_input_case


def _write_snapshot(store, snapshot, *, inputs=None):
    return store.put_json(
        snapshot,
        artifacts.PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=artifacts.SchemaInfo(name=DataSnapshot.ARTIFACT_SCHEMA_NAME, version="0.3.0"),
            inputs=(
                inputs
                if inputs is not None
                else [
                    artifacts.input_ref_from_artifact_ref(ref, role=role)
                    for ref, role in data_snapshot_owner_input_requirements(snapshot)
                ]
            ),
        ),
        return_selected_profile=True,
    )


def test_derived_snapshot_replays_values_preserves_candidate_limits_and_refuses_grafts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real native rows and certified outputs define the entire copied payload."""
    case, metadata = prepare_selected_method_input_case(
        tmp_path / "method", method_class=PeriodFlowToStock
    )
    try:
        materialize_registered_method_input_case(case, metadata)
        batch = metadata["batch_materialization"]
        snapshot = artifacts.validate_core_model_json_artifact(
            DataSnapshot, case.store, batch.data_snapshot_ref
        )
        assert isinstance(snapshot.source_lineage, DerivedModelInputDataSnapshotLineage)
        reader = artifacts.FileSystemCAS.open_existing_read_only(case.store.root)
        selection = snapshot.source_lineage.selections[0]
        recipe = derivations.CompositionRecipe.model_validate(
            artifacts.load_core_json_artifact(reader, selection.recipe_ref)
        )
        actual_reopen = derivations._reopen_composition_recipe
        reopened = []

        def observe_reopen(store, selected_recipe, replay):
            reopened.append(selected_recipe.recipe_id)
            return actual_reopen(store, selected_recipe, replay)

        with monkeypatch.context() as observed:
            observed.setattr(derivations, "_reopen_composition_recipe", observe_reopen)
            result = validate_data_snapshot_owner_lineage(
                reader, batch.data_snapshot_ref, snapshot, candidate_only=True
            )
        assert reopened == [recipe.recipe_id]
        assert set(DERIVED_MODEL_INPUT_LIMITATIONS) <= set(result.required_admissibility_blockers)
        assert result.acquisition_source_row_status == "not_applicable"
        with pytest.raises(DataSnapshotLineageError, match="derived_model_input_candidate_only"):
            validate_data_snapshot_owner_lineage(reader, batch.data_snapshot_ref, snapshot)

        actual_inputs = case.store.get_manifest(batch.data_snapshot_ref).inputs
        missing_edge_ref = _write_snapshot(case.store, snapshot, inputs=actual_inputs[:-1])
        with pytest.raises(DataSnapshotLineageError, match="parent_inputs_mismatch"):
            validate_data_snapshot_owner_lineage(
                case.store, missing_edge_ref, snapshot, candidate_only=True
            )

        payload = artifacts.load_core_json_artifact(case.store, snapshot.data_ref)
        selected_key = selection.source_path.split(".")[1]
        changed = copy.deepcopy(payload)
        changed["derived_inputs"][selected_key]["value"] += Decimal("1")
        payload_manifest = case.store.get_manifest(snapshot.data_ref)
        changed_ref = case.store.put_json(
            changed,
            artifacts.PutOptions(
                kind=snapshot.data_ref.kind,
                media_type=snapshot.data_ref.media_type,
                schema=payload_manifest.artifact_schema,
                inputs=payload_manifest.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        changed_snapshot = snapshot.model_copy(update={"data_ref": changed_ref})
        changed_snapshot_ref = _write_snapshot(case.store, changed_snapshot)
        with pytest.raises(DataSnapshotLineageError, match="payload_replay_mismatch"):
            validate_data_snapshot_owner_lineage(
                case.store, changed_snapshot_ref, changed_snapshot, candidate_only=True
            )

        stripped = snapshot.model_copy(update={"source_lineage": None})
        stripped_ref = case.store.put_json(
            stripped,
            artifacts.PutOptions(
                kind=DataSnapshot.ARTIFACT_KIND,
                media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
                schema=artifacts.SchemaInfo(
                    name=DataSnapshot.ARTIFACT_SCHEMA_NAME, version="0.2.0"
                ),
                inputs=[artifacts.input_ref_from_artifact_ref(snapshot.data_ref, role="data_ref")],
            ),
            return_selected_profile=True,
        )
        with pytest.raises(DataSnapshotLineageError, match="derived_model_input_lineage_missing"):
            validate_data_snapshot_owner_lineage(
                case.store, stripped_ref, stripped, candidate_only=True
            )

        actual_get = case.store.get_bytes

        def removed_certificate(ref):
            if isinstance(ref, artifacts.ArtifactRef) and artifacts.artifact_ref_identity_key(
                ref
            ) == artifacts.artifact_ref_identity_key(selection.certificate_ref):
                raise FileNotFoundError("test removed the selected arithmetic certificate")
            return actual_get(ref)

        with monkeypatch.context() as control:
            control.setattr(case.store, "get_bytes", removed_certificate)
            with pytest.raises((DataSnapshotLineageError, FileNotFoundError)):
                validate_data_snapshot_owner_lineage(
                    case.store, batch.data_snapshot_ref, snapshot, candidate_only=True
                )
    finally:
        case.close()


def test_registered_graph_snapshot_replays_only_selected_root_and_requires_ancestor_recipe(
    tmp_path: Path,
) -> None:
    """A fresh snapshot reader checks the root input and its exact ancestry."""
    from polisyos.core.contracts.semantic_composition_binding import (
        load_registered_derived_graph_correspondence,
    )
    from polisyos.runtime.quality.model_input_routing import (
        materialize_registered_derived_model_inputs,
    )
    from tests.unit.foundry.data_plane.test_registered_derivation_graph import _native_collection
    from tests.unit.foundry.data_plane.test_selected_method_input_bindings import _removed_blob
    from tests.unit.runtime.quality.test_n7_registered_derivation_plan import (
        prepare_selected_plan_case,
    )

    setup = prepare_selected_plan_case(
        tmp_path / "root", role_populations={"denominator": "public-health-expenditure"}
    )
    case = setup["case"]
    try:
        request = _native_collection(tmp_path, setup, foreign_scope=False, reverse=False)
        batch = materialize_registered_derived_model_inputs(
            case.store,
            base_data_snapshot_ref=case.data_snapshot_ref,
            obligation_set_ref=setup["obligation_set_ref"],
            inputs=(request,),
        )
        reader = artifacts.FileSystemCAS.open_existing_read_only(case.store.root)
        snapshot = artifacts.validate_core_model_json_artifact(
            DataSnapshot, reader, batch.data_snapshot_ref
        )
        assert isinstance(snapshot.source_lineage, DerivedModelInputDataSnapshotLineage)
        (selection,) = snapshot.source_lineage.selections
        proof = load_registered_derived_graph_correspondence(reader, selection.correspondence_ref)
        intermediate, root = proof.operations
        assert proof.root == root and intermediate.node_id == "derived-b"
        payload = artifacts.load_core_json_artifact(reader, snapshot.data_ref)
        assert payload["derived_inputs"] == {
            selection.source_path.split(".")[1]: {"value": Decimal("-2500000000")}
        }

        def replay():
            fresh = artifacts.FileSystemCAS.open_existing_read_only(case.store.root)
            return validate_data_snapshot_owner_lineage(
                fresh, batch.data_snapshot_ref, snapshot, candidate_only=True
            )

        result = replay()
        assert set(DERIVED_MODEL_INPUT_LIMITATIONS) <= set(result.required_admissibility_blockers)
        assert result.acquisition_source_row_status == "not_applicable"
        with (
            _removed_blob(case.store, intermediate.recipe_ref),
            pytest.raises(
                DataSnapshotLineageError, match=r"^derived_model_input_owner_replay_failed$"
            ) as refused,
        ):
            replay()
        cause = refused.value.__cause__
        assert isinstance(cause, derivations.DerivationRefusalError)
        assert cause.code is derivations.DerivationRefusalCode.INPUT_ARTIFACT_DRIFT
        assert cause.detail == "composition recipe artifact readback failed"
        assert replay() == result
    finally:
        case.close()
