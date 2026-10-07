"Independent check-output quantities; does not invoke checks or producer collector."

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from defusedxml import ElementTree

if TYPE_CHECKING:
    from pathlib import Path


def content_digest(path: Path) -> dict[str, object]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
            size += len(block)
    return {"bytes": size, "sha256": h.hexdigest()}


def junit_quantities(path: Path) -> dict[str, object]:
    root = ElementTree.parse(path, forbid_dtd=True).getroot()
    counts = {"cases": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    bad = []
    case_ids = []
    for case in root.iter("testcase"):
        counts["cases"] += 1
        identity = {
            "classname": case.get("classname"),
            "name": case.get("name"),
            "file": case.get("file"),
            "line": case.get("line"),
        }
        failures = case.findall("failure")
        errors = case.findall("error")
        skips = case.findall("skipped")
        outcome = "failed" if failures else "errors" if errors else "skipped" if skips else "passed"
        counts[outcome] += 1
        case_ids.append(identity | {"outcome": outcome})
        if failures or errors or skips:
            bad.append(
                identity
                | {
                    "outcome": outcome,
                    "details": [
                        {"tag": n.tag, "attributes": dict(n.attrib), "text": n.text}
                        for n in failures + errors + skips
                    ],
                }
            )
    if not (sum(counts[k] for k in ["passed", "failed", "errors", "skipped"]) == counts["cases"]):
        raise AssertionError
    return {
        "counts": counts,
        "case_ids": case_ids,
        "non_pass_cases": bad,
        "xml_digest": content_digest(path),
    }


def receipt_outcome(receipt: object, counts: object) -> object:
    immutable = (
        receipt.get("source_identity_before") == receipt.get("source_identity_after")
        and receipt.get("head_at_end") == receipt.get("candidate_sha")
        and receipt.get("git_input_config", {}).get("stable") is True
        and receipt.get("git_input_config", {}).get("sha256")
        == receipt.get("git_input_config", {}).get("after_sha256")
        and receipt.get("source_immutable") is True
    )
    if not immutable:
        return "FAIL"
    if receipt.get("backend_error") is not None:
        return "UNRUN"
    if counts and counts["cases"] and counts["skipped"] == counts["cases"]:
        return "SKIP"
    return "PASS" if receipt.get("exit_code") == 0 else "FAIL"


def validate_receipt(receipt: object, freeze: object, tree: str, observed: object) -> object:
    if not (receipt["candidate_sha"] == freeze and receipt["candidate_tree_sha"] == tree):
        raise AssertionError
    if not (type(receipt["exit_code"]) is int and type(receipt["source_immutable"]) is bool):
        raise AssertionError
    if not (
        receipt["stdout_bytes"] == observed["stdout"]["bytes"]
        and receipt["stdout_sha256"] == observed["stdout"]["sha256"]
    ):
        raise AssertionError
    counts = None if observed.get("junit") is None else observed["junit"]["counts"]
    if counts is not None and not (all(type(x) is int for x in receipt["counts"].values())):
        raise AssertionError
    if not (receipt.get("counts") == counts):
        raise AssertionError
    if observed.get("tracked_source") is not None and not (
        receipt["source_identity_before"]
        == receipt["source_identity_after"]
        == observed["tracked_source"]
    ):
        raise AssertionError
    if observed.get("private_config") is not None:
        config = receipt["git_input_config"]
        if not (
            config["bytes"] == observed["private_config"]["bytes"]
            and config["sha256"] == config["after_sha256"] == observed["private_config"]["sha256"]
        ):
            raise AssertionError
    expected = receipt_outcome(receipt, counts)
    if not (receipt["outcome"] == expected):
        raise AssertionError
    if expected == "PASS" and counts and not (counts["failed"] == counts["errors"] == 0):
        raise AssertionError
    if expected == "PASS":
        if not (receipt["exit_code"] == 0):
            raise AssertionError
        if observed.get("kind") == "numerical" and (
            not (counts is not None and counts["cases"] > 0)
        ):
            raise AssertionError
    return expected


def validate_stage_scope(scope: str) -> object:
    failed = False
    seen = []
    for row in scope["steps"]:
        outcome = row["outcome"]
        if outcome not in ["PASS", "FAIL", "UNRUN"]:
            raise AssertionError
        if failed and not (outcome == "UNRUN"):
            raise AssertionError
        if outcome == "PASS" and not (row.get("exit_code") == 0 and "started_unix" in row):
            raise AssertionError
        if outcome == "FAIL":
            if "started_unix" not in row:
                raise AssertionError
            failed = True
        if outcome == "UNRUN" and not ("started_unix" not in row and "reason" in row):
            raise AssertionError
        seen.append(
            {
                "label": row["label"],
                "outcome": outcome,
                "command": row["command"],
                "cwd": row["cwd"],
            }
        )
    return seen
