"""Native HNSW and fresh-process witnesses for selected vector snapshots."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from polisyos.core.artifacts import input_ref_from_artifact_ref
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.agent.vector_memory import VectorMemoryStore


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
    store = FileSystemCAS(root)
    memory = VectorMemoryStore(dim=2, max_elements=4)
    memory.add("A", [1.0, 0.0], {"source": "A"})
    memory.add("B", [0.0, 1.0], {"source": "B"})
    ref = memory.save_to_artifact(store, emit_rows=True)
    code = """
import json, sys
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent.vector_memory import VectorMemoryStore
store = FileSystemCAS(sys.argv[1])
ref = ArtifactRef.model_validate_json(sys.argv[2])
memory = VectorMemoryStore.from_portable_artifact(store, ref)
print(json.dumps({'status': memory.index_binding_status, 'rows': memory.query([1.,0.], 2)}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(root), ref.model_dump_json()],
        check=True,
        text=True,
        capture_output=True,
        timeout=30,
    )
    output = json.loads(result.stdout)
    assert output["status"] == "rows_selected"
    assert [row[0] for row in output["rows"]] == ["A", "B"]
    assert [row[1] for row in output["rows"]] == pytest.approx([0.0, 1.0])
    assert [row[2] for row in output["rows"]] == [{"source": "A"}, {"source": "B"}]
