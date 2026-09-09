"""Reissue only M1's derived source snapshot, preserving unrelated JSON bytes."""
from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path

from tools.quality.validation import check_layer3_gy_generated_public_lifecycle_audit as owner

ROOT = Path(__file__).resolve().parents[2]
DECODER = json.JSONDecoder()


def spans(text: str) -> dict[tuple, tuple[int, int]]:
    positions = {}

    def skip(i):
        while i < len(text) and text[i].isspace():
            i += 1
        return i

    def walk(i, path):
        i = skip(i)
        begin = i
        if text[i] == "{":
            i = skip(i + 1)
            while text[i] != "}":
                key, i = DECODER.raw_decode(text, i)
                i = skip(i)
                assert text[i] == ":"
                i = skip(walk(i + 1, (*path, key)))
                if text[i] == ",":
                    i = skip(i + 1)
                else:
                    break
            assert text[i] == "}"
            i += 1
        elif text[i] == "[":
            i = skip(i + 1)
            index = 0
            while text[i] != "]":
                i = skip(walk(i, (*path, index)))
                index += 1
                if text[i] == ",":
                    i = skip(i + 1)
                else:
                    break
            assert text[i] == "]"
            i += 1
        else:
            _, i = DECODER.raw_decode(text, i)
        positions[path] = (begin, i)
        return i

    walk(0, ())
    return positions


def surgical(path, updates):
    original = path.read_text()
    positions = spans(original)
    patches = []
    for key, value in updates.items():
        start, end = positions[key]
        if json.loads(original[start:end]) == value:
            continue
        line = original[original.rfind("\n", 0, start) + 1:start]
        prefix = re.match(r" *", line).group()
        replacement = json.dumps(value, indent=2, ensure_ascii=False).replace("\n", "\n" + prefix)
        patches.append((start, end, replacement))
    output = original
    for start, end, replacement in sorted(patches, reverse=True):
        output = output[:start] + replacement + output[end:]
    json.loads(output)
    path.write_text(output)
    return len(patches)


def inventory(families):
    path = ROOT / "architecture/policy_design_case/inventory.json"
    original = path.read_text()
    entries = json.loads(original)["artifacts"]
    seen = {entry["path"] for entry in entries}
    added = []
    for family in families:
        if family.get("gy_lifecycle_family") is not True:
            continue
        for output in family.get("outputs", []):
            if output in seen:
                continue
            seen.add(output)
            added.append({
                "id": "gy_lifecycle_" + re.sub(r"[^a-zA-Z0-9]+", "_", output).strip("_"),
                "path": output,
                "kind": "layer3_gy_lifecycle_artifact",
                "owner": family["owner"],
                "family_id": family["id"],
                "lifecycle": family["lifecycle"],
                "validator": "tools/quality/validation/check_layer3_gy_generated_public_lifecycle_audit.py",
                "authority_boundary": "lifecycle_custody_only_no_new_runtime_or_publication_authority",
                "status": "active",
            })
    if added:
        _, end = spans(original)[("artifacts",)]
        insert = original.rfind("\n", 0, end - 1)
        content = ",\n".join("    " + json.dumps(entry, indent=2).replace("\n", "\n    ") for entry in added)
        output = original[:insert] + ",\n" + content + original[insert:]
        assert json.loads(output)["artifacts"] == entries + added
        path.write_text(output)
    return [entry["path"] for entry in added]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", action="store_true")
    args = parser.parse_args()
    families = tomllib.loads((ROOT / "architecture/generated_artifacts.toml").read_text())["family"]
    added = inventory(families) if args.inventory else []
    report = owner.validate_gy_lifecycle_registry(ROOT)
    facts = owner._lifecycle_facts(ROOT, report)
    expected = owner._expected_file_sets(ROOT, report)
    path = ROOT / "architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_generated_public_lifecycle_audit.json"
    audit = json.loads(path.read_text())
    updates = {("schema_version",): "layer3_gy_generated_public_lifecycle_audit.v2"}
    for key in audit["summary"]:
        if key in facts:
            updates[("summary", key)] = facts[key]
    updates[("summary", "gy_validators_detected")] = len(expected["validators"])
    updates[("summary", "gy_validator_tests_detected")] = len(expected["validator_tests"])
    for key in audit["source_registry_facts"]:
        if key in facts:
            updates[("source_registry_facts", key)] = facts[key]
    for key, value in expected.items():
        updates[("gy_artifact_inventory", key)] = value
    for key in ("registered_output_count", "orphan_count", "duplicate_claim_count", "phantom_output_count"):
        if key in audit["gy_artifact_inventory"]:
            updates[("gy_artifact_inventory", key)] = report["registered_artifact_count" if key == "registered_output_count" else key]
    for index, row in enumerate(audit["lifecycle_matrix"]):
        prefix = ("lifecycle_matrix", index)
        if row["row_id"] == "layer3_gy_task0_audit_artifacts":
            updates[(*prefix, "outputs_registered_count")] = facts["gy_artifact_files_registered_count"]
        if row["row_id"] == "policy_design_case_inventory":
            custody = [family for family in families if "architecture/policy_design_case/inventory.json" in family.get("outputs", [])]
            assert len(custody) == 1
            updates.update({
                (*prefix, "registered"): True,
                (*prefix, "family_id"): custody[0]["id"],
                (*prefix, "artifact_count"): facts["policy_design_case_inventory_artifact_count"],
                (*prefix, "gy_entry_count"): facts["policy_design_case_inventory_gy_entries"],
                (*prefix, "detected_outputs_count"): facts["policy_design_case_inventory_gy_entries"],
                (*prefix, "outputs_registered_count"): 1,
                (*prefix, "classification"): "registered_source_committed_control_plane_inventory",
                (*prefix, "verifier"): "registered source integrity and generated-artifacts lifecycle class gate",
            })
    pdc = ("source_registry_facts", "policy_design_case_inventory")
    updates[(*pdc, "artifact_count")] = facts["policy_design_case_inventory_artifact_count"]
    updates[(*pdc, "gy_entry_count")] = facts["policy_design_case_inventory_gy_entries"]
    updates[(*pdc, "registered_in_generated_artifacts")] = facts["policy_design_case_inventory_registered_in_generated_artifacts"]
    changed = surgical(path, updates)
    print(json.dumps({"source_snapshot_changed_values": changed, "inventory_added_paths": added,
                      "pre_refresh_registry_issues": report["issues"]}, indent=2))


if __name__ == "__main__":
    main()
