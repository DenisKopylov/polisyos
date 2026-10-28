"""Behavioral witnesses for vector-memory generation and CAS custody."""

from __future__ import annotations

import inspect
import json
import struct
import sys
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import input_ref_from_artifact_ref
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.agent.vector_memory import VectorMemoryStore


class _PortableIndex:
    """Deterministic stand-in for the HNSW protocol, not native proof."""

    def __init__(self, *, space: str, dim: int) -> None:
        del space
        self.dim = dim
        self.max_elements = 0
        self.M = 16
        self.ef_construction = 200
        self.rows: dict[int, list[float]] = {}

    def init_index(self, *, max_elements: int, **options: Any) -> None:
        self.max_elements = max_elements
        self.M = min(options.get("M", 16), 10000)
        self.ef_construction = max(options.get("ef_construction", 200), self.M)

    def set_ef(self, _: int) -> None:
        return

    def add_items(self, embeddings: list[list[float]], labels: list[int]) -> None:
        for embedding, label in zip(embeddings, labels, strict=True):
            self.rows[int(label)] = list(embedding)

    def knn_query(
        self, embeddings: list[list[float]], *, k: int
    ) -> tuple[list[list[int]], list[list[float]]]:
        query = embeddings[0]
        ranked = sorted(
            (
                (sum((a - b) ** 2 for a, b in zip(row, query, strict=True)), label)
                for label, row in self.rows.items()
            )
        )[:k]
        return [[label for _, label in ranked]], [[distance for distance, _ in ranked]]

    def save_index(self, path: str) -> None:
        offset_data = 2 * self.M * 4 + 4
        label_offset = offset_data + self.dim * 4
        row_size = label_offset + 8
        header = struct.pack(
            "<6QiI3QdQ",
            0,
            self.max_elements,
            len(self.rows),
            row_size,
            label_offset,
            offset_data,
            0,
            0,
            self.M,
            self.M * 2,
            self.M,
            1.0,
            self.ef_construction,
        )
        records = []
        for label, vector in self.rows.items():
            row = bytearray(row_size)
            struct.pack_into(f"<{self.dim}f", row, offset_data, *vector)
            struct.pack_into("<Q", row, label_offset, label)
            records.append(bytes(row))
        Path(path).write_bytes(header + b"".join(records) + b"\x00\x00\x00\x00" * len(records))

    def load_index(self, path: str, *, max_elements: int) -> None:
        data = Path(path).read_bytes()
        fields = struct.unpack_from("<6QiI3QdQ", data)
        _, _, count, row_size, label_offset, offset_data, _, _, m, _, _, _, ef = fields
        self.max_elements = max_elements
        self.M = m
        self.ef_construction = ef
        self.rows = {}
        pos = struct.calcsize("<6QiI3QdQ")
        for i in range(count):
            label = struct.unpack_from("<Q", data, pos + i * row_size + label_offset)[0]
            vector = struct.unpack_from(f"<{self.dim}f", data, pos + i * row_size + offset_data)
            self.rows[label] = list(vector)

    def get_items(self, labels: list[int]) -> list[list[float]]:
        return [list(self.rows[label]) for label in labels]

    def get_current_count(self) -> int:
        return len(self.rows)

    def get_max_elements(self) -> int:
        return self.max_elements

    def get_ids_list(self) -> list[int]:
        return list(self.rows)


@pytest.fixture(autouse=True)
def _portable_hnsw(monkeypatch: pytest.MonkeyPatch) -> None:
    import polisyos.scientist.agent.vector_memory as module

    class _Module:
        Index = _PortableIndex

    # The module does not bind the hnswlib name when its optional import fails.
    monkeypatch.setattr(module, "hnswlib", _Module(), raising=False)
    monkeypatch.setattr(module, "_HAS_HNSW", True)
    monkeypatch.setattr(module, "_require_supported_hnsw_abi", lambda: None)


class _ObservedLock:
    """Report actual publication-lock contention or completed acquisition."""

    def __init__(self, raw: Any, writer_decided: threading.Event) -> None:
        self.raw = raw
        self.writer_decided = writer_decided
        self.fast_writer: int | None = None

    def __enter__(self) -> _ObservedLock:
        if threading.current_thread().name == "writer":
            if self.raw.acquire(blocking=False):
                self.fast_writer = threading.get_ident()
            else:
                # The writer has reached the actual publication lock and was
                # refused acquisition. The reader may now complete its snapshot.
                self.writer_decided.set()
                self.raw.acquire()
        else:
            self.raw.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        fast = self.fast_writer == threading.get_ident()
        self.raw.release()
        if fast:
            # On an unlocked-reader mutant, release only after the actual
            # writer publication completed; old labels now meet new tables.
            self.writer_decided.set()


@pytest.mark.parametrize("operation", ["load", "add"])
def test_query_returns_single_generation_during_real_publication(
    tmp_path: Path, operation: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    memory = VectorMemoryStore(dim=2, max_elements=4)
    memory.add("A", [1.0, 0.0], {"generation": "old-A"})
    memory.add("B", [0.0, 1.0], {"generation": "old-B"})
    replacement = VectorMemoryStore(dim=2, max_elements=4)
    replacement.add("C", [0.0, 1.0], {"generation": "new-C"})
    replacement.add("D", [1.0, 0.0], {"generation": "new-D"})
    replacement_ref = replacement.save_to_artifact(store, emit_v2=True)

    reader_entered = threading.Event()
    writer_decided = threading.Event()
    original_index = memory._get_generation().index
    memory._generation_lock = _ObservedLock(memory._generation_lock, writer_decided)

    class _PausedIndex:
        def knn_query(self, *args: Any, **kwargs: Any) -> Any:
            reader_entered.set()
            assert writer_decided.wait(5), "writer did not reach/complete publication"
            return original_index.knn_query(*args, **kwargs)

        def __getattr__(self, name: str) -> Any:
            return getattr(original_index, name)

    memory._generation = replace(memory._get_generation(), index=_PausedIndex())
    observed: list[list[tuple[str, float, dict[str, Any]]]] = []
    errors: list[BaseException] = []

    def read() -> None:
        try:
            observed.append(memory.query([1.0, 0.0], 2))
        except BaseException as exc:
            errors.append(exc)

    def publish() -> None:
        try:
            if operation == "load":
                memory.load_from_artifact(store, replacement_ref, allow_trusted_native=True)
            else:
                memory.add("B", [1.0, 0.0], {"generation": "new-B"})
        except BaseException as exc:
            errors.append(exc)
            writer_decided.set()

    reader = threading.Thread(target=read, name="reader")
    writer = threading.Thread(target=publish, name="writer")
    reader.start()
    assert reader_entered.wait(5), "reader did not reach native lookup"
    writer.start()
    reader.join(5)
    writer.join(5)
    assert not reader.is_alive() and not writer.is_alive()
    assert not errors
    assert observed == [[("A", 0.0, {"generation": "old-A"}), ("B", 2.0, {"generation": "old-B"})]]
    if operation == "load":
        assert memory.query([1.0, 0.0], 2) == [
            ("D", 0.0, {"generation": "new-D"}),
            ("C", 2.0, {"generation": "new-C"}),
        ]
    else:
        assert memory.query([1.0, 0.0], 2) == [
            ("A", 0.0, {"generation": "old-A"}),
            ("B", 0.0, {"generation": "new-B"}),
        ]


def test_metadata_intake_rejects_reentrant_and_self_aliasing_callbacks(tmp_path: Path) -> None:
    memory = VectorMemoryStore(dim=2)
    memory.add("old", [1.0, 0.0], {"nested": [1, {"ok": True}]})
    calls: list[str] = []

    class _Reentrant:
        def __deepcopy__(self, memo: object) -> _Reentrant:
            del memo
            calls.append("invoked")
            memory.add("other", [0.0, 1.0], {"changed": True})
            return self

    with pytest.raises(TypeError, match="JSON"):
        memory.add("bad", [0.0, 1.0], {"x": _Reentrant()})
    assert calls == []
    assert memory.query([1.0, 0.0], 1) == [("old", 0.0, {"nested": [1, {"ok": True}]})]
    ref = memory.save_to_artifact(FileSystemCAS(tmp_path / "cas"))
    assert ref.kind == "vector_memory.bundle"
    assert calls == []


@pytest.mark.parametrize("bad", [{1: "key"}, {"x": float("nan")}, {"x": object()}, {"x": (1, 2)}])
def test_invalid_json_metadata_never_changes_a_generation(bad: dict[Any, Any]) -> None:
    memory = VectorMemoryStore(dim=2)
    memory.add("old", [1.0, 0.0], {"nested": [1]})
    with pytest.raises((TypeError, ValueError)):
        memory.add("old", [0.0, 1.0], bad)
    assert memory.query([1.0, 0.0], 1) == [("old", 0.0, {"nested": [1]})]


def test_metadata_is_isolated_at_both_write_and_read_boundaries() -> None:
    memory = VectorMemoryStore(dim=2)
    supplied = {"identity": {"run_id": "source"}}
    memory.add("source", [1.0, 0.0], supplied)
    supplied["identity"]["run_id"] = "changed-before-read"
    first = memory.query([1.0, 0.0], 1)
    first[0][2]["identity"]["run_id"] = "changed-after-read"
    assert memory.query([1.0, 0.0], 1)[0][2] == {"identity": {"run_id": "source"}}


def test_failed_partial_add_and_failed_rollback_poison_until_fresh_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    memory = VectorMemoryStore(dim=2)
    memory.add("old", [1.0, 0.0], {"version": "old"})
    before = memory.save_to_artifact(store, emit_v2=True)
    original = memory._get_generation().index

    class _PartialFailure:
        def add_items(self, embeddings: Any, labels: Any) -> None:
            original.add_items(embeddings, labels)
            raise RuntimeError("partial native mutation")

        def __getattr__(self, name: str) -> Any:
            return getattr(original, name)

    memory._generation = replace(memory._get_generation(), index=_PartialFailure())

    def failed_restore(_: bytes, __: Any) -> None:
        raise OSError("rollback failed")

    monkeypatch.setattr(memory, "_restore_index_bytes", failed_restore)
    with pytest.raises(RuntimeError, match="generation_unavailable"):
        memory.add("old", [0.0, 1.0], {"version": "new"})
    with pytest.raises(RuntimeError, match="generation_unavailable"):
        memory.query([1.0, 0.0], 1)
    with pytest.raises(RuntimeError, match="generation_unavailable"):
        memory.save_to_artifact(store, emit_v2=True)
    with pytest.raises(RuntimeError, match="generation_unavailable"):
        memory.add("new", [1.0, 0.0])
    memory.load_from_artifact(store, before, allow_trusted_native=True)
    assert memory.query([1.0, 0.0], 1) == [("old", 0.0, {"version": "old"})]


def _bundle(store: FileSystemCAS, ref: ArtifactRef) -> dict[str, Any]:
    return json.loads(store.get_bytes(ref))


def _write_v2_bundle(
    store: FileSystemCAS, payload: dict[str, Any], index_ref: ArtifactRef | None
) -> ArtifactRef:
    inputs = (
        []
        if index_ref is None
        else [input_ref_from_artifact_ref(index_ref, role="vector_memory_index")]
    )
    return store.put_json(
        payload,
        PutOptions(
            kind="vector_memory.bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.VectorMemoryBundle", version="2.0"),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def test_selected_index_view_beats_foreign_default_and_reopens_fresh(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2, max_elements=4)
    source.add("A", [1.0, 0.0], {"tag": "A"})
    native = source._save_index_bytes()
    foreign = store.put_bytes(
        native, PutOptions(kind="foreign", media_type="application/octet-stream")
    )
    bundle_ref = source.save_to_artifact(store, emit_v2=True)
    payload = _bundle(store, bundle_ref)
    selected = ArtifactRef.model_validate(payload["index_ref"])
    assert payload["schema_version"] == "2.0"
    assert "index_artifact_id" not in payload
    assert selected.manifest_profile_sha256 is not None
    assert selected.artifact_id == foreign.artifact_id
    assert store.get_manifest(foreign).kind == "foreign"
    assert store.get_manifest(selected).kind == "vector_memory.index"
    assert store.get_manifest(bundle_ref).inputs == [
        input_ref_from_artifact_ref(selected, role="vector_memory_index")
    ]

    class _ReadObserver:
        def __init__(self, inner: FileSystemCAS) -> None:
            self.inner = inner
            self.index_reads: list[object] = []

        def __getattr__(self, name: str) -> Any:
            return getattr(self.inner, name)

        def get_bytes(self, selector: Any) -> bytes:
            if selector == selected or selector == selected.artifact_id:
                self.index_reads.append(selector)
            return self.inner.get_bytes(selector)

    reopened = VectorMemoryStore(dim=1)
    observer = _ReadObserver(FileSystemCAS(tmp_path / "cas"))
    reopened.load_from_artifact(observer, bundle_ref, allow_trusted_native=True)
    assert observer.index_reads == [selected]
    assert reopened.index_binding_status == "exact_selected"
    assert reopened.query([1.0, 0.0], 1) == [("A", 0.0, {"tag": "A"})]


def test_sparse_native_labels_refuse_without_publication(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2, max_elements=4)
    source.add("A", [1.0, 0.0], {"tag": "A"})
    source.add("B", [0.0, 1.0], {"tag": "B"})
    bundle_ref = source.save_to_artifact(store, emit_v2=True)
    payload = _bundle(store, bundle_ref)
    sparse_index = _PortableIndex(space="cosine", dim=2)
    sparse_index.init_index(max_elements=4)
    sparse_index.add_items([[1.0, 0.0]], [0])
    sparse_index.add_items([[0.0, 1.0]], [7])
    sparse_path = tmp_path / "sparse.index"
    sparse_index.save_index(str(sparse_path))
    sparse = sparse_path.read_bytes()
    sparse_ref = store.put_bytes(
        sparse,
        PutOptions(kind="vector_memory.index", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    payload["index_ref"] = sparse_ref.model_dump(mode="json")
    payload["index_bytes_len"] = len(sparse)
    malformed = _write_v2_bundle(store, payload, sparse_ref)
    prior = VectorMemoryStore(dim=2)
    prior.add("prior", [1.0, 0.0], {"tag": "prior"})
    with pytest.raises(ValueError, match="labels"):
        prior.load_from_artifact(store, malformed, allow_trusted_native=True)
    assert prior.query([1.0, 0.0], 1) == [("prior", 0.0, {"tag": "prior"})]


def test_missing_index_edge_refuses_valid_native_member(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2)
    source.add("A", [1.0, 0.0], {"tag": "A"})
    payload = _bundle(store, source.save_to_artifact(store, emit_v2=True))
    no_edge = _write_v2_bundle(store, payload, None)
    prior = VectorMemoryStore(dim=2)
    prior.add("prior", [1.0, 0.0], {"tag": "prior"})
    with pytest.raises(ValueError, match="lineage"):
        prior.load_from_artifact(store, no_edge, allow_trusted_native=True)
    assert prior.query([1.0, 0.0], 1) == [("prior", 0.0, {"tag": "prior"})]


def test_legacy_bundle_default_view_is_explicitly_limited(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2)
    source.add("A", [1.0, 0.0], {"tag": "A"})
    current = source.save_to_artifact(store, emit_v2=True)
    payload = _bundle(store, current)
    selected = ArtifactRef.model_validate(payload.pop("index_ref"))
    payload.pop("schema_version")
    payload["index_artifact_id"] = str(selected.artifact_id)
    legacy = store.put_json(
        payload,
        PutOptions(kind="vector_memory.bundle", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    reader = VectorMemoryStore(dim=2)
    reader.load_from_artifact(store, legacy, allow_trusted_native=True)
    assert reader.index_binding_status == "legacy_default_at_read"
    assert reader.query([1.0, 0.0], 1) == [("A", 0.0, {"tag": "A"})]


def test_real_transfer_registration_survives_vector_cas_reopen(tmp_path: Path) -> None:
    """Real transfer metadata is JSON-owned and carries the exact history ref."""
    from polisyos.scientist.methods.search.objective import (
        BudgetDeficitObjective,
        ObjectiveValue,
        OptimizationDirection,
        configured_objective_rule_spec,
    )
    from polisyos.scientist.methods.search.strategies.transfer import (
        RunFingerprint,
        TransferLearningManager,
    )
    from polisyos.scientist.methods.search.strategies.types import Evaluation, EvaluationStatus

    store = FileSystemCAS(tmp_path / "cas")
    objective = BudgetDeficitObjective(expected_unit="points")
    score_input = {"budget_deficit": 0.8, "metric_units": {"budget_deficit": "points"}}
    assessed = objective.evaluate(score_input)
    value = ObjectiveValue(
        name="score",
        raw_value=float(assessed.raw_value),
        direction=OptimizationDirection.MINIMIZE,
        weight=assessed.weight,
        is_satisfied=assessed.is_satisfied,
        threshold=assessed.threshold,
        score_status=assessed.score_status,
        score_assessment=assessed.score_assessment,
    )
    candidate = store.put_json(
        {"candidate": "local-test"},
        PutOptions(kind="test.candidate", media_type="application/json"),
    )
    evaluation = Evaluation(
        candidate_id=str(candidate.artifact_id),
        params={"x": 0.5},
        params_normalized=(0.5,),
        objectives=[value],
        scalar_score=float(assessed.raw_value),
        stage_a_passed=True,
        stage_b_result=score_input,
        status=EvaluationStatus.SUCCESS,
        metadata={"source_run_id": "source"},
        score_status=assessed.score_status,
        score_assessment=assessed.score_assessment,
    )
    source = RunFingerprint(
        run_id="source",
        space_hash="space-v1",
        objective_names=["score"],
        bounds={"x": [0.0, 1.0]},
        split="selection",
        units={"score": "points"},
        origin="simulator-v1",
        tenant_id="tenant-a",
        objective_directions={"score": "minimize"},
        objective_rule_specs={"score": configured_objective_rule_spec(objective) or ""},
        embedding=[1.0, 0.0],
    )
    index = VectorMemoryStore(dim=2)
    history_ref = TransferLearningManager(store, index).register_run(source, [evaluation])
    assert history_ref is not None
    index_ref = index.save_to_artifact(store, emit_v2=True)
    fresh_index = VectorMemoryStore(dim=2)
    fresh_index.load_from_artifact(
        FileSystemCAS(tmp_path / "cas"), index_ref, allow_trusted_native=True
    )
    manager = TransferLearningManager(store, fresh_index)
    target = source.model_copy(update={"run_id": "target"})
    matches = manager.find_similar_runs(target)
    assert len(matches) == 1
    assert matches[0].history_ref == history_ref
    warm = manager.get_warm_start_evaluations(matches, target_fingerprint=target)
    assert [item.candidate_id for item in warm] == [str(candidate.artifact_id)]


def test_v2_forged_selected_profile_or_bundle_kind_refuses(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2)
    source.add("A", [1.0, 0.0], {"tag": "A"})
    original = source.save_to_artifact(store, emit_v2=True)
    payload = _bundle(store, original)
    selected = ArtifactRef.model_validate(payload["index_ref"])
    payload["index_ref"]["manifest_profile_sha256"] = "sha256:" + "0" * 64
    forged = _write_v2_bundle(store, payload, selected)
    target = VectorMemoryStore(dim=2)
    target.add("old", [1.0, 0.0], {"tag": "old"})
    with pytest.raises(ValueError, match="lineage"):
        target.load_from_artifact(store, forged, allow_trusted_native=True)
    assert target.query([1.0, 0.0], 1) == [("old", 0.0, {"tag": "old"})]
    foreign = store.put_json(
        _bundle(store, original),
        PutOptions(kind="foreign.bundle", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    with pytest.raises(ValueError, match="bundle reference"):
        target.load_from_artifact(store, foreign, allow_trusted_native=True)
    assert target.query([1.0, 0.0], 1) == [("old", 0.0, {"tag": "old"})]


def test_legacy_wrong_default_kind_refuses_instead_of_inventing_selected_view(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2)
    source.add("A", [1.0, 0.0], {"tag": "A"})
    native = source._save_index_bytes()
    store.put_bytes(native, PutOptions(kind="foreign", media_type="application/octet-stream"))
    payload = _bundle(store, source.save_to_artifact(store, emit_v2=True))
    selected = ArtifactRef.model_validate(payload.pop("index_ref"))
    payload.pop("schema_version")
    payload["index_artifact_id"] = str(selected.artifact_id)
    legacy = store.put_json(
        payload,
        PutOptions(kind="vector_memory.bundle", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    prior = VectorMemoryStore(dim=2)
    prior.add("old", [1.0, 0.0], {"tag": "old"})
    with pytest.raises(ValueError, match="index reference kind or media"):
        prior.load_from_artifact(store, legacy, allow_trusted_native=True)
    assert prior.query([1.0, 0.0], 1) == [("old", 0.0, {"tag": "old"})]


def test_cyclic_metadata_refuses_before_native_mutation() -> None:
    memory = VectorMemoryStore(dim=2)
    memory.add("old", [1.0, 0.0], {"tag": "old"})
    cycle: list[Any] = []
    cycle.append(cycle)
    with pytest.raises(ValueError, match="cycles"):
        memory.add("old", [0.0, 1.0], {"cycle": cycle})
    assert memory.query([1.0, 0.0], 1) == [("old", 0.0, {"tag": "old"})]


def test_v2_payload_with_wrong_manifest_schema_refuses(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2)
    source.add("A", [1.0, 0.0], {"tag": "A"})
    payload = _bundle(store, source.save_to_artifact(store, emit_v2=True))
    selected = ArtifactRef.model_validate(payload["index_ref"])
    incompatible = store.put_json(
        payload,
        PutOptions(
            kind="vector_memory.bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.VectorMemoryBundle", version="1.0"),
            inputs=[input_ref_from_artifact_ref(selected, role="vector_memory_index")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    prior = VectorMemoryStore(dim=2)
    prior.add("old", [1.0, 0.0], {"tag": "old"})
    with pytest.raises(ValueError, match="schema"):
        prior.load_from_artifact(store, incompatible, allow_trusted_native=True)
    assert prior.query([1.0, 0.0], 1) == [("old", 0.0, {"tag": "old"})]


def _interrupt_at_line(function: Any, fragment: str) -> Any:
    lines, first = inspect.getsourcelines(function)
    matches = [first + i for i, line in enumerate(lines) if fragment in line]
    assert len(matches) == 1

    def trace(frame: Any, event: str, arg: Any) -> Any:
        del arg
        if frame.f_code is function.__code__ and event == "line" and frame.f_lineno == matches[0]:
            raise RuntimeError("injected publication interruption")
        return trace

    return trace


def test_interrupted_add_restores_prior_complete_generation() -> None:
    memory = VectorMemoryStore(dim=2)
    memory.add("A", [1.0, 0.0], {"generation": "old"})
    prior = memory.query([1.0, 0.0], 1)
    previous_trace = sys.gettrace()
    sys.settrace(_interrupt_at_line(VectorMemoryStore.add, "self._generation = next_generation"))
    try:
        with pytest.raises(RuntimeError, match="injected publication interruption"):
            memory.add("A", [0.0, 1.0], {"generation": "new"})
    finally:
        sys.settrace(previous_trace)
    assert memory.query([1.0, 0.0], 1) == prior


def test_interrupted_load_keeps_prior_complete_generation(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    replacement = VectorMemoryStore(dim=3)
    replacement.add("B", [0.0, 1.0, 0.0], {"generation": "new"})
    ref = replacement.save_to_artifact(store, emit_v2=True)
    memory = VectorMemoryStore(dim=2)
    memory.add("A", [1.0, 0.0], {"generation": "old"})
    prior = memory.query([1.0, 0.0], 1)
    previous_trace = sys.gettrace()
    sys.settrace(_interrupt_at_line(VectorMemoryStore.load_from_artifact, "# publish_native"))
    try:
        with pytest.raises(RuntimeError, match="injected publication interruption"):
            memory.load_from_artifact(store, ref, allow_trusted_native=True)
    finally:
        sys.settrace(previous_trace)
    assert memory.dim == 2
    assert memory.query([1.0, 0.0], 1) == prior


def test_save_and_native_mutation_produce_one_complete_generation(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    memory = VectorMemoryStore(dim=2, max_elements=4)
    memory.add("A", [1.0, 0.0], {"generation": "old-A"})
    memory.add("B", [0.0, 1.0], {"generation": "old-B"})
    saver_entered = threading.Event()
    writer_decided = threading.Event()
    original = memory._get_generation().index
    memory._generation_lock = _ObservedLock(memory._generation_lock, writer_decided)

    class _PausedSave:
        def save_index(self, path: str) -> None:
            if threading.current_thread().name != "saver":
                original.save_index(path)
                return
            first = list(original.rows[0])
            saver_entered.set()
            assert writer_decided.wait(5), "writer did not reach or finish publication"
            captured = _PortableIndex(space="cosine", dim=2)
            captured.init_index(max_elements=4)
            captured.add_items([first], [0])
            captured.add_items([list(original.rows[1])], [1])
            captured.save_index(path)

        def __getattr__(self, name: str) -> Any:
            return getattr(original, name)

    memory._generation = replace(memory._get_generation(), index=_PausedSave())
    results: list[ArtifactRef] = []
    errors: list[BaseException] = []

    def save() -> None:
        try:
            results.append(memory.save_to_artifact(store, emit_v2=True))
        except BaseException as exc:
            errors.append(exc)
            writer_decided.set()

    def write() -> None:
        try:
            memory.add("B", [1.0, 0.0], {"generation": "new-B"})
        except BaseException as exc:
            errors.append(exc)
            writer_decided.set()

    saver = threading.Thread(target=save, name="saver")
    writer = threading.Thread(target=write, name="writer")
    saver.start()
    assert saver_entered.wait(5), "save did not reach native capture"
    writer.start()
    saver.join(5)
    writer.join(5)
    assert not saver.is_alive() and not writer.is_alive() and not errors
    assert len(results) == 1
    reopened = VectorMemoryStore(dim=2)
    reopened.load_from_artifact(
        FileSystemCAS(tmp_path / "cas"), results[0], allow_trusted_native=True
    )
    assert reopened.query([1.0, 0.0], 2) == [
        ("A", 0.0, {"generation": "old-A"}),
        ("B", 2.0, {"generation": "old-B"}),
    ]


@pytest.mark.parametrize("declared_dim", [1, 3])
def test_declared_dimension_must_match_native_layout(tmp_path: Path, declared_dim: int) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2)
    source.add("A", [1.0, 0.0], {"tag": "source"})
    payload = _bundle(store, source.save_to_artifact(store, emit_v2=True))
    selected = ArtifactRef.model_validate(payload["index_ref"])
    payload["dim"] = declared_dim
    forged = _write_v2_bundle(store, payload, selected)
    prior = VectorMemoryStore(dim=2)
    prior.add("old", [1.0, 0.0], {"tag": "prior"})
    with pytest.raises(ValueError, match="native header"):
        prior.load_from_artifact(store, forged, allow_trusted_native=True)
    assert prior.query([1.0, 0.0], 1) == [("old", 0.0, {"tag": "prior"})]


def test_deleted_native_row_is_refused_before_publication(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2)
    source.add("A", [1.0, 0.0], {"tag": "source"})
    payload = _bundle(store, source.save_to_artifact(store, emit_v2=True))
    selected = ArtifactRef.model_validate(payload["index_ref"])
    native = bytearray(store.get_bytes(selected))
    native[struct.calcsize("<6QiI3QdQ") + 2] |= 1
    deleted = store.put_bytes(
        bytes(native),
        PutOptions(kind="vector_memory.index", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    payload["index_ref"] = deleted.model_dump(mode="json")
    forged = _write_v2_bundle(store, payload, deleted)
    prior = VectorMemoryStore(dim=2)
    prior.add("old", [1.0, 0.0], {"tag": "prior"})
    with pytest.raises(ValueError, match="deleted"):
        prior.load_from_artifact(store, forged, allow_trusted_native=True)
    assert prior.query([1.0, 0.0], 1) == [("old", 0.0, {"tag": "prior"})]


def test_legacy_writer_default_and_v2_opt_in(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2)
    source.add("A", [1.0, 0.0], {"tag": "A"})
    legacy = source.save_to_artifact(store)
    legacy_payload = _bundle(store, legacy)
    assert "index_artifact_id" in legacy_payload
    assert "schema_version" not in legacy_payload and "index_ref" not in legacy_payload
    reader = VectorMemoryStore(dim=2)
    reader.load_from_artifact(store, legacy, allow_trusted_native=True)
    assert reader.index_binding_status == "legacy_default_at_read"
    assert reader.query([1.0, 0.0], 1) == [("A", 0.0, {"tag": "A"})]
    v2_payload = _bundle(store, source.save_to_artifact(store, emit_v2=True))
    assert v2_payload["schema_version"] == "2.0"
    assert "index_artifact_id" not in v2_payload and "index_ref" in v2_payload


def test_default_writer_refuses_foreign_default_profile(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2)
    source.add("A", [1.0, 0.0], {"tag": "A"})
    store.put_bytes(
        source._save_index_bytes(),
        PutOptions(kind="foreign", media_type="application/octet-stream"),
    )
    with pytest.raises(ValueError, match="non-default"):
        source.save_to_artifact(store)
    selected = source.save_to_artifact(store, emit_v2=True)
    assert _bundle(store, selected)["schema_version"] == "2.0"


def test_key_origin_is_not_established_by_exact_index_bytes(tmp_path: Path) -> None:
    """Residual witness: rewrapping valid bytes under swapped names is admitted."""
    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2)
    source.add("A", [1.0, 0.0], {"tag": "A"})
    source.add("B", [0.0, 1.0], {"tag": "B"})
    payload = _bundle(store, source.save_to_artifact(store, emit_v2=True))
    selected = ArtifactRef.model_validate(payload["index_ref"])
    payload["keys"] = ["B", "A"]
    forged = _write_v2_bundle(store, payload, selected)
    reopened = VectorMemoryStore(dim=2)
    reopened.load_from_artifact(store, forged, allow_trusted_native=True)
    assert reopened.query([1.0, 0.0], 1) == [("B", 0.0, {"tag": "A"})]


def test_native_record_guard_does_not_establish_graph_topology(tmp_path: Path) -> None:
    """Residual witness: inspect the guard only; do not feed forged graph bytes to native code."""
    from polisyos.scientist.agent.vector_memory import _validate_native_index_bytes

    index = _PortableIndex(space="cosine", dim=2)
    index.init_index(max_elements=4)
    index.add_items([[1.0, 0.0]], [0])
    path = tmp_path / "index"
    index.save_index(str(path))
    raw = bytearray(path.read_bytes())
    struct.pack_into("<I", raw, 6 * 8 + 4, 99)  # impossible entrypoint
    _validate_native_index_bytes(
        bytes(raw), dim=2, max_elements=4, ef_construction=200, M=16, count=1
    )


def test_concurrent_caller_mutation_is_outside_admission_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Residual witness: owned-copy cannot synchronize mutable caller-owned input."""
    import polisyos.scientist.agent.vector_memory as module

    source = {"a": 1, "b": 1}
    reached = threading.Event()
    changed = threading.Event()
    real_copy = module._owned_json
    once = False

    def paused_copy(value: Any, active: set[int] | None = None) -> Any:
        nonlocal once
        if type(value) is int and not once:
            once = True
            reached.set()
            assert changed.wait(5)
        return real_copy(value, active)

    monkeypatch.setattr(module, "_owned_json", paused_copy)
    memory = VectorMemoryStore(dim=2)
    errors: list[BaseException] = []

    def write() -> None:
        try:
            memory.add("A", [1.0, 0.0], source)
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=write)
    worker.start()
    assert reached.wait(5)
    source["a"] = 2
    source["b"] = 2
    changed.set()
    worker.join(5)
    assert not worker.is_alive() and not errors
    assert memory.query([1.0, 0.0], 1)[0][2] == {"a": 1, "b": 2}


def test_row_bundle_rebuilds_from_selected_vectors_without_native_graph_load(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2, max_elements=4)
    source.add("A", [1.0, 0.0], {"tag": "A"})
    source.add("B", [0.0, 1.0], {"tag": "B"})
    ref = source.save_to_artifact(store, emit_rows=True)
    payload = _bundle(store, ref)
    assert payload["schema_version"] == "3.0"
    assert "index_ref" not in payload and "index_artifact_id" not in payload
    member = ArtifactRef.model_validate(payload["vectors_ref"])
    assert store.get_manifest(ref).inputs == [
        input_ref_from_artifact_ref(member, role="vector_memory_vectors")
    ]
    target = VectorMemoryStore(dim=2)
    target.load_from_artifact(FileSystemCAS(tmp_path / "cas"), ref)
    assert target.query([1.0, 0.0], 2) == [("A", 0.0, {"tag": "A"}), ("B", 2.0, {"tag": "B"})]


def test_legacy_native_load_requires_explicit_trusted_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.scientist.agent.vector_memory import UntrustedNativeVectorBundleError

    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2)
    source.add("A", [1.0, 0.0], {"tag": "A"})
    legacy = source.save_to_artifact(store)
    v2 = source.save_to_artifact(store, emit_v2=True)
    target = VectorMemoryStore(dim=2)
    target.add("prior", [1.0, 0.0], {"tag": "prior"})

    def forbidden_native_load(*_: Any, **__: Any) -> None:
        raise AssertionError("native load must not be invoked")

    monkeypatch.setattr(_PortableIndex, "load_index", forbidden_native_load)
    for ref in (legacy, v2):
        with pytest.raises(UntrustedNativeVectorBundleError):
            target.load_from_artifact(store, ref)
        assert target.query([1.0, 0.0], 1) == [("prior", 0.0, {"tag": "prior"})]


def test_exact_key_lookup_uses_generation_metadata_not_ann(monkeypatch: pytest.MonkeyPatch) -> None:
    source = VectorMemoryStore(dim=2)
    source.add("A", [1.0, 0.0], {"nested": [1]})
    monkeypatch.setattr(source, "query", lambda *_, **__: pytest.fail("ANN must not run"))
    row = source.lookup_metadata("A")
    assert row == {"nested": [1]}
    assert row is not None
    row["nested"].append(2)
    assert source.lookup_metadata("A") == {"nested": [1]}
    assert source.lookup_metadata("absent") is None


def test_known_run_without_history_ref_uses_exact_key_not_ann(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.scientist.methods.search.objective import (
        BudgetDeficitObjective,
        ObjectiveValue,
        OptimizationDirection,
        configured_objective_rule_spec,
    )
    from polisyos.scientist.methods.search.strategies.transfer import (
        RunFingerprint,
        TransferLearningManager,
    )
    from polisyos.scientist.methods.search.strategies.types import Evaluation, EvaluationStatus

    store = FileSystemCAS(tmp_path / "cas")
    objective = BudgetDeficitObjective(expected_unit="points")
    measured = {"budget_deficit": 0.8, "metric_units": {"budget_deficit": "points"}}
    assessed = objective.evaluate(measured)
    evaluation = Evaluation(
        candidate_id="candidate",
        params={"x": 0.5},
        params_normalized=(0.5,),
        objectives=[
            ObjectiveValue(
                name="score",
                raw_value=float(assessed.raw_value),
                direction=OptimizationDirection.MINIMIZE,
                weight=assessed.weight,
                is_satisfied=assessed.is_satisfied,
                threshold=assessed.threshold,
                score_status=assessed.score_status,
                score_assessment=assessed.score_assessment,
            )
        ],
        scalar_score=float(assessed.raw_value),
        stage_a_passed=True,
        stage_b_result=measured,
        status=EvaluationStatus.SUCCESS,
        score_status=assessed.score_status,
        score_assessment=assessed.score_assessment,
    )
    source = RunFingerprint(
        run_id="source",
        space_hash="space-v1",
        objective_names=["score"],
        bounds={"x": [0.0, 1.0]},
        split="selection",
        units={"score": "points"},
        origin="simulator-v1",
        tenant_id="tenant-a",
        objective_directions={"score": "minimize"},
        objective_rule_specs={"score": configured_objective_rule_spec(objective) or ""},
        embedding=[1.0, 0.0],
    )
    index = VectorMemoryStore(dim=2, max_elements=1100)
    manager = TransferLearningManager(store, index)
    original_ref = manager.register_run(source, [evaluation])
    assert original_ref is not None
    for number in range(1001):
        index.add(f"other-{number}", [0.0, 1.0], {"tag": number})
    target = source.model_copy(update={"run_id": "target"})
    query = index.query
    calls = []

    def observe_query(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        return query(*args, **kwargs)

    monkeypatch.setattr(index, "query", observe_query)
    for top_k in (1, 3):
        before = len(calls)
        discovered = manager.find_similar_runs(target, top_k=top_k)
        assert [row.run_id for row in discovered] == ["source"]
        assert len(calls) == before + 1
        assert [
            value.candidate_id
            for value in manager.get_warm_start_evaluations(discovered, target_fingerprint=target)
        ] == ["candidate"]
        assert len(calls) == before + 1
    monkeypatch.setattr(
        index, "query", lambda *_, **__: pytest.fail("known key must not query ANN")
    )
    assert source.history_ref is None
    values = manager.get_warm_start_evaluations([source], target_fingerprint=target)
    assert [value.candidate_id for value in values] == ["candidate"]
    wrong_payload = _bundle(store, original_ref)
    wrong_payload["run_id"] = "other-source"
    wrong_ref = store.put_json(
        wrong_payload,
        PutOptions(kind="search.transfer.history", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    meta = index.lookup_metadata("source")
    assert meta is not None
    meta["artifact_id"] = str(wrong_ref.artifact_id)
    meta["manifest_profile_sha256"] = wrong_ref.manifest_profile_sha256
    index.add("source", [1.0, 0.0], meta)
    with pytest.raises(ValueError, match="run_id"):
        manager.get_warm_start_evaluations([source], target_fingerprint=target)


def _write_rows_bundle(
    store: FileSystemCAS, payload: dict[str, Any], member: ArtifactRef | None
) -> ArtifactRef:
    return store.put_json(
        payload,
        PutOptions(
            kind="vector_memory.bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.VectorMemoryBundle", version="3.0"),
            inputs=[]
            if member is None
            else [input_ref_from_artifact_ref(member, role="vector_memory_vectors")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


@pytest.mark.parametrize(
    "change", ["no_edge", "duplicate_key", "wrong_dim", "huge_capacity", "huge_ef", "wrong_kind"]
)
def test_invalid_row_bundle_refuses_before_native_allocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    import polisyos.scientist.agent.vector_memory as module

    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2, max_elements=4)
    source.add("A", [1.0, 0.0], {"tag": "A"})
    source.add("B", [0.0, 1.0], {"tag": "B"})
    payload = _bundle(store, source.save_to_artifact(store, emit_rows=True))
    selected = ArtifactRef.model_validate(payload["vectors_ref"])
    edge: ArtifactRef | None = selected
    if change == "no_edge":
        edge = None
    elif change == "duplicate_key":
        payload["keys"] = ["A", "A"]
    elif change == "wrong_dim":
        payload["dim"] = 3
    elif change == "huge_capacity":
        payload["max_elements"] = 1_000_000_000
    elif change == "huge_ef":
        payload["ef_construction"] = 1_000_001
    else:
        payload["vectors_ref"]["kind"] = "foreign"
        edge = ArtifactRef.model_validate(payload["vectors_ref"])
    forged = _write_rows_bundle(store, payload, edge)

    def forbidden_index(*_: Any, **__: Any) -> Any:
        pytest.fail("invalid row bundle must refuse before native allocation")

    class _NoNative:
        Index = staticmethod(forbidden_index)

    monkeypatch.setattr(module, "hnswlib", _NoNative())
    with pytest.raises((ValueError, OSError)):
        VectorMemoryStore.from_portable_artifact(store, forged)


def test_row_bundle_rejects_object_npz_before_native_allocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    import numpy as np

    import polisyos.scientist.agent.vector_memory as module

    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2, max_elements=4)
    source.add("A", [1.0, 0.0], {"tag": "A"})
    payload = _bundle(store, source.save_to_artifact(store, emit_rows=True))
    stream = io.BytesIO()
    np.savez(stream, vectors=np.asarray([[object(), object()]], dtype=object))
    raw = stream.getvalue()
    member = store.put_bytes(
        raw,
        PutOptions(kind="vector_memory.vectors", media_type="application/x-npz"),
        return_selected_profile=True,
    )
    payload["vectors_ref"] = member.model_dump(mode="json")
    payload["vectors_bytes_len"] = len(raw)
    forged = _write_rows_bundle(store, payload, member)

    def forbidden_index(*_: Any, **__: Any) -> Any:
        pytest.fail("object NPZ must refuse before native allocation")

    class _NoNative:
        Index = staticmethod(forbidden_index)

    monkeypatch.setattr(module, "hnswlib", _NoNative())
    with pytest.raises(ValueError):
        VectorMemoryStore.from_portable_artifact(store, forged)


def test_large_finite_portable_rows_are_normalized_before_native_rebuild(tmp_path: Path) -> None:
    import io

    import numpy as np

    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2, max_elements=4)
    source.add("A", [1.0, 1.0], {"tag": "A"})
    payload = _bundle(store, source.save_to_artifact(store, emit_rows=True))
    stream = io.BytesIO()
    np.savez(stream, vectors=np.asarray([[1e20, 1e20]], dtype="<f4"))
    raw = stream.getvalue()
    member = store.put_bytes(
        raw,
        PutOptions(kind="vector_memory.vectors", media_type="application/x-npz"),
        return_selected_profile=True,
    )
    payload["vectors_ref"] = member.model_dump(mode="json")
    payload["vectors_bytes_len"] = len(raw)
    reopened = VectorMemoryStore.from_portable_artifact(
        store, _write_rows_bundle(store, payload, member)
    )
    row = reopened.query([1.0, 1.0], 1)[0]
    assert row[0] == "A" and row[2] == {"tag": "A"}
    assert row[1] == pytest.approx(0.0, abs=1e-6)


def test_row_bundle_reads_exact_selected_member_with_foreign_default(tmp_path: Path) -> None:
    first = FileSystemCAS(tmp_path / "first")
    source = VectorMemoryStore(dim=2, max_elements=4)
    source.add("A", [1.0, 0.0], {"tag": "A"})
    payload = _bundle(first, source.save_to_artifact(first, emit_rows=True))
    original = ArtifactRef.model_validate(payload["vectors_ref"])
    raw = first.get_bytes(original)
    store = FileSystemCAS(tmp_path / "second")
    foreign = store.put_bytes(raw, PutOptions(kind="foreign", media_type="application/x-npz"))
    selected = store.put_bytes(
        raw,
        PutOptions(kind="vector_memory.vectors", media_type="application/x-npz"),
        return_selected_profile=True,
    )
    assert foreign.artifact_id == selected.artifact_id
    assert store.get_manifest(foreign).kind == "foreign"
    payload["vectors_ref"] = selected.model_dump(mode="json")
    ref = _write_rows_bundle(store, payload, selected)

    class Observer:
        def __init__(self, inner: FileSystemCAS) -> None:
            self.inner = inner
            self.selected_reads: list[object] = []

        def __getattr__(self, name: str) -> Any:
            return getattr(self.inner, name)

        def get_raw_manifest_bytes_bounded(self, selector: Any, **kwargs: Any) -> bytes:
            if getattr(selector, "artifact_id", selector) == selected.artifact_id:
                self.selected_reads.append(selector)
            return self.inner.get_raw_manifest_bytes_bounded(selector, **kwargs)

        def open_member_bounded(self, selector: Any, *args: Any, **kwargs: Any) -> Any:
            if getattr(selector, "artifact_id", selector) == selected.artifact_id:
                self.selected_reads.append(selector)
            return self.inner.open_member_bounded(selector, *args, **kwargs)

    observer = Observer(FileSystemCAS(tmp_path / "second"))
    reopened = VectorMemoryStore.from_portable_artifact(observer, ref)
    assert reopened.query([1.0, 0.0], 1) == [("A", 0.0, {"tag": "A"})]
    assert observer.selected_reads == [selected, selected]


def test_row_writer_refuses_oversize_metadata_before_numpy_serialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import numpy as np

    source = VectorMemoryStore(dim=2, max_elements=4)
    source.add("A", [1.0, 0.0], {"oversize": "x" * (256 * 1024 + 1)})

    def forbidden_save(*_: Any, **__: Any) -> None:
        pytest.fail("oversize metadata must refuse before numpy serialization")

    monkeypatch.setattr(np, "savez", forbidden_save)
    with pytest.raises(ValueError, match="json_limit"):
        source.save_to_artifact(FileSystemCAS(tmp_path / "cas"), emit_rows=True)


@pytest.mark.parametrize(
    "metadata",
    [
        {"_type": "float", "repr": "1"},
        {"nested": {"_type": "float", "repr": "1"}},
        {"nested": [{"deep": {"_type": "unknown", "data": 1}}]},
    ],
)
def test_reserved_canonical_tag_is_refused_before_generation_mutation(
    metadata: dict[str, Any],
) -> None:
    memory = VectorMemoryStore(dim=2, max_elements=4)
    memory.add("A", [1.0, 0.0], {"version": "old"})
    prior = memory.query([1.0, 0.0], 1)
    with pytest.raises(ValueError, match="reserved.*_type"):
        memory.add("A", [0.0, 1.0], metadata)
    assert memory.query([1.0, 0.0], 1) == prior


def test_portable_metadata_preserves_null_absence_and_nested_objects(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    expected = {
        "present": None,
        "nested": {"present": None, "_type_hint": "ordinary"},
        "list": [None, {"x": 1.0}],
    }
    source = VectorMemoryStore(dim=2, max_elements=4)
    source.add("A", [1.0, 0.0], expected)
    ref = source.save_to_artifact(store, emit_rows=True)
    reopened = VectorMemoryStore.from_portable_artifact(FileSystemCAS(tmp_path / "cas"), ref)
    row = reopened.query([1.0, 0.0], 1)[0]
    assert row[2] == expected
    assert "absent" not in row[2] and "absent" not in row[2]["nested"]


def test_portable_save_and_add_capture_one_complete_generation(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    memory = VectorMemoryStore(dim=2, max_elements=4)
    memory.add("A", [1.0, 0.0], {"generation": "old-A"})
    memory.add("B", [0.0, 1.0], {"generation": "old-B"})
    saver_entered = threading.Event()
    writer_decided = threading.Event()
    original = memory._get_generation().index
    memory._generation_lock = _ObservedLock(memory._generation_lock, writer_decided)

    class _PausedRows:
        def get_items(self, labels: list[int]) -> list[list[float]]:
            assert labels == [0, 1]
            first = list(original.rows[0])
            saver_entered.set()
            assert writer_decided.wait(5), "writer did not reach or finish publication"
            return [first, list(original.rows[1])]

        def __getattr__(self, name: str) -> Any:
            return getattr(original, name)

    memory._generation = replace(memory._get_generation(), index=_PausedRows())
    results: list[ArtifactRef] = []
    errors: list[BaseException] = []

    def save() -> None:
        try:
            results.append(memory.save_to_artifact(store, emit_rows=True))
        except BaseException as exc:
            errors.append(exc)
            writer_decided.set()

    def write() -> None:
        try:
            memory.add("B", [1.0, 0.0], {"generation": "new-B"})
        except BaseException as exc:
            errors.append(exc)
            writer_decided.set()

    saver = threading.Thread(target=save, name="saver")
    writer = threading.Thread(target=write, name="writer")
    saver.start()
    assert saver_entered.wait(5), "save did not reach portable row capture"
    writer.start()
    saver.join(5)
    writer.join(5)
    assert not saver.is_alive() and not writer.is_alive() and not errors
    assert len(results) == 1
    reopened = VectorMemoryStore.from_portable_artifact(FileSystemCAS(tmp_path / "cas"), results[0])
    assert reopened.query([1.0, 0.0], 2) == [
        ("A", 0.0, {"generation": "old-A"}),
        ("B", 2.0, {"generation": "old-B"}),
    ]
