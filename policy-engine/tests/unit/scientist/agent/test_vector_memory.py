"""Native generation integrity checks for vector memory."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.scientist.agent.vector_memory import VectorMemoryStore

pytest.importorskip("hnswlib")


def test_metadata_cannot_mutate_the_published_generation(tmp_path):
    memory = VectorMemoryStore(dim=2, max_elements=4)
    metadata = {"binding": {"origin": "original", "quality": 0.8}}
    memory.add("first", [1.0, 0.0], metadata)
    metadata["binding"]["origin"] = "input mutation"
    result = memory.query([1.0, 0.0], top_k=1)[0]
    assert result[2]["binding"]["origin"] == "original"
    result[2]["binding"]["origin"] = "query mutation"
    store = FileSystemCAS(tmp_path / "cas")
    restored = VectorMemoryStore(dim=2)
    restored.load_from_artifact(store, memory.save_to_artifact(store))
    assert restored.query([1.0, 0.0], top_k=1)[0][2] == {
        "binding": {"origin": "original", "quality": 0.8}
    }


@pytest.mark.parametrize("mutation", ["missing_label", "duplicate_key", "bad_metadata"])
def test_valid_native_bytes_cannot_publish_mismatched_metadata(tmp_path, mutation):
    import json

    store = FileSystemCAS(tmp_path / "cas")
    original = VectorMemoryStore(dim=2, max_elements=4)
    original.add("first", [1.0, 0.0], {"origin": "first"})
    original.add("second", [0.0, 1.0], {"origin": "second"})
    bundle_ref = original.save_to_artifact(store)
    bundle = json.loads(store.get_bytes(bundle_ref.artifact_id))
    if mutation == "missing_label":
        bundle["keys"] = bundle["keys"][:1]
        bundle["metadata"] = bundle["metadata"][:1]
    elif mutation == "duplicate_key":
        bundle["keys"] = ["duplicate", "duplicate"]
    else:
        bundle["metadata"] = [[], {}]
    corrupt_ref = store.put_json(
        bundle, PutOptions(kind="vector_memory.bundle", media_type="application/json")
    )
    live = VectorMemoryStore(dim=2, max_elements=4)
    live.add("live", [1.0, 0.0], {"origin": "live"})
    before = deepcopy(live.query([1.0, 0.0], top_k=1))
    with pytest.raises(ValueError):
        live.load_from_artifact(store, corrupt_ref)
    assert live.query([1.0, 0.0], top_k=1) == before


def test_partial_native_update_failure_restores_previous_vectors_and_metadata():
    memory = VectorMemoryStore(dim=2, max_elements=4)
    memory.add("first", [1.0, 0.0], {"origin": "first"})
    native = memory._index

    class FailAfterMutation:
        def save_index(self, path):
            native.save_index(path)

        def add_items(self, embeddings, labels):
            native.add_items(embeddings, labels)
            raise RuntimeError("failure after native mutation")

    memory._index = FailAfterMutation()
    with pytest.raises(RuntimeError, match="after native mutation"):
        memory.add("first", [0.0, 1.0], {"origin": "replacement"})
    key, distance, metadata = memory.query([1.0, 0.0], top_k=1)[0]
    assert key == "first"
    assert distance == pytest.approx(0.0)
    assert metadata == {"origin": "first"}


@pytest.mark.parametrize("embedding", [[float("nan"), 0.0], [float("inf"), 0.0]])
def test_nonfinite_vector_is_refused_before_native_mutation(embedding):
    memory = VectorMemoryStore(dim=2, max_elements=2)
    memory.add("first", [1.0, 0.0])
    with pytest.raises(ValueError, match="finite"):
        memory.add("bad", embedding)
    assert len(memory) == 1
    assert memory.query([1.0, 0.0], top_k=1)[0][0] == "first"


def test_query_waits_for_native_update_and_metadata_publication():
    memory = VectorMemoryStore(dim=2, max_elements=2)
    memory.add("first", [1.0, 0.0], {"origin": "old"})
    native = memory._index
    mutated, release, query_started, native_query_entered = (Event() for _ in range(4))

    class PausedUpdate:
        def save_index(self, path):
            native.save_index(path)

        def add_items(self, embeddings, labels):
            native.add_items(embeddings, labels)
            mutated.set()
            assert release.wait(5)

        def knn_query(self, embeddings, *, k):
            native_query_entered.set()
            return native.knn_query(embeddings, k=k)

    def read():
        query_started.set()
        return memory.query([0.0, 1.0], top_k=1)

    memory._index = PausedUpdate()
    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(memory.add, "first", [0.0, 1.0], {"origin": "new"})
        assert mutated.wait(5)
        reader = pool.submit(read)
        assert query_started.wait(5)
        try:
            assert not native_query_entered.wait(0.1)
        finally:
            release.set()
        writer.result(timeout=5)
        assert reader.result(timeout=5)[0][2] == {"origin": "new"}
