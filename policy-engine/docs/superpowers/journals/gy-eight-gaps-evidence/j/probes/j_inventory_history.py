"""Align only J's completed predecessor inventory rows with its real history owner."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import tomllib

from _build.gy_gaps.refresh_m1_snapshot import surgical

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    checker = ROOT / "tools/quality/validation/check_layer3_gy_loop_artifacts.py"
    tree = ast.parse(checker.read_bytes())
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                    "HISTORY_FAMILY_ID", "HISTORICAL_LOOP_OUTPUTS_SHA256"
                }:
                    assert target.id not in constants
                    constants[target.id] = ast.literal_eval(node.value)
    hashes = constants["HISTORICAL_LOOP_OUTPUTS_SHA256"]
    registry = tomllib.loads((ROOT / "architecture/generated_artifacts.toml").read_text())
    matched = [f for f in registry["family"] if f["id"] == constants["HISTORY_FAMILY_ID"]]
    assert len(matched) == 1
    family = matched[0]
    assert set(family["outputs"]) == set(hashes)
    assert family["source_integrity_sha256"] == hashes
    assert family["lifecycle"] == "source_committed"
    for relative, expected in hashes.items():
        actual = "sha256:" + hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected, relative
    path = ROOT / "architecture/policy_design_case/inventory.json"
    original = path.read_bytes()
    rows = json.loads(original)["artifacts"]
    by_path = {}
    for index, row in enumerate(rows):
        by_path.setdefault(row["path"], []).append((index, row))
    counts = Counter(row["path"] for row in rows)
    assert {key: len(value) for key, value in by_path.items()} == dict(counts)
    assert sum(counts.values()) == len(rows)
    assert all(len(by_path[relative]) == 1 for relative in hashes)
    selected = {relative: by_path[relative][0] for relative in hashes}
    independent = [row for row in rows if row["path"] in family["outputs"]]
    assert {row["path"] for row in independent} == set(selected)
    assert len(independent) == len(selected) == len(family["outputs"])
    updates, deltas = {}, []
    for relative, (index, row) in sorted(selected.items()):
        changed = dict(row)
        for key, value in {"family_id": family["id"], "lifecycle": family["lifecycle"]}.items():
            if key not in row or row[key] != value:
                deltas.append({"path": relative, "field": key,
                               "before_present": key in row,
                               "before": row[key] if key in row else None, "after": value})
                changed[key] = value
        if changed != row:
            updates[("artifacts", index)] = changed
    if args.write:
        surgical(path, updates)
        after = json.loads(path.read_bytes())
        expected = json.loads(original)
        for (_, index), value in updates.items():
            expected["artifacts"][index] = value
        assert after == expected
    else:
        assert path.read_bytes() == original
    print(json.dumps({"mode": "write" if args.write else "inspect",
                      "inventory_json_artifact_row_denominator": len(rows),
                      "independent_counter_row_denominator": sum(counts.values()),
                      "complete_duplicate_path_multiplicities": {
                          key: value for key, value in sorted(counts.items()) if value != 1
                      },
                      "history_output_denominator": len(selected),
                      "independent_filtered_history_denominator": len(independent),
                      "history_bytes_match_complete_owner_hashes": True,
                      "field_identity_delta": deltas,
                      "changed_inventory_entry_paths": sorted(r["path"] for r in updates.values()),
                      "inventory_sha256_before": hashlib.sha256(original).hexdigest(),
                      "inventory_sha256_after": hashlib.sha256(path.read_bytes()).hexdigest()},
                     indent=2))


if __name__ == "__main__":
    main()
