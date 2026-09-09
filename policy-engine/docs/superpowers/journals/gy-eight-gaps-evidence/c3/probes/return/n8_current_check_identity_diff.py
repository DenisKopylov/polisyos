"""Compare complete governing/ambient findings from the same real N8 check."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def _nodes(value: object, pointer: str = "") -> dict[str, dict]:
    """Walk every report node, preserving container shape and JSON scalar types."""
    if isinstance(value, dict):
        result = {pointer: {"type": "object", "keys": sorted(value)}}
        for key, child in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            result.update(_nodes(child, pointer + "/" + escaped))
        return result
    if isinstance(value, list):
        result = {pointer: {"type": "array", "length": len(value)}}
        for index, child in enumerate(value):
            result.update(_nodes(child, pointer + "/" + str(index)))
        return result
    return {pointer: {"type": type(value).__name__, "value": value}}


def _read(path: Path) -> tuple[dict, dict[str, set[str]]]:
    receipt = json.loads(path.read_bytes())
    if receipt.get("timed_out") is not False or receipt.get("returncode") not in (0, 1):
        raise ValueError(f"{path}: incomplete or crashed check")
    # This exact CLI emits one complete JSON report; refuse noise/partial output
    # rather than interpreting fewer parseable lines as fewer findings.
    report = json.loads(receipt["stdout"])
    if not isinstance(report, dict) or report.get("validator") != "policyos.layer3.gy.n8.value-gate-contract" or report.get("mode") != "check":
        raise ValueError(f"{path}: not the current N8 check report")
    claimed = report.get("receipt_sha256")
    measured = "sha256:" + hashlib.sha256(_canonical({key: value for key, value in report.items() if key != "receipt_sha256"}).encode()).hexdigest()
    if claimed != measured:
        raise ValueError(f"{path}: report content hash mismatch")
    identities = {}
    for field in ("issues", "ambient_findings"):
        # Absence/null/non-list is unreadable, never an empty denominator.
        rows = report[field]
        if not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get("code"), str) for row in rows):
            raise ValueError(f"{path}: invalid complete {field} population")
        if any(row["code"] == "value_gate_execution_failed" for row in rows):
            raise ValueError(f"{path}: owner failed before completing semantic check")
        values = [_canonical(row) for row in rows]
        if len(values) != len(set(values)):
            raise ValueError(f"{path}: duplicate finding identity")
        identities[field] = set(values)
    expected_status = "fail" if identities["issues"] else "pass"
    if report.get("status") != expected_status or receipt["returncode"] != int(expected_status == "fail"):
        raise ValueError(f"{path}: semantic/process disposition mismatch")
    return receipt, identities


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args()
    before, left = _read(args.before)
    after, right = _read(args.after)
    if before["command"] != after["command"] or before["cwd"] != after["cwd"]:
        raise ValueError("N8 comparison command/station mismatch")
    before_report = json.loads(before["stdout"])
    after_report = json.loads(after["stdout"])
    before_nodes, after_nodes = _nodes(before_report), _nodes(after_report)
    absent = object()
    changed = sorted(
        pointer for pointer in before_nodes.keys() | after_nodes.keys()
        if before_nodes.get(pointer, absent) != after_nodes.get(pointer, absent)
    )
    # Independent complete structural recursion; never .get(path) with null default.
    def recursive_delta(a: object, b: object, pointer: str = "") -> set[str]:
        def shape_and_children(value: object) -> tuple[object, dict]:
            if isinstance(value, dict):
                return ("object", sorted(value)), value
            if isinstance(value, list):
                return ("array", len(value)), dict(zip(map(str, range(len(value))), value))
            return (type(value).__name__, value), {}
        a_shape, a_children = shape_and_children(a)
        b_shape, b_children = shape_and_children(b)
        result = {pointer} if a_shape != b_shape else set()
        for key in a_children.keys() | b_children.keys():
            escaped = key.replace("~", "~0").replace("/", "~1")
            child = pointer + "/" + escaped
            if key not in a_children or key not in b_children:
                source = a_children[key] if key in a_children else b_children[key]
                result.update(_nodes(source, child))
            else:
                result.update(recursive_delta(a_children[key], b_children[key], child))
        return result
    if set(changed) != recursive_delta(before_report, after_report):
        raise ValueError("Independent complete report node delta disagrees")
    print(json.dumps({
        "before": str(args.before), "after": str(args.after),
        "comparison": {
            field: {"added": [json.loads(value) for value in sorted(right[field]-left[field])],
                    "lost": [json.loads(value) for value in sorted(left[field]-right[field])],
                    "retained": [json.loads(value) for value in sorted(left[field]&right[field])]}
            for field in ("issues", "ambient_findings")},
        "complete_report_payload_delta": [
            {"pointer": pointer,
             "before": {"presence": "present", "node": before_nodes[pointer]}
             if pointer in before_nodes else {"presence": "absent"},
             "after": {"presence": "present", "node": after_nodes[pointer]}
             if pointer in after_nodes else {"presence": "absent"}}
            for pointer in changed],
        "independent_report_node_delta_equal": True,
        "limit": (
            "This is the complete emitted CLI report payload, not its un-emitted live "
            "build_payload result. Equal finding identities do not prove an unchanged "
            "underlying catalog where the baseline already reports that divergence class. "
            "The before run is temporal before SCM, not a slice-base P41 attribution."
        ),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
