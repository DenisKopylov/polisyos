"""Native reader oracles for indivisible vector-memory generations."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from polisyos.core import artifacts, canon
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent.vector_memory import VectorMemoryStore


@pytest.mark.parametrize("operation", ["load", "update"])
def test_query_captures_one_generation_during_native_publication(tmp_path, monkeypatch, operation):
    """A real old HNSW answer cannot acquire the newly published metadata."""
    import hnswlib

    store = FileSystemCAS(tmp_path / "cas")
    memory = VectorMemoryStore(dim=2, max_elements=4)
    memory.add("old", [1.0, 0.0], {"generation": "old", "nested": [1]})
    new = VectorMemoryStore(dim=2, max_elements=4)
    new.add("new", [0.0, 1.0], {"generation": "new", "nested": [2]})
    ref = new.save_to_artifact(store)
    arrived, release = threading.Event(), threading.Event()
    native_query = hnswlib.Index.knn_query

    def paused_native(index, *args, **kwargs):
        result = native_query(index, *args, **kwargs)
        arrived.set()
        assert release.wait(10), "writer did not release native reader"
        return result

    monkeypatch.setattr(hnswlib.Index, "knn_query", paused_native)
    with ThreadPoolExecutor(max_workers=1) as pool:
        reader = pool.submit(memory.query, [1.0, 0.0], top_k=1)
        try:
            assert arrived.wait(10), "reader did not execute real HNSW"
            if operation == "load":
                memory.load_from_artifact(store, ref)
            else:
                memory.add("old", [0.0, 1.0], {"generation": "new", "nested": [2]})
        finally:
            release.set()
        assert reader.result(10) == [("old", 0.0, {"generation": "old", "nested": [1]})]
    expected_key = "new" if operation == "load" else "old"
    assert memory.query([1.0, 0.0], top_k=1) == [
        (expected_key, 1.0, {"generation": "new", "nested": [2]})
    ]


def test_metadata_copies_and_failed_native_mutation_preserve_generation(tmp_path, monkeypatch):
    """Published native objects and nested metadata survive a partial failed add."""
    import hnswlib

    memory = VectorMemoryStore(dim=2, max_elements=3)
    metadata = {"nested": {"values": [1]}}
    memory.add("old", [1.0, 0.0], metadata)
    metadata["nested"]["values"].append(2)
    response = memory.query([1.0, 0.0], top_k=1)
    response[0][2]["nested"]["values"].append(3)
    native_add = hnswlib.Index.add_items

    def fail_after_mutation(index, *args, **kwargs):
        native_add(index, *args, **kwargs)
        raise RuntimeError("native operation failed after changing its candidate")

    monkeypatch.setattr(hnswlib.Index, "add_items", fail_after_mutation)
    with pytest.raises(RuntimeError, match="after changing"):
        memory.add("old", [0.0, 1.0], {"nested": {"values": [9]}})
    assert memory.query([1.0, 0.0], top_k=1) == [("old", 0.0, {"nested": {"values": [1]}})]


def test_same_ref_altered_bytes_refuses_load_without_publishing(tmp_path):
    """CAS integrity, rather than reference shape, admits the complete bundle."""
    store = FileSystemCAS(tmp_path / "cas")
    old = VectorMemoryStore(dim=2, max_elements=3)
    old.add("old", [1.0, 0.0], {"generation": "old"})
    new = VectorMemoryStore(dim=2, max_elements=3)
    new.add("new", [0.0, 1.0], {"generation": "new"})
    ref = new.save_to_artifact(store)
    blob, _ = store._paths(ref.artifact_id)
    blob.write_bytes(b'{"dim":2,"keys":["false-key"]}')
    with pytest.raises(Exception, match="(sha256|mismatch|integrity)"):
        old.load_from_artifact(store, ref)
    assert old.query([1.0, 0.0], top_k=1) == [("old", 0.0, {"generation": "old"})]


@pytest.mark.parametrize(
    "change",
    [
        "outer-kind",
        "outer-media",
        "schema",
        "missing-schema",
        "dimension",
        "count",
        "capacity",
        "index-kind",
        "truncated-index",
    ],
)
def test_real_bundle_envelope_refuses_disagreement_before_publication(tmp_path, change):
    """Shape-valid CAS inputs cannot misdescribe the physical native generation."""
    store = FileSystemCAS(tmp_path / "cas")
    old = VectorMemoryStore(dim=2, max_elements=3)
    old.add("old", [1.0, 0.0], {"generation": "old"})
    new = VectorMemoryStore(dim=2, max_elements=3)
    new.add("new", [0.0, 1.0], {"generation": "new"})
    original = new.save_to_artifact(store)
    payload = canon.from_canonical_bytes(store.get_bytes(original))
    kind, media = original.kind, original.media_type
    if change == "outer-kind":
        kind = "foreign.vector.bundle"
    elif change == "outer-media":
        media = "text/plain"
    elif change == "schema":
        payload["schema_version"] = "3.0"
    elif change == "missing-schema":
        del payload["schema_version"]
    elif change == "dimension":
        payload["dim"] = 3
    elif change == "count":
        payload["keys"].append("false-key")
        payload["metadata"].append({})
    elif change == "capacity":
        payload["max_elements"] = 4
    else:
        index_ref = artifacts.ArtifactRef.model_validate(payload["index_ref"])
        data = store.get_bytes(index_ref)
        changed = store.put_bytes(
            data[:5] if change == "truncated-index" else data,
            artifacts.PutOptions(
                kind="foreign.vector.index" if change == "index-kind" else index_ref.kind,
                media_type=index_ref.media_type,
            ),
        )
        payload["index_ref"] = changed.model_dump(mode="json")
    ref = store.put_bytes(
        canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False)),
        artifacts.PutOptions(kind=kind, media_type=media),
    )
    with pytest.raises(ValueError):
        old.load_from_artifact(store, ref)
    assert old.query([1.0, 0.0], top_k=1) == [("old", 0.0, {"generation": "old"})]


def test_explicit_schema_absent_legacy_bundle_uses_default_native_view(tmp_path):
    """Legacy ID-only refs remain bounded to CAS's default manifest view."""
    store = FileSystemCAS(tmp_path / "cas")
    memory = VectorMemoryStore(dim=2, max_elements=3)
    memory.add("legacy", [1.0, 0.0], {"source": "legacy"})
    ref = memory.save_to_artifact(store)
    payload = canon.from_canonical_bytes(store.get_bytes(ref))
    index_ref = artifacts.ArtifactRef.model_validate(payload.pop("index_ref"))
    del payload["schema_version"]
    payload["index_artifact_id"] = str(index_ref.artifact_id)
    legacy = store.put_json(payload, artifacts.PutOptions(kind=ref.kind, media_type=ref.media_type))
    restored = VectorMemoryStore(dim=1)
    restored.load_from_artifact(store, legacy)
    assert restored.query([1.0, 0.0], top_k=1) == [("legacy", 0.0, {"source": "legacy"})]


def test_same_native_ref_changed_bytes_preserves_published_generation(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    old = VectorMemoryStore(dim=2, max_elements=3)
    old.add("old", [1.0, 0.0], {})
    ref = old.save_to_artifact(store)
    payload = canon.from_canonical_bytes(store.get_bytes(ref))
    index_ref = artifacts.ArtifactRef.model_validate(payload["index_ref"])
    blob, _ = store._paths(index_ref.artifact_id)
    blob.write_bytes(b"changed native bytes")
    with pytest.raises(Exception, match="(sha256|mismatch|integrity)"):
        old.load_from_artifact(store, ref)
    assert old.query([1.0, 0.0], top_k=1) == [("old", 0.0, {})]
