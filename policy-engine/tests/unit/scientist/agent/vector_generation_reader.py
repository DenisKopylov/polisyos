"""Fresh native reader for the bounded TRN-02 exact-CAS consumer witness."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

from polisyos.core import artifacts
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent.vector_memory import VectorMemoryStore


def main():
    request = json.loads(Path(sys.argv[1]).read_text())
    store = FileSystemCAS(Path(request["cas"]))
    captured = []
    read = store.get_verified_snapshot

    def snapshot(ref):
        assert isinstance(ref, artifacts.ArtifactRef)
        result = read(ref)
        manifest = result.manifest
        captured.append(
            {
                "ref": ref.model_dump(mode="json"),
                "actual_sha256": hashlib.sha256(result.data).hexdigest(),
                "manifest_sha256": hashlib.sha256(result.manifest_bytes).hexdigest(),
                "bytes": len(result.data),
                "kind": manifest.kind,
                "media_type": manifest.media_type,
            }
        )
        return result

    store.get_verified_snapshot = snapshot
    memory = VectorMemoryStore(dim=2, max_elements=1008)
    memory.add("prior-reader", [1.0, 0.0], {"generation": "prior"})
    old = memory.query([1.0, 0.0])
    bundle = artifacts.ArtifactRef.model_validate(request["bundle"])
    try:
        memory.load_from_artifact(store, bundle)
    except (RuntimeError, ValueError) as exc:
        assert memory.query([1.0, 0.0]) == old
        print(
            json.dumps(
                {"status": "refused", "reason": str(exc), "unchanged": True, "reads": captured}
            )
        )
        return
    if request.get("native_only"):
        print(json.dumps({"status": "admitted", "query": memory.query([1.0, 0.0])}))
        return
    from polisyos.scientist.methods.search.strategies.transfer import (
        RunFingerprint,
        TransferLearningManager,
    )

    source = RunFingerprint.model_validate(request["source"])
    target = RunFingerprint.model_validate(request["target"])
    manager = TransferLearningManager(store, memory)

    def no_ann(*args, **kwargs):
        raise AssertionError("Exact history read must not perform ANN discovery")

    memory.query = no_ann
    records = manager._load_run_evaluations(source.run_id)
    rows = manager.get_warm_start_evaluations([source], target_fingerprint=target)
    print(
        json.dumps(
            {
                "status": "admitted",
                "generation_count": len(memory),
                "history_count": len(records),
                "candidate_ids": [row.candidate_id for row in rows],
                "scores": [row.scalar_score for row in rows],
                "reads": captured,
                "backend": {
                    "hnswlib": importlib.metadata.version("hnswlib"),
                    "numpy": importlib.metadata.version("numpy"),
                    "python": sys.version,
                },
                "source_paths": {
                    "vector_memory": sys.modules[VectorMemoryStore.__module__].__file__,
                    "cas": sys.modules[FileSystemCAS.__module__].__file__,
                },
            }
        )
    )


if __name__ == "__main__":
    main()
