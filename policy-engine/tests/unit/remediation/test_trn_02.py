"""Characterization tests for TRN-02 transfer history and native generations.

These tests intentionally describe the bounded B129/B133/B134 contract.  The
first commit is test-only: the expected failures are the evidence used before
the production repair is selected.
"""

from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent import vector_memory as vector_memory_module
from polisyos.scientist.agent.vector_memory import VectorMemoryStore


def test_discovery_preserves_history_ref_and_reads_cas_without_second_ann(
    tmp_path, monkeypatch
) -> None:
    """B129: ANN discovers only; exact CAS admission never performs a second ANN."""
    pytest.importorskip("hnswlib")
    from tests.unit.scientist.methods.search.strategies.test_transfer import measured_history

    _, index, manager, source, target, _, _ = measured_history(tmp_path, count=2)
    similar = manager.find_similar_runs(target, top_k=1)
    assert similar[0].history_ref == source.history_ref
    monkeypatch.setattr(index, "query", lambda *args, **kwargs: pytest.fail("second ANN query"))
    assert (
        len(manager.get_warm_start_evaluations(similar, max_evals=1, target_fingerprint=target))
        == 1
    )


def test_history_cache_is_bound_to_snapshot_and_consumer_sort_is_non_mutating(tmp_path) -> None:
    """B133: local cache keys exact CAS snapshots and copies consumer metadata."""
    pytest.importorskip("hnswlib")
    from tests.unit.scientist.methods.search.strategies.test_transfer import (
        changed_history,
        measured_history,
    )

    store, _, manager, source, target, _, _ = measured_history(tmp_path, count=2)
    originals = manager._load_run_evaluations(source)
    source_new = changed_history(store, source, lambda payload: payload["evaluations"].reverse())
    first = manager.get_warm_start_evaluations([source], max_evals=1, target_fingerprint=target)
    second = manager.get_warm_start_evaluations(
        [source_new], max_evals=1, target_fingerprint=target
    )
    assert first[0].candidate_id == second[0].candidate_id
    assert manager._load_run_evaluations(source) == originals
    assert manager.cache_info["entries"] == 2


def test_failed_native_add_does_not_publish_a_second_python_record() -> None:
    """B134: a native capacity error leaves the previous generation usable."""
    pytest.importorskip("hnswlib")
    memory = VectorMemoryStore(dim=2, max_elements=1)
    memory.add("first", [1.0, 0.0], {"origin": "first"})

    with pytest.raises(RuntimeError):
        memory.add("second", [0.0, 1.0], {"origin": "second"})

    assert len(memory) == 1
    assert [row[0] for row in memory.query([1.0, 0.0], top_k=1)] == ["first"]


def test_failed_native_load_does_not_publish_partial_bundle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """B134: controlled native load failure retains the prior generation."""
    pytest.importorskip("hnswlib")
    memory = VectorMemoryStore(dim=2, max_elements=2)
    memory.add("first", [1.0, 0.0], {"origin": "first"})
    store = FileSystemCAS(tmp_path / "cas")
    replacement = VectorMemoryStore(dim=2, max_elements=2)
    replacement.add("new", [0.0, 1.0], {})
    bundle_ref = replacement.save_to_artifact(store)

    class _ControlledLoadFailureIndex:
        def __init__(self, *, space: str, dim: int) -> None:
            del space, dim

        def load_index(self, path: str, *, max_elements: int) -> None:
            del path, max_elements
            raise RuntimeError("controlled native load failure")

        def set_ef(self, value: int) -> None:
            del value

    monkeypatch.setattr(
        vector_memory_module.hnswlib,
        "Index",
        _ControlledLoadFailureIndex,
    )

    with pytest.raises(RuntimeError):
        memory.load_from_artifact(store, bundle_ref)

    assert len(memory) == 1
    assert [row[0] for row in memory.query([1.0, 0.0], top_k=1)] == ["first"]


def test_native_roundtrip_preserves_one_small_generation(tmp_path) -> None:
    """B134 control: a valid small native bundle reloads intact."""
    pytest.importorskip("hnswlib")
    artifact_store = FileSystemCAS(tmp_path / "cas")
    memory = VectorMemoryStore(dim=2, max_elements=4)
    memory.add("first", [1.0, 0.0], {"origin": "first"})
    memory.add("second", [0.0, 1.0], {"origin": "second"})

    bundle_ref = memory.save_to_artifact(artifact_store)
    restored = VectorMemoryStore(dim=2, max_elements=4)
    restored.load_from_artifact(artifact_store, bundle_ref)

    assert len(restored) == 2
    assert {row[0] for row in restored.query([1.0, 0.0], top_k=2)} == {
        "first",
        "second",
    }
