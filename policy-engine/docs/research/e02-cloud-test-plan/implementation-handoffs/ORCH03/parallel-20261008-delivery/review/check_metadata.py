"""Read-only Git/receipt checker; no product imports or tests.

This emits mechanical metadata observations only.  An independent human-readable
coordination review must read both final inputs and qualify all check scopes.
It never reviews C07's source independently or issues a product acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--report", required=True)
parser.add_argument("--output", required=True)
parser.add_argument("--repository", default="/dev/shm/e02-orch03-20261008/c07")
args = parser.parse_args()
checks = []


def git(*arguments: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", args.repository, *arguments], stderr=subprocess.PIPE
    )


def record(label: str, observed, expected=None) -> None:
    checks.append(
        {
            "label": label,
            "observed": observed,
            "expected": expected,
            "state": "OBSERVED" if expected is None else "PASS" if observed == expected else "FAIL",
        }
    )


def attempt(label: str, operation) -> None:
    try:
        operation()
    except (subprocess.CalledProcessError, KeyError, ValueError, TypeError) as exc:
        checks.append({"label": label, "state": "ERROR", "message": str(exc)})


def tree(commit: str) -> str:
    return git("rev-parse", f"{commit}^{{tree}}").decode().strip()


def commit_tree(commit: str, expected_tree: str, label: str) -> None:
    record(f"{label}: exact tree", tree(commit), expected_tree)


def receipt(value: dict, label: str) -> None:
    data = git("show", f"{value['commit']}:{value['path']}")
    if "sha256" in value:
        record(f"{label}: receipt sha256", hashlib.sha256(data).hexdigest(), value["sha256"])
    if "bytes" in value:
        record(f"{label}: receipt bytes", len(data), value["bytes"])
    if "blob" in value:
        record(
            f"{label}: receipt blob",
            git("rev-parse", f"{value['commit']}:{value['path']}").decode().strip(),
            value["blob"],
        )


sha = re.compile(r"^[0-9a-f]{40}$")


def walk(value, label="root") -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            walk(item, f"{label}[{index}]")
        return
    if not isinstance(value, dict):
        return
    if isinstance(value.get("commit"), str) and sha.fullmatch(value["commit"]) and isinstance(value.get("path"), str):
        attempt(label, lambda: receipt(value, label))
    for pair in [("sha", "tree"), ("source", "tree"), ("runtime_source", "runtime_tree"), ("passive_companion", "passive_tree")]:
        commit, expected_tree = value.get(pair[0]), value.get(pair[1])
        if isinstance(commit, str) and sha.fullmatch(commit) and isinstance(expected_tree, str) and sha.fullmatch(expected_tree):
            attempt(label, lambda c=commit, t=expected_tree, p=pair: commit_tree(c, t, f"{label}.{p[0]}"))
    if isinstance(value.get("source"), str) and isinstance(value.get("source_parent"), str):
        attempt(label, lambda: record(
            f"{label}: exact source parent",
            git("rev-parse", f"{value['source']}^").decode().strip(),
            value["source_parent"],
        ))
    if all(isinstance(value.get(k), str) and sha.fullmatch(value[k]) for k in ["sha", "parent"]):
        attempt(label, lambda: record(
            f"{label}: declared parent",
            git("rev-parse", f"{value['sha']}^").decode().strip(), value["parent"],
        ))
    for key, item in value.items():
        walk(item, f"{label}.{key}")


input_path = Path(args.input)
report_path = Path(args.report)
input_bytes = input_path.read_bytes()
report_bytes = report_path.read_bytes()
payload = json.loads(input_bytes)
walk(payload)
record("coordination_only", payload.get("coordination_only"), True)
record("no assembled product candidate", payload.get("no_assembled_product_candidate"), True)
record("no G formal closure", "not_issued" in payload.get("formal_closure_G", ""), True)
for leaf in payload.get("leaf_sources", []):
    role = leaf.get("role")
    mechanism = leaf.get("mechanism", "")
    if role == "C07":
        record("B31 original owner", leaf.get("original_owner"), "A")
    elif "sample-mean" in mechanism:
        record("B21 original owner", leaf.get("original_owner"), "A")
    elif role == "C08":
        record("B214/B56 original owner", leaf.get("original_owner"), "F")
for boundary in payload.get("remaining_boundaries", []):
    if boundary.get("id") == "LA-036-observed-feature-law":
        record("LA-036 original owner", boundary.get("original_owner"), "C")
g_record = payload.get("fetched_G", {})
if "delta_from" in g_record and "sha" in g_record:
    def check_g_delta():
        actual = git("diff", "--name-status", g_record["delta_from"], g_record["sha"]).decode().splitlines()
        record("G exact full delta denominator", actual, g_record.get("delta_paths"))
        docs_only = all(x.split("\t")[-1].startswith("policy-engine/docs/") for x in actual)
        docs_only_claim = "docs/evidence-only" in g_record.get("relation_to_commissioning_G", "")
        record("G delta docs/evidence classification", docs_only, True if docs_only_claim else None)
        record("G exact product/test/companion paths", [x for x in actual if not x.split("\t")[-1].startswith("policy-engine/docs/")])
    attempt("G delta", check_g_delta)

result = {
    "schema": "policyos.e02.orch03.coordination_metadata_observations.v1",
    "purpose": "Read-only coordination metadata, never C07 author source independent review or product/G acceptance",
    "input": {"path": str(input_path), "bytes": len(input_bytes), "sha256": hashlib.sha256(input_bytes).hexdigest()},
    "report": {"path": str(report_path), "bytes": len(report_bytes), "sha256": hashlib.sha256(report_bytes).hexdigest()},
    "checks": checks,
    "contradictions": [check for check in checks if check["state"] in ["FAIL", "ERROR"]],
    "verdict": "NOT_ISSUED: mechanical observations require complete final-input independent coordination reading",
}
Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"checks": len(checks), "contradictions": len(result["contradictions"]), "input_sha256": result["input"]["sha256"], "report_sha256": result["report"]["sha256"]}))
