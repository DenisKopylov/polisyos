"""Characterization tests for TRN-02 transfer history and native generations.

These tests intentionally describe the bounded B129/B133/B134 contract.  The
first commit is test-only: the expected failures are the evidence used before
the production repair is selected.
"""

from __future__ import annotations

import copy
import json
import struct
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import artifact_manifest_profile_sha256, input_ref_from_artifact_ref
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, CanonInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.agent import vector_memory as vector_memory_module
from polisyos.scientist.agent.vector_memory import VectorMemoryStore
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreStatus,
    ObjectiveValue,
    OptimizationDirection,
    _assess_search_metric,
    _configured_search_metric_rule_spec,
)
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
    source = {"metrics": {"score": score}, "metric_units": {"score": "points"}}
    assessment = _assess_search_metric(
        source, "score", OptimizationDirection.MINIMIZE.value, "points"
    )
    objective = ObjectiveValue(
        name="score",
        raw_value=score,
        direction=OptimizationDirection.MINIMIZE,
        score_status=ObjectiveScoreStatus.AVAILABLE,
        score_assessment=assessment,
    )
    return {
        "history_schema_version": "4",
        "candidate_id": candidate_id,
        "params": {"x": 0.5, "nested": {"labels": ["original"]}},
        "params_normalized": [0.5],
        "scalar_score": score,
        "stage_a_passed": True,
        "stage_b_result": source,
        "status": "success",
        "objectives": [
            {
                "name": objective.name,
                "raw_value": objective.raw_value,
                "direction": objective.direction.value,
                "score_status": objective.score_status.value,
                "score_assessment": assessment.to_payload(),
            }
        ],
        "score_status": assessment.status.value,
        "score_assessment": assessment.to_payload(),
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
        "objective_rule_specs": fingerprint.objective_rule_specs,
        "history_schema_version": "4",
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
        objective_rule_specs={
            "score": _configured_search_metric_rule_spec("score", "minimize", "points") or ""
        },
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
                    "objective_rule_specs": _fingerprint("source-run").objective_rule_specs,
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

    target = _fingerprint("target")
    similar = manager.find_similar_runs(target, top_k=1)

    assert len(similar) == 1
    assert similar[0].history_ref == history_ref
    evaluations = manager.get_warm_start_evaluations(
        similar, max_evals=1, target_fingerprint=target
    )

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

    first = manager.get_warm_start_evaluations(
        [old_snapshot], max_evals=1, target_fingerprint=_fingerprint("target")
    )

    assert [evaluation.candidate_id for evaluation in first] == ["old-low"]
    assert first[0].stage_b_result is not None
    first[0].params["nested"]["labels"].append("mutated")
    first[0].stage_b_result["metrics"]["coverage"].append(99)
    first[0].metadata["nested"]["labels"].append("mutated")

    old_replay = manager.get_warm_start_evaluations(
        [old_snapshot], max_evals=1, target_fingerprint=_fingerprint("target")
    )
    second = manager.get_warm_start_evaluations(
        [new_snapshot], max_evals=1, target_fingerprint=_fingerprint("target")
    )

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

    assert [
        row.candidate_id
        for row in manager.get_warm_start_evaluations(
            [source], 1, target_fingerprint=_fingerprint("target")
        )
    ] == ["candidate"]
    cache_key = manager._history_cache_key(history_ref, source)
    manager._eval_cache[cache_key] = b"x" * len(manager._eval_cache[cache_key])

    with pytest.raises(ValueError, match="Malformed transfer history artifact"):
        manager.get_warm_start_evaluations([source], 1, target_fingerprint=_fingerprint("target"))

    assert cache_key not in manager._eval_cache
    assert manager._eval_cache_bytes == 0
    assert [
        row.candidate_id
        for row in manager.get_warm_start_evaluations(
            [source], 1, target_fingerprint=_fingerprint("target")
        )
    ] == ["candidate"]
    assert store.reads == [history_ref, history_ref]


def test_failed_native_add_does_not_publish_a_second_python_record(tmp_path) -> None:
    """B134: capacity refusal preserves the complete prior generation."""
    pytest.importorskip("hnswlib")
    artifact_store = FileSystemCAS(tmp_path / "cas")
    memory = VectorMemoryStore(dim=3, max_elements=2, ef_construction=64, M=8)
    memory.add("first", [1.0, 0.0, 0.0], {"origin": "first", "nested": {"v": [1]}})
    memory.add("second", [0.0, 1.0, 0.0], {"origin": "second", "nested": {"v": [2]}})
    before = _capture_vector_memory_generation(memory)
    persisted_before = _capture_persisted_vector_memory(artifact_store, memory)

    with pytest.raises(RuntimeError, match="capacity exhausted"):
        memory.add("third", [0.0, 0.0, 1.0], {"origin": "third"})

    _assert_vector_memory_generation(memory, before)
    _assert_persisted_vector_memory(artifact_store, persisted_before)
    _assert_resaved_vector_memory(memory, artifact_store, before)


def test_failed_native_load_does_not_publish_partial_bundle(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B134: a genuine selected bundle reaching native load cannot partially publish."""
    pytest.importorskip("hnswlib")
    artifact_store = FileSystemCAS(tmp_path / "cas")

    source_memory = VectorMemoryStore(dim=3, max_elements=5)
    source_memory.add("replacement", [0.0, 0.0, 1.0], {"origin": "replacement"})
    source_bundle_ref = source_memory.save_to_artifact(artifact_store, emit_v2=True)
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
    assert source_bundle_manifest.artifact_schema == SchemaInfo(
        name="polisyos.scientist.VectorMemoryBundle", version="2.0"
    )
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
        "index_ref",
        "schema_version",
    }
    assert bundle["schema_version"] == "2.0"
    assert bundle["dim"] == 3
    assert bundle["max_elements"] == 5
    assert bundle["ef_construction"] == 200
    assert bundle["M"] == 16
    assert bundle["keys"] == ["replacement"]
    assert bundle["metadata"] == [{"origin": "replacement"}]

    index_id = ArtifactRef.model_validate(bundle["index_ref"])
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
        memory.load_from_artifact(store, selected_bundle_ref, allow_trusted_native=True)

    assert native_constructions == [("cosine", 3)]
    assert native_loads == [(3, 5, len(index_bytes))]
    assert store.reads == [selected_bundle_ref, index_id]
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

    bundle_ref = memory.save_to_artifact(artifact_store, emit_v2=True)
    restored = VectorMemoryStore(dim=2, max_elements=4)
    restored.load_from_artifact(artifact_store, bundle_ref, allow_trusted_native=True)

    assert len(restored) == 2
    assert {row[0] for row in restored.query([1.0, 0.0], top_k=2)} == {
        "first",
        "second",
    }


class _BundleProfileOverrideStore:
    """Test-only writer that alters one bundle field before the real CAS write."""

    def __init__(self, store: FileSystemCAS, overrides: dict[str, Any]) -> None:
        self._store = store
        self._overrides = overrides

    def __getattr__(self, name: str) -> Any:
        return getattr(self._store, name)

    def put_json(
        self,
        obj: object,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        if opts.kind == "vector_memory.bundle":
            if not isinstance(obj, dict):
                raise AssertionError("vector-memory producer did not write an object bundle")
            obj = {**obj, **self._overrides}
        return self._store.put_json(
            obj,
            opts,
            canon_spec,
            return_selected_profile=return_selected_profile,
        )


def _capture_vector_memory_generation(memory: VectorMemoryStore) -> dict[str, Any]:
    query_vectors: list[list[float]] = []
    for axis in range(memory.dim):
        vector = [0.0] * memory.dim
        vector[axis] = 1.0
        query_vectors.append(vector)
    queries = [
        (
            vector,
            [
                (key, distance, copy.deepcopy(metadata))
                for key, distance, metadata in memory.query(vector, top_k=len(memory))
            ],
        )
        for vector in query_vectors
    ]
    return {
        "configuration": (
            memory._get_generation().dim,
            memory._get_generation().max_elements,
            memory._get_generation().ef_construction,
            memory._get_generation().M,
        ),
        "keys": list(memory._get_generation().keys),
        "metadata": list(copy.deepcopy(memory._get_generation().metadata)),
        "key_to_idx": dict(memory._get_generation().key_to_idx),
        "native_bytes": memory._save_index_bytes(),
        "queries": queries,
    }


def _assert_vector_memory_generation(
    memory: VectorMemoryStore,
    expected: dict[str, Any],
    *,
    compare_native_bytes: bool = True,
) -> None:
    assert (
        memory._get_generation().dim,
        memory._get_generation().max_elements,
        memory._get_generation().ef_construction,
        memory._get_generation().M,
    ) == expected["configuration"]
    assert list(memory._get_generation().keys) == expected["keys"]
    assert list(memory._get_generation().metadata) == expected["metadata"]
    assert memory._get_generation().key_to_idx == expected["key_to_idx"]
    if compare_native_bytes:
        assert memory._save_index_bytes() == expected["native_bytes"]
    for vector, expected_rows in expected["queries"]:
        rows = memory.query(vector, top_k=len(memory))
        assert [row[0] for row in rows] == [row[0] for row in expected_rows]
        assert [row[1] for row in rows] == pytest.approx([row[1] for row in expected_rows])
        assert [row[2] for row in rows] == [row[2] for row in expected_rows]


def _selected_vector_memory_bundle(
    store: FileSystemCAS,
    bundle_ref: ArtifactRef,
) -> tuple[ArtifactRef, Any]:
    manifest = store.get_manifest(bundle_ref)
    selected_ref = ArtifactRef(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=artifact_manifest_profile_sha256(manifest),
    )
    return selected_ref, manifest


def _capture_persisted_vector_memory(
    store: FileSystemCAS,
    memory: VectorMemoryStore,
) -> dict[str, Any]:
    bundle_ref, _ = _selected_vector_memory_bundle(
        store, memory.save_to_artifact(store, emit_v2=True)
    )
    bundle_manifest = store.get_manifest(bundle_ref)
    bundle_bytes = store.get_bytes(bundle_ref)
    bundle = json.loads(bundle_bytes)
    index_id = ArtifactRef.model_validate(bundle["index_ref"])
    return {
        "bundle_ref": bundle_ref,
        "bundle_manifest": bundle_manifest,
        "bundle_bytes": bundle_bytes,
        "index_id": index_id,
        "index_manifest": store.get_manifest(index_id),
        "index_bytes": store.get_bytes(index_id),
    }


def _assert_persisted_vector_memory(
    store: FileSystemCAS,
    expected: dict[str, Any],
) -> None:
    assert store.get_manifest(expected["bundle_ref"]) == expected["bundle_manifest"]
    assert store.get_bytes(expected["bundle_ref"]) == expected["bundle_bytes"]
    assert store.get_manifest(expected["index_id"]) == expected["index_manifest"]
    assert store.get_bytes(expected["index_id"]) == expected["index_bytes"]


def _assert_resaved_vector_memory(
    memory: VectorMemoryStore,
    store: FileSystemCAS,
    expected: dict[str, Any],
) -> None:
    bundle_ref, _ = _selected_vector_memory_bundle(
        store, memory.save_to_artifact(store, emit_v2=True)
    )
    restored = VectorMemoryStore(dim=1, max_elements=1)
    restored.load_from_artifact(store, bundle_ref, allow_trusted_native=True)
    _assert_vector_memory_generation(restored, expected, compare_native_bytes=False)


def _populate_vector_memory(
    memory: VectorMemoryStore,
    prefix: str,
    *,
    count: int = 3,
) -> None:
    vectors = (
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    )
    for index, vector in enumerate(vectors[:count]):
        memory.add(
            f"{prefix}-{index}",
            vector,
            {"origin": f"{prefix}-{index}", "nested": {"positions": [index, index + 1]}},
        )


def test_failed_native_update_preserves_complete_prior_generation(tmp_path) -> None:
    """B134: a wrong-shaped update leaves vector, label, and metadata unchanged."""
    pytest.importorskip("hnswlib")
    artifact_store = FileSystemCAS(tmp_path / "cas")
    memory = VectorMemoryStore(dim=3, max_elements=4, ef_construction=64, M=8)
    _populate_vector_memory(memory, "prior")
    before = _capture_vector_memory_generation(memory)
    persisted_before = _capture_persisted_vector_memory(artifact_store, memory)

    with pytest.raises(ValueError, match="dimension mismatch"):
        memory.add("prior-0", [1.0, 0.0], {"origin": "replacement"})

    _assert_vector_memory_generation(memory, before)
    _assert_persisted_vector_memory(artifact_store, persisted_before)
    _assert_resaved_vector_memory(memory, artifact_store, before)


def test_native_capacity_mismatch_refuses_before_load_and_preserves_generation(
    tmp_path,
) -> None:
    """B134: the application rejects a capacity mismatch before native load."""
    pytest.importorskip("hnswlib")
    artifact_store = FileSystemCAS(tmp_path / "cas")

    prior_memory = VectorMemoryStore(dim=3, max_elements=5, ef_construction=64, M=8)
    _populate_vector_memory(prior_memory, "prior")
    before = _capture_vector_memory_generation(prior_memory)
    persisted_before = _capture_persisted_vector_memory(artifact_store, prior_memory)

    candidate_source = VectorMemoryStore(dim=3, max_elements=5, ef_construction=128, M=12)
    _populate_vector_memory(candidate_source, "candidate", count=2)
    candidate_bundle_ref = candidate_source.save_to_artifact(
        _BundleProfileOverrideStore(artifact_store, {"max_elements": 1}), emit_v2=True
    )
    selected_bundle_ref, candidate_bundle_manifest = _selected_vector_memory_bundle(
        artifact_store,
        candidate_bundle_ref,
    )
    assert selected_bundle_ref.manifest_profile_sha256 is not None
    assert candidate_bundle_manifest.kind == "vector_memory.bundle"
    assert candidate_bundle_manifest.media_type == "application/json"

    bundle_bytes = artifact_store.get_bytes(selected_bundle_ref)
    bundle = json.loads(bundle_bytes)
    assert bundle["max_elements"] == 1
    assert len(bundle["keys"]) == 2
    index_id = ArtifactRef.model_validate(bundle["index_ref"])
    index_manifest = artifact_store.get_manifest(index_id)
    index_bytes = artifact_store.get_bytes(index_id)
    assert index_manifest.kind == "vector_memory.index"
    assert index_manifest.media_type == "application/octet-stream"
    assert index_manifest.byte_size == len(index_bytes) == bundle["index_bytes_len"]

    store = _CountingStore(artifact_store)
    # The record-shape guard refuses a native capacity mismatch before native load.
    with pytest.raises(
        ValueError,
        match="Vector memory native header does not match bundle configuration",
    ):
        prior_memory.load_from_artifact(store, selected_bundle_ref, allow_trusted_native=True)

    assert store.reads == [selected_bundle_ref, index_id]
    _assert_vector_memory_generation(prior_memory, before)
    _assert_persisted_vector_memory(artifact_store, persisted_before)
    _assert_resaved_vector_memory(prior_memory, artifact_store, before)


def test_truncated_native_index_refuses_and_preserves_generation(tmp_path) -> None:
    """B134: a bounded truncated native member is rejected before publication."""
    pytest.importorskip("hnswlib")
    artifact_store = FileSystemCAS(tmp_path / "cas")

    prior_memory = VectorMemoryStore(dim=3, max_elements=5, ef_construction=64, M=8)
    _populate_vector_memory(prior_memory, "prior")
    before = _capture_vector_memory_generation(prior_memory)
    persisted_before = _capture_persisted_vector_memory(artifact_store, prior_memory)

    candidate_source = VectorMemoryStore(dim=3, max_elements=7, ef_construction=128, M=12)
    _populate_vector_memory(candidate_source, "candidate", count=3)
    producer_bundle_ref = candidate_source.save_to_artifact(artifact_store, emit_v2=True)
    selected_producer_ref, producer_bundle_manifest = _selected_vector_memory_bundle(
        artifact_store,
        producer_bundle_ref,
    )
    assert selected_producer_ref.manifest_profile_sha256 is not None
    assert producer_bundle_manifest.kind == "vector_memory.bundle"
    assert producer_bundle_manifest.media_type == "application/json"
    assert producer_bundle_manifest.artifact_schema == SchemaInfo(
        name="polisyos.scientist.VectorMemoryBundle", version="2.0"
    )
    assert producer_bundle_manifest.canon == CanonInfo.from_spec(CanonSpec(forbid_floats=False))

    producer_bundle_bytes = artifact_store.get_bytes(selected_producer_ref)
    producer_bundle = json.loads(producer_bundle_bytes)
    producer_index_id = ArtifactRef.model_validate(producer_bundle["index_ref"])
    producer_index_manifest = artifact_store.get_manifest(producer_index_id)
    producer_index_bytes = artifact_store.get_bytes(producer_index_id)
    assert producer_index_manifest.kind == "vector_memory.index"
    assert producer_index_manifest.media_type == "application/octet-stream"
    assert producer_index_manifest.byte_size == len(producer_index_bytes)
    assert producer_bundle["index_bytes_len"] == len(producer_index_bytes)
    assert len(producer_index_bytes) > 4

    # The v0.8.0 writer emits these native POD fields consecutively, followed by
    # cur_element_count * size_data_per_element bytes and then per-row link-list
    # sizes. Truncate exactly at the first link-list size. loadIndex's preflight
    # is rejected before native load or allocation.
    size_t_bytes = struct.calcsize("@N")
    current_count = struct.unpack_from("@N", producer_index_bytes, 2 * size_t_bytes)[0]
    size_data_per_element = struct.unpack_from("@N", producer_index_bytes, 3 * size_t_bytes)[0]
    header_bytes = (
        10 * size_t_bytes + struct.calcsize("@i") + struct.calcsize("@I") + struct.calcsize("@d")
    )
    link_lists_offset = header_bytes + current_count * size_data_per_element
    assert current_count == len(producer_bundle["keys"]) > 0
    assert 0 < link_lists_offset < len(producer_index_bytes)
    truncated_index_bytes = producer_index_bytes[:link_lists_offset]
    assert len(truncated_index_bytes) == link_lists_offset
    assert len(truncated_index_bytes) < len(producer_index_bytes)
    truncated_index_ref = artifact_store.put_bytes(
        truncated_index_bytes,
        PutOptions(kind="vector_memory.index", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    truncated_index_manifest = artifact_store.get_manifest(truncated_index_ref)
    assert truncated_index_ref.artifact_id != producer_index_id.artifact_id
    assert truncated_index_manifest.kind == producer_index_manifest.kind
    assert truncated_index_manifest.media_type == producer_index_manifest.media_type
    assert truncated_index_manifest.artifact_schema == producer_index_manifest.artifact_schema
    assert truncated_index_manifest.canon == producer_index_manifest.canon
    assert truncated_index_manifest.byte_size == len(truncated_index_bytes)
    assert artifact_store.get_bytes(truncated_index_ref) == truncated_index_bytes

    corrupted_bundle = dict(producer_bundle)
    corrupted_bundle["index_ref"] = truncated_index_ref.model_dump(mode="json")
    corrupted_bundle["index_bytes_len"] = len(truncated_index_bytes)
    assert {
        key: value
        for key, value in corrupted_bundle.items()
        if key not in {"index_ref", "index_bytes_len"}
    } == {
        key: value
        for key, value in producer_bundle.items()
        if key not in {"index_ref", "index_bytes_len"}
    }
    corrupted_bundle_ref = artifact_store.put_json(
        corrupted_bundle,
        PutOptions(
            kind="vector_memory.bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.VectorMemoryBundle", version="2.0"),
            inputs=[input_ref_from_artifact_ref(truncated_index_ref, role="vector_memory_index")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    selected_corrupted_ref, corrupted_bundle_manifest = _selected_vector_memory_bundle(
        artifact_store,
        corrupted_bundle_ref,
    )
    assert selected_corrupted_ref.manifest_profile_sha256 is not None
    assert selected_corrupted_ref.artifact_id != selected_producer_ref.artifact_id
    assert corrupted_bundle_manifest.kind == producer_bundle_manifest.kind
    assert corrupted_bundle_manifest.media_type == producer_bundle_manifest.media_type
    assert corrupted_bundle_manifest.artifact_schema == producer_bundle_manifest.artifact_schema
    assert corrupted_bundle_manifest.canon == producer_bundle_manifest.canon
    assert artifact_store.get_manifest(selected_corrupted_ref) == corrupted_bundle_manifest
    assert artifact_store.get_bytes(selected_corrupted_ref) == artifact_store.get_bytes(
        corrupted_bundle_ref
    )

    # The selected corrupt clone has a fresh identity; its producer artifact and
    # original member remain byte-for-byte intact.
    assert artifact_store.get_manifest(selected_producer_ref) == producer_bundle_manifest
    assert artifact_store.get_bytes(selected_producer_ref) == producer_bundle_bytes
    assert artifact_store.get_bytes(producer_index_id) == producer_index_bytes
    persisted_corrupted_bundle = json.loads(artifact_store.get_bytes(selected_corrupted_ref))
    assert persisted_corrupted_bundle["index_ref"] == truncated_index_ref.model_dump(mode="json")
    assert persisted_corrupted_bundle["index_bytes_len"] == len(truncated_index_bytes)

    store = _CountingStore(artifact_store)
    with pytest.raises(ValueError, match="Vector memory native links are truncated"):
        prior_memory.load_from_artifact(store, selected_corrupted_ref, allow_trusted_native=True)

    assert store.reads == [selected_corrupted_ref, truncated_index_ref]
    _assert_vector_memory_generation(prior_memory, before)
    _assert_persisted_vector_memory(artifact_store, persisted_before)
    _assert_resaved_vector_memory(prior_memory, artifact_store, before)


@pytest.mark.parametrize(
    "keys_override",
    [
        ["candidate-0", ["unhashable"]],
        ["candidate-0", "candidate-0"],
    ],
    ids=["unhashable-key", "duplicate-key"],
)
def test_malformed_candidate_keys_refuse_before_native_load_and_preserve_generation(
    tmp_path,
    keys_override: list[Any],
) -> None:
    """Malformed present keys cannot fail after candidate fields are published."""
    pytest.importorskip("hnswlib")
    artifact_store = FileSystemCAS(tmp_path / "cas")

    prior_memory = VectorMemoryStore(dim=3, max_elements=5, ef_construction=64, M=8)
    _populate_vector_memory(prior_memory, "prior")
    before = _capture_vector_memory_generation(prior_memory)
    persisted_before = _capture_persisted_vector_memory(artifact_store, prior_memory)

    candidate_source = VectorMemoryStore(dim=3, max_elements=5)
    _populate_vector_memory(candidate_source, "candidate", count=2)
    candidate_bundle_ref = candidate_source.save_to_artifact(
        _BundleProfileOverrideStore(artifact_store, {"keys": keys_override}), emit_v2=True
    )
    selected_bundle_ref, _ = _selected_vector_memory_bundle(
        artifact_store,
        candidate_bundle_ref,
    )

    store = _CountingStore(artifact_store)
    with pytest.raises(ValueError, match="keys"):
        prior_memory.load_from_artifact(store, selected_bundle_ref, allow_trusted_native=True)

    assert store.reads == [selected_bundle_ref]
    _assert_vector_memory_generation(prior_memory, before)
    _assert_persisted_vector_memory(artifact_store, persisted_before)
    _assert_resaved_vector_memory(prior_memory, artifact_store, before)
