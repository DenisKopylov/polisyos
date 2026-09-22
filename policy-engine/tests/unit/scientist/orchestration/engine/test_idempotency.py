from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
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
    REPLAY_EPOCH,
    NodeCacheEntry,
    NodeResultCache,
    _build_journal_proof,
    compute_idempotency_key,
)
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state


def _artifact(store: FileSystemCAS, payload: dict[str, object], *, kind: str = "test.payload"):
    return store.put_json(payload, PutOptions(kind=kind, media_type="application/json"))


def _outcome(run_id: str = "R_test") -> NodeOutcome:
    state = branch_state(ExperimentState(run_id=run_id), write_paths=()).state
    return NodeOutcome(status="ok", state=state)


def _plain_outcome(run_id: str = "R_test") -> NodeOutcome:
    return NodeOutcome(status="ok", state=ExperimentState(run_id=run_id))


def _with_journal(outcome: NodeOutcome) -> NodeOutcome:
    state = branch_state(outcome.state, write_paths=()).state
    return outcome.model_copy(update={"state": state})


def _rewrite_cache_entry(store: FileSystemCAS, entry_ref, **updates):
    payload = dict(from_canonical_bytes(store.get_bytes(entry_ref.artifact_id)))
    payload.update(updates)
    manifest = store.get_manifest(entry_ref.artifact_id)
    return store.put_json(
        payload,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
        ),
    )


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
    store = FileSystemCAS(tmp_path)
    cache = NodeResultCache(store, run_id="R_cache_roundtrip")
    key = "a" * 64
    expected = _outcome("R_cache_roundtrip")
    ids_before = {str(artifact_id) for artifact_id in store.iter_artifact_ids()}

    entry_ref = cache.put(key, node_id="scientist.node_test@1.0.0", outcome=expected)
    actual = cache.get(key)
    entry = NodeCacheEntry.model_validate(
        from_canonical_bytes(store.get_bytes(entry_ref.artifact_id))
    )

    assert entry_ref.kind == "scientist.node_cache_entry"
    assert getattr(entry, "outcome_ref", None) is None
    assert getattr(entry, "outcome_payload", None) is not None
    assert {str(artifact_id) for artifact_id in store.iter_artifact_ids()} - ids_before == {
        str(entry_ref.artifact_id)
    }
    assert actual is not None
    assert actual.model_dump(mode="python") == expected.model_dump(mode="python")


def test_node_result_cache_failed_publication_has_no_index_or_new_cas_ids(
    tmp_path, monkeypatch
) -> None:
    store = FileSystemCAS(tmp_path)
    cache = NodeResultCache(store, run_id="R_cache_failed_publication")
    key = "p" * 64
    ids_before = {str(artifact_id) for artifact_id in store.iter_artifact_ids()}

    def fail_publication(*args, **kwargs):
        del args, kwargs
        raise OSError("cache entry publication interrupted")

    monkeypatch.setattr(store, "put_json", fail_publication)

    with pytest.raises(OSError, match="publication interrupted"):
        cache.put(key, node_id="scientist.node_test@1.0.0", outcome=_outcome(cache.run_id))

    assert not cache.has(key)
    assert cache.get(key) is None
    assert {str(artifact_id) for artifact_id in store.iter_artifact_ids()} == ids_before


def test_node_result_cache_reloads_legacy_v1_entry(tmp_path) -> None:
    """The one-artifact writer remains able to replay the predecessor wire shape."""
    store = FileSystemCAS(tmp_path)
    run_id = "R_legacy_replay"
    key = "q" * 64
    outcome = _outcome(run_id)
    journal = getattr(outcome.state, "_polisyos_state_mutation_journal")
    state_mutations = tuple(journal.operations)
    outcome_ref = store.put_json(
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
    legacy_schema = SchemaInfo(
        name="polisyos.scientist.orchestration.engine.NodeCacheEntry", version="1.0"
    )
    legacy_producer = ProducerInfo(component="scientist.engine.idempotency", version="1.0.0")
    without_proof = NodeCacheEntry(
        schema_version="1.0",
        run_id=run_id,
        node_id="scientist.node_test@1.0.0",
        idempotency_key=key,
        outcome_ref=outcome_ref,
        state_mutations=state_mutations,
        state_mutations_version="1.0",
        replay_epoch=REPLAY_EPOCH,
    )
    entry = without_proof.model_copy(
        update={
            "journal_proof": _build_journal_proof(
                without_proof,
                manifest_schema=legacy_schema,
                manifest_producer=legacy_producer,
            )
        }
    )
    entry_ref = store.put_json(
        entry.model_dump(mode="python", by_alias=True, exclude_none=False),
        PutOptions(
            kind="scientist.node_cache_entry",
            media_type="application/json",
            schema=legacy_schema,
            producer=legacy_producer,
        ),
    )

    restored = NodeResultCache(store, run_id=run_id)

    assert restored.load_entry(entry_ref) is True
    loaded = restored.get(key)
    assert loaded is not None
    assert loaded.model_dump(mode="python") == outcome.model_dump(mode="python")


def test_node_result_cache_rejects_tampered_embedded_outcome(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_cache_tamper"
    key = "t" * 64
    cache = NodeResultCache(store, run_id=run_id)
    entry_ref = cache.put(key, node_id="scientist.node_test@1.0.0", outcome=_outcome(run_id))
    entry_payload = dict(from_canonical_bytes(store.get_bytes(entry_ref.artifact_id)))
    embedded_payload = entry_payload.get("outcome_payload")
    assert isinstance(embedded_payload, dict), "self-contained outcome payload is missing"
    embedded = dict(embedded_payload)
    state = dict(embedded["state"])
    state["run_id"] = "foreign-run"
    embedded["state"] = state
    forged_ref = _rewrite_cache_entry(store, entry_ref, outcome_payload=embedded)

    restored = NodeResultCache(store, run_id=run_id)

    with pytest.raises(ValueError, match="run_identity_mismatch"):
        restored.load_entry(forged_ref)
    assert not restored.has(key)


def test_node_result_cache_serializes_concurrent_journals_consistently(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    cache = NodeResultCache(store, run_id="R_cache_concurrency")
    keys = [f"{index:064x}" for index in range(6)]

    def publish(key: str):
        return cache.put(key, node_id="scientist.node_test@1.0.0", outcome=_outcome(cache.run_id))

    with ThreadPoolExecutor(max_workers=6) as pool:
        refs = list(pool.map(publish, keys))
        outcomes = list(pool.map(cache.get, keys))

    assert len(refs) == len(keys)
    assert cache.size == len(keys)
    assert all(outcome is not None for outcome in outcomes)


def test_node_result_cache_corrupted_entry_is_treated_as_miss(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    cache = NodeResultCache(store, run_id="R_corrupt")
    key = "b" * 64
    entry_ref = cache.put(
        key,
        node_id="scientist.node_test@1.0.0",
        outcome=_outcome("R_corrupt"),
    )
    entry_blob, _ = store._paths(entry_ref.artifact_id)
    entry_blob.write_bytes(b"not canonical json")

    assert cache.get(key) is None
    assert not cache.has(key)


# Production mutation caught: an outcome without a proven mutation journal
# must not be cached and reused as an exact replay contract.
def test_node_result_cache_does_not_reuse_outcome_without_journal(tmp_path) -> None:
    cache = NodeResultCache(FileSystemCAS(tmp_path), run_id="R_unproven_journal")
    key = "u" * 64

    cache.put(
        key,
        node_id="scientist.node_test@1.0.0",
        outcome=_plain_outcome("R_unproven_journal"),
    )

    assert cache.get(key) is None


# Production mutation caught: unknown cache-entry and mutation-contract
# versions must be rejected instead of replayed by the current interpreter.
@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", "9.9"), ("state_mutations_version", "2.0")],
)
def test_node_result_cache_rejects_unknown_replay_versions(tmp_path, field, value) -> None:
    store = FileSystemCAS(tmp_path)
    key = "v" * 64
    cache = NodeResultCache(store, run_id="R_unknown_version")
    entry_ref = cache.put(
        key,
        node_id="scientist.node_test@1.0.0",
        outcome=_outcome("R_unknown_version"),
    )
    forged_entry_ref = _rewrite_cache_entry(store, entry_ref, **{field: value})

    restored = NodeResultCache(store, run_id="R_unknown_version")

    assert restored.load_entry(forged_entry_ref) is False
    assert restored.get(key) is None


# Production mutation caught: an exact legacy v1 entry with a plain outcome
# and empty operations must be rejected before indexing so execution may rerun.
def test_node_result_cache_rejects_legacy_empty_unproven_contract(tmp_path) -> None:
    from polisyos.core.artifacts import ProducerInfo, SchemaInfo
    from polisyos.core.canon import CanonSpec

    store = FileSystemCAS(tmp_path)
    key = "l" * 64
    outcome = _plain_outcome("R_legacy_empty")
    outcome_ref = store.put_json(
        outcome.model_dump(mode="python", by_alias=True, exclude_none=False),
        PutOptions(
            kind="scientist.node_outcome",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.NodeOutcome",
                version="1.0",
            ),
            producer=ProducerInfo(component="scientist.engine.idempotency", version="1.0.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    entry = NodeCacheEntry(
        schema_version="1.0",
        run_id=outcome.state.run_id,
        node_id="scientist.node_test@1.0.0",
        idempotency_key=key,
        outcome_ref=outcome_ref,
        state_mutations=(),
        state_mutations_version="1.0",
    )
    entry_ref = store.put_json(
        entry.model_dump(mode="python", by_alias=True, exclude_none=False),
        PutOptions(
            kind="scientist.node_cache_entry",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.NodeCacheEntry",
                version="1.0",
            ),
            producer=ProducerInfo(component="scientist.engine.idempotency", version="1.0.0"),
        ),
    )

    cache = NodeResultCache(store, run_id=outcome.state.run_id)

    assert cache.load_entry(entry_ref) is False
    assert not cache.has(key)
    assert cache.get(key) is None

    replacement = _outcome("R_legacy_empty")
    cache.put(key, node_id="scientist.node_test@1.0.0", outcome=replacement)
    assert cache.get(key) is not None


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
    outcome = _with_journal(_output_aware_transport_outcome(store))
    cache = NodeResultCache(store, run_id=outcome.state.run_id)
    key = "e" * 64
    entry_ref = cache.put(key, node_id="scientist.node_transport@2.0.0", outcome=outcome)
    restored = cache.get(key)
    assert type(restored) is OutputAwareNodeOutcome
    assert restored.model_dump(mode="json") == outcome.model_dump(mode="json")
    entry = NodeCacheEntry.model_validate(
        from_canonical_bytes(store.get_bytes(entry_ref.artifact_id))
    )
    assert getattr(entry, "outcome_ref", None) is None
    embedded_payload = getattr(entry, "outcome_payload", None)
    assert embedded_payload is not None
    assert "output_dispositions" in embedded_payload
    entry_manifest = store.get_manifest(entry_ref.artifact_id)
    assert entry_manifest.artifact_schema.name == (
        "polisyos.scientist.orchestration.engine.NodeCacheEntry"
    )
    assert entry_manifest.artifact_schema.version == "2.0"
    assert entry_manifest.producer.version == "2.0.0"


def test_ordinary_cache_embeds_outcome_in_current_entry_epoch(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    outcome = _outcome()
    cache = NodeResultCache(store, run_id=outcome.state.run_id)
    entry_ref = cache.put("f" * 64, node_id="scientist.node_test@1.0.0", outcome=outcome)
    entry = NodeCacheEntry.model_validate(
        from_canonical_bytes(store.get_bytes(entry_ref.artifact_id))
    )
    assert getattr(entry, "outcome_ref", None) is None
    assert getattr(entry, "outcome_payload", None) is not None
    manifest = store.get_manifest(entry_ref.artifact_id)
    assert manifest.artifact_schema.name == (
        "polisyos.scientist.orchestration.engine.NodeCacheEntry"
    )
    assert manifest.artifact_schema.version == "2.0"
    assert manifest.producer.version == "1.0.0"


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
        schema_version="1.0",
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


def test_output_aware_cache_writes_current_embedded_epoch(tmp_path) -> None:
    from tests.unit.scientist.orchestration.engine.runner.test_serialization import (
        _output_aware_transport_outcome,
    )

    store = FileSystemCAS(tmp_path)
    outcome = _with_journal(_output_aware_transport_outcome(store))
    cache = NodeResultCache(store, run_id=outcome.state.run_id)
    key = "a" * 64
    legacy_ref = _base_epoch_output_aware_cache_entry(store, outcome, key)
    entry_ref = cache.put(key, node_id="scientist.node_transport@2.0.0", outcome=outcome)
    assert entry_ref != legacy_ref
    assert cache.get(key) is not None
    entry_manifest = store.get_manifest(entry_ref.artifact_id)
    assert entry_manifest.artifact_schema.version == "2.0"
    assert entry_manifest.producer.version == "2.0.0"


def test_output_aware_cache_refuses_loading_base_epoch_entry(tmp_path) -> None:
    from tests.unit.scientist.orchestration.engine.runner.test_serialization import (
        _output_aware_transport_outcome,
    )

    store = FileSystemCAS(tmp_path)
    outcome = _with_journal(_output_aware_transport_outcome(store))
    cache = NodeResultCache(store, run_id=outcome.state.run_id)
    key = "b" * 64
    entry_ref = _base_epoch_output_aware_cache_entry(store, outcome, key)
    with pytest.raises(ValueError, match="output_aware_cache_custody"):
        cache.load_entry(entry_ref)
    assert not cache.has(key)


def test_output_aware_cache_refuses_old_entry_epoch(tmp_path) -> None:
    from tests.unit.scientist.orchestration.engine.runner.test_serialization import (
        _output_aware_transport_outcome,
    )

    store = FileSystemCAS(tmp_path)
    outcome = _with_journal(_output_aware_transport_outcome(store))
    cache = NodeResultCache(store, run_id=outcome.state.run_id)
    key = "d" * 64
    # The predecessor emits its separate outcome and entry under the old
    # epoch. Both actual manifests must be checked.
    entry_ref = _base_epoch_output_aware_cache_entry(store, outcome, key)
    entry = NodeCacheEntry.model_validate(
        from_canonical_bytes(store.get_bytes(entry_ref.artifact_id))
    )
    assert store.get_manifest(entry.outcome_ref.artifact_id).producer.version == "1.0.0"
    assert store.get_manifest(entry_ref.artifact_id).producer.version == "1.0.0"
    with pytest.raises(ValueError, match="output_aware_cache_custody"):
        cache.load_entry(entry_ref)
    assert not cache.has(key)
