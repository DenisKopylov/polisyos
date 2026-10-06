"""Native reader oracles for indivisible vector-memory generations."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

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
