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
    for discovery_limit in (1, 2):
        bounded = manager.find_similar_runs(target, top_k=discovery_limit)
        reselected = next(run for run in bounded if run.run_id == source.run_id)
        assert reselected.history_ref == selected.history_ref
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


@pytest.mark.parametrize("intake", ["empty", "invalid", "unavailable", "nonempty"])
def test_persisted_empty_transfer_history_is_not_a_rejected_or_unavailable_intake(
    tmp_path, record_property, intake
):
    pytest.importorskip("hnswlib")
    from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
    from polisyos.scientist.methods.search.strategies.transfer import (
        TransferLearningManager,
    )
    from tests.unit.scientist.methods.search.strategies.test_transfer import (
        changed_history,
        measured_history,
    )

    store, index, _, source, target, originals, _ = measured_history(tmp_path, count=2)

    def change(payload):
        if intake == "empty":
            payload["evaluations"].clear()
        elif intake == "invalid":
            for row in payload["evaluations"]:
                row["scalar_score"] = False
        elif intake == "unavailable":
            payload["schema_version"] = "unsupported"

    persisted = changed_history(store, source, change)
    snapshot = store.get_verified_snapshot(persisted.history_ref)
    assert snapshot.manifest.kind == "search.transfer.history"
    assert snapshot.manifest.media_type == "application/json"
    payload = canon.from_canonical_bytes(snapshot.data)
    assert len(payload["evaluations"]) == (0 if intake == "empty" else 2)
    metadata = persisted.model_dump(mode="json", exclude={"history_ref", "embedding"})
    metadata["history_ref"] = persisted.history_ref.model_dump(mode="json")
    index.add(persisted.run_id, persisted.embedding, metadata)
    bundle = index.save_to_artifact(store)

    # A fresh native generation and fresh CAS owner supply the ordinary bridge.
    # This is a reader fixture, not a change to the empty register_run policy.
    reopened_store = FileSystemCAS(store.root)
    reopened_index = VectorMemoryStore(dim=2, max_elements=10)
    reopened_index.load_from_artifact(reopened_store, bundle)
    manager = TransferLearningManager(reopened_store, reopened_index)
    discovered = manager.find_similar_runs(target)
    assert len(discovered) == 1 and discovered[0].history_ref == persisted.history_ref
    bridge = WarmStartBridge(manager, max_evals=2, top_k_runs=1)
    rows = bridge.load_warm_start(target)
    report = bridge.last_load_report
    counts = {
        name: report[name] for name in ("loaded", "accepted", "rejected", "unavailable", "selected")
    }
    expected = {
        "empty": dict(loaded=0, accepted=0, rejected=0, unavailable=0, selected=0),
        "invalid": dict(loaded=2, accepted=0, rejected=2, unavailable=0, selected=0),
        "unavailable": dict(loaded=0, accepted=0, rejected=0, unavailable=1, selected=0),
        "nonempty": dict(loaded=2, accepted=2, rejected=0, unavailable=0, selected=2),
    }
    assert counts == expected[intake]
    assert len(rows) == expected[intake]["selected"]
    if intake in ("empty", "nonempty"):
        assert report["rejections"] == []
    elif intake == "invalid":
        assert len(report["rejections"]) == 2
        assert all(
            "scalar_score must be a finite JSON number" in r["reason"] for r in report["rejections"]
        )
    else:
        assert "Unsupported transfer history codec" in report["rejections"][0]["reason"]
    if intake == "nonempty":
        assert {row.candidate_id for row in rows} == {row.candidate_id for row in originals}
    record_property(
        "persisted_intake_receipt",
        json.dumps(
            {
                "intake": intake,
                "history_ref": persisted.history_ref.model_dump(mode="json"),
                "bundle_ref": bundle.model_dump(mode="json"),
                "report": report,
            },
            sort_keys=True,
        ),
    )
