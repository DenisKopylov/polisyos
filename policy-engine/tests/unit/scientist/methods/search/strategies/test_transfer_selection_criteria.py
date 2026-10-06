"""Original transfer selection criteria through persisted measured observations."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event

import pytest

pytest.importorskip("hnswlib", reason="UNRUN: transfer selection requires native HNSW")

from polisyos.core import artifacts, canon
from polisyos.scientist.agent.vector_memory import VectorMemoryStore
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    persist_benchmark_evaluation,
)
from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from polisyos.scientist.methods.search.strategies.transfer import TransferLearningManager
from tests.unit.scientist.methods.search.strategies.test_transfer import (
    changed_history,
    measured_history,
)

pytestmark = pytest.mark.integration


def _registered(manager, source, rows, *, run_id, embedding):
    fingerprint = source.model_copy(
        deep=True, update={"run_id": run_id, "embedding": embedding, "history_ref": None}
    )
    fingerprint.history_ref = manager.register_run(fingerprint, rows)
    return fingerprint


@pytest.mark.parametrize("limit", [0, 1, 3, 4, 10])
def test_uneven_histories_redistribute_only_admitted_remaining_quota(tmp_path, limit):
    _, _, manager, source, target, originals, _ = measured_history(tmp_path, count=4)
    short = _registered(manager, source, originals[:1], run_id="short", embedding=[0.9, 0.1])
    long = _registered(manager, source, originals[1:], run_id="long", embedding=[0.8, 0.2])
    rows = manager.get_warm_start_evaluations(
        [short, long], max_evals=limit, target_fingerprint=target
    )
    assert len(rows) == min(limit, 4)
    if limit:
        assert rows[0].candidate_id == originals[0].candidate_id
        assert [row.scalar_score for row in rows[1:]] == sorted(
            row.scalar_score for row in originals[1:]
        )[: max(0, limit - 1)]
    assert manager.last_admission_report["selected"] == len(rows)


def test_complete_score_ties_preserve_explicit_independent_replica_identity(tmp_path):
    store, _, manager, source, target, originals, _ = measured_history(tmp_path, count=1)
    first = originals[0]
    replica = deepcopy(first)
    replica.metadata["replica_id"] = "independent-repeat"
    original_ref = artifacts.ArtifactRef.model_validate(first.metadata["evaluation_ref"])
    original = BenchmarkEvaluation.model_validate(
        canon.from_canonical_bytes(store.get_verified_snapshot(original_ref).data)
    )
    replica_ref = persist_benchmark_evaluation(
        store,
        original.model_copy(
            deep=True,
            update={"metadata": {**original.metadata, "replica_id": "independent-repeat"}},
        ),
    )
    replica.provenance_ref = str(replica_ref.artifact_id)
    replica.metadata["evaluation_ref"] = replica_ref.model_dump(mode="json")
    tied = _registered(manager, source, [first, replica], run_id="ties", embedding=[0.9, 0.1])
    rows = manager.get_warm_start_evaluations([tied], max_evals=2, target_fingerprint=target)
    assert [row.scalar_score for row in rows] == [first.scalar_score, first.scalar_score]
    assert [row.metadata["replica_id"] for row in rows] == [0, "independent-repeat"]
    assert rows[0].provenance_ref != rows[1].provenance_ref
    assert manager.get_warm_start_evaluations([tied], max_evals=1, target_fingerprint=target) == [
        rows[0]
    ]


def test_bridge_source_limit_follows_content_admission_and_replay_has_no_ann(tmp_path, monkeypatch):
    store, _, _, source, target, originals, basis = measured_history(tmp_path, count=2)
    index = VectorMemoryStore(dim=2, max_elements=10)
    manager = TransferLearningManager(store, index)
    incompatible = source.model_copy(
        deep=True,
        update={"numeric_basis": basis.model_copy(update={"origin": "other-measurement"})},
    )
    _registered(manager, incompatible, originals, run_id="nearest-incompatible", embedding=[1, 0])
    malformed = _registered(
        manager, source, originals, run_id="next-malformed", embedding=[0.9, 0.1]
    )
    malformed = changed_history(
        store,
        malformed,
        lambda history: [row.update(stage_a_passed="false") for row in history["evaluations"]],
    )
    metadata = malformed.model_dump(mode="json", exclude={"history_ref", "embedding"})
    metadata["history_ref"] = malformed.history_ref.model_dump(mode="json")
    index.add(malformed.run_id, malformed.embedding, metadata)
    valid = _registered(manager, source, originals, run_id="valid", embedding=[0, 1])
    assert manager.find_similar_runs(target, top_k=1)[0].run_id == "nearest-incompatible"
    native_query = index.query
    calls = []

    def observed(*args, **kwargs):
        calls.append(kwargs["top_k"])
        return native_query(*args, **kwargs)

    monkeypatch.setattr(index, "query", observed)
    bridge = WarmStartBridge(manager, top_k_runs=1, max_evals=1)
    rows = bridge.load_warm_start(target)
    assert len(rows) == 1
    assert rows[0].metadata["transfer_history_ref"] == valid.history_ref.model_dump(mode="json")
    assert {
        key: bridge.last_load_report[key]
        for key in ("loaded", "accepted", "rejected", "selected", "unavailable")
    } == {
        "loaded": 6,
        "accepted": 2,
        "rejected": 4,
        "selected": 1,
        "unavailable": 0,
    }
    assert len(calls) == 1
    monkeypatch.setattr(index, "query", lambda *a, **k: pytest.fail("replay performed ANN"))
    assert bridge.admit_warm_start(rows, basis) == rows


def test_bridge_preserves_the_declared_limit_on_nonempty_admitted_sources(tmp_path):
    store, _, _, source, target, originals, _ = measured_history(tmp_path, count=4)
    index = VectorMemoryStore(dim=2, max_elements=10)
    manager = TransferLearningManager(store, index)
    first = _registered(manager, source, originals[:1], run_id="first", embedding=[1, 0])
    _registered(manager, source, originals[1:], run_id="second", embedding=[0, 1])
    bridge = WarmStartBridge(manager, top_k_runs=1, max_evals=4)
    rows = bridge.load_warm_start(target)
    assert len(rows) == 1
    assert rows[0].metadata["transfer_history_ref"] == first.history_ref.model_dump(mode="json")
    assert bridge.last_load_report["loaded"] == bridge.last_load_report["accepted"] == 1


def test_whole_catalog_query_captures_one_native_generation_during_publication(
    tmp_path, monkeypatch
):
    import hnswlib

    store, _, _, _, _, _, _ = measured_history(tmp_path, count=1)
    memory = VectorMemoryStore(dim=2, max_elements=5)
    memory.add("old-first", [1, 0], {"generation": "old"})
    memory.add("old-second", [0, 1], {"generation": "old"})
    replacement = VectorMemoryStore(dim=2, max_elements=5)
    for key, vector in (("new-first", [-1, 0]), ("new-second", [0, -1]), ("new-third", [1, 1])):
        replacement.add(key, vector, {"generation": "new"})
    ref = replacement.save_to_artifact(store)
    arrived, release = Event(), Event()
    native_query = hnswlib.Index.knn_query

    def paused(index, *args, **kwargs):
        result = native_query(index, *args, **kwargs)
        arrived.set()
        assert release.wait(10), "writer did not release captured catalog reader"
        return result

    monkeypatch.setattr(hnswlib.Index, "knn_query", paused)
    with ThreadPoolExecutor() as pool:
        reader = pool.submit(memory.query, [1, 0], top_k=None)
        try:
            assert arrived.wait(10), "reader did not execute native HNSW"
            memory.load_from_artifact(store, ref)
        finally:
            release.set()
        rows = reader.result(10)
    assert {key for key, _, _ in rows} == {"old-first", "old-second"}
    assert all(metadata == {"generation": "old"} for _, _, metadata in rows)
    current = memory.query([1, 0], top_k=None)
    assert {key for key, _, _ in current} == {"new-first", "new-second", "new-third"}
    assert all(metadata == {"generation": "new"} for _, _, metadata in current)
