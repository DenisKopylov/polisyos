"""Replicate one pinned functional WMR through CoreCAS without rebuilding its owner."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def main() -> int:
    """Keep the source read-only and verify exact bytes plus the actual WMR contract."""
    from polisyos.core.artifacts import ArtifactID, FileSystemCAS
    from polisyos.runtime.quality.world_model_record import load_world_model_record

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--artifact-ref", required=True)
    parser.add_argument("--record-hash", required=True)
    args = parser.parse_args()
    source = FileSystemCAS(args.source)
    artifact = ArtifactID(args.artifact_ref)
    before = source.get_bytes(artifact)
    if "sha256:" + hashlib.sha256(before).hexdigest() != str(artifact):
        raise ValueError("pinned_source_artifact_hash_mismatch")
    exported = source.export_subgraph([artifact], args.destination, compress=False)
    if exported.missing_artifacts or exported.missing_manifests:
        raise ValueError("pinned_functional_export_incomplete")
    destination = FileSystemCAS(args.destination)
    after = destination.get_bytes(artifact)
    if before != after:
        raise ValueError("functional_replica_byte_mismatch")
    record = load_world_model_record(destination, str(artifact))
    if record.content_hash != args.record_hash:
        raise ValueError("pinned_world_record_hash_mismatch")
    sys.stdout.write(
        json.dumps(
            {
                "status": "pass",
                "purpose": "functional_input_replica_not_a_new_world_model",
                "source": str(args.source),
                "destination": str(args.destination),
                "artifact_ref": str(artifact),
                "record_hash": record.content_hash,
                "source_and_destination_bytes_equal": True,
                "artifact_hash_independently_recomputed": True,
                "record_contract_recomputed": True,
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
