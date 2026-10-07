"""Author metadata controls for exact candidate roles, without product checks."""

from __future__ import annotations

import hashlib
import json
import runpy
import sys
from copy import deepcopy
from pathlib import Path

OUT = Path(__file__).parent
SOURCE = OUT / "validate_binding_v3.py"
OLDER_COLLECTOR_COMMIT = "2f7e7e12516dd98678903c5b4a89553a28b08608"


def main() -> int:
    module = runpy.run_path(str(SOURCE), run_name="author_metadata_controls")
    binding, packet = module["load_original"]()
    original_index = module["ORIGINAL"] / "copy-index.json"
    original_digest = hashlib.sha256(original_index.read_bytes()).hexdigest()
    module["validate"](binding, packet)
    rows = [{"control": "unchanged current and distinct historical roles", "outcome": "BOUND"}]

    def replace_current_source(b: dict, _p: dict) -> None:
        b["source_rows"][0]["current_source"]["commit"] = module["HISTORICAL_SHA"]

    def replace_g_current_ref(b: dict, _p: dict) -> None:
        ref = next(
            row
            for row in b["new_owner_action_and_carried_packet_refs"]
            if row["path"] == b["canonical_collector_v4"]["path"]
        )
        ref["commit"] = OLDER_COLLECTOR_COMMIT

    def replace_current_collector(b: dict, _p: dict) -> None:
        b["canonical_collector_v4"]["commit"] = OLDER_COLLECTOR_COMMIT

    def replace_packet_collector(_b: dict, p: dict) -> None:
        p["canonical_collector_readiness"]["current_source"]["commit"] = OLDER_COLLECTOR_COMMIT

    def replace_caller_source(b: dict, _p: dict) -> None:
        b["actual_caller_coordinates"][0]["git_source"]["commit"] = module["HISTORICAL_SHA"]

    controls = [
        ("same real bytes but old5e in current_source", replace_current_source),
        ("same collector bytes but old2f7 in current owner/G reference", replace_g_current_ref),
        ("same collector bytes but old2f7 in binding current collector", replace_current_collector),
        ("same collector bytes but old2f7 in packet current collector", replace_packet_collector),
        ("same caller bytes but old5e in current caller source", replace_caller_source),
        (
            "current source assigned to explicitly historical5e role",
            lambda b, _p: b["source_rows"][0]["failed5e_source"].update(
                commit=module["CURRENT_SHA"]
            ),
        ),
        (
            "binding candidate pin replaced by old5e",
            lambda b, _p: b["current_committed_source"].update(sha=module["HISTORICAL_SHA"]),
        ),
        (
            "packet candidate pin replaced by old5e",
            lambda _b, p: p["current_committed_source"].update(sha=module["HISTORICAL_SHA"]),
        ),
        (
            "valid content digest with counterfeit declared Git blob",
            lambda b, _p: b["source_rows"][0]["current_source"].update(git_blob="0" * 40),
        ),
        (
            "present source ref with fake content digest",
            lambda b, _p: b["source_rows"][0]["current_source"].update(sha256="0" * 64),
        ),
        (
            "present current owner-action ref with fake digest",
            lambda b, _p: b["new_owner_action_and_carried_packet_refs"][0].update(sha256="0" * 64),
        ),
        (
            "current source ref path differs from admitted row role",
            lambda b, _p: b["source_rows"][0]["current_source"].update(path="AGENTS.md"),
        ),
        (
            "missing-ref reason replaced by floor failure",
            lambda _b, p: p["A_reason_scenarios"][0].update(
                expected_S6_reason="s10://calibration/calibration_floor_not_met"
            ),
        ),
        (
            "resolved limited reason replaced by missing ref",
            lambda _b, p: p["A_reason_scenarios"][1].update(
                expected_S6_reason="s10://calibration/fail-closed/empirical_evidence_ref_missing"
            ),
        ),
        (
            "historical1492 promoted to current generated measurement",
            lambda _b, p: p["generator_evidence_boundary"].update(
                current_generated_dependency_count=1492, current_generator_check_state="PASS"
            ),
        ),
        (
            "installed compiler PASS promoted to FRC acceptance",
            lambda _b, p: p["new_G_owner_result"].update(FRC_acceptance=True),
        ),
        (
            "historical preparation snapshot marked as measured PASS",
            lambda _b, p: p["canonical_collector_readiness"].update(
                actual_wave_at_preparation="PASS"
            ),
        ),
    ]
    for label, mutate in controls:
        b, p = deepcopy(binding), deepcopy(packet)
        mutate(b, p)
        try:
            module["validate"](b, p)
        except module["BindingAdmissionError"] as error:
            rows.append({"control": label, "outcome": "TYPED_REFUSAL", "reason": str(error)})
        else:
            raise AssertionError(label)

    # Remove only the shared commit-role predicate; retain all names and fields.
    source_text = SOURCE.read_text()
    predicate = (
        '    if ref["commit"] != expected_commit:\n'
        "        raise BindingAdmissionError("
        '"Git ref candidate differs from its declared current role")\n'
    )
    if source_text.count(predicate) != 1:
        raise AssertionError("exact shared predicate source changed")
    removal_path = OUT / "commit_role_predicate_removed.py.txt"
    if removal_path.exists() or removal_path.is_symlink():
        raise FileExistsError("preserve prior removal source")
    removal_path.write_text(source_text.replace(predicate, ""))
    removed = runpy.run_path(str(removal_path), run_name="author_effective_role_removal")
    for label, mutate in controls[:2]:
        b, p = deepcopy(binding), deepcopy(packet)
        mutate(b, p)
        removed["validate"](b, p)
        rows.append(
            {
                "control": label + " with only shared commit predicate removed",
                "outcome": "REACCEPTED",
            }
        )
    if hashlib.sha256(original_index.read_bytes()).hexdigest() != original_digest:
        raise AssertionError("original immutable packet changed")
    result = {
        "scope": "Author metadata only; no product/numerical/generator/gate commands",
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "original_index_unchanged": True,
        "checks": rows,
        "preparation_snapshot_note": (
            "Original packet's NOT_LAUNCHED describes its preparation tim"
            "e; actual corrected wave is now RUNNING separately. This val"
            "idator does not inspect or classify that wave."
        ),
    }
    encoded = json.dumps(result, indent=2) + "\n"
    result_path = OUT / "binding-controls-v3.json"
    if result_path.exists() or result_path.is_symlink():
        raise FileExistsError("preserve prior control results")
    result_path.write_text(encoded)
    sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
