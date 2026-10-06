"""Reconcile the complete retained N5 property-removal evidence set."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ACCEPTED = {
    "engine_selection": "removed_property_keep_markers:n8_negative_admitted:identity_multiple_selected_decisions",
    "sibling_receipt_hash": "removed_property_keep_markers:n8_negative_admitted:sibling_digest_mismatch",
    "explicit_empty_atoms": "removed_property_keep_markers:n8_negative_admitted:explicit_empty_candidate_atoms",
    "point_outcome_distribution": "removed_property_keep_markers:n8_negative_admitted:missing_selected_point_outcome",
    "absent_atom_fallback": "removed_property_keep_markers:absent_atom_fallback_lost:",
    "casless_digest": "removed_property_keep_markers:casless_digest_admitted_before_fallback:",
}
TARGET = "test_n5_fresh_process_readback_binds_default_n8_to_cas_identity"
EXPECTED_SOURCE = "99c2d86fb7b0e94ceb8d316b8faa9496e5984698d6c3aa112cfb4565d0331a6b"
EXPECTED_TEST = "e8ec4a70f2a7356b21907f601d41e9a6b27c90cfa69893d185897c4b84724218"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    accepted_dirs = {
        path.name: path for path in (ROOT / "removal-controls").iterdir() if path.is_dir()
    }
    nonpass_dirs = {
        path.name: path
        for path in (ROOT / "nonpassing" / "mutation-attempts").iterdir()
        if path.is_dir()
    }
    assert set(accepted_dirs) == set(ACCEPTED), (sorted(accepted_dirs), sorted(ACCEPTED))
    assert len(nonpass_dirs) == 3, sorted(nonpass_dirs)

    target_failures = 0
    for property_name, expected_label in ACCEPTED.items():
        directory = accepted_dirs[property_name]
        metadata = json.loads((directory / "metadata.json").read_text())
        junit_root = ET.parse(directory / "junit.xml").getroot()
        cases = list(junit_root.iter("testcase"))
        assert len(cases) == 1 and cases[0].attrib.get("name") == TARGET
        failures = cases[0].findall("failure")
        errors = cases[0].findall("error")
        skipped = cases[0].findall("skipped")
        failure_text = "\n".join(
            part
            for failure in failures
            for part in (failure.attrib.get("message", ""), failure.text or "")
            if part
        )
        assert len(failures) == 1 and not errors and not skipped, property_name
        assert expected_label in failure_text, property_name
        assert metadata["git_head"] == "7ffbf5c71d6352f7712673a6591be5e553993745"
        assert metadata["git_tree"] == "221f31490189a5a2865f1ce2e4b335d6342d6bd6"
        assert metadata["source_sha256"] == EXPECTED_SOURCE
        assert metadata["test_sha256"] == EXPECTED_TEST
        harness_name = Path(metadata["harness"]).name
        harness = ROOT / "harness" / harness_name
        harness_text = harness.read_text()
        assert sha256(harness) == metadata["harness_sha256"], property_name
        assert "unexpected_mutation_hits" in harness_text, property_name
        expected_hits = 2 if property_name == "explicit_empty_atoms" else 1
        if metadata.get("expected_mutation_hits") is not None:
            assert metadata["expected_mutation_hits"] == expected_hits, property_name
        stdout = (directory / "stdout.txt").read_text()
        assert f"REMOVAL_PROBE=PASS property={property_name}" in stdout
        result = json.loads((directory / "result.json").read_text())
        if "junit_valid_target_failure_no_collection_error" in result:
            assert result["junit_valid_target_failure_no_collection_error"] is True
            assert result["mutation_applied_marker_present_with_expected_hit_count"] is True
            assert result["expected_behavioral_assertion_in_junit_failure"] is True
        target_failures += 1

    for directory in nonpass_dirs.values():
        assert (directory / "metadata.json").is_file()
        assert (directory / "junit.xml").is_file()
        assert (directory / "stdout.txt").is_file()
        assert (directory / "stderr.txt").is_file()

    total = len(accepted_dirs) + len(nonpass_dirs)
    metadata_files = total
    junit_files = total
    print(
        f"mutation evidence census: directories={total} "
        "(removal-controls/* plus nonpassing/mutation-attempts/*); "
        f"file-type denominator=metadata.json:{metadata_files}, junit.xml:{junit_files}; "
        f"accepted exact target failures={target_failures}/{len(ACCEPTED)}; "
        f"retained nonpasses={len(nonpass_dirs)}"
    )
    print(
        "accepted properties="
        + ",".join(ACCEPTED)
    )
    print(
        "nonpassing="
        + ",".join(sorted(nonpass_dirs))
    )


if __name__ == "__main__":
    main()
