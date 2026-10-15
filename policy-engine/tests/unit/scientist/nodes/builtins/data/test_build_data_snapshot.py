from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    CanonInfo,
    PutOptions,
    SchemaInfo,
    artifact_manifest_profile_sha256,
    artifact_ref_identity_key,
)
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.scientist.nodes.builtins.data.build_data_snapshot import (
    BuildDataSnapshotNode,
    _read_snapshot_pii_summary,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_DATA_VIEW_REQUEST_REF,
)
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state as real_branch_state,
)


def test_snapshot_via_fabric_mock(execution_context, minimal_state, artifact_ref_factory):
    """With fabric port and data_view_request_ref, builds a snapshot."""
    view_ref = artifact_ref_factory(kind="ir.data_view_request")
    snapshot_ref = _put_snapshot(execution_context.store)

    mock_fabric = MagicMock()
    mock_fabric.snapshot.return_value = snapshot_ref
    ctx = replace(execution_context, fabric=mock_fabric)

    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_DATA_VIEW_REQUEST_REF] = view_ref

    outcome = BuildDataSnapshotNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert INPUT_DATA_SNAPSHOT_REF in outcome.state.inputs
    assert artifact_ref_identity_key(outcome.state.inputs[INPUT_DATA_SNAPSHOT_REF]) == (
        artifact_ref_identity_key(snapshot_ref)
    )
    selected_request = mock_fabric.snapshot.call_args.args[1]
    assert selected_request.manifest_profile_sha256 == artifact_manifest_profile_sha256(
        execution_context.store.get_manifest(view_ref)
    )
    assert artifact_ref_identity_key(
        outcome.state.inputs[INPUT_DATA_VIEW_REQUEST_REF]
    ) == artifact_ref_identity_key(selected_request)
    mock_fabric.snapshot.assert_called_once_with(execution_context.store, selected_request)


def test_no_fabric_port(execution_context, minimal_state):
    """Without fabric port and no existing snapshot, node fails."""
    outcome = BuildDataSnapshotNode().execute(execution_context, minimal_state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.missing_input"


def test_snapshot_already_exists(execution_context, minimal_state, artifact_ref_factory):
    """When data_snapshot_ref is already in inputs, no-op."""
    snapshot_ref = artifact_ref_factory(kind="fabric.data_snapshot")
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_DATA_SNAPSHOT_REF] = snapshot_ref
    outcome = BuildDataSnapshotNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert outcome.state is state


def test_snapshot_pii_summary_load_failure_fails_node(
    execution_context,
    minimal_state,
    artifact_ref_factory,
):
    view_ref = artifact_ref_factory(kind="ir.data_view_request")
    snapshot_ref = artifact_ref_factory(kind="fabric.data_snapshot")

    mock_fabric = MagicMock()
    mock_fabric.snapshot.return_value = snapshot_ref
    ctx = replace(execution_context, fabric=mock_fabric, metrics=None)

    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_DATA_VIEW_REQUEST_REF] = view_ref

    with (
        patch.object(
            execution_context.store,
            "get_bytes",
            side_effect=RuntimeError("snapshot read failed"),
        ),
    ):
        outcome = BuildDataSnapshotNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.invalid_state"
    assert "pii_scan_results" not in outcome.state.params


def test_snapshot_builder_uses_branch_state_for_declared_outputs(
    execution_context, minimal_state, artifact_ref_factory
):
    view_ref = artifact_ref_factory(kind="ir.data_view_request")
    snapshot_ref = artifact_ref_factory(kind="fabric.data_snapshot")

    mock_fabric = MagicMock()
    mock_fabric.snapshot.return_value = snapshot_ref
    ctx = replace(execution_context, fabric=mock_fabric)

    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_DATA_VIEW_REQUEST_REF] = view_ref
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.data.build_data_snapshot.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.data.build_data_snapshot._read_snapshot_pii_summary",
            return_value={"max_severity": "none", "total_entities_found": 0},
        ),
    ):
        outcome = BuildDataSnapshotNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "inputs.data_snapshot_ref",
        "inputs.data_view_request_ref",
        "params.pii_scan_results",
    )
    assert state.params["nested"] == {"baseline": True}
    assert INPUT_DATA_SNAPSHOT_REF not in state.inputs
    assert artifact_ref_identity_key(outcome.state.inputs[INPUT_DATA_SNAPSHOT_REF]) == (
        artifact_ref_identity_key(snapshot_ref)
    )
    assert outcome.state.params["pii_scan_results"]["max_severity"] == "none"


def _put_snapshot(store) -> DataSnapshotRef:
    data_ref = store.put_json(
        {"rows": []},
        PutOptions(kind="fabric.tabular_payload", media_type="application/json"),
    )
    selected_ref = store.put_json(
        DataSnapshot(
            data_ref=data_ref,
            pii_scan_summary={"max_severity": "none", "total_entities_found": 0},
        ),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
    return DataSnapshotRef.model_validate(selected_ref.model_dump(mode="json"))


def test_pii_summary_reader_refuses_same_snapshot_bytes_under_wrong_schema(
    execution_context,
) -> None:
    store = execution_context.store
    data_ref = store.put_json(
        {"rows": []},
        PutOptions(kind="fabric.tabular_payload", media_type="application/json"),
    )
    snapshot = DataSnapshot(
        data_ref=data_ref,
        pii_scan_summary={"max_severity": "none", "total_entities_found": 0},
    )
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    selected_ref = store.put_bytes(
        to_canonical_bytes(snapshot, spec),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name="polisyos.test.DataSnapshot", version="9.9"),
            canon=CanonInfo.from_spec(spec),
        ),
        return_selected_profile=True,
    )
    typed_ref = DataSnapshotRef.model_validate(selected_ref.model_dump(mode="json"))

    with pytest.raises(
        CanonicalProfileRefusalError,
        match="canon_profile_typed_artifact_schema_name_mismatch",
    ):
        _read_snapshot_pii_summary(execution_context, typed_ref)
