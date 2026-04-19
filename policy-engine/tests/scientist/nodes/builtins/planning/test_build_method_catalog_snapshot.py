from __future__ import annotations

from unittest.mock import patch

from polisyos.scientist.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins.planning.build_method_catalog_snapshot import (
    BuildMethodCatalogSnapshotNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF,
    ARTIFACT_METHOD_CATALOG_SNAPSHOT_REF,
)


def test_snapshot_creation(execution_context, minimal_state):
    outcome = BuildMethodCatalogSnapshotNode().execute(execution_context, minimal_state)
    assert outcome.status == "ok"
    assert ARTIFACT_METHOD_CATALOG_SNAPSHOT_REF in outcome.state.artifacts_index
    assert ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF in outcome.state.artifacts_index
    assert outcome.state.params.get("method_catalog_snapshot_ref") is not None
    assert outcome.state.params.get("causal_capability_hash") is not None
    assert len(outcome.artifacts) == 2


def test_snapshot_has_events(execution_context, minimal_state):
    outcome = BuildMethodCatalogSnapshotNode().execute(execution_context, minimal_state)
    assert outcome.status == "ok"
    assert len(outcome.events) >= 1
    assert any("catalog" in e.message.lower() for e in outcome.events)


def test_snapshot_refs_stored_on_state(execution_context, minimal_state):
    outcome = BuildMethodCatalogSnapshotNode().execute(execution_context, minimal_state)
    assert outcome.status == "ok"
    assert outcome.state.method_catalog_snapshot_ref is not None
    assert outcome.state.causal_capability_contract_ref is not None


def test_method_catalog_snapshot_uses_branch_state_for_declared_outputs(
    execution_context, minimal_state
):
    state = minimal_state.model_copy(deep=True)
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with patch(
        "polisyos.scientist.nodes.builtins.planning.build_method_catalog_snapshot.branch_state",
        _spy_branch,
    ):
        outcome = BuildMethodCatalogSnapshotNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "method_catalog_snapshot_ref",
        "causal_capability_contract_ref",
        "params.method_catalog_snapshot_ref",
        "params.causal_capability_hash",
        "artifacts_index.method_catalog_snapshot_ref",
        "artifacts_index.causal_capability_contract_ref",
    )
    assert state.params["nested"] == {"baseline": True}
    assert state.method_catalog_snapshot_ref is None
    assert state.causal_capability_contract_ref is None
    assert outcome.state.method_catalog_snapshot_ref is not None
    assert outcome.state.causal_capability_contract_ref is not None
