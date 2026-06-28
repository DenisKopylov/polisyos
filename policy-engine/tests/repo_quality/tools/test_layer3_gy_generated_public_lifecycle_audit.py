from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_PATH = (
    REPO_ROOT
    / "architecture"
    / "policy_design_case"
    / "layer3_gy_task0_audit"
    / "layer3_gy_generated_public_lifecycle_audit.json"
)


def _validator() -> Any:
    return import_module("tools.quality.validation.check_layer3_gy_generated_public_lifecycle_audit")


def _load_audit() -> dict[str, Any]:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def _codes(violations: list[dict[str, Any]]) -> set[str]:
    return {str(item["code"]) for item in violations}


def _row(audit: dict[str, Any], row_id: str) -> dict[str, Any]:
    for row in audit["lifecycle_matrix"]:
        if row.get("row_id") == row_id:
            return row
    raise AssertionError(f"missing row {row_id}")


def _surface(audit: dict[str, Any], surface_id: str) -> dict[str, Any]:
    for row in audit["public_surface_lifecycle"]:
        if row.get("surface_id") == surface_id:
            return row
    raise AssertionError(f"missing surface {surface_id}")


def _negative(audit: dict[str, Any], negative_id: str) -> dict[str, Any]:
    for row in audit["negative_assertions"]:
        if row.get("id") == negative_id:
            return row
    raise AssertionError(f"missing negative assertion {negative_id}")


def test_gy_generated_public_lifecycle_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_audit()) == []


def test_gy_generated_public_lifecycle_rejects_missing_gy_family_registration() -> None:
    validator = _validator()
    audit = _load_audit()
    gy = _row(audit, "layer3_gy_task0_audit_artifacts")
    gy["registered"] = False
    gy["family_id"] = None
    gy["outputs_registered_count"] = 0
    gy["stale_output_behavior"] = "missing_registry"
    audit["summary"]["gy_generated_family_registered"] = False
    audit["summary"]["gy_artifact_files_registered_count"] = 0

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "gy_family_registration_drift" in codes
    assert "gy_family_id_drift" in codes
    assert "gy_registered_output_count_drift" in codes
    assert "gy_stale_policy_drift" in codes


def test_gy_generated_public_lifecycle_rejects_public_surface_family_drift() -> None:
    validator = _validator()
    audit = _load_audit()
    surface = _surface(audit, "policy_design_case_generated_audit_surfaces_section")
    surface["gy_surface_registered"] = False
    audit["summary"]["gy_public_surface_family_registered"] = False

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "gy_public_surface_registration_drift" in codes


def test_gy_generated_public_lifecycle_rejects_projection_refs_as_api_enforcement() -> None:
    validator = _validator()
    audit = _load_audit()
    projection = _surface(audit, "layer3_public_export_projection_refs")
    projection["api_dashboard_enforcement"] = True
    projection["public_export_route_registered"] = True
    _negative(
        audit,
        "do_not_count_projection_refs_as_api_dashboard_enforcement",
    )["assertion_holds"] = False

    codes = _codes(validator.validate(audit))
    assert "projection_refs_api_enforcement_laundering" in codes
    assert "projection_refs_public_export_laundering" in codes
    assert "negative_assertion_not_enforced" in codes


def test_gy_generated_public_lifecycle_rejects_missing_registered_stale_policy() -> None:
    validator = _validator()
    audit = _load_audit()
    openapi = _row(audit, "runtime_openapi_snapshot")
    openapi["stale_output_behavior"] = ""

    codes = _codes(validator.validate(audit))
    assert "registered_family_missing_lifecycle_metadata" in codes


def test_gy_generated_public_lifecycle_rejects_missing_pdc_inventory_gy_entries() -> None:
    validator = _validator()
    audit = _load_audit()
    pdc = _row(audit, "policy_design_case_inventory")
    pdc["contains_gy_entries"] = False
    audit["summary"]["policy_design_case_inventory_gy_entries"] = 0

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "pdc_inventory_gy_entry_missing" in codes


def test_gy_generated_public_lifecycle_rejects_file_inventory_drift() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["gy_artifact_inventory"]["paths"] = audit["gy_artifact_inventory"]["paths"][:-1]
    audit["summary"]["gy_artifact_files_detected"] -= 1

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "gy_detected_artifact_list_drift" in codes


def test_gy_generated_public_lifecycle_rejects_missing_pattern_and_acceptance() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["classification"]["patterns"] = [
        pattern for pattern in audit["classification"]["patterns"] if pattern != "P31"
    ]
    audit["acceptance_signal"] = [
        item
        for item in audit["acceptance_signal"]
        if "producer write-closure" not in item
    ]

    codes = _codes(validator.validate(audit))
    assert "pattern_coverage_drift" in codes
    assert "missing_acceptance_guardrail" in codes
