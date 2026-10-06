"""Separate native producers/readers for exact CAS vector-generation admission."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def produce(root: Path) -> None:
    from polisyos.scientist.agent.vector_memory import VectorMemoryStore
    from tests.unit.scientist.methods.search.strategies.test_transfer import measured_history

    store, index, _, source, target, evaluations, _ = measured_history(root, count=3)
    large = VectorMemoryStore(dim=2, max_elements=1100)
    large.add(source.run_id, source.embedding, index.metadata_for_key(source.run_id))
    for number in range(1001):
        # These are discovery entries, never fabricated measured observations.
        large.add(f"unrelated-{number}", [0.0, 1.0], {"objective_names": ["other"]})
    bundle = large.save_to_artifact(store)
    packet = {
        "bundle": bundle.model_dump(mode="json"),
        "source": source.model_dump(mode="json"),
        "target": target.model_dump(mode="json"),
        "expected_evaluation_refs": sorted(e.provenance_ref for e in evaluations),
        "catalog_count": len(large),
    }
    (root / "input.json").write_text(json.dumps(packet, sort_keys=True))
    print("NATIVE_PRODUCER", json.dumps(packet, sort_keys=True))


def receive(root: Path) -> None:
    from polisyos.core import artifacts, canon
    from polisyos.scientist.agent.vector_memory import VectorMemoryStore
    from polisyos.scientist.methods.search.strategies.transfer import (
        RunFingerprint,
        TransferLearningManager,
    )

    packet = json.loads((root / "input.json").read_text())
    store = artifacts.FileSystemCAS(root / "cas")
    snapshot_reader = store.get_verified_snapshot
    reads = []

    def observed_snapshot(ref):
        result = snapshot_reader(ref)
        reads.append(ref.model_dump(mode="json"))
        return result

    def legacy_read_forbidden(*args, **kwargs):
        raise AssertionError("The composed native consumer must use B's actual snapshot port")

    store.get_verified_snapshot = observed_snapshot
    store.get_bytes = legacy_read_forbidden
    store.get_manifest = legacy_read_forbidden
    bundle_ref = artifacts.ArtifactRef.model_validate(packet["bundle"])
    memory = VectorMemoryStore(dim=1, max_elements=2)
    memory.add("previous", [1.0], {"generation": "previous"})
    memory.load_from_artifact(store, bundle_ref)
    generation = memory._generation
    assert generation.dim == 2
    assert len(generation.keys) == len(generation.metadata) == len(generation.key_to_idx) == 1002
    assert len(memory) == packet["catalog_count"]
    assert generation.ref_identity == artifacts.artifact_ref_identity_key(bundle_ref)
    query = memory.query
    ann_calls = []
    phase = "discovery"

    def observed_ann(*args, **kwargs):
        assert phase == "discovery", "Exact history addressing cannot call ANN again"
        ann_calls.append(phase)
        return query(*args, **kwargs)

    memory.query = observed_ann
    manager = TransferLearningManager(store, memory)
    target = RunFingerprint.model_validate(packet["target"])
    selected = manager.find_similar_runs(target, top_k=1)
    assert len(selected) == 1
    assert selected[0].history_ref.model_dump(mode="json") == packet["source"]["history_ref"]
    phase = "address"
    rows = manager.get_warm_start_evaluations(selected, max_evals=3, target_fingerprint=target)
    assert sorted(e.provenance_ref for e in rows) == packet["expected_evaluation_refs"]
    assert manager.last_admission_report["accepted"] == len(rows) == 3
    assert manager.last_admission_report["rejected"] == 0
    assert ann_calls == ["discovery"]
    rows[0].params["x"] = 999
    assert all(row["params"]["x"] < 1 for row in manager._load_run_evaluations("source"))
    assert ann_calls == ["discovery"]

    bundle = canon.from_canonical_bytes(snapshot_reader(bundle_ref).data)
    native_ref = artifacts.ArtifactRef.model_validate(bundle["index_ref"])
    original_bytes = snapshot_reader(native_ref).data
    (root / "native-before-tamper.bin").write_bytes(original_bytes)
    blob, _ = store._paths(native_ref.artifact_id)
    blob.write_bytes(b"altered native bytes under the same complete ArtifactRef")
    try:
        memory.load_from_artifact(store, bundle_ref)
    except (ValueError, OSError, RuntimeError) as exc:
        refusal = {"type": type(exc).__name__, "reason": str(exc)}
    else:
        raise AssertionError("Same-ref content mutation must refuse before publication")
    assert memory._generation is generation
    assert query([1.0, 0.0], top_k=1)[0][0] == "source"
    assert memory.metadata_for_key("source")["history_ref"] == packet["source"]["history_ref"]
    print(
        "NATIVE_RECEIVER",
        json.dumps(
            {
                "catalog_count": len(memory),
                "ann_calls": ann_calls,
                "accepted": 3,
                "snapshot_reads": reads,
                "bundle_ref": packet["bundle"],
                "old_generation_coherent_after_mutation": True,
                "refusal": refusal,
                "original_native_sha256": hashlib.sha256(original_bytes).hexdigest(),
            },
            sort_keys=True,
        ),
    )
    for name in (
        "polisyos.core.artifacts.store",
        "polisyos.scientist.agent.vector_memory",
        "polisyos.scientist.methods.search.strategies.transfer",
        "hnswlib",
    ):
        origin = Path(sys.modules[name].__file__)
        print(
            "ACTUAL_PROCESS_ORIGIN", name, origin, hashlib.sha256(origin.read_bytes()).hexdigest()
        )


def corrupted_native(root: Path) -> None:
    from polisyos.core import artifacts, canon
    from polisyos.scientist.agent.vector_memory import VectorMemoryStore

    store = artifacts.FileSystemCAS(root / "cas")
    old = VectorMemoryStore(dim=2, max_elements=3)
    old.add("old", [1.0, 0.0], {"generation": "old"})
    previous = old._generation
    new = VectorMemoryStore(dim=2, max_elements=3)
    new.add("new", [0.0, 1.0], {"generation": "new"})
    original = new.save_to_artifact(store)
    payload = canon.from_canonical_bytes(store.get_verified_snapshot(original).data)
    native_ref = artifacts.ArtifactRef.model_validate(payload["index_ref"])
    native = store.get_verified_snapshot(native_ref).data
    # Preserve the admitted native header. Failure must occur in actual load_index.
    truncated = store.put_bytes(
        native[:96], artifacts.PutOptions(kind=native_ref.kind, media_type=native_ref.media_type)
    )
    payload["index_ref"] = truncated.model_dump(mode="json")
    broken = store.put_json(
        payload,
        artifacts.PutOptions(kind=original.kind, media_type=original.media_type),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )
    old._admit_native_header(native[:96], dim=2, capacity=3, count=1)
    try:
        old.load_from_artifact(store, broken)
    except RuntimeError as exc:
        refusal = str(exc)
    else:
        raise AssertionError("Actual native HNSW load must reject the corrupted payload")
    assert old._generation is previous
    assert old.query([1.0, 0.0], top_k=1) == [("old", 0.0, {"generation": "old"})]
    print("ACTUAL_NATIVE_LOAD_REFUSAL", refusal, "OLD_GENERATION_COHERENT")


if __name__ == "__main__":
    action, path = sys.argv[1:]
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    {"produce": produce, "receive": receive, "corrupted_native": corrupted_native}[action](root)
