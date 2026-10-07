"""Explicit persisted old-scalar and placeholder refusal through native/CAS consumers."""

import json

import pytest

from polisyos.core import artifacts, canon
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent.vector_memory import VectorMemoryStore
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    persist_benchmark_evaluation,
)
from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from polisyos.scientist.methods.search.objective import OptimizationDirection
from polisyos.scientist.methods.search.strategies.transfer import TransferLearningManager
from tests.unit.scientist.methods.search.strategies.test_transfer import (
    changed_history,
    measured_history,
)

pytest.importorskip("hnswlib", reason="UNRUN: legacy transfer refusal requires native HNSW")
pytestmark = pytest.mark.integration


@pytest.mark.parametrize("direction", list(OptimizationDirection))
@pytest.mark.parametrize("legacy", ["schema1", "schema-absent", "placeholder"])
def test_persisted_legacy_scalar_or_placeholder_has_visible_refusal_without_promotion(
    tmp_path, record_property, direction, legacy
) -> None:
    """An unsupported scalar convention or zero address never becomes measured history."""
    store, index, _, source, target, _, basis = measured_history(
        tmp_path, direction=direction, count=2
    )
    supported = WarmStartBridge(TransferLearningManager(store, index), max_evals=2)
    assert len(supported.load_warm_start(target)) == 2

    def alter(payload):
        if legacy == "schema1":
            payload["schema_version"] = "1.0"
        elif legacy == "schema-absent":
            del payload["schema_version"]
        else:
            placeholder = artifacts.ArtifactRef(
                artifact_id="sha256:" + "0" * 64,
                kind="search.candidate",
                media_type="application/json",
            )
            for row in payload["evaluations"]:
                ref = artifacts.ArtifactRef.model_validate(row["metadata"]["evaluation_ref"])
                original = BenchmarkEvaluation.model_validate(
                    canon.from_canonical_bytes(store.get_verified_snapshot(ref).data)
                )
                rewritten = persist_benchmark_evaluation(
                    store, original.model_copy(update={"candidate_ref": placeholder})
                )
                row["candidate_id"] = str(placeholder.artifact_id)
                row["provenance_ref"] = str(rewritten.artifact_id)
                row["metadata"]["candidate_ref"] = placeholder.model_dump(mode="json")
                row["metadata"]["evaluation_ref"] = rewritten.model_dump(mode="json")

    old = changed_history(store, source, alter)
    metadata = old.model_dump(mode="json", exclude={"history_ref", "embedding"})
    metadata["history_ref"] = old.history_ref.model_dump(mode="json")
    index.add(old.run_id, old.embedding, metadata)
    bundle = index.save_to_artifact(store)
    reopened = FileSystemCAS(store.root)
    native = VectorMemoryStore(dim=2, max_elements=10)
    native.load_from_artifact(reopened, bundle)
    manager = TransferLearningManager(reopened, native)
    bridge = WarmStartBridge(manager, max_evals=2)
    rows = bridge.load_warm_start(target)
    assert rows == []
    report = bridge.last_load_report
    counts = {
        key: report[key] for key in ("loaded", "accepted", "rejected", "unavailable", "selected")
    }
    assert counts == (
        dict(loaded=2, accepted=0, rejected=2, unavailable=0, selected=0)
        if legacy == "placeholder"
        else dict(loaded=0, accepted=0, rejected=0, unavailable=1, selected=0)
    )
    if legacy != "placeholder":
        assert "Unsupported transfer history codec" in report["rejections"][0]["reason"]
        assert manager.cache_info["entries"] == 0
    else:
        assert len(report["rejections"]) == 2
        assert all("reason" in refusal and refusal["reason"] for refusal in report["rejections"])
    benchmarks = bridge.evaluations_to_benchmarks(rows, target_basis=basis, loop_id="receiving")
    assert benchmarks == []
    record_property(
        "legacy_refusal_receipt",
        json.dumps(
            {
                "legacy": legacy,
                "direction": direction.value,
                "history_ref": old.history_ref.model_dump(mode="json"),
                "bundle_ref": bundle.model_dump(mode="json"),
                "counts": counts,
                "rejections": report["rejections"],
                "admitted_numeric_rows": len(rows),
                "reverse_replay_rows": len(benchmarks),
                "profile": (
                    "Explicit v2 required; missing old scalar convention "
                    "or real candidate is not inferred"
                ),
            },
            sort_keys=True,
        ),
    )
