"""Reconcile complete CG3 report identities without copying their derived sets."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

BASE = "9619f6d2d892d7994ae3f29d3230362c41862f2d"
SOURCE = "tools/quality/validation/check_grounding_admission_contract.py"
ARTIFACT = "architecture/policy_design_case/grounding_admission_contract.json"


def _git_blob(path: str) -> bytes:
    return subprocess.check_output(  # noqa: S603 - fixed local git show, constant paths.
        ["git", "show", f"{BASE}:policy-engine/{path}"]  # noqa: S607 - ordinary local git.
    )


def _hash(values: set[str]) -> str:
    return hashlib.sha256(json.dumps(sorted(values), separators=(",", ":")).encode()).hexdigest()


def _source_identities(raw: bytes) -> tuple[set[str], set[str], set[str]]:
    tree = ast.parse(raw)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "build_live_payload")
    payload = next(node.value for node in ast.walk(function) if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "payload"
                           for target in node.targets))
    probes = next(value for key, value in zip(payload.keys, payload.values, strict=True)
                  if isinstance(key, ast.Constant) and key.value == "probes")
    probe_ids = {ast.literal_eval(key) for key in probes.keys}
    declared = next(ast.literal_eval(node.value) for node in tree.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "EXPECTED_MUTATIONS"
                            for target in node.targets))
    called = [ast.literal_eval(node.args[0]) for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id == "_mutation_row"]
    if len(called) != len(set(called)):
        raise ValueError("duplicate_mutation_producer_identity")
    return probe_ids, declared, set(called)


def _record(label: str, expected: set[str], observed: set[str]) -> dict[str, object]:
    return {"denominator": label, "expected_count": len(expected), "observed_count": len(observed),
            "expected_identity_hash": _hash(expected), "observed_identity_hash": _hash(observed),
            "missing": sorted(expected - observed), "unexpected": sorted(observed - expected)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    old_source, old_bytes = _git_blob(SOURCE), _git_blob(ARTIFACT)
    old = json.loads(old_bytes)
    prior_probes, prior_expected, prior_called = _source_identities(old_source)
    probes, expected, called = _source_identities(Path(SOURCE).read_bytes())
    records = [
        _record("complete prior producer probe keys vs prior report probe keys",
                prior_probes, set(old["probes"])),
        _record("complete prior declared mutations vs prior producer calls",
                prior_expected, prior_called),
        _record("complete prior declared mutations vs prior report rows", prior_expected,
                {row["mutation_id"] for row in old["behavioral_mutations"]}),
        _record("complete prior vs current producer probe keys", prior_probes, probes),
        _record("complete current declared mutations vs current producer calls", expected, called),
        _record("complete prior mutations plus the source-authority migration", 
                prior_expected | {"source_authority_resolution_removed"}, expected),
    ]
    if args.live:
        live = json.loads(Path(ARTIFACT).read_bytes())
        identities = [row["mutation_id"] for row in live["behavioral_mutations"]]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate_live_mutation_identity")
        records.extend([
            _record("complete current producer vs regenerated report probe keys",
                    probes, set(live["probes"])),
            _record("complete current mutations vs regenerated report rows",
                    expected, set(identities)),
        ])
    result = {"slice_base": BASE, "source": SOURCE, "artifact": ARTIFACT,
              "comparison": records, "live_report_checked": args.live}
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    if any(row["missing"] or row["unexpected"] for row in records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
