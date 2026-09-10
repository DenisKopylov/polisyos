"""Read all Phase2 output/source identities; import no product or scratch owner."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib


class Number(str):
    """Preserve a JSON number's exact token without bool/float coercion."""


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def parse(raw):
    return json.loads(raw, parse_int=Number, parse_float=Number)


def label(value):
    if type(value) is dict:
        return ("object", None)
    if type(value) is list:
        return ("array", len(value))
    if type(value) is Number:
        return ("number", str(value))
    if value is None:
        return ("null", None)
    if type(value) is bool:
        return ("boolean", value)
    if type(value) is str:
        return ("string", value)
    raise TypeError(type(value))


def pointer(parent, key):
    return parent + "/" + str(key).replace("~", "~0").replace("/", "~1")


def recursive(value, path="", result=None):
    if result is None:
        result = {}
    result[path] = label(value)
    children = value.items() if type(value) is dict else enumerate(value) if type(value) is list else ()
    for key, child in children:
        recursive(child, pointer(path, key), result)
    return result


def iterative(value):
    result, pending = {}, [("", value)]
    while pending:
        path, child = pending.pop()
        result[path] = label(child)
        children = child.items() if type(child) is dict else enumerate(child) if type(child) is list else ()
        pending.extend((pointer(path, key), node) for key, node in children)
    return result


def delta(before, after):
    left, right = recursive(before), iterative(after)
    assert left == iterative(before) and right == recursive(after)
    absent = ("absent", None)
    changes = {
        key: {"before": left.get(key, absent), "after": right.get(key, absent)}
        for key in sorted(left.keys() | right.keys())
        if left.get(key, absent) != right.get(key, absent)
    }
    independent = ((right.keys() - left.keys()) | (left.keys() - right.keys())
                   | {key for key in left.keys() & right.keys() if left[key] != right[key]})
    assert changes.keys() == independent
    return {"before_nodes": len(left), "after_nodes": len(right),
            "changed_node_count": len(changes), "complete_delta": changes}


def constants(raw):
    values = {}

    def resolve(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return values[node.id]
        if isinstance(node, (ast.List, ast.Tuple)):
            return [resolve(item) for item in node.elts]
        if isinstance(node, ast.Dict):
            return {resolve(key): resolve(value) for key, value in zip(node.keys, node.values, strict=True)}
        raise ValueError("not_a_literal_declaration")

    for node in ast.parse(raw).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                values[node.targets[0].id] = resolve(node.value)
            except (KeyError, ValueError):
                pass
    return values


def source_basis(root):
    roots = ("src", "tools", "tests")
    paths = {p.relative_to(root).as_posix() for name in roots for p in (root / name).rglob("*.py")}
    walked = {Path(directory, name).relative_to(root).as_posix()
              for part in roots for directory, _, names in os.walk(root / part)
              for name in names if name.endswith(".py")}
    listed = {p for p in subprocess.check_output(
        ["rg", "--files", "--hidden", "--no-ignore", *roots], cwd=root, text=True
    ).splitlines() if p.endswith(".py")}
    assert paths == walked == listed and paths
    hashes = {path: digest((root / path).read_bytes()) for path in sorted(paths)}
    return hashes, {"roots": list(roots), "file_type": ".py", "rglob": len(paths),
                    "os_walk": len(walked), "rg": len(listed),
                    "raw_hash_basis": digest(json.dumps(hashes, sort_keys=True).encode())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--baseline-revision", required=True)
    parser.add_argument("--write-receipt", type=Path, required=True)
    parser.add_argument("--baseline-receipt", type=Path, required=True)
    parser.add_argument("--recorder-source", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    owner = "tools/quality/validation/check_layer3_gy_phase2_artifacts.py"
    registry = "architecture/generated_artifacts.toml"
    own_source, recorder = Path(__file__).resolve(), (root / args.recorder_source).resolve()
    executing = {str(path.relative_to(root)): digest(path.read_bytes()) for path in (own_source, recorder)}
    branch = subprocess.check_output(["git", "symbolic-ref", "-q", "HEAD"], cwd=root, text=True).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()

    def previous(path):
        return subprocess.check_output(["git", "show", args.baseline_revision + ":policy-engine/" + path], cwd=root)

    raw_owner = (root / owner).read_bytes()
    declarations = constants(raw_owner)
    paths, protected = declarations["OUTPUTS"], declarations["PROTECTED_OUTPUTS"]
    historical = declarations["HISTORICAL_OUTPUTS_SHA256"]
    fence_paths = [owner, registry, *paths, *historical,
                   str(args.write_receipt), str(args.baseline_receipt)]
    fence = {path: digest((root / path).read_bytes()) for path in fence_paths}
    source_before, source = source_basis(root)
    families = tomllib.loads((root / registry).read_text())["family"]
    old_families = tomllib.loads(previous(registry).decode())["family"]
    selected = {}
    for family_id in (declarations["FAMILY_ID"], declarations["HISTORY_FAMILY_ID"]):
        current, = [family for family in families if family["id"] == family_id]
        old, = [family for family in old_families if family["id"] == family_id]
        assert current == old
        selected[family_id] = current
    current = selected[declarations["FAMILY_ID"]]
    assert len(paths) == len(set(paths)) == len(current["outputs"]) == 5
    assert set(paths) == set(current["outputs"])
    write_raw = (root / args.write_receipt).read_bytes()
    write = json.loads(write_raw)
    report = json.loads(write["stdout"])
    assert report["checked_artifacts"] == paths and report["write"] is True
    output_deltas, changed, decoded = [], [], {}
    for path in paths:
        old, new = previous(path), (root / path).read_bytes()
        decoded[path] = json.loads(new)
        if old != new:
            changed.append(path)
        output_deltas.append({"path": path, "before_raw_hash": digest(old),
                              "after_raw_hash": digest(new), **delta(parse(old), parse(new))})
    assert set(changed) == set(report["written_artifacts"]) == set(paths) - set(protected)
    assert raw_owner == previous(owner)
    history_checks = {}
    for path, pin in historical.items():
        raw = (root / path).read_bytes()
        assert digest(raw) == pin and previous(path) == raw
        history_checks[path] = {"raw_hash": digest(raw), "pin_and_baseline_equal": True}
    for path in changed:
        basis = decoded[path]["return_strangles"]["caller_basis"]
        assert basis["source_basis_hash"] == source["raw_hash_basis"]
        assert basis["source_denominator"]["rglob"] == source["rglob"]
    loop = "src/polisyos/runtime/quality/workspace/loop.py"
    replacement = loop + "@" + source_before[loop] + "#_phase2_value_method_selection"
    first = decoded[declarations["PLAYBOOK_PROOF_PATH"]]["return_strangles"]["receipts"][0]
    assert first["replacement_ref"][0] == first["replaced_members"][0]["replacement_ref"] == replacement
    old_receipt_raw = (root / args.baseline_receipt).read_bytes()
    old_report = json.loads(json.loads(old_receipt_raw)["stdout"])
    identity = lambda rows: Counter(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows)
    old_findings, new_findings = identity(old_report["issues"]), identity(report["issues"])
    assert old_findings == new_findings
    source_after, after_source = source_basis(root)
    assert source_before == source_after and source == after_source
    assert fence == {path: digest((root / path).read_bytes()) for path in fence}
    assert executing == {str(path.relative_to(root)): digest(path.read_bytes()) for path in (own_source, recorder)}
    assert head == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    assert branch == subprocess.check_output(["git", "symbolic-ref", "-q", "HEAD"], cwd=root, text=True).strip()
    print(json.dumps({
        "station": {"cwd": str(root), "python": sys.executable, "head": head, "branch": branch},
        "execution_sources_before_and_after": executing,
        "executing_sources_unchanged": True,
        "baseline_revision": args.baseline_revision,
        "complete_five_outputs": paths,
        "independent_membership": "literal AST declarations = registry membership = actual writer checked order",
        "complete_output_deltas": output_deltas,
        "changed_outputs_equal_actual_writer_set": changed,
        "protected_outputs_byte_identical": protected,
        "source_basis_before_and_after": source,
        "current_source_basis_matches_both_reissues": True,
        "replacement_ref_matches_actual_source": replacement,
        "governance": {"owner": owner + "@" + digest(raw_owner), "owner_unchanged_from_baseline": True,
                       "current_and_history_families_unchanged": True,
                       "freshness_rule": current["freshness_rule"],
                       "historical_pin_checks": history_checks},
        "finding_comparison": {
            "baseline": str(args.baseline_receipt) + "@" + digest(old_receipt_raw),
            "current": str(args.write_receipt) + "@" + digest(write_raw),
            "actual_write_returncode": write["returncode"],
            "task_measurements": report["task_measurements"],
            "baseline_identity_count": len(old_findings), "current_identity_count": len(new_findings),
            "baseline_occurrences": sum(old_findings.values()), "current_occurrences": sum(new_findings.values()),
            "added_complete_identities": [], "lost_complete_identities": [], "multiplicity_delta": []},
        "complete_source_artifact_execution_fence_unchanged": True,
        "scope": "stdlib readback only; no product imports, product gates or canonical writes",
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
