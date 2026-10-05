"""CAS snapshot and consumer isolation checks for numerical transfer."""

from __future__ import annotations

import json

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.scientist.methods.search.strategies.transfer import (
    RunFingerprint,
    TransferLearningManager,
)


def test_history_consumer_mutation_cannot_change_cached_snapshot(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        json.dumps(
            {
                "run_id": "run",
                "evaluations": [
                    {
                        "candidate_id": "candidate",
                        "params": {"x": 0.5},
                        "params_normalized": [0.5],
                        "scalar_score": 1.0,
                        "stage_a_passed": True,
                        "status": "success",
                        "objectives": [
                            {"name": "score", "raw_value": 1.0, "direction": "minimize"}
                        ],
                        "metadata": {"source_run_id": "run", "binding": {"basis": "original"}},
                    }
                ],
            }
        ).encode(),
        PutOptions(kind="search.transfer.history", media_type="application/json"),
    )
    fingerprint = RunFingerprint(
        run_id="run", space_hash="space", objective_names=["score"], history_ref=ref
    )
    manager = TransferLearningManager(store, None)
    first = manager.get_warm_start_evaluations([fingerprint])[0]
    first.params["x"] = 0.9
    first.metadata["binding"]["basis"] = "mutated"
    second = manager.get_warm_start_evaluations([fingerprint])[0]
    cold = TransferLearningManager(store, None).get_warm_start_evaluations([fingerprint])[0]
    assert second.params == cold.params == {"x": 0.5}
    assert second.metadata["binding"] == cold.metadata["binding"] == {"basis": "original"}
