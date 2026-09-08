"""Require the normal DS11 owner to refuse a corrupted content binding."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    """Mutate one digest, execute the actual check, and restore writer bytes."""
    path = Path("apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json")
    original = path.read_bytes()
    before = json.loads(original)
    original_digest = before["payload_digest"]
    false_digest = "sha256:" + "0" * 64
    if original_digest == false_digest:
        raise ValueError("writer_digest_already_zero")
    marker = json.dumps(original_digest).encode()
    if original.count(marker) != 1:
        raise ValueError("mutation_identity_ambiguous")
    corrupted = original.replace(marker, json.dumps(false_digest).encode())
    after = json.loads(corrupted)
    after["payload_digest"] = original_digest
    if after != before:
        raise ValueError("unexpected_additional_mutation")
    command = [
        sys.executable,
        "-m",
        "tools.quality.validation.check_trust_claim_posture",
        "--repo-root",
        ".",
        "--check",
    ]
    started = time.monotonic()
    try:
        path.write_bytes(corrupted)
        result = subprocess.run(  # noqa: S603 — fixed owner command, no user input.
            command, capture_output=True, text=True, check=False
        )
    finally:
        path.write_bytes(original)
    restored = path.read_bytes()
    evidence = {
        "artifact": str(path),
        "mutation_path": "/payload_digest",
        "original_value": original_digest,
        "mutated_value": false_digest,
        "all_other_parsed_values_equal": after == before,
        "cwd": str(Path.cwd()),
        "argv": command,
        "PATH": os.environ.get("PATH"),
        "PYTHONPATH": os.environ.get("PYTHONPATH"),
        "returncode": result.returncode,
        "elapsed_seconds": time.monotonic() - started,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "restored_sha256": hashlib.sha256(restored).hexdigest(),
        "byte_identical_restoration": original == restored,
    }
    sys.stdout.write(json.dumps(evidence, indent=2) + "\n")
    if original != restored:
        raise ValueError("restoration_not_byte_identical")
    if result.returncode != 1 or "ValueError: DS11-GENERATED-DRIFT" not in result.stderr:
        raise ValueError("real_owner_did_not_refuse_corrupted_binding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
