"""Reconcile every frozen/current posture field and its admitted source provenance."""

# ruff: noqa: S101, S603, T201 - forensic identity assertions and read-only local Git provenance

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

root = Path.cwd()
base = root.parent.parent / "gyphase5-lane-basecheck/policy-engine"
relative = Path("apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json")
before_bytes = (root / relative).read_bytes()
after_bytes = (root / ".tmp/gyphase5-trust-posture-audit" / relative).read_bytes()
before = json.loads(before_bytes)
after = json.loads(after_bytes)


def recursive(value: object, path: tuple[str | int, ...] = ()) -> dict[tuple, Any]:
    """Retain complete leaves, with null and empty containers as explicit values."""
    if isinstance(value, dict) and value:
        return {
            key: leaf
            for name, child in value.items()
            for key, leaf in recursive(child, (*path, name)).items()
        }
    if isinstance(value, list) and value:
        return {
            key: leaf
            for index, child in enumerate(value)
            for key, leaf in recursive(child, (*path, index)).items()
        }
    return {path: {"type": type(value).__name__, "value": value}}


def iterative(value: object) -> dict[tuple, Any]:
    """Independently enumerate the whole object using a work stack."""
    pending = [((), value)]
    leaves = {}
    while pending:
        path, item = pending.pop()
        if isinstance(item, dict) and item:
            pending.extend(((*path, key), child) for key, child in item.items())
        elif isinstance(item, list) and item:
            pending.extend(((*path, key), child) for key, child in enumerate(item))
        else:
            leaves[path] = {"type": type(item).__name__, "value": item}
    return leaves


def diff(left: object, right: object) -> list[dict[str, Any]]:
    """Compare identities and values without conflating absent with null."""
    old = recursive(left)
    new = recursive(right)
    assert old == iterative(left)
    assert new == iterative(right)
    return [
        {
            "path": list(path),
            "frozen": {"presence": "present", **old[path]}
            if path in old
            else {"presence": "absent"},
            "current": {"presence": "present", **new[path]}
            if path in new
            else {"presence": "absent"},
        }
        for path in sorted(old.keys() | new.keys(), key=repr)
        if path not in old or path not in new or old[path] != new[path]
    ]


def rows(payload: dict, collection: str, key: str) -> dict[str, dict]:
    """Index every typed collection member, refusing duplicate identities."""
    result = {row[key]: row for row in payload[collection]}
    assert len(result) == len(payload[collection])
    return result


collections = {}
for collection, key in (
    ("claims", "claim_id"),
    ("admitted_sources", "path"),
    ("source_inventory", "path"),
):
    old = rows(before, collection, key)
    new = rows(after, collection, key)
    collections[collection] = {
        "frozen_identities": sorted(old),
        "current_identities": sorted(new),
        "added": sorted(new.keys() - old.keys()),
        "removed": sorted(old.keys() - new.keys()),
        "changed_shared": {
            identity: diff(old[identity], new[identity])
            for identity in sorted(old.keys() & new.keys())
            if old[identity] != new[identity]
        },
        "added_records": {identity: new[identity] for identity in sorted(new.keys() - old.keys())},
        "removed_records": {
            identity: old[identity] for identity in sorted(old.keys() - new.keys())
        },
    }
old_claims = rows(before, "claims", "claim_id")
new_claims = rows(after, "claims", "claim_id")
decisions = {
    identity: diff(
        {key: value for key, value in old_claims[identity].items() if key != "source_bindings"},
        {key: value for key, value in new_claims[identity].items() if key != "source_bindings"},
    )
    for identity in sorted(old_claims.keys() & new_claims.keys())
}
sources = []
ambiguous = []
old_sources = rows(before, "admitted_sources", "path")
new_sources = rows(after, "admitted_sources", "path")
for path in sorted(old_sources.keys() | new_sources.keys()):
    observed = {}
    for label, station in ("slice_base", base), ("current", root):
        target = station / path
        if not target.exists():
            observed[label] = {"presence": "absent"}
        else:
            try:
                observed[label] = {
                    "presence": "present",
                    "content_digest": "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest(),
                }
            except OSError as exc:
                ambiguous.append({"path": str(target), "error": repr(exc)})
                observed[label] = {"presence": "ambiguous", "error": repr(exc)}
    sources.append(
        {
            "path": path,
            **observed,
            "frozen_admission": {"presence": "present", **old_sources[path]}
            if path in old_sources
            else {"presence": "absent"},
            "current_admission": {"presence": "present", **new_sources[path]}
            if path in new_sources
            else {"presence": "absent"},
        }
    )
commands = []
for args in (
    ["git", "rev-parse", "HEAD"],
    ["git", "-C", str(base), "rev-parse", "HEAD"],
    ["git", "log", "-1", "--format=fuller", "--", str(relative)],
    ["git", "diff", "--name-only", "3d572c146", "HEAD"],
):
    result = subprocess.run(args, cwd=root, capture_output=True, text=True, check=False)
    commands.append(
        {
            "argv": args,
            "cwd": str(root),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )
    assert result.returncode == 0
packet = {
    "frozen_sha256": hashlib.sha256(before_bytes).hexdigest(),
    "current_sha256": hashlib.sha256(after_bytes).hexdigest(),
    "denominator": (
        "Every field of both complete posture artifacts, independently reconciled "
        "recursive/iterative walks; every member of typed claims/admitted_sources/source_inventory "
        "keyed by its owner identity."
    ),
    "frozen_field_identities": [list(path) for path in sorted(recursive(before), key=repr)],
    "current_field_identities": [list(path) for path in sorted(recursive(after), key=repr)],
    "complete_field_differences": diff(before, after),
    "complete_collections": collections,
    "shared_claim_decision_field_differences": {
        key: value for key, value in decisions.items() if value
    },
    "unchanged_top_level_fields": sorted(
        key for key in before.keys() & after.keys() if before[key] == after[key]
    ),
    "changed_top_level_fields": sorted(
        key for key in before.keys() & after.keys() if before[key] != after[key]
    ),
    "complete_source_provenance": sources,
    "ambiguous": ambiguous,
    "git_provenance_commands": commands,
    "complete_frozen_artifact": before,
    "complete_actual_scratch_artifact": after,
}
target = root / "docs/superpowers/journals/gy-phase5-evidence/pr1/trust-posture-complete-delta.json"
target.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
print(
    json.dumps(
        {
            "output": str(target),
            "ambiguous": ambiguous,
            "changed_top_level_fields": packet["changed_top_level_fields"],
            "unchanged_top_level_fields": packet["unchanged_top_level_fields"],
            "claim_added": collections["claims"]["added"],
            "claim_removed": collections["claims"]["removed"],
            "shared_claim_decision_field_differences": packet[
                "shared_claim_decision_field_differences"
            ],
            "source_changed": sorted(collections["admitted_sources"]["changed_shared"]),
            "source_added": collections["admitted_sources"]["added"],
            "source_removed": collections["admitted_sources"]["removed"],
        },
        indent=2,
    )
)
raise SystemExit(bool(ambiguous))
