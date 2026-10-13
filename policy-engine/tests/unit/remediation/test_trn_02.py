"""Characterization tests for TRN-02 transfer history and native generations.

These tests intentionally describe the bounded B129/B133/B134 contract.  The
first commit is test-only: the expected failures are the evidence used before
the production repair is selected.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, CanonInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
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
        "params": {"x": 0.5, "nested": {"labels": ["original"]}},
        "params_normalized": [0.5],
        "scalar_score": score,
        "stage_a_passed": True,
        "stage_b_result": {"metrics": {"coverage": [1, 2]}},
        "status": "success",
        "objectives": [
            {
                "name": "score",
                "raw_value": score,
                "direction": OptimizationDirection.MINIMIZE.value,
            }
        ],
        "provenance_ref": str(_artifact_ref("e").artifact_id),
        "metadata": {
            "source_run_id": run_id,
            "nested": {"labels": ["original"]},
        },
    }


def _history_document(
    run_id: str,
    *rows: tuple[str, float],
) -> dict[str, Any]:
    fingerprint = _fingerprint(run_id)
    return {
        "run_id": run_id,
        "space_hash": fingerprint.space_hash,
        "objective_names": fingerprint.objective_names,
        "bounds": fingerprint.bounds,
        "split": fingerprint.split,
        "units": fingerprint.units,
        "origin": fingerprint.origin,
        "tenant_id": fingerprint.tenant_id,
        "objective_directions": fingerprint.objective_directions,
        "evaluations": [_stored_eval(candidate_id, score, run_id) for candidate_id, score in rows],
    }


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


class _CountingStore:
    def __init__(self, store: FileSystemCAS) -> None:
        self.store = store
        self.reads: list[ArtifactID | ArtifactRef | str] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self.store, name)

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        self.reads.append(artifact_id)
        return self.store.get_bytes(artifact_id)


def _write_history(
    store: FileSystemCAS,
    run_id: str,
    *rows: tuple[str, float],
) -> ArtifactRef:
    return store.put_json(
        _history_document(run_id, *rows),
        PutOptions(kind="search.transfer.history", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


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
                    "manifest_profile_sha256": self.history_ref.manifest_profile_sha256,
                },
            )
        ]


def test_discovery_preserves_history_ref_and_reads_cas_without_second_ann(tmp_path) -> None:
    """B129: discovery carries the exact selected immutable history address."""
    artifact_store = FileSystemCAS(tmp_path / "cas")
    history_ref = _write_history(
        artifact_store,
        "source-run",
        ("candidate", 0.5),
    )
    store = _CountingStore(artifact_store)
    index = _DiscoveryIndex(history_ref=history_ref)
    manager = TransferLearningManager(store, index)

    similar = manager.find_similar_runs(_fingerprint("target"), top_k=1)

    assert len(similar) == 1
    assert similar[0].history_ref == history_ref
    evaluations = manager.get_warm_start_evaluations(similar, max_evals=1)

    assert [evaluation.candidate_id for evaluation in evaluations] == ["candidate"]
    assert len(index.query_calls) == 1
    assert store.reads == [history_ref]


def test_history_cache_is_bound_to_snapshot_and_consumer_sort_is_non_mutating(
    tmp_path,
) -> None:
    """B133: cache identity is the full immutable view, and decoded consumers never alias it."""
    artifact_store = FileSystemCAS(tmp_path / "cas")
    old_ref = _write_history(
        artifact_store,
        "same-run",
        ("old-high", 9.0),
        ("old-low", 1.0),
    )
    new_ref = _write_history(artifact_store, "same-run", ("new", 8.0))
    store = _CountingStore(artifact_store)
    manager = TransferLearningManager(store, _DiscoveryIndex(history_ref=old_ref))
    old_snapshot = _fingerprint("same-run")
    old_snapshot.history_ref = old_ref
    new_snapshot = _fingerprint("same-run")
    new_snapshot.history_ref = new_ref

    first = manager.get_warm_start_evaluations([old_snapshot], max_evals=1)

    assert [evaluation.candidate_id for evaluation in first] == ["old-low"]
    assert first[0].stage_b_result is not None
    first[0].params["nested"]["labels"].append("mutated")
    first[0].stage_b_result["metrics"]["coverage"].append(99)
    first[0].metadata["nested"]["labels"].append("mutated")

    old_replay = manager.get_warm_start_evaluations([old_snapshot], max_evals=1)
    second = manager.get_warm_start_evaluations([new_snapshot], max_evals=1)

    assert [evaluation.candidate_id for evaluation in old_replay] == ["old-low"]
    assert old_replay[0].params["nested"]["labels"] == ["original"]
    assert old_replay[0].stage_b_result == {"metrics": {"coverage": [1, 2]}}
    assert old_replay[0].metadata["nested"]["labels"] == ["original"]
    assert [evaluation.candidate_id for evaluation in second] == ["new"]
    assert store.reads == [old_ref, new_ref]


def test_cached_history_bytes_are_revalidated_before_reuse(tmp_path) -> None:
    """A corrupt in-memory byte entry refuses; the next read reacquires the CAS bytes."""
    artifact_store = FileSystemCAS(tmp_path / "cas")
    history_ref = _write_history(
        artifact_store,
        "same-run",
        ("candidate", 1.0),
    )
    store = _CountingStore(artifact_store)
    manager = TransferLearningManager(store, _DiscoveryIndex(history_ref=history_ref))
    source = _fingerprint("same-run")
    source.history_ref = history_ref

    assert [row.candidate_id for row in manager.get_warm_start_evaluations([source], 1)] == [
        "candidate"
    ]
    cache_key = manager._history_cache_key(history_ref, source)
    manager._eval_cache[cache_key] = b"x" * len(manager._eval_cache[cache_key])

    with pytest.raises(ValueError, match="Malformed transfer history artifact"):
        manager.get_warm_start_evaluations([source], 1)

    assert cache_key not in manager._eval_cache
    assert manager._eval_cache_bytes == 0
    assert [row.candidate_id for row in manager.get_warm_start_evaluations([source], 1)] == [
        "candidate"
    ]
    assert store.reads == [history_ref, history_ref]


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
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B134: a genuine selected bundle reaching native load cannot partially publish."""
    pytest.importorskip("hnswlib")
    artifact_store = FileSystemCAS(tmp_path / "cas")

    source_memory = VectorMemoryStore(dim=3, max_elements=5)
    source_memory.add("replacement", [0.0, 0.0, 1.0], {"origin": "replacement"})
    source_bundle_ref = source_memory.save_to_artifact(artifact_store)
    source_bundle_manifest = artifact_store.get_manifest(source_bundle_ref)
    selected_bundle_ref = ArtifactRef(
        artifact_id=source_bundle_manifest.artifact_id,
        kind=source_bundle_manifest.kind,
        media_type=source_bundle_manifest.media_type,
        manifest_profile_sha256=artifact_manifest_profile_sha256(source_bundle_manifest),
    )

    assert selected_bundle_ref.manifest_profile_sha256 is not None
    assert source_bundle_manifest.kind == "vector_memory.bundle"
    assert source_bundle_manifest.media_type == "application/json"
    assert source_bundle_manifest.artifact_schema is None
    assert source_bundle_manifest.canon == CanonInfo.from_spec(CanonSpec(forbid_floats=False))
    assert artifact_store.get_manifest(selected_bundle_ref) == source_bundle_manifest

    bundle = json.loads(artifact_store.get_bytes(selected_bundle_ref))
    assert set(bundle) == {
        "dim",
        "max_elements",
        "ef_construction",
        "M",
        "keys",
        "metadata",
        "index_bytes_len",
        "index_artifact_id",
    }
    assert bundle["dim"] == 3
    assert bundle["max_elements"] == 5
    assert bundle["ef_construction"] == 200
    assert bundle["M"] == 16
    assert bundle["keys"] == ["replacement"]
    assert bundle["metadata"] == [{"origin": "replacement"}]

    index_id = ArtifactID.model_validate(bundle["index_artifact_id"])
    index_manifest = artifact_store.get_manifest(index_id)
    index_bytes = artifact_store.get_bytes(index_id)
    assert index_manifest.kind == "vector_memory.index"
    assert index_manifest.media_type == "application/octet-stream"
    assert index_manifest.byte_size == len(index_bytes) == bundle["index_bytes_len"]

    memory = VectorMemoryStore(dim=2, max_elements=2)
    memory.add("first", [1.0, 0.0], {"origin": "first"})
    native_constructions: list[tuple[str, int]] = []
    native_loads: list[tuple[int, int, int]] = []

    class _ControlledLoadFailureIndex:
        def __init__(self, *, space: str, dim: int) -> None:
            native_constructions.append((space, dim))
            self.dim = dim

        def load_index(self, path: str, *, max_elements: int) -> None:
            loaded_bytes = Path(path).read_bytes()
            assert loaded_bytes == index_bytes
            native_loads.append((self.dim, max_elements, len(loaded_bytes)))
            raise RuntimeError("controlled native load failure")

        def set_ef(self, value: int) -> None:
            del value

    monkeypatch.setattr(
        vector_memory_module.hnswlib,
        "Index",
        _ControlledLoadFailureIndex,
    )

    store = _CountingStore(artifact_store)
    with pytest.raises(RuntimeError, match="controlled native load failure"):
        memory.load_from_artifact(store, selected_bundle_ref)

    assert native_constructions == [("cosine", 3)]
    assert native_loads == [(3, 5, len(index_bytes))]
    assert store.reads == [selected_bundle_ref, str(index_id)]
    assert memory.dim == 2
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
