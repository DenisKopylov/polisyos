"""Recompute FRC packet output hashes and case counts with corrupt controls."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from defusedxml.ElementTree import parse


def validate(
    root: Path, lane: Path, records: list[dict[str, Any]], receipt: dict[str, Any]
) -> None:
    """Bind the complete deciding-output set and recompute each JUnit count."""

    actual = {str(path.relative_to(lane)) for path in (root / "checks").iterdir() if path.is_file()}
    if len(records) != len(actual) or {record["path"] for record in records} != actual:
        raise ValueError("deciding-output denominator mismatch")
    for record in records:
        path = lane / record["path"]
        if path.stat().st_size != record["bytes"]:
            raise ValueError("deciding-output size mismatch")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("deciding-output digest mismatch")
    for check in receipt["checks"]:
        if "junit" not in check:
            continue
        if check["junit"] not in actual:
            raise ValueError("JUnit outside bound output set")
        cases = parse(lane / check["junit"]).getroot().findall(".//testcase")
        states = dict.fromkeys(("PASS", "FAIL", "ERROR", "SKIP"), 0)
        for case in cases:
            state = (
                "FAIL"
                if case.find("failure") is not None
                else "ERROR"
                if case.find("error") is not None
                else "SKIP"
                if case.find("skipped") is not None
                else "PASS"
            )
            states[state] += 1
        if states != check["states"] or len(cases) != check["cases"]:
            raise ValueError("JUnit case/state mismatch")
    candidate = receipt["candidate_sha"]
    if not isinstance(candidate, str) or re.fullmatch(r"[0-9a-f]{40}", candidate) is None:
        raise ValueError("candidate must be an exact SHA1 object hash")
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git unavailable")
    tree = subprocess.check_output(  # noqa: S603 - fixed git command, validated object hash.
        [executable, "rev-parse", candidate + "^{tree}"], cwd=lane, text=True
    ).strip()
    if tree != receipt["candidate_tree_sha"]:
        raise ValueError("candidate tree mismatch")


def validate_independent_copies(root: Path, lane: Path) -> int:
    """Bind every published independent byte and the reused candidate packet."""

    index = json.loads((root / "independent-output-copy-index.json").read_text())
    records = index["records"]
    destinations = {record["published_path"] for record in records}
    if len(destinations) != len(records):
        raise ValueError("duplicate independent output")
    expected = {
        str(path.relative_to(lane))
        for path in (root / "independent-review").iterdir()
        if path.is_file()
    } | {str((root / "a-status-reason-tests.py.txt").relative_to(lane))}
    if destinations != expected:
        raise ValueError("independent-output denominator mismatch")
    for record in records:
        path = lane / record["published_path"]
        if path.stat().st_size != record["bytes"]:
            raise ValueError("independent-output size mismatch")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("independent-output digest mismatch")
    return len(records)


def main() -> None:
    """Validate local receipt bytes and ensure four in-memory corruptions fail."""

    root = Path(__file__).resolve().parent
    lane = next(parent for parent in root.parents if (parent / ".git").exists())
    index = json.loads((root / "deciding-output-index.json").read_text())
    receipt = json.loads((root / "implementation-handoff.json").read_text())
    validate(root, lane, index["records"], receipt)
    independent_records = validate_independent_copies(root, lane)
    controls = []
    for mutation in ("digest", "size", "missing-output", "forged-count"):
        bad_records = copy.deepcopy(index["records"])
        bad_receipt = copy.deepcopy(receipt)
        if mutation == "digest":
            bad_records[0]["sha256"] = "0" * 64
        elif mutation == "size":
            bad_records[0]["bytes"] += 1
        elif mutation == "missing-output":
            bad_records.pop()
        else:
            next(check for check in bad_receipt["checks"] if "junit" in check)["states"][
                "PASS"
            ] += 1
        try:
            validate(root, lane, bad_records, bad_receipt)
        except ValueError:
            controls.append({"mutation": mutation, "rejected": True})
        else:
            raise RuntimeError("corrupt control escaped: " + mutation)
    sys.stdout.write(
        json.dumps(
            {
                "candidate": receipt["candidate_sha"],
                "validation": "PASS",
                "records": len(index["records"]),
                "independent_records": independent_records,
                "controls": controls,
            }
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
