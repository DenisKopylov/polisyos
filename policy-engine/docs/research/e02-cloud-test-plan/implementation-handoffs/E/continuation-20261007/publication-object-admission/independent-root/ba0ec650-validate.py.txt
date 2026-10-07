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


def _admit_hash(value: object, length: int) -> None:
    if not isinstance(value, str) or re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is None:
        raise ValueError("source identity must be an exact hexadecimal hash")


def _admit_path(value: object) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError("output path must be a canonical repository-relative string")
    relative = Path(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or ".." in relative.parts
        or value != relative.as_posix()
        or value.startswith("-")
        or ":" in value
        or any(character.isspace() or character == "\0" for character in value)
    ):
        raise ValueError("output path must be canonical and repository relative")


def _admit_records(records: list[dict[str, Any]], key: str) -> None:
    if not isinstance(records, list):
        raise ValueError("output records must be a complete list")
    paths = []
    for record in records:
        _admit_path(record[key])
        paths.append(record[key])
        if type(record["bytes"]) is not int or record["bytes"] < 0:
            raise ValueError("output size must be a nonnegative integer")
        _admit_hash(record["sha256"], 64)
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate output path")


def _admit_receipt(records: list[dict[str, Any]], receipt: dict[str, Any]) -> None:
    _admit_records(records, "path")
    _admit_hash(receipt["candidate_sha"], 40)
    _admit_hash(receipt["candidate_tree_sha"], 40)
    for check in receipt["checks"]:
        if "junit" not in check:
            continue
        _admit_path(check["junit"])
        states = check["states"]
        if not isinstance(states, dict) or set(states) != {"PASS", "FAIL", "ERROR", "SKIP"}:
            raise ValueError("JUnit states must name each case outcome")
        if any(type(count) is not int or count < 0 for count in states.values()):
            raise ValueError("JUnit state counts must be nonnegative integers")
        if type(check["cases"]) is not int or check["cases"] < 0:
            raise ValueError("JUnit total must be a nonnegative integer")
        if sum(states.values()) != check["cases"]:
            raise ValueError("JUnit state/total declarations differ")


def validate(
    root: Path, lane: Path, records: list[dict[str, Any]], receipt: dict[str, Any]
) -> None:
    """Bind the complete deciding-output set and recompute each JUnit count."""

    _admit_receipt(records, receipt)
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
    _admit_records(records, "published_path")
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
