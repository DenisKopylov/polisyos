from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.scientist.nodes.builtins import builtin_nodes as scientist_builtin_nodes
from polisyos.scientist.nodes.builtins.governance.data_plane_gate import DataPlaneGateNode
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


def _bound_cache(store: FileSystemCAS, run_id: str, tenant_context: ArtifactTenantContextInfo):
    """Turn an absent scope-binding API into an explicit test failure."""
    try:
        return NodeResultCache(store, run_id=run_id, tenant_context=tenant_context)
    except TypeError as exc:
        pytest.fail(f"NodeResultCache tenant_context contract is missing: {exc}")


def _cache_get_with_deadline(cache: NodeResultCache, key: str, deadline_monotonic: float):
    """Turn an absent cache deadline API into an explicit test failure."""
    try:
        return cache.get(key, deadline_monotonic=deadline_monotonic)
    except TypeError as exc:
        pytest.fail(f"NodeResultCache deadline contract is missing: {exc}")


def _cache_put_with_deadline(
    cache: NodeResultCache,
    key: str,
    *,
    deadline_monotonic: float,
    outcome: NodeOutcome,
):
    """Turn an absent publication deadline API into an explicit test failure."""
    try:
        return cache.put(
            key,
            node_id="scientist.node_test@1.0.0",
            outcome=outcome,
            deadline_monotonic=deadline_monotonic,
        )
    except TypeError as exc:
        pytest.fail(f"NodeResultCache deadline contract is missing: {exc}")


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


def test_idempotency_key_preserves_presence_and_nested_missing_semantics(tmp_path) -> None:
    """Declared reads distinguish absent values from explicit null and falsy values."""
    del tmp_path

    def _key(read_path: str, params: dict[str, object]) -> str:
        spec = DataPlaneGateNode().spec.model_copy(update={"state_reads": [read_path]})
        return compute_idempotency_key(
            spec,
            ExperimentState(run_id="R_presence_semantics", params=params),
        )

    missing = _key("params.threshold", {})
    explicit_null = _key("params.threshold", {"threshold": None})
    zero = _key("params.threshold", {"threshold": 0})
    false = _key("params.threshold", {"threshold": False})
    empty = _key("params.threshold", {"threshold": []})

    assert missing not in {explicit_null, zero, false, empty}
    assert len({explicit_null, zero, false, empty}) == 4

    missing_intermediate = _key("params.nested.value", {})
    missing_leaf = _key("params.nested.value", {"nested": {}})
    nested_null = _key("params.nested.value", {"nested": {"value": None}})
    assert missing_intermediate == missing_leaf
    assert missing_intermediate != nested_null


def test_idempotency_key_applies_only_declared_consumer_default(tmp_path) -> None:
    """A real consumer default reuses the effective value, not explicit null."""
    del tmp_path
    spec = DataPlaneGateNode().spec

    def _key(params: dict[str, object]) -> str:
        return compute_idempotency_key(
            spec,
            ExperimentState(run_id="R_data_plane_presence", params=params),
        )

    assert _key({}) == _key({"tenant_tier": "shared"})
    assert _key({}) != _key({"tenant_tier": None})
    assert _key({}) != _key({"tenant_tier": 0})
    assert _key({}) != _key({"tenant_tier": False})
    assert _key({}) != _key({"tenant_tier": []})


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


def test_node_cache_replays_artifact_ref_and_keeps_excluded_null_presence_bounded(
    tmp_path,
) -> None:
    run_id = "R_cache_artifact_ref_null_presence"
    reference = ArtifactRef(
        artifact_id=f"sha256:{'d' * 64}",
        kind="scientist.discovery_artifact_bundle",
        media_type="application/json",
        manifest_profile_sha256=None,
    )
    assert "manifest_profile_sha256" in reference.model_fields_set

    branch = branch_state(
        ExperimentState(run_id=run_id),
        write_paths=("artifacts_index",),
    )
    branch.state.artifacts_index["reference"] = reference
    assert branch.journal.operations[-1].value_kind == "artifact_ref"

    store = FileSystemCAS(tmp_path)
    cache = NodeResultCache(store, run_id=run_id)
    key = "d" * 64
    entry_ref = cache.put(
        key,
        node_id="scientist.node_test@1.0.0",
        outcome=NodeOutcome(status="ok", state=branch.state),
    )
    payload = from_canonical_bytes(store.get_bytes(entry_ref.artifact_id))
    serialized_ref = payload["state_mutations"][0]["value"]
    assert "manifest_profile_sha256" not in serialized_ref

    restored = cache.get(key)
    assert restored is not None
    restored_ref = restored.state.artifacts_index["reference"]
    assert isinstance(restored_ref, ArtifactRef)
    assert restored_ref.manifest_profile_sha256 is None
    # ArtifactRef excludes a None profile from its wire form, so its transient
    # model_fields_set provenance is deliberately not represented after CAS load.
    assert "manifest_profile_sha256" not in restored_ref.model_fields_set
    # Equality follows the ArtifactRef values despite the omitted provenance bit.
    assert restored_ref == reference
    assert reference == restored_ref
    # The cache validates the canonical journal record; this normalized ref is
    # still a hit on a subsequent full entry read.
    assert cache.get(key) is not None


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
    journal = outcome.state._polisyos_state_mutation_journal
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

    bound = _bound_cache(
        store,
        run_id,
        ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a"),
    )
    with pytest.raises(ValueError, match="cache_entry: unbound_legacy_entry"):
        bound.load_entry(entry_ref)


def test_node_result_cache_rejects_legacy_and_foreign_scope_for_bound_cache(tmp_path) -> None:
    """A bound cache cannot replay an unbound or foreign tenant artifact."""
    store = FileSystemCAS(tmp_path)
    run_id = "R_cache_scope"
    key = "s" * 64
    tenant_a = ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a")
    tenant_b = ArtifactTenantContextInfo(tenant_id="tenant-b", cell_id="cell-b")

    cache_a = _bound_cache(store, run_id, tenant_a)
    entry_ref = cache_a.put(
        key,
        node_id="scientist.node_test@1.0.0",
        outcome=_outcome(run_id),
    )
    entry = NodeCacheEntry.model_validate(
        from_canonical_bytes(store.get_bytes(entry_ref.artifact_id))
    )
    manifest = store.get_manifest(entry_ref.artifact_id)

    assert getattr(entry, "tenant_context", None) == tenant_a
    assert manifest.tenant_context == tenant_a

    foreign = _bound_cache(store, run_id, tenant_b)
    with pytest.raises(ValueError, match="cache_entry: tenant_scope_mismatch"):
        foreign.load_entry(entry_ref)

    unbound = NodeResultCache(store, run_id=run_id)
    with pytest.raises(ValueError, match="cache_entry: scoped_artifact_on_unbound_cache"):
        unbound.load_entry(entry_ref)


def test_node_result_cache_rejects_expired_deadline_before_store_io(tmp_path, monkeypatch) -> None:
    """An expired cache deadline is not converted into an ordinary cache miss."""
    store = FileSystemCAS(tmp_path)
    cache = NodeResultCache(store, run_id="R_cache_deadline")
    key = "e" * 64
    cache.put(key, node_id="scientist.node_test@1.0.0", outcome=_outcome(cache.run_id))
    calls = 0
    original_get_bytes = store.get_bytes

    def count_get_bytes(artifact_id):
        nonlocal calls
        calls += 1
        return original_get_bytes(artifact_id)

    monkeypatch.setattr(store, "get_bytes", count_get_bytes)

    with pytest.raises(TimeoutError, match="cache deadline exceeded"):
        _cache_get_with_deadline(cache, key, time.perf_counter() - 1.0)

    assert calls == 0


def test_node_result_cache_rejects_expired_deadline_before_publication(
    tmp_path, monkeypatch
) -> None:
    """An expired publication deadline does not start a CAS write."""
    store = FileSystemCAS(tmp_path)
    cache = NodeResultCache(store, run_id="R_cache_put_deadline")
    calls = 0
    original_put_json = store.put_json

    def count_put_json(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_put_json(*args, **kwargs)

    monkeypatch.setattr(store, "put_json", count_put_json)

    with pytest.raises(TimeoutError, match="cache deadline exceeded"):
        _cache_put_with_deadline(
            cache,
            "d" * 64,
            outcome=_outcome(cache.run_id),
            deadline_monotonic=time.perf_counter() - 1.0,
        )

    assert calls == 0


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


def test_node_result_cache_does_not_replay_status_blind_epoch_two_entries(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_cache_status_epoch"
    key = "s" * 64
    current = NodeResultCache(store, run_id=run_id)
    current_ref = current.put(
        key,
        node_id="scientist.node_test@1.0.0",
        outcome=_outcome(run_id),
    )
    current_entry = NodeCacheEntry.model_validate(
        from_canonical_bytes(store.get_bytes(current_ref.artifact_id))
    )
    manifest = store.get_manifest(current_ref.artifact_id)
    legacy_without_proof = current_entry.model_copy(
        update={"replay_epoch": "2.0", "journal_proof": None}
    )
    legacy_entry = legacy_without_proof.model_copy(
        update={
            "journal_proof": _build_journal_proof(
                legacy_without_proof,
                manifest_schema=manifest.artifact_schema,
                manifest_producer=manifest.producer,
            )
        }
    )
    legacy_ref = store.put_json(
        legacy_entry.model_dump(mode="python", by_alias=True, exclude_none=False),
        PutOptions(
            kind="scientist.node_cache_entry",
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
        ),
    )

    restored = NodeResultCache(store, run_id=run_id)

    assert restored.load_entry(legacy_ref) is False
    assert restored.get(key) is None


def test_node_result_cache_serializes_concurrent_journals_consistently(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    cache = NodeResultCache(store, run_id="R_cache_concurrency")
    keys = [f"{index:064x}" for index in range(6)]

    def publish_and_read(key: str):
        ref = cache.put(key, node_id="scientist.node_test@1.0.0", outcome=_outcome(cache.run_id))
        return ref, cache.get(key)

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(publish_and_read, keys))

    refs = [ref for ref, _outcome in results]
    outcomes = [outcome for _ref, outcome in results]
    assert len(refs) == len(keys)
    assert cache.size == len(keys)
    assert all(outcome is not None for outcome in outcomes)


def test_node_result_cache_discard_revokes_blocked_write_without_waiting(tmp_path) -> None:
    """A blocked CAS write cannot hold the cache-index lock against discard."""
    store = FileSystemCAS(tmp_path)
    cache = NodeResultCache(store, run_id="R_cache_discard_write")
    key = "w" * 64
    entered = threading.Event()
    release = threading.Event()
    discard_returned = threading.Event()
    original_put_json = store.put_json

    def delayed_put_json(obj, opts, *args, **kwargs):
        if str(getattr(opts, "kind", "")) == "scientist.node_cache_entry":
            entered.set()
            release.wait()
        return original_put_json(obj, opts, *args, **kwargs)

    store.put_json = delayed_put_json
    with ThreadPoolExecutor(max_workers=2) as pool:
        put_future = pool.submit(
            cache.put, key, "scientist.node_test@1.0.0", _outcome(cache.run_id)
        )
        try:
            assert entered.wait(timeout=3.0), "cache put did not reach its provider call"

            def discard() -> None:
                cache.discard(key)
                discard_returned.set()

            discard_future = pool.submit(discard)
            discarded_while_write_blocked = discard_returned.wait(timeout=0.25)
        finally:
            release.set()
        discard_future.result(timeout=3.0)
        with pytest.raises(RuntimeError, match="cache_entry: publication_invalidated"):
            put_future.result(timeout=3.0)

    assert discarded_while_write_blocked is True
    assert cache.has(key) is False
    assert cache.size == 0


def test_node_result_cache_discard_revokes_blocked_read_without_waiting(tmp_path) -> None:
    """A read completed after discard is a miss and cannot resurrect its entry."""
    store = FileSystemCAS(tmp_path)
    cache = NodeResultCache(store, run_id="R_cache_discard_read")
    key = "r" * 64
    cache.put(key, "scientist.node_test@1.0.0", _outcome(cache.run_id))
    entered = threading.Event()
    release = threading.Event()
    discard_returned = threading.Event()
    original_get_bytes = store.get_bytes

    def delayed_get_bytes(artifact_id):
        entered.set()
        release.wait()
        return original_get_bytes(artifact_id)

    store.get_bytes = delayed_get_bytes
    with ThreadPoolExecutor(max_workers=2) as pool:
        read_future = pool.submit(cache.get, key)
        try:
            assert entered.wait(timeout=3.0), "cache read did not reach its provider call"

            def discard() -> None:
                cache.discard(key)
                discard_returned.set()

            discard_future = pool.submit(discard)
            discarded_while_read_blocked = discard_returned.wait(timeout=0.25)
        finally:
            release.set()
        discard_future.result(timeout=3.0)
        assert read_future.result(timeout=3.0) is None

    assert discarded_while_read_blocked is True
    assert cache.has(key) is False
    assert cache.size == 0


def test_node_result_cache_discard_revokes_blocked_recovery_admission(tmp_path) -> None:
    """Recovery admission is invalidated if discard arrives during entry verification."""
    store = FileSystemCAS(tmp_path)
    writer = NodeResultCache(store, run_id="R_cache_discard_load")
    key = "l" * 64
    entry_ref = writer.put(key, "scientist.node_test@1.0.0", _outcome(writer.run_id))
    reader = NodeResultCache(store, run_id=writer.run_id)
    entered = threading.Event()
    release = threading.Event()
    discard_returned = threading.Event()
    original_get_bytes = store.get_bytes

    def delayed_get_bytes(artifact_id):
        entered.set()
        release.wait()
        return original_get_bytes(artifact_id)

    store.get_bytes = delayed_get_bytes
    with ThreadPoolExecutor(max_workers=2) as pool:
        load_future = pool.submit(reader.load_entry, entry_ref)
        try:
            assert entered.wait(timeout=3.0), "cache recovery did not reach its provider call"

            def discard() -> None:
                reader.discard(key)
                discard_returned.set()

            discard_future = pool.submit(discard)
            discarded_while_load_blocked = discard_returned.wait(timeout=0.25)
        finally:
            release.set()
        discard_future.result(timeout=3.0)
        assert load_future.result(timeout=3.0) is False

    assert discarded_while_load_blocked is True
    assert reader.has(key) is False
    assert reader.size == 0


def _hold_cache_put_for_key(store: FileSystemCAS, blocked_key: str):
    entered = threading.Event()
    release = threading.Event()
    provider_keys: list[str] = []
    original_put_json = store.put_json

    def delayed_put_json(obj, opts, *args, **kwargs):
        if str(getattr(opts, "kind", "")) == "scientist.node_cache_entry":
            key = str(obj["idempotency_key"])
            provider_keys.append(key)
            if key == blocked_key and not entered.is_set():
                entered.set()
                release.wait()
        return original_put_json(obj, opts, *args, **kwargs)

    store.put_json = delayed_put_json
    return entered, release, provider_keys


def _watch_cache_registration(cache: NodeResultCache, watched_key: str | None):
    registered = threading.Event()
    original_register = cache._register_io_locked

    def recording_register(key: str | None):
        operation = original_register(key)
        if key == watched_key:
            registered.set()
        return operation

    cache._register_io_locked = recording_register
    return registered


@pytest.mark.parametrize(
    ("discard_pending_key", "pending_write_is_admitted"),
    [(True, False), (False, True)],
)
def test_node_result_cache_discard_reaches_queued_write_tokens(
    tmp_path, discard_pending_key: bool, pending_write_is_admitted: bool
) -> None:
    """Discard revokes matching queued writes without cancelling an unrelated key."""
    store = FileSystemCAS(tmp_path)
    cache = NodeResultCache(store, run_id="R_cache_queued_discard")
    active_key = "a" * 64
    pending_key = "b" * 64
    unrelated_key = "u" * 64
    entered, release, provider_keys = _hold_cache_put_for_key(store, active_key)
    pending_registered = _watch_cache_registration(cache, pending_key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        active = pool.submit(
            cache.put, active_key, "scientist.node_test@1.0.0", _outcome(cache.run_id)
        )
        try:
            assert entered.wait(timeout=3.0), "active cache write did not enter the provider"
            pending = pool.submit(
                cache.put, pending_key, "scientist.node_test@1.0.0", _outcome(cache.run_id)
            )
            assert pending_registered.wait(timeout=3.0), "queued write was not registered"
            cache.discard(pending_key if discard_pending_key else unrelated_key)
        finally:
            release.set()

        active.result(timeout=3.0)
        if pending_write_is_admitted:
            pending.result(timeout=3.0)
        else:
            with pytest.raises(RuntimeError, match="cache_entry: publication_invalidated"):
                pending.result(timeout=3.0)

    assert provider_keys == (
        [active_key, pending_key] if pending_write_is_admitted else [active_key]
    )
    assert cache.has(active_key)
    assert cache.has(pending_key) is pending_write_is_admitted
    assert not cache._pending_io


def test_node_result_cache_clear_invalidates_active_and_queued_writes(tmp_path) -> None:
    """Clear revokes all cache operations already waiting on the provider lane."""
    store = FileSystemCAS(tmp_path)
    cache = NodeResultCache(store, run_id="R_cache_queued_clear")
    active_key = "c" * 64
    pending_key = "d" * 64
    entered, release, provider_keys = _hold_cache_put_for_key(store, active_key)
    pending_registered = _watch_cache_registration(cache, pending_key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        active = pool.submit(
            cache.put, active_key, "scientist.node_test@1.0.0", _outcome(cache.run_id)
        )
        try:
            assert entered.wait(timeout=3.0), "active cache write did not enter the provider"
            pending = pool.submit(
                cache.put, pending_key, "scientist.node_test@1.0.0", _outcome(cache.run_id)
            )
            assert pending_registered.wait(timeout=3.0), "queued write was not registered"
            cache.clear()
        finally:
            release.set()

        with pytest.raises(RuntimeError, match="cache_entry: publication_invalidated"):
            active.result(timeout=3.0)
        with pytest.raises(RuntimeError, match="cache_entry: publication_invalidated"):
            pending.result(timeout=3.0)

    assert provider_keys == [active_key]
    assert cache.size == 0
    assert not cache.has(active_key)
    assert not cache.has(pending_key)
    assert not cache._pending_io


@pytest.mark.parametrize("invalidation", ["discard", "clear", "prune"])
def test_node_result_cache_invalidation_reaches_queued_recovery(
    tmp_path, invalidation: str
) -> None:
    """Owner mutations revoke unknown-key recovery before it reads its CAS entry."""
    store = FileSystemCAS(tmp_path)
    run_id = "R_cache_queued_recovery_invalidation"
    cache = NodeResultCache(store, run_id=run_id)
    active_key = "e" * 64
    recovery_key = "f" * 64
    cache.put(active_key, "scientist.node_test@1.0.0", _outcome(run_id))
    recovery_writer = NodeResultCache(store, run_id=run_id)
    recovery_ref = recovery_writer.put(recovery_key, "scientist.node_test@1.0.0", _outcome(run_id))
    entered, release, provider_keys = _hold_cache_put_for_key(store, active_key)
    recovery_registered = _watch_cache_registration(cache, None)
    original_get_bytes = store.get_bytes
    recovery_reads: list[str] = []

    def recording_get_bytes(artifact_id):
        if str(artifact_id) == recovery_ref.artifact_id:
            recovery_reads.append(str(artifact_id))
        return original_get_bytes(artifact_id)

    store.get_bytes = recording_get_bytes
    with ThreadPoolExecutor(max_workers=2) as pool:
        active = pool.submit(cache.put, active_key, "scientist.node_test@1.0.0", _outcome(run_id))
        try:
            assert entered.wait(timeout=3.0), "active cache write did not enter the provider"
            recovery = pool.submit(cache.load_entry, recovery_ref)
            assert recovery_registered.wait(timeout=3.0), (
                "recovery was not registered before queueing"
            )
            if invalidation == "discard":
                cache.discard(recovery_key)
            elif invalidation == "clear":
                cache.clear()
            else:
                assert cache.prune(0) == 1
        finally:
            release.set()

        if invalidation == "discard":
            active.result(timeout=3.0)
        else:
            with pytest.raises(RuntimeError, match="cache_entry: publication_invalidated"):
                active.result(timeout=3.0)
        assert recovery.result(timeout=3.0) is False

    assert provider_keys == [active_key]
    assert recovery_reads == []
    assert cache.has(recovery_key) is False
    assert cache.size == (1 if invalidation == "discard" else 0)
    assert cache.has(active_key) is (invalidation == "discard")
    assert not cache._pending_io


def test_node_result_cache_discard_reaches_queued_read_tokens(tmp_path) -> None:
    """Discard stops a queued read before it reopens an evicted cache artifact."""
    store = FileSystemCAS(tmp_path)
    cache = NodeResultCache(store, run_id="R_cache_queued_read")
    active_key = "g" * 64
    pending_key = "h" * 64
    pending_ref = cache.put(pending_key, "scientist.node_test@1.0.0", _outcome(cache.run_id))
    entered, release, _provider_keys = _hold_cache_put_for_key(store, active_key)
    pending_registered = _watch_cache_registration(cache, pending_key)
    original_get_bytes = store.get_bytes
    pending_reads: list[str] = []

    def recording_get_bytes(artifact_id):
        if str(artifact_id) == pending_ref.artifact_id:
            pending_reads.append(str(artifact_id))
        return original_get_bytes(artifact_id)

    store.get_bytes = recording_get_bytes
    with ThreadPoolExecutor(max_workers=2) as pool:
        active = pool.submit(
            cache.put, active_key, "scientist.node_test@1.0.0", _outcome(cache.run_id)
        )
        try:
            assert entered.wait(timeout=3.0), "active cache write did not enter the provider"
            pending = pool.submit(cache.get, pending_key)
            assert pending_registered.wait(timeout=3.0), "queued read was not registered"
            cache.discard(pending_key)
        finally:
            release.set()

        active.result(timeout=3.0)
        assert pending.result(timeout=3.0) is None

    assert pending_reads == []
    assert cache.has(active_key)
    assert not cache.has(pending_key)
    assert not cache._pending_io


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
