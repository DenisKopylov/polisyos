from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

from polisyos.scientist.nodes.builtins.data.build_data_snapshot import BuildDataSnapshotNode
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_DATA_VIEW_REQUEST_REF,
)


def test_snapshot_via_fabric_mock(execution_context, minimal_state, artifact_ref_factory):
    """With fabric port and data_view_request_ref, builds a snapshot."""
    view_ref = artifact_ref_factory(kind="ir.data_view_request")
    snapshot_ref = artifact_ref_factory(kind="fabric.data_snapshot")

    mock_fabric = MagicMock()
    mock_fabric.snapshot.return_value = snapshot_ref
    ctx = replace(execution_context, fabric=mock_fabric)

    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_DATA_VIEW_REQUEST_REF] = view_ref

    outcome = BuildDataSnapshotNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert INPUT_DATA_SNAPSHOT_REF in outcome.state.inputs
    assert outcome.state.inputs[INPUT_DATA_SNAPSHOT_REF] == snapshot_ref
    mock_fabric.snapshot.assert_called_once()


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
