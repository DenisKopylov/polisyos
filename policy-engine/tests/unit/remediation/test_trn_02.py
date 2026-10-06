"""Characterization tests for TRN-02 transfer history and native generations.

These tests intentionally describe the bounded B129/B133/B134 contract.  The
first commit is test-only: the expected failures are the evidence used before
the production repair is selected.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent import vector_memory as vector_memory_module
from polisyos.scientist.agent.vector_memory import VectorMemoryStore
from polisyos.scientist.methods.search.objective import OptimizationDirection
from polisyos.scientist.methods.search.strategies.transfer import (
    RunFingerprint,
    TransferLearningManager,
)


def _artifact_ref(seed: str) -> ArtifactRef:
    """Build a deterministic artifact reference for an isolated test payload."""
    return ArtifactRef(
        artifact_id=f"sha256:{seed * 64}",
        kind="search.transfer.history",
        media_type="application/json",
    )


def _stored_eval(candidate_id: str, score: float, run_id: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "params": {"x": 0.5},
        "params_normalized": [0.5],
        "scalar_score": score,
        "stage_a_passed": True,
        "status": "success",
        "objectives": [
            {
                "name": "score",
                "raw_value": score,
                "direction": OptimizationDirection.MINIMIZE.value,
            }
        ],
        "provenance_ref": str(_artifact_ref("e").artifact_id),
        "metadata": {"source_run_id": run_id},
    }


def _history_payload(
    run_id: str,
    *rows: tuple[str, float],
) -> bytes:
    return json.dumps(
        {
            "run_id": run_id,
            "evaluations": [
                _stored_eval(candidate_id, score, run_id) for candidate_id, score in rows
            ],
        }
    ).encode("utf-8")


def _fingerprint(run_id: str, *, embedding: list[float] | None = None) -> RunFingerprint:
    return RunFingerprint(
        run_id=run_id,
        space_hash="space-v1",
        objective_names=["score"],
        bounds={"x": [0.0, 1.0]},
        split="selection",
        units={"score": "points"},
        origin="simulator-v1",
        tenant_id="tenant-a",
        objective_directions={"score": OptimizationDirection.MINIMIZE.value},
        embedding=embedding or [0.1, 0.2],
    )


class _ReadStore:
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self._payloads = payloads
        self.reads: list[str] = []

    def get_bytes(self, artifact_id: object) -> bytes:
        key = str(artifact_id)
        self.reads.append(key)
        return self._payloads[key]


class _DiscoveryIndex:
    dim = 2

    def __init__(self, *, history_ref: ArtifactRef) -> None:
        self.history_ref = history_ref
        self.query_calls: list[tuple[list[float], int]] = []

    def query(
        self,
        embedding: list[float],
        top_k: int,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        self.query_calls.append((embedding, top_k))
        if len(self.query_calls) > 1:
            raise AssertionError(
                "history loading must use the discovered ArtifactRef, not a second ANN query"
            )
        return [
            (
                "source-run",
                0.01,
                {
                    "space_hash": "space-v1",
                    "objective_names": ["score"],
                    "bounds": {"x": [0.0, 1.0]},
                    "split": "selection",
                    "units": {"score": "points"},
                    "origin": "simulator-v1",
                    "tenant_id": "tenant-a",
                    "objective_directions": {"score": OptimizationDirection.MINIMIZE.value},
                    "artifact_id": str(self.history_ref.artifact_id),
                },
            )
        ]


class _BundleStore:
    def __init__(self, bundle_ref: ArtifactRef, index_ref: ArtifactRef) -> None:
        self.bundle_ref = bundle_ref
        self.index_ref = index_ref

    def get_bytes(self, artifact_id: object) -> bytes:
        artifact_id = getattr(artifact_id, "artifact_id", artifact_id)
        if str(artifact_id) == str(self.bundle_ref.artifact_id):
            return json.dumps(
                {
                    "dim": 2,
                    "max_elements": 2,
                    "ef_construction": 200,
                    "M": 16,
                    "keys": ["new-key"],
                    "metadata": [{}],
                    "index_artifact_id": str(self.index_ref.artifact_id),
                }
            ).encode("utf-8")
        if str(artifact_id) == str(self.index_ref.artifact_id):
            return b"controlled-load-failure-payload"
        raise KeyError(str(artifact_id))


def test_discovery_preserves_history_ref_and_reads_cas_without_second_ann() -> None:
    """B129: discovery must carry the selected immutable history address."""
    history_ref = _artifact_ref("a")
    store = _ReadStore(
        {str(history_ref.artifact_id): _history_payload("source-run", ("candidate", 0.5))}
    )
    index = _DiscoveryIndex(history_ref=history_ref)
    manager = TransferLearningManager(store, index)

    similar = manager.find_similar_runs(_fingerprint("target"), top_k=1)

    assert len(similar) == 1
    assert similar[0].history_ref == history_ref
    evaluations = manager.get_warm_start_evaluations(similar, max_evals=1)

    assert [evaluation.candidate_id for evaluation in evaluations] == ["candidate"]
    assert len(index.query_calls) == 1
    assert store.reads == [str(history_ref.artifact_id)]


def test_history_cache_is_bound_to_snapshot_and_consumer_sort_is_non_mutating() -> None:
    """B133: cache identity is the immutable history snapshot, not run_id."""
    old_ref = _artifact_ref("b")
    new_ref = _artifact_ref("c")
    store = _ReadStore(
        {
            str(old_ref.artifact_id): _history_payload(
                "same-run", ("old-high", 9.0), ("old-low", 1.0)
            ),
            str(new_ref.artifact_id): _history_payload("same-run", ("new", 8.0)),
        }
    )
    manager = TransferLearningManager(store, _DiscoveryIndex(history_ref=old_ref))
    old_snapshot = _fingerprint("same-run")
    old_snapshot.history_ref = old_ref
    new_snapshot = _fingerprint("same-run")
    new_snapshot.history_ref = new_ref

    first = manager.get_warm_start_evaluations([old_snapshot], max_evals=1)
    second = manager.get_warm_start_evaluations([new_snapshot], max_evals=1)

    assert [evaluation.candidate_id for evaluation in first] == ["old-low"]
    assert [evaluation.candidate_id for evaluation in second] == ["new"]
    assert store.reads == [str(old_ref.artifact_id), str(new_ref.artifact_id)]


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
