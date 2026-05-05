from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock, patch

from polisyos.scientist.engine.state_branching import branch_state as real_branch_state
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


def test_snapshot_pii_summary_load_failure_degrades(
    execution_context,
    minimal_state,
    artifact_ref_factory,
):
    view_ref = artifact_ref_factory(kind="ir.data_view_request")
    snapshot_ref = artifact_ref_factory(kind="fabric.data_snapshot")

    mock_fabric = MagicMock()
    mock_fabric.snapshot.return_value = snapshot_ref
    store = MagicMock()
    store.get_bytes.side_effect = RuntimeError("snapshot read failed")
    ctx = replace(execution_context, fabric=mock_fabric, store=store, metrics=None)

    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_DATA_VIEW_REQUEST_REF] = view_ref

    with patch(
        "polisyos.scientist.nodes.builtins.data.build_data_snapshot.emit_degraded_path",
    ) as degraded:
        outcome = BuildDataSnapshotNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert "pii_scan_results" not in outcome.state.params
    degraded.assert_called_once()


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
        "params.pii_scan_results",
    )
    assert state.params["nested"] == {"baseline": True}
    assert INPUT_DATA_SNAPSHOT_REF not in state.inputs
    assert outcome.state.inputs[INPUT_DATA_SNAPSHOT_REF] == snapshot_ref
    assert outcome.state.params["pii_scan_results"]["max_severity"] == "none"
