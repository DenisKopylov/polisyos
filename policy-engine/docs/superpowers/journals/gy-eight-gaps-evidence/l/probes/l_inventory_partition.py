"""Reconcile the full inventory, then update only the L epoch companion."""

from __future__ import annotations

import argparse
import hashlib
import json
import tomllib
from collections import defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    path = Path("architecture/policy_design_case/inventory.json")
    original = path.read_bytes()
    entries = json.loads(original)["artifacts"]
    families = tomllib.loads(Path("architecture/generated_artifacts.toml").read_text())["family"]
    by_path = defaultdict(list)
    for family in families:
        for output in family.get("outputs", []):
            by_path[output].append(family)
    keys = (("family_id", "id"), ("lifecycle", "lifecycle"), ("owner", "owner"))
    scope = {"policy-design-case-layer3-gy-loop-artifacts",
             "policy-design-case-layer3-gy-loop-history-artifacts"}
    changes = []
    selected = []
    for index, entry in enumerate(entries):
        if entry.get("kind") != "layer3_gy_lifecycle_artifact":
            continue
        selected.append(index)
        owners = by_path[entry["path"]]
        assert len(owners) == 1, (entry["path"], owners)
        for field, registry_field in keys:
            if entry.get(field) != owners[0][registry_field]:
                assert owners[0]["id"] in scope, "unrelated inventory mismatch"
                changes.append({"index": index, "path": entry["path"], "field": field,
                                "before": entry.get(field), "after": owners[0][registry_field]})
    independent = []
    for index in selected:
        entry = entries[index]
        matches = [row for row in families if entry["path"] in row.get("outputs", [])]
        assert len(matches) == 1
        independent.extend((index, field) for field, key in keys if entry.get(field) != matches[0][key])
    assert independent == [(row["index"], row["field"]) for row in changes]
    if args.write:
        from _build.gy_gaps.refresh_m1_snapshot import surgical
        surgical(path, {("artifacts", row["index"], row["field"]): row["after"] for row in changes})
    print(json.dumps({"inventory_path": path.as_posix(), "inventory_denominator": len(entries),
                     "lifecycle_entry_denominator": len(selected), "changes": changes,
                     "independent_field_identities_reconciled": True, "write": args.write,
                     "before_sha256": hashlib.sha256(original).hexdigest(),
                     "after_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
