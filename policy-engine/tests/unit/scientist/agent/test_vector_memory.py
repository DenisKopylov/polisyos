from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonViolation
from polisyos.scientist.agent.vector_memory import VectorMemoryStore


def test_vector_memory_cas_round_trip_preserves_float_fingerprint_metadata(tmp_path) -> None:
    pytest.importorskip("hnswlib")
    store = FileSystemCAS(tmp_path)
    source_identity = {
        "run_id": "source-run",
        "space_hash": "space-v1",
        "objective_names": ["employment"],
        "bounds": {"wage_support_amount": {"lower": 0.5, "upper": 1.5}},
        "split": "selection",
        "units": {"wage_support_amount": "dimensionless"},
        "origin": "controlled-candidate-transfer",
        "tenant_id": "controlled-tenant",
        "objective_directions": {"employment": "maximize"},
    }

    source = VectorMemoryStore(dim=2)
    source.add("source-run", [1.0, 0.0], metadata=source_identity)
    bundle_ref = source.save_to_artifact(store, emit_rows=True)

    restored = VectorMemoryStore(dim=2)
    restored.load_from_artifact(store, bundle_ref)
    results = restored.query([1.0, 0.0], top_k=1)

    assert len(results) == 1
    key, distance, metadata = results[0]
    assert key == "source-run"
    assert distance == pytest.approx(0.0)
    assert metadata == source_identity
    assert type(metadata["bounds"]["wage_support_amount"]["lower"]) is float
    assert type(metadata["bounds"]["wage_support_amount"]["upper"]) is float

    with pytest.raises(CanonViolation, match="float forbidden in canonical JSON"):
        store.put_json(
            {"bound": 0.5},
            PutOptions(kind="test.strict-default", media_type="application/json"),
        )
