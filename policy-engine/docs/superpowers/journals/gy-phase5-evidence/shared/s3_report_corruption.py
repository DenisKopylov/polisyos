"""Corrupt one substantive emitted claim, run the real owner, and restore bytes."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    """Require the unchanged full report checker to detect a false completion claim."""
    path = Path("architecture/policy_design_case/layer3_gy_intervention_substrate_contract.json")
    original = path.read_bytes()
    before = json.loads(original)
    if before["task_acceptance"]["mechanism_validation_is_task_completion"] is not False:
        raise ValueError("owner_completion_limitation_missing")
    marker = b'"mechanism_validation_is_task_completion": false'
    if original.count(marker) != 1:
        raise ValueError("mutation_identity_ambiguous")
    corrupted = original.replace(marker, marker.replace(b"false", b"true"))
    after = json.loads(corrupted)
    after["task_acceptance"]["mechanism_validation_is_task_completion"] = False
    if after != before:
        raise ValueError("unexpected_additional_mutation")
    command = [
        sys.executable,
        "-m",
        "tools.quality.validation.check_layer3_gy_intervention_substrate_contract",
        "--check",
        "--output-format",
        "json",
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
    # The owner logs registry boot before its final indented JSON report.
    report_start = result.stdout.rfind("\n{") + 1
    report = json.loads(result.stdout[report_start:])
    evidence = {
        "artifact": str(path),
        "mutation_path": "/task_acceptance/mechanism_validation_is_task_completion",
        "original_value": False,
        "mutated_value": True,
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
    if result.returncode != 1 or report["behavior_status"] != "pass":
        raise ValueError("real_owner_did_not_refuse_only_the_corrupted_record")
    if {item["code"] for item in report["issues"]} != {
        "intervention_substrate_contract_drift"
    }:
        raise ValueError("unexpected_owner_issue_identity_set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
