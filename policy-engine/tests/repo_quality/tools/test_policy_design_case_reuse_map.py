# ruff: noqa: S101

from __future__ import annotations

import copy
from pathlib import Path

from tools.quality.validation import check_policy_design_case_reuse_map as reuse_map

REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWED_CLASSIFICATIONS = {
    "wire-existing",
    "extend-existing",
    "consolidate-existing",
    "build-new",
}


def test_phase_1_3_reuse_map_is_generated_from_sdd_capability_map() -> None:
    payload = reuse_map.load_reuse_map(REPO_ROOT)
    generated = reuse_map.build_reuse_map_payload(REPO_ROOT)
    validation = reuse_map.validate_reuse_map_payload(payload, repo_root=REPO_ROOT)

    assert validation["status"] == "pass", validation["issues"]
    assert payload["schema_version"] == "policyos.policy_design_case.reuse_map.v1"
    assert payload["summary"]["target_capability_count"] == 27
    assert payload["entries"] == generated["entries"]
    assert {entry["classification"] for entry in payload["entries"]} <= ALLOWED_CLASSIFICATIONS
    assert {
        "wire-existing",
        "extend-existing",
        "consolidate-existing",
        "build-new",
    } <= {entry["classification"] for entry in payload["entries"]}
    assert any(
        entry["target_capability"] == "Formal substrate invariant specification"
        and entry["classification"] == "build-new"
        and "runtime_quality" in entry["sensitive_overlap_domains"]
        and entry["rejected_reuse_evidence"]
        for entry in payload["entries"]
    )


def test_phase_1_3_reuse_map_rejects_missing_reuse_classification() -> None:
    payload = reuse_map.build_reuse_map_payload(REPO_ROOT)
    payload = copy.deepcopy(payload)
    payload["entries"][0].pop("classification")

    validation = reuse_map.validate_reuse_map_payload(payload, repo_root=REPO_ROOT)

    assert validation["status"] == "fail"
    assert "pdc_reuse_classification_missing" in _issue_codes(validation)


def test_phase_1_3_reuse_map_rejects_build_new_overlap_without_evidence() -> None:
    payload = reuse_map.build_reuse_map_payload(REPO_ROOT)
    payload = copy.deepcopy(payload)
    payload["entries"][0] = {
        **payload["entries"][0],
        "target_capability": "Data Forge production corpus rebuild",
        "existing_owner_or_surface": "src/polisyos/data_forge/*",
        "classification": "build-new",
        "rejected_reuse_evidence": [],
    }

    validation = reuse_map.validate_reuse_map_payload(payload, repo_root=REPO_ROOT)

    assert validation["status"] == "fail"
    assert "pdc_build_new_reuse_evidence_missing" in _issue_codes(validation)


def _issue_codes(validation: dict[str, object]) -> set[str]:
    return {str(issue["code"]) for issue in validation["issues"]}  # type: ignore[index]
