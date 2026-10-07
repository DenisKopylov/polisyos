"""Native cosine admission and a fresh-process exact-CAS transfer consumer."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from polisyos.core import artifacts, canon
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent.vector_memory import VectorMemoryStore


@pytest.mark.parametrize(
    "value",
    [10**400, True, "1", float("nan"), float("inf")],
    ids=["huge-int", "bool", "string", "nan", "inf"],
)
@pytest.mark.parametrize("operation", ["add", "query"])
def test_invalid_native_coordinate_refuses_with_index_and_keeps_generation(value, operation):
    pytest.importorskip("hnswlib")
    memory = VectorMemoryStore(dim=2, max_elements=2)
    memory.add("prior", [1.0, 0.0], {"generation": "prior"})
    before = memory._generation
    call = (
        (lambda: memory.add("invalid", [1.0, value], {"generation": "invalid"}))
        if operation == "add"
        else lambda: memory.query([1.0, value])
    )
    with pytest.raises(ValueError, match="coordinate 1"):
        call()
    assert memory._generation is before
    assert memory.query([1.0, 0.0]) == [("prior", 0.0, {"generation": "prior"})]


@pytest.mark.parametrize("scale", [1e300, 1e30, 1.0, 1e-300])
def test_cosine_direction_survives_native_float32_narrowing(scale):
    pytest.importorskip("hnswlib")
    memory = VectorMemoryStore(dim=2, max_elements=3)
    memory.add("direction", [scale, scale], {})
    memory.add("orthogonal", [scale, -scale], {})
    memory.add("axis", [scale, 0.0], {})
    rows = memory.query([scale, scale], top_k=3)
    assert [row[0] for row in rows] == ["direction", "axis", "orthogonal"]
    expected = [0.0, 1.0 - 1.0 / math.sqrt(2.0), 1.0]
    assert [row[1] for row in rows] == pytest.approx(expected, abs=2e-6)
    assert all(math.isfinite(row[1]) for row in rows)


def test_zero_embedding_preserves_supported_native_control():
    pytest.importorskip("hnswlib")
    memory = VectorMemoryStore(dim=2, max_elements=2)
    memory.add("zero", [0, 0.0], {})
    rows = memory.query([0.0, 0], top_k=1)
    assert rows[0][0] == "zero" and math.isfinite(rows[0][1])


def test_exact_transfer_reference_beyond_1000_keys_survives_fresh_native_reader(
    tmp_path, monkeypatch, record_property
):
    pytest.importorskip("hnswlib")
    from polisyos.scientist.methods.search.strategies.transfer import TransferLearningManager
    from tests.unit.scientist.methods.search.strategies.test_transfer import measured_history

    store, _, _, source, target, originals, _ = measured_history(tmp_path, count=2)
    memory = VectorMemoryStore(dim=2, max_elements=1008)
    manager = TransferLearningManager(store, memory)
    donor_rows = canon.from_canonical_bytes(store.get_verified_snapshot(source.history_ref).data)[
        "evaluations"
    ]
    registered_refs = set()
    # These are 1001 discovery snapshots through the ordinary producer, each
    # carrying the same controlled donor observations without changing their
    # original source IDs or basis. They are not 1001 new measured executions.
    # Only the original source below is admitted as numerical training data.
    for number in range(1001):
        angle = math.pi / 3.0 + (math.pi / 3.0) * number / 1000.0
        distractor = source.model_copy(
            deep=True,
            update={
                "run_id": f"distractor-{number}",
                "embedding": [math.cos(angle), math.sin(angle)],
                "history_ref": None,
            },
        )
        history_ref = manager.register_run(distractor, originals)
        assert history_ref is not None
        snapshot = store.get_verified_snapshot(history_ref)
        assert snapshot.manifest.kind == "search.transfer.history"
        assert snapshot.manifest.media_type == "application/json"
        payload = canon.from_canonical_bytes(snapshot.data)
        assert payload["schema_version"] == "2.0"
        assert payload["fingerprint"]["run_id"] == distractor.run_id
        assert payload["evaluations"] == donor_rows
        registered_refs.add(str(history_ref.artifact_id))
        assert memory.metadata_for_key(distractor.run_id)["history_ref"] == history_ref.model_dump(
            mode="json"
        )
    assert len(registered_refs) == 1001
    source.history_ref = manager.register_run(source, originals)
    discovered = manager.find_similar_runs(target, top_k=None)
    assert len(memory) == len(discovered) == 1002
    selected = next(run for run in discovered if run.run_id == source.run_id)
    assert selected.history_ref == source.history_ref
    assert memory.metadata_for_key(source.run_id)["history_ref"] == source.history_ref.model_dump(
        mode="json"
    )
    monkeypatch.setattr(memory, "query", lambda *args, **kwargs: pytest.fail("Second ANN query"))
    rows = manager.get_warm_start_evaluations([selected], target_fingerprint=target)
    assert len(rows) == 2
    bundle = memory.save_to_artifact(store)
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "cas": str(store.root),
                "bundle": bundle.model_dump(mode="json"),
                "source": source.model_dump(mode="json"),
                "target": target.model_dump(mode="json"),
            }
        )
    )
    worker = Path(__file__).with_name("vector_generation_reader.py")
    response = subprocess.run(
        [sys.executable, str(worker), str(request)], capture_output=True, text=True, check=True
    )
    result = json.loads(response.stdout)
    record_property("fresh_native_receipt", response.stdout)
    assert result["status"] == "admitted" and result["generation_count"] == 1002
    assert result["history_count"] == 2
    assert result["candidate_ids"] == [row.candidate_id for row in rows]
    assert result["scores"] == [row.scalar_score for row in rows]
    assert any(
        read["ref"] == source.history_ref.model_dump(mode="json") for read in result["reads"]
    )
    assert all(
        read["actual_sha256"] == artifacts.ArtifactRef.model_validate(read["ref"]).artifact_id.hex
        for read in result["reads"]
    )
    assert result["backend"]["hnswlib"] == "0.8.0"
    assert any(read["kind"] == "vector_memory.index" for read in result["reads"])
    blob, _ = store._paths(bundle.artifact_id)
    blob.write_bytes(b"changed bytes while retaining the exact composite ref")
    failed = subprocess.run(
        [sys.executable, str(worker), str(request)], capture_output=True, text=True, check=True
    )
    refusal = json.loads(failed.stdout)
    record_property("fresh_native_tamper_receipt", failed.stdout)
    assert refusal["status"] == "refused" and refusal["unchanged"]


def test_valid_cas_legacy_native_nonfinite_refuses_before_pointer_publication(
    tmp_path, monkeypatch, record_property
):
    pytest.importorskip("hnswlib")
    store = FileSystemCAS(tmp_path / "cas")
    legacy = VectorMemoryStore(dim=2, max_elements=2)
    # Reproduce the old native narrowing with real HNSW, retaining a valid
    # composite schema, native header, labels, CAS digest and manifest.
    monkeypatch.setattr(legacy, "_embedding", lambda embedding, dim: list(embedding))
    with pytest.warns(RuntimeWarning, match="overflow encountered in cast"):
        legacy.add("historical-nonfinite", [1e300, 1.0], {"origin": "legacy"})
    ref = legacy.save_to_artifact(store)
    assert store.get_verified_snapshot(ref).manifest.kind == "vector_memory.bundle"
    reader = VectorMemoryStore(dim=2, max_elements=2)
    reader.add("prior", [1.0, 0.0], {"generation": "prior"})
    before = reader._generation
    with pytest.raises(ValueError, match="Native embedding row 0 coordinate 0 must be finite"):
        reader.load_from_artifact(store, ref)
    assert reader._generation is before
    assert reader.query([1.0, 0.0]) == [("prior", 0.0, {"generation": "prior"})]
    request = tmp_path / "legacy-request.json"
    request.write_text(
        json.dumps(
            {"cas": str(store.root), "bundle": ref.model_dump(mode="json"), "native_only": True}
        )
    )
    worker = Path(__file__).with_name("vector_generation_reader.py")
    response = subprocess.run(
        [sys.executable, str(worker), str(request)], capture_output=True, text=True, check=True
    )
    result = json.loads(response.stdout)
    record_property("fresh_legacy_native_refusal", response.stdout)
    assert result["status"] == "refused" and result["unchanged"]
    assert "Native embedding row 0 coordinate 0 must be finite" in result["reason"]
