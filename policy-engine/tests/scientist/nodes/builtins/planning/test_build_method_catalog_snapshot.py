from __future__ import annotations

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
