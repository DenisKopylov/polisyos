"""Native HNSW and fresh-process witnesses for selected vector snapshots."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import perf_counter

import pytest

from polisyos.core.artifacts import input_ref_from_artifact_ref, load_core_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.scientist.agent.vector_memory import VectorMemoryStore
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    configured_objective_rule_spec,
)
from polisyos.scientist.methods.search.strategies.transfer import (
    RunFingerprint,
    TransferLearningManager,
)
from polisyos.scientist.methods.search.strategies.types import Evaluation, EvaluationStatus


def test_native_bundle_reopens_exact_selected_view_in_a_fresh_process(tmp_path: Path) -> None:
    pytest.importorskip("hnswlib")
    root = tmp_path / "cas"
    store = FileSystemCAS(root)
    memory = VectorMemoryStore(dim=2, max_elements=4)
    memory.add("A", [1.0, 0.0], {"source": "A"})
    memory.add("B", [0.0, 1.0], {"source": "B"})
    ref = memory.save_to_artifact(store, emit_v2=True)
    code = """
import json, sys
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent.vector_memory import VectorMemoryStore
store = FileSystemCAS(sys.argv[1])
ref = ArtifactRef.model_validate_json(sys.argv[2])
memory = VectorMemoryStore(dim=2)
memory.load_from_artifact(store, ref, allow_trusted_native=True)
print(json.dumps({'status': memory.index_binding_status, 'rows': memory.query([1.0, 0.0], 2)}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(root), ref.model_dump_json()],
        check=True,
        text=True,
        capture_output=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "exact_selected"
    assert [row[0] for row in payload["rows"]] == ["A", "B"]
    assert [row[2] for row in payload["rows"]] == [{"source": "A"}, {"source": "B"}]
    assert payload["rows"][0][1] == pytest.approx(0.0)
    assert payload["rows"][1][1] == pytest.approx(1.0)


def test_native_same_count_sparse_labels_refuse_before_publication(tmp_path: Path) -> None:
    hnsw = pytest.importorskip("hnswlib")
    store = FileSystemCAS(tmp_path / "cas")
    source = VectorMemoryStore(dim=2, max_elements=4)
    source.add("A", [1.0, 0.0], {"source": "A"})
    source.add("B", [0.0, 1.0], {"source": "B"})
    bundle = json.loads(store.get_bytes(source.save_to_artifact(store, emit_v2=True)))
    index = hnsw.Index(space="cosine", dim=2)
    index.init_index(max_elements=4, ef_construction=200, M=16)
    index.add_items([[1.0, 0.0], [0.0, 1.0]], [0, 7])
    path = tmp_path / "sparse.index"
    index.save_index(str(path))
    raw = path.read_bytes()
    index_ref = store.put_bytes(
        raw,
        PutOptions(kind="vector_memory.index", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    bundle["index_ref"] = index_ref.model_dump(mode="json")
    bundle["index_bytes_len"] = len(raw)
    forged = store.put_json(
        bundle,
        PutOptions(
            kind="vector_memory.bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.VectorMemoryBundle", version="2.0"),
            inputs=[input_ref_from_artifact_ref(index_ref, role="vector_memory_index")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    prior = VectorMemoryStore(dim=2)
    prior.add("old", [1.0, 0.0], {"source": "old"})
    with pytest.raises(ValueError, match="labels"):
        prior.load_from_artifact(store, forged, allow_trusted_native=True)
    assert prior.query([1.0, 0.0], 1)[0][0] == "old"


def test_native_scaled_inputs_preserve_cosine_semantics() -> None:
    pytest.importorskip("hnswlib")
    memory = VectorMemoryStore(dim=2, max_elements=4)
    memory.add("scaled", [1e300, 1e300], {"tag": "scaled"})
    memory.add("orthogonal", [1.0, -1.0], {"tag": "orthogonal"})
    rows = memory.query([1e20, 1e20], 2)
    assert [row[0] for row in rows] == ["scaled", "orthogonal"]
    assert rows[0][1] == pytest.approx(0.0, abs=1e-5)
    assert rows[1][1] == pytest.approx(1.0, abs=1e-5)
    assert [row[2] for row in rows] == [{"tag": "scaled"}, {"tag": "orthogonal"}]


def test_native_wrong_dimensions_and_deleted_row_refuse_in_isolated_process(tmp_path: Path) -> None:
    pytest.importorskip("hnswlib")
    code = r"""
import json, sys
from pathlib import Path
import hnswlib
from polisyos.core.artifacts import input_ref_from_artifact_ref
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.agent.vector_memory import VectorMemoryStore
root = Path(sys.argv[1])
store = FileSystemCAS(root / 'cas')
source = VectorMemoryStore(dim=2, max_elements=4)
source.add('A', [1., 0.], {'tag':'A'})
source.add('B', [0., 1.], {'tag':'B'})
payload = json.loads(store.get_bytes(source.save_to_artifact(store, emit_v2=True)))
def bundle(value, member):
    return store.put_json(value, PutOptions(kind='vector_memory.bundle', media_type='application/json',
        schema=SchemaInfo(name='polisyos.scientist.VectorMemoryBundle',version='2.0'),
        inputs=[input_ref_from_artifact_ref(member, role='vector_memory_index')]),
        canon_spec=CanonSpec(forbid_floats=False), return_selected_profile=True)
member = ArtifactRef.model_validate(payload['index_ref'])
cases = []
for dim in (1, 3):
    changed = dict(payload, dim=dim)
    cases.append((f'dim-{dim}', bundle(changed, member)))
index = hnswlib.Index(space='cosine', dim=2)
index.init_index(max_elements=4, ef_construction=200, M=16)
index.add_items([[1.,0.],[0.,1.]], [0,1])
index.mark_deleted(1)
path = root / 'deleted.index'
index.save_index(str(path))
raw = path.read_bytes()
deleted = store.put_bytes(raw, PutOptions(kind='vector_memory.index', media_type='application/octet-stream'), return_selected_profile=True)
changed = dict(payload, index_ref=deleted.model_dump(mode='json'), index_bytes_len=len(raw))
cases.append(('deleted', bundle(changed, deleted)))
observed = {}
for name, ref in cases:
    target = VectorMemoryStore(dim=2)
    target.add('old', [1., 0.], {'tag':'old'})
    try:
        target.load_from_artifact(store, ref, allow_trusted_native=True)
    except ValueError as exc:
        observed[name] = {'reason':str(exc), 'rows':target.query([1.,0.],1)}
    else:
        observed[name] = {'reason':'unexpected acceptance', 'rows':target.query([1.,0.],1)}
print(json.dumps(observed))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    observed = json.loads(result.stdout)
    for case in ("dim-1", "dim-3"):
        assert "native header" in observed[case]["reason"]
    assert "deleted" in observed["deleted"]["reason"]
    for case in observed.values():
        assert case["rows"] == [["old", pytest.approx(0.0), {"tag": "old"}]]


def test_native_portable_rows_rebuild_without_external_graph_in_fresh_process(
    tmp_path: Path,
) -> None:
    pytest.importorskip("hnswlib")
    root = tmp_path / "cas-rows"
    store = FileSystemCAS(root).with_ambient_ownership_enforcement()
    memory = VectorMemoryStore(dim=2, max_elements=4)
    objective = BudgetDeficitObjective(expected_unit="points")
    rule = configured_objective_rule_spec(objective)
    assert rule is not None
    observed = {"budget_deficit": 0.8, "metric_units": {"budget_deficit": "points"}}
    score = objective.evaluate(observed)
    source = RunFingerprint(
        run_id="source",
        space_hash="declared-space-v1",
        objective_names=[objective.name],
        bounds={"x": [0.0, 1.0]},
        split="selection",
        units={objective.name: "points"},
        origin="configured-fiscal-method",
        tenant_id="tenant-transfer",
        objective_directions={objective.name: objective.direction.value},
        objective_rule_specs={objective.name: rule},
        embedding=[1.0, 0.0],
        num_evaluations=1,
    )
    with tenant_scope(None, tenant_id="tenant-transfer"):
        candidate = store.put_json(
            {"params": {"x": 0.5}},
            PutOptions(kind="test.search.candidate", media_type="application/json"),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        history = TransferLearningManager(store, memory).register_run(
            source,
            [
                Evaluation(
                    candidate_id=str(candidate.artifact_id),
                    params={"x": 0.5},
                    params_normalized=(0.5,),
                    objectives=[score],
                    scalar_score=score.raw_value,
                    stage_a_passed=True,
                    stage_b_result=observed,
                    status=EvaluationStatus.SUCCESS,
                    score_status=score.score_status,
                    score_assessment=score.score_assessment,
                )
            ],
        )
        assert history is not None
        memory.add("unbound-neighbor", [0.0, 1.0], {"source": "unbound"})
        start = perf_counter()
        ref = memory.save_to_artifact(store, emit_rows=True)
        save_seconds = perf_counter() - start
        manifest = store.get_manifest(ref)
        bundle = load_core_json_artifact(store, ref)
        member = ArtifactRef.model_validate(bundle["vectors_ref"])
        member_bytes = store.get_manifest(member).byte_size
        assert manifest.artifact_schema is not None and manifest.artifact_schema.version == "3.0"
        assert manifest.inputs == [
            input_ref_from_artifact_ref(member, role="vector_memory_vectors")
        ]

        def persist_variant(payload, selected_member):
            return store.put_json(
                payload,
                PutOptions(
                    kind=ref.kind,
                    media_type=ref.media_type,
                    schema=manifest.artifact_schema,
                    inputs=[]
                    if selected_member is None
                    else [
                        input_ref_from_artifact_ref(selected_member, role="vector_memory_vectors")
                    ],
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )

        bad_bytes = b"invalid experiment NPZ"
        bad_npz = store.put_bytes(
            bad_bytes,
            PutOptions(kind=member.kind, media_type=member.media_type),
            return_selected_profile=True,
        )
        missing_lineage = persist_variant(bundle, None)
        assert missing_lineage.artifact_id == ref.artifact_id and missing_lineage != ref
        controls = {
            "missing_lineage": missing_lineage,
            "bad_npz": persist_variant(
                {
                    **bundle,
                    "vectors_ref": bad_npz.model_dump(mode="json"),
                    "vectors_bytes_len": len(bad_bytes),
                },
                bad_npz,
            ),
            "too_large": persist_variant({**bundle, "max_elements": 1_000_000_000}, member),
            "native_graph": memory.save_to_artifact(store, emit_v2=True),
        }
    target = source.model_copy(update={"run_id": "target"})
    code = """
import json, sys
from importlib.metadata import version
from time import perf_counter
from unittest.mock import patch
import hnswlib
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.scientist.agent.vector_memory import VectorMemoryStore
from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from polisyos.scientist.methods.search.strategies.transfer import RunFingerprint, TransferLearningManager

store = FileSystemCAS(sys.argv[1]).with_ambient_ownership_enforcement()
ref = ArtifactRef.model_validate_json(sys.argv[2])
target = RunFingerprint.model_validate_json(sys.argv[3])
native_index = hnswlib.Index
calls = []

class ObservedIndex:
    def __init__(self, *args, **kwargs):
        calls.append('construct')
        self.native = native_index(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.native, name)

    def add_items(self, *args, **kwargs):
        calls.append('add_items')
        return self.native.add_items(*args, **kwargs)

    def knn_query(self, *args, **kwargs):
        calls.append('query')
        return self.native.knn_query(*args, **kwargs)

    def save_index(self, *args, **kwargs):
        calls.append('native_save')
        return self.native.save_index(*args, **kwargs)

    def load_index(self, *args, **kwargs):
        calls.append('native_load')
        return self.native.load_index(*args, **kwargs)

with tenant_scope(None, tenant_id=target.tenant_id), patch.object(hnswlib, 'Index', ObservedIndex):
    start = perf_counter()
    memory = VectorMemoryStore.from_portable_artifact(store, ref)
    rebuild_seconds = perf_counter() - start
    manager = TransferLearningManager(store, memory)
    discovery = manager.discover_similar_runs(target, top_k=1)
    discovery_calls = list(calls)
    start = perf_counter()
    observation, = WarmStartBridge(manager).load_warm_start(target, similar_runs=discovery.runs)
    history_read_seconds = perf_counter() - start
    assert calls == discovery_calls
    for name, value in json.loads(sys.argv[4]).items():
        try:
            memory.load_from_artifact(store, ArtifactRef.model_validate(value))
        except ValueError as exc:
            refusal = str(exc)
        else:
            raise AssertionError(f'{name} published a new index')
        assert memory.index_binding_status == 'rows_selected'
        nearest = memory.query([1., 0.], 2)
        assert [row[0] for row in nearest] == ['source', 'unbound-neighbor']
        assert [row[1] for row in nearest] == [0.0, 1.0]
        if name == 'missing_lineage':
            assert 'lineage_mismatch' in refusal
        elif name == 'bad_npz':
            assert 'npz' in refusal.lower()
        elif name == 'too_large':
            assert 'resource_limit' in refusal
        else:
            assert 'legacy_native_index_not_admitted' in refusal
    print(json.dumps({
        'native_version': version('hnswlib'), 'status': memory.index_binding_status,
        'discovery_status': discovery.status, 'scanned': discovery.scanned,
        'history': discovery.runs[0].history_ref.model_dump(mode='json'),
        'candidate_id': observation.candidate_id, 'scalar': observation.scalar_score,
        'params': observation.params, 'valid': observation.is_valid, 'calls': calls,
        'rebuild_seconds': rebuild_seconds, 'history_read_seconds': history_read_seconds,
    }))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(root),
            ref.model_dump_json(),
            target.model_dump_json(),
            json.dumps({key: value.model_dump(mode="json") for key, value in controls.items()}),
        ],
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["status"] == "rows_selected" and output["discovery_status"] == "filled"
    assert output["scanned"] == 1 and output["history"] == history.model_dump(mode="json")
    assert output["valid"] and output["params"] == {"x": 0.5}
    assert output["candidate_id"] == str(candidate.artifact_id) and output["scalar"] == 0.8
    assert output["calls"] == [
        "construct",
        "add_items",
        "add_items",
        "query",
        "query",
        "query",
        "query",
        "query",
    ]
    print(json.dumps({"portable_save_seconds": save_seconds, "npz_bytes": member_bytes, **output}))


def test_real_native_partial_update_restores_or_disables_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("hnswlib")
    store = FileSystemCAS(tmp_path / "cas")
    memory = VectorMemoryStore(dim=2, max_elements=16, ef_construction=16, M=4)
    saved = memory._save_index_bytes
    restored = memory._restore_index_bytes
    snapshots: list[tuple[int, float]] = []
    rollbacks: list[float] = []

    def observe_snapshot() -> bytes:
        start = perf_counter()
        raw = saved()
        snapshots.append((len(raw), perf_counter() - start))
        return raw

    def observe_restore(raw, generation):
        start = perf_counter()
        index = restored(raw, generation)
        rollbacks.append(perf_counter() - start)
        return index

    monkeypatch.setattr(memory, "_save_index_bytes", observe_snapshot)
    monkeypatch.setattr(memory, "_restore_index_bytes", observe_restore)
    start = perf_counter()
    for number in range(16):
        angle = 0.19 * number
        memory.add(f"row-{number}", [math.cos(angle), math.sin(angle)], {"number": number})
    add_seconds = perf_counter() - start
    with pytest.raises(RuntimeError, match="capacity exhausted"):
        memory.add("overflow", [1.0, 0.0])
    with pytest.raises(ValueError, match="dimension mismatch"):
        memory.add("row-0", [1.0])
    cycle = {}
    cycle["self"] = cycle
    with pytest.raises(ValueError, match="cannot contain cycles"):
        memory.add("row-0", [1.0, 0.0], cycle)
    with pytest.raises(ValueError, match="reserved"):
        memory.add("row-0", [1.0, 0.0], {"nested": {"_type": "alias"}})
    assert len(snapshots) == 16
    original_bound_index = saved()
    original_ref = memory.save_to_artifact(store, emit_v2=True)
    original_rows = memory.query([1.0, 0.0], 16)
    assert original_rows[0] == ("row-0", 0.0, {"number": 0})
    entered = Event()
    release = Event()
    physically_mutated: list[list[float]] = []

    class FailAfterNativeAdd:
        def __init__(self, native):
            self.native = native

        def __getattr__(self, name):
            return getattr(self.native, name)

        def add_items(self, vectors, labels):
            self.native.add_items(vectors, labels)
            physically_mutated.append(self.native.get_items(labels)[0].tolist())
            entered.set()
            assert release.wait(5)
            raise RuntimeError("injected after the native update")

    def install_native_fault() -> None:
        generation = memory._get_generation()
        memory._generation = replace(generation, index=FailAfterNativeAdd(generation.index))

    def run_during_mutation(ready: Event, run):
        assert not memory._generation_lock.acquire(blocking=False)
        ready.set()
        return run()

    install_native_fault()
    with ThreadPoolExecutor(max_workers=3) as worker:
        write = worker.submit(memory.add, "row-0", [0.0, 1.0], {"changed": True})
        queried = Event()
        persisted = Event()
        try:
            assert entered.wait(5)
            read = worker.submit(run_during_mutation, queried, lambda: memory.query([1.0, 0.0], 16))
            save = worker.submit(
                run_during_mutation, persisted, lambda: memory.save_to_artifact(store, emit_v2=True)
            )
            assert queried.wait(5) and persisted.wait(5)
        finally:
            release.set()
        with pytest.raises(RuntimeError, match="injected after the native update"):
            write.result(timeout=5)
        assert read.result(timeout=5) == original_rows
        assert save.result(timeout=5) == original_ref
    assert physically_mutated == [[0.0, 1.0]]
    assert saved() == original_bound_index and len(rollbacks) == 1
    snapshot_count = len(snapshots)
    assert memory.query([1.0, 0.0], 16) == original_rows
    assert len(snapshots) == snapshot_count and len(rollbacks) == 1

    def fail_after_native_restore(raw, generation):
        observe_restore(raw, generation)
        raise OSError("injected generation recovery failure")

    monkeypatch.setattr(memory, "_restore_index_bytes", fail_after_native_restore)
    install_native_fault()
    unavailable = "vector_memory_generation_unavailable_after_failed_rollback"
    with pytest.raises(RuntimeError, match=unavailable):
        memory.add("row-0", [0.0, 1.0], {"changed": True})
    assert physically_mutated == [[0.0, 1.0], [0.0, 1.0]] and len(rollbacks) == 2
    for operation in (
        lambda: memory.query([1.0, 0.0]),
        lambda: memory.lookup_metadata("row-0"),
        lambda: memory.save_to_artifact(store, emit_v2=True),
        lambda: memory.add("row-0", [1.0, 0.0]),
    ):
        with pytest.raises(RuntimeError, match=unavailable):
            operation()
    memory.load_from_artifact(store, original_ref, allow_trusted_native=True)
    assert memory.index_binding_status == "exact_selected"
    assert memory.query([1.0, 0.0], 16) == original_rows
    print(
        json.dumps(
            {
                "native_rows": 16,
                "add_seconds": add_seconds,
                "add_snapshots": snapshots[:16],
                "native_rollback_seconds": rollbacks,
            }
        )
    )
