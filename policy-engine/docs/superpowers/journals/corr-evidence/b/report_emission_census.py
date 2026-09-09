"""Reconcile every changed governed JSON emission and its own synthetic marker."""

from __future__ import annotations

import fnmatch
import hashlib
import importlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

BASE = "9619f6d2d892d7994ae3f29d3230362c41862f2d"


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(  # noqa: S603 - fixed local git; paths are argv data.
        ["/usr/bin/git", *args], cwd=repo,
    )


def _hash(values: set[str]) -> str:
    return hashlib.sha256(json.dumps(sorted(values), separators=(",", ":")).encode()).hexdigest()


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"ambiguous_duplicate_json_key:{key}")
        result[key] = value
    return result


def _synthetic_paths(value: object) -> tuple[set[str], set[str]]:
    recursive: set[str] = set()

    def walk(node: object, path: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            for key, nested in node.items():
                child = (*path, str(key))
                if key == "synthetic" and type(nested) is bool and nested:
                    recursive.add("/" + "/".join(child))
                walk(nested, child)
        elif isinstance(node, list):
            for index, nested in enumerate(node):
                walk(nested, (*path, str(index)))

    walk(value, ())
    iterative: set[str] = set()
    pending: list[tuple[tuple[str, ...], object]] = [((), value)]
    while pending:
        path, node = pending.pop()
        children = node.items() if isinstance(node, dict) else (
            enumerate(node) if isinstance(node, list) else ()
        )
        for key, nested in children:
            child = (*path, str(key))
            if isinstance(node, dict) and key == "synthetic" and type(nested) is bool and nested:
                iterative.add("/" + "/".join(child))
            pending.append((child, nested))
    if recursive != iterative:
        raise ValueError("synthetic_path_identity_walk_disagrees")
    return recursive, iterative


def main() -> int:
    """Measure actual saved outputs; never run a generator or rewrite a receipt."""
    root = Path.cwd()
    repo = root.parent
    prefix = f"{root.name}/"
    untracked = {name.decode().removeprefix(prefix) for name in _git(
        repo, "ls-files", "--others", "--exclude-standard", "-z", "--", prefix
    ).split(b"\0") if name.endswith(b".json")}
    changed = {
        name.decode().removeprefix(prefix)
        for name in _git(repo, "diff", "--name-only", "-z", BASE, "--", prefix).split(b"\0")
        if name.endswith(b".json")
    } | untracked
    baseline: dict[str, str] = {}
    for entry in _git(repo, "ls-tree", "-r", "-z", BASE, "--", prefix).split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", maxsplit=1)
        if name.endswith(b".json"):
            baseline[name.decode().removeprefix(prefix)] = metadata.split()[2].decode()
    tracked = {
        name.decode().removeprefix(prefix)
        for name in _git(repo, "ls-files", "-z", "--", prefix).split(b"\0")
        if name.endswith(b".json")
    } | untracked
    observed: dict[str, str] = {}
    for name in tracked:
        data = (root / name).read_bytes()
        observed[name] = hashlib.sha1(  # noqa: S324 - Git blob identity, not security hashing.
            b"blob " + str(len(data)).encode() + b"\0" + data
        ).hexdigest()
    independently_changed = {
        name for name in set(baseline) | set(observed)
        if baseline.get(name) != observed.get(name)
    }
    if changed != independently_changed:
        raise ValueError({"changed_artifact_identity_difference": sorted(
            changed ^ independently_changed
        )})
    families = tomllib.loads((root / "architecture/generated_artifacts.toml").read_text())["family"]
    owners: dict[str, set[str]] = {}
    records: list[dict[str, Any]] = []
    gaps: list[str] = []
    logs: set[str] = set()
    other_json: set[str] = set()
    for path in sorted(changed):
        payload = json.loads((root / path).read_bytes(), object_pairs_hook=_unique)
        if not isinstance(payload, dict):
            raise ValueError(f"ambiguous_nonobject_governed_artifact:{path}")
        matched = [family for family in families if any(
            fnmatch.fnmatchcase(path, pattern)
            or (pattern.endswith("/") and path.startswith(pattern))
            for pattern in family.get("outputs", [])
        )]
        if not matched and not path.startswith("architecture/"):
            if {"command", "stdout", "stderr"}.issubset(payload):
                logs.add(path)
                continue
            if "schema_version" not in payload:
                other_json.add(path)
                continue
        workflows = {family["workflow"] for family in matched
                     if str(family.get("workflow", "")).endswith(".py")}
        for workflow in workflows:
            if workflow not in owners:
                module = importlib.import_module(workflow.removesuffix(".py").replace("/", "."))
                outputs = module.declared_outputs()
                if len(outputs) != len(set(outputs)):
                    raise ValueError(f"duplicate_declared_output:{workflow}")
                owners[workflow] = set(outputs)
            if path not in owners[workflow]:
                raise ValueError(
                    f"lifecycle_and_actual_declared_outputs_disagree:{path}:{workflow}"
                )
        true_paths, independently_true_paths = _synthetic_paths(payload)
        nested = true_paths - {"/synthetic"}
        own = payload.get("synthetic") if "synthetic" in payload else "absent"
        if (workflows or path.startswith("architecture/")) and nested and own is not True:
            gaps.append(path)
        records.append({
            "artifact": f"{path}@{observed[path]}",
            "schema_version": payload.get("schema_version", "absent"),
            "lifecycle_families": sorted(family["id"] for family in matched),
            "actual_declared_output_owners": sorted(workflows),
            "registration_plane": (
                "python_generated_output" if workflows else
                "non_python_registered_artifact" if matched else
                "outside_generated_output_registry"
            ),
            "own_synthetic": own,
            "nested_true_count": len(nested),
            "nested_true_identity_hash": _hash(nested),
            "independent_nested_true_identity_hash": _hash(
                independently_true_paths - {"/synthetic"}
            ),
            "nested_true_roots": sorted({path.split("/")[1] for path in nested}),
        })
    declared_changed = changed & set().union(*owners.values())
    registered_changed = {record["artifact"].split("@")[0] for record in records
                          if record["actual_declared_output_owners"]}
    if declared_changed != registered_changed:
        raise ValueError("complete_lifecycle_declared_output_identity_difference")
    result = {
        "base": BASE,
        "denominator": (
            "Every product-root JSON changed from slice base, including untracked JSON; "
            "actual lifecycle and owner declared_outputs select generated outputs "
            "without a directory filter"
        ),
        "changed_count": len(changed),
        "independently_changed_count": len(independently_changed),
        "changed_identity_hash": _hash(changed),
        "independent_changed_identity_hash": _hash(independently_changed),
        "identity_difference": sorted(changed ^ independently_changed),
        "capture_logs": {"count": len(logs), "identity_hash": _hash(logs)},
        "other_nonregistered_json": {"count": len(other_json), "identity_hash": _hash(other_json)},
        "generated_report_count": len(declared_changed),
        "generated_report_identity_hash": _hash(declared_changed),
        "independent_generated_report_identity_hash": _hash(registered_changed),
        "artifact_observations": records,
        "own_marker_gaps": gaps,
        "status": "fail" if gaps else "pass",
    }
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return int(bool(gaps))


if __name__ == "__main__":
    raise SystemExit(main())
