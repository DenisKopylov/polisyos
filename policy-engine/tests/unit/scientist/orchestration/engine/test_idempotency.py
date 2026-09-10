from __future__ import annotations

import json

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.scientist.nodes.builtins import builtin_nodes as scientist_builtin_nodes
from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EXEC_PLAN_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.builtins import builtin_nodes as engine_builtin_nodes
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeCacheEntry,
    NodeResultCache,
    compute_idempotency_key,
)
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _artifact(store: FileSystemCAS, payload: dict[str, object], *, kind: str = "test.payload"):
    return store.put_json(payload, PutOptions(kind=kind, media_type="application/json"))


def _outcome(run_id: str = "R_test") -> NodeOutcome:
    return NodeOutcome(status="ok", state=ExperimentState(run_id=run_id))


def test_compute_idempotency_key_stable_for_same_inputs(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    exec_plan_ref = _artifact(store, {"value": 1}, kind="foundry.exec_plan")
    data_snapshot_ref = _artifact(store, {"rows": [1, 2]}, kind="fabric.data_snapshot")
    registry_ref = build_default_registry_bundle(store).bundle_ref

    node = RunSimulationNode()
    state = ExperimentState(
        run_id="R_key_stable",
        inputs={
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_ref,
        },
        artifacts_index={ARTIFACT_EXEC_PLAN_REF: exec_plan_ref},
        params={"simulation_method": "foundry.execute"},
    )
    params_a = {"config": {"z": 2, "a": 1}}
    params_b = {"config": {"a": 1, "z": 2}}

    key_a = compute_idempotency_key(node.spec, state, params_a)
    key_b = compute_idempotency_key(node.spec, state, params_b)

    assert key_a == key_b
    assert len(key_a) == 64


def test_compute_idempotency_key_changes_on_artifact_change(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    exec_plan_a = _artifact(store, {"value": 1}, kind="foundry.exec_plan")
    exec_plan_b = _artifact(store, {"value": 2}, kind="foundry.exec_plan")
    data_snapshot_ref = _artifact(store, {"rows": [1, 2]}, kind="fabric.data_snapshot")
    registry_ref = build_default_registry_bundle(store).bundle_ref

    node = RunSimulationNode()
    state_a = ExperimentState(
        run_id="R_key_change",
        inputs={
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_ref,
        },
        artifacts_index={ARTIFACT_EXEC_PLAN_REF: exec_plan_a},
        params={"simulation_method": "foundry.execute"},
    )
    state_b = state_a.model_copy(deep=True)
    state_b.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = exec_plan_b

    assert compute_idempotency_key(node.spec, state_a) != compute_idempotency_key(
        node.spec,
        state_b,
    )


def test_compute_idempotency_key_available_for_all_builtin_nodes(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    state = ExperimentState(
        run_id="R_all_nodes",
        inputs={INPUT_REGISTRY_BUNDLE_REF: registry_ref},
        params={"simulation_method": "foundry.execute"},
    )
    nodes = [*engine_builtin_nodes(), *scientist_builtin_nodes()]

    for node in nodes:
        key = compute_idempotency_key(node.spec, state, {})
        assert len(key) == 64


def test_node_result_cache_roundtrip(tmp_path) -> None:
    cache = NodeResultCache(FileSystemCAS(tmp_path), run_id="R_cache_roundtrip")
    key = "a" * 64
    expected = _outcome("R_cache_roundtrip")

    entry_ref = cache.put(key, node_id="scientist.node_test@1.0.0", outcome=expected)
    actual = cache.get(key)

    assert entry_ref.kind == "scientist.node_cache_entry"
    assert actual is not None
    assert actual.model_dump(mode="python") == expected.model_dump(mode="python")


def test_node_result_cache_corrupted_entry_is_treated_as_miss(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    cache = NodeResultCache(store, run_id="R_corrupt")
    key = "b" * 64
    entry_ref = cache.put(
        key,
        node_id="scientist.node_test@1.0.0",
        outcome=_outcome("R_corrupt"),
    )
    entry_payload = NodeCacheEntry.model_validate(
        from_canonical_bytes(store.get_bytes(entry_ref.artifact_id))
    )
    outcome_blob, _ = store._paths(entry_payload.outcome_ref.artifact_id)
    outcome_blob.write_bytes(b"not canonical json")

    assert cache.get(key) is None
    assert not cache.has(key)


def test_node_result_cache_seed_from_trace(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    key = "c" * 64
    cache_a = NodeResultCache(store, run_id="R_seed")
    entry_ref = cache_a.put(key, node_id="scientist.node_test@1.0.0", outcome=_outcome("R_seed"))

    trace_path = tmp_path / "runs" / "R_seed" / "trace.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "NODE_CACHE_STORE",
                        "refs": {"outputs": [entry_ref.model_dump(mode="json")]},
                    }
                ),
                json.dumps({"event": "NODE_OK", "refs": {"outputs": []}}),
            ]
        ),
        encoding="utf-8",
    )

    cache_b = NodeResultCache(store, run_id="R_seed")
    restored = cache_b.seed_from_trace(trace_path)
    loaded = cache_b.get(key)

    assert restored == 1
    assert loaded is not None
    assert loaded.state.run_id == "R_seed"


def test_node_result_cache_seed_ignores_other_runs(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    key = "d" * 64
    cache = NodeResultCache(store, run_id="R_other")
    entry_ref = cache.put(key, node_id="scientist.node_test@1.0.0", outcome=_outcome("R_other"))
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        json.dumps(
            {
                "event": "NODE_CACHE_STORE",
                "refs": {"outputs": [entry_ref.model_dump(mode="json")]},
            }
        ),
        encoding="utf-8",
    )

    miss_cache = NodeResultCache(store, run_id="R_miss")
    assert miss_cache.seed_from_trace(trace_path) == 0


def test_output_aware_cache_preserves_complete_outcome(tmp_path) -> None:
    from polisyos.scientist.orchestration.engine import OutputAwareNodeOutcome
    from tests.unit.scientist.orchestration.engine.runner.test_serialization import (
        _output_aware_transport_outcome,
    )

    store = FileSystemCAS(tmp_path)
    outcome = _output_aware_transport_outcome(store)
    cache = NodeResultCache(store, run_id=outcome.state.run_id)
    key = "e" * 64
    entry_ref = cache.put(key, node_id="scientist.node_transport@2.0.0", outcome=outcome)
    restored = cache.get(key)
    assert type(restored) is OutputAwareNodeOutcome
    assert restored.model_dump(mode="json") == outcome.model_dump(mode="json")
    entry = NodeCacheEntry.model_validate(
        from_canonical_bytes(store.get_bytes(entry_ref.artifact_id))
    )
    manifest = store.get_manifest(entry.outcome_ref.artifact_id)
    assert (
        manifest.artifact_schema.name
        == "polisyos.scientist.orchestration.engine.OutputAwareNodeOutcome"
    )
    assert manifest.artifact_schema.version == "1.0"
    assert manifest.producer.version == "2.0.0"
    assert store.get_manifest(entry_ref.artifact_id).producer.version == "2.0.0"


def test_ordinary_cache_keeps_existing_schema_epoch(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    outcome = _outcome()
    cache = NodeResultCache(store, run_id=outcome.state.run_id)
    entry_ref = cache.put("f" * 64, node_id="scientist.node_test@1.0.0", outcome=outcome)
    entry = NodeCacheEntry.model_validate(
        from_canonical_bytes(store.get_bytes(entry_ref.artifact_id))
    )
    manifest = store.get_manifest(entry.outcome_ref.artifact_id)
    assert manifest.artifact_schema.name == "polisyos.scientist.orchestration.engine.NodeOutcome"
    assert manifest.artifact_schema.version == "1.0"
    assert manifest.producer.version == "1.0.0"
    assert store.get_manifest(entry_ref.artifact_id).producer.version == "1.0.0"


def _base_epoch_output_aware_cache_entry(store, outcome, key):
    """Seed the unchanged predecessor writer's exact payload/schema combination."""
    from polisyos.core.artifacts import ProducerInfo, SchemaInfo
    from polisyos.core.canon import CanonSpec

    ref = store.put_json(
        outcome.model_dump(mode="python", by_alias=True, exclude_none=False),
        PutOptions(
            kind="scientist.node_outcome",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.NodeOutcome", version="1.0"
            ),
            producer=ProducerInfo(component="scientist.engine.idempotency", version="1.0.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    entry = NodeCacheEntry(
        run_id=outcome.state.run_id,
        node_id="scientist.node_transport@2.0.0",
        idempotency_key=key,
        outcome_ref=ref,
    )
    return store.put_json(
        entry.model_dump(mode="python", by_alias=True, exclude_none=False),
        PutOptions(
            kind="scientist.node_cache_entry",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.NodeCacheEntry", version="1.0"
            ),
            producer=ProducerInfo(component="scientist.engine.idempotency", version="1.0.0"),
        ),
    )


def test_output_aware_cache_refuses_existing_base_epoch_manifest(tmp_path) -> None:
    import pytest

    from tests.unit.scientist.orchestration.engine.runner.test_serialization import (
        _output_aware_transport_outcome,
    )

    store = FileSystemCAS(tmp_path)
    outcome = _output_aware_transport_outcome(store)
    cache = NodeResultCache(store, run_id=outcome.state.run_id)
    key = "a" * 64
    _base_epoch_output_aware_cache_entry(store, outcome, key)
    with pytest.raises(ValueError, match="output_aware_cache_custody"):
        cache.put(key, node_id="scientist.node_transport@2.0.0", outcome=outcome)
    assert not cache.has(key)


def test_output_aware_cache_refuses_loading_base_epoch_entry(tmp_path) -> None:
    import pytest

    from tests.unit.scientist.orchestration.engine.runner.test_serialization import (
        _output_aware_transport_outcome,
    )

    store = FileSystemCAS(tmp_path)
    outcome = _output_aware_transport_outcome(store)
    cache = NodeResultCache(store, run_id=outcome.state.run_id)
    key = "b" * 64
    entry_ref = _base_epoch_output_aware_cache_entry(store, outcome, key)
    with pytest.raises(ValueError, match="output_aware_cache_custody"):
        cache.load_entry(entry_ref)
    assert not cache.has(key)


def test_output_aware_cache_refuses_old_entry_even_with_current_outcome(tmp_path) -> None:
    import pytest

    from tests.unit.scientist.orchestration.engine.runner.test_serialization import (
        _output_aware_transport_outcome,
    )

    store = FileSystemCAS(tmp_path)
    outcome = _output_aware_transport_outcome(store)
    cache = NodeResultCache(store, run_id=outcome.state.run_id)
    cache.put("c" * 64, node_id="scientist.node_transport@2.0.0", outcome=outcome)
    key = "d" * 64
    # The predecessor reuses the already-current outcome bytes, but emits its
    # separate entry under the old epoch. Both actual manifests must be checked.
    entry_ref = _base_epoch_output_aware_cache_entry(store, outcome, key)
    entry = NodeCacheEntry.model_validate(
        from_canonical_bytes(store.get_bytes(entry_ref.artifact_id))
    )
    assert store.get_manifest(entry.outcome_ref.artifact_id).producer.version == "2.0.0"
    assert store.get_manifest(entry_ref.artifact_id).producer.version == "1.0.0"
    with pytest.raises(ValueError, match="output_aware_cache_custody"):
        cache.load_entry(entry_ref)
    assert not cache.has(key)
