"""Project complete measured claim/source deltas into a concise review packet."""

# ruff: noqa: S101, T201 - complete frozen/current assertions and documentary output

import json
from pathlib import Path

root = Path.cwd()
evidence = root / "docs/superpowers/journals/gy-phase5-evidence/pr1"
packet = json.loads((evidence / "trust-posture-complete-delta.json").read_text())
before = packet["complete_frozen_artifact"]
after = packet["complete_actual_scratch_artifact"]
old = {row["claim_id"]: row for row in before["claims"]}
new = {row["claim_id"]: row for row in after["claims"]}
assert len(old) == len(before["claims"])
assert len(new) == len(after["claims"])
other_changes = {
    key: value
    for key, value in packet["shared_claim_decision_field_differences"].items()
    if any(item["path"][0] != "may_not_use_for" for item in value)
}
denied_changes = {
    key: {
        "added": sorted(set(new[key]["may_not_use_for"]) - set(old[key]["may_not_use_for"])),
        "removed": sorted(set(old[key]["may_not_use_for"]) - set(new[key]["may_not_use_for"])),
    }
    for key in sorted(old.keys() & new.keys())
    if old[key]["may_not_use_for"] != new[key]["may_not_use_for"]
}
source_changes = set(packet["complete_collections"]["admitted_sources"]["changed_shared"])
source_categories = {"unchanged_since_slice_base": [], "changed_in_lane": [], "not_established": []}
for source in packet["complete_source_provenance"]:
    if source["path"] not in source_changes:
        continue
    current = source["current"]
    base = source["slice_base"]
    if current["presence"] != "present" or base["presence"] != "present":
        source_categories["not_established"].append(source["path"])
    elif current["content_digest"] == base["content_digest"]:
        source_categories["unchanged_since_slice_base"].append(source["path"])
    else:
        source_categories["changed_in_lane"].append(source["path"])
base_lines = (
    (
        root.parent.parent
        / "gyphase5-lane-basecheck/policy-engine/docs/plans/active/DEBT-REGISTER.md"
    )
    .read_text()
    .splitlines()
)
old_custody = {row["debt_id"]: row for row in before["custody_appointment_sources"]}
new_custody = {row["debt_id"]: row for row in after["custody_appointment_sources"]}
assert old_custody.keys() == new_custody.keys()
custody = [
    {
        "debt_id": key,
        "frozen_status": old_custody[key]["status"],
        "current_status": new_custody[key]["status"],
        "current_exact_row_already_in_slice_base": new_custody[key]["source_content"] in base_lines,
    }
    for key in sorted(old_custody)
    if old_custody[key] != new_custody[key]
]
result = {
    "denominator": (
        "All complete claim identity sets, all shared decision-field changes, every changed "
        "admitted source, every custody source row in the reconciled full artifact packet."
    ),
    "frozen_claim_identities": sorted(old),
    "current_claim_identities": sorted(new),
    "added_claims": [
        {
            "claim_id": key,
            "state": new[key]["effective_state"],
            "subject": new[key]["subject"],
            "authoritative_for": new[key]["authoritative_for"],
            "binding_coordinates": [
                binding["coordinate"] for binding in new[key]["source_bindings"]
            ],
        }
        for key in sorted(new.keys() - old.keys())
    ],
    "removed_claims": [
        {
            "claim_id": key,
            "state": old[key]["effective_state"],
            "binding_coordinates": [
                binding["coordinate"] for binding in old[key]["source_bindings"]
            ],
        }
        for key in sorted(old.keys() - new.keys())
    ],
    "shared_claim_changes_other_than_denied_use": other_changes,
    "complete_denied_use_identity_changes": denied_changes,
    "changed_source_attribution": source_categories,
    "custody_source_changes": custody,
}
(evidence / "trust-posture-semantic-summary.json").write_text(
    json.dumps(result, indent=2, sort_keys=True) + "\n"
)
print(
    json.dumps(
        {
            key: value
            for key, value in result.items()
            if key
            not in {
                "frozen_claim_identities",
                "current_claim_identities",
                "complete_denied_use_identity_changes",
            }
        },
        indent=2,
    )
)
