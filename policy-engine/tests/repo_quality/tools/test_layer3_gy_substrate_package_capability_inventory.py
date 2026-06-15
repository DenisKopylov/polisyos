from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
INVENTORY_PATH = (
    REPO_ROOT
    / "architecture"
    / "policy_design_case"
    / "layer3_gy_task0_audit"
    / "layer3_gy_substrate_package_capability_inventory.json"
)


def _validator() -> Any:
    return import_module(
        "tools.quality.validation.check_layer3_gy_substrate_package_capability_inventory"
    )


def _load_inventory() -> dict[str, Any]:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def _codes(violations: list[dict[str, Any]]) -> set[str]:
    return {str(item["code"]) for item in violations}


def _row(inventory: dict[str, Any], module: str) -> dict[str, Any]:
    for row in inventory["package_inventory"]:
        if row.get("module") == module:
            return row
    raise AssertionError(f"missing row {module}")


def _negative(inventory: dict[str, Any], negative_id: str) -> dict[str, Any]:
    for row in inventory["negative_assertions"]:
        if row.get("id") == negative_id:
            return row
    raise AssertionError(f"missing negative assertion {negative_id}")


def test_gy_substrate_package_inventory_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_inventory()) == []


def test_gy_substrate_inventory_rejects_data_requirement_surface_greenwash() -> None:
    validator = _validator()
    inventory = _load_inventory()
    data_requirement = _row(inventory, "polisyos.data_requirement")
    data_requirement["package_contract_registered"] = True
    data_requirement["public_surface_registered"] = True
    data_requirement["missing_labels"] = []
    data_requirement["route_participation"] = "route_pinned_substrate"
    inventory["summary"]["data_requirement_package_contract_registered"] = True
    inventory["summary"]["data_requirement_public_surface_registered"] = True

    codes = _codes(validator.validate(inventory))
    assert "summary_semantics_drift" in codes
    assert "data_requirement_package_contract_greenwash" in codes
    assert "data_requirement_public_surface_greenwash" in codes
    assert "data_requirement_missing_label_drift" in codes
    assert "data_requirement_route_classification_drift" in codes


def test_gy_substrate_inventory_rejects_evidence_support_laundering() -> None:
    validator = _validator()
    inventory = _load_inventory()
    evidence = _row(inventory, "polisyos.evidence")
    evidence["authority_boundary_summary"] = (
        "Authoritative for claim authority and positive support strength."
    )
    evidence["missing_labels"] = []
    _negative(
        inventory,
        "do_not_count_evidence_conflict_or_raw_count_as_positive_support",
    )["assertion_holds"] = False

    codes = _codes(validator.validate(inventory))
    assert "evidence_support_authority_greenwash" in codes
    assert "evidence_missing_label_drift" in codes
    assert "negative_assertion_not_enforced" in codes


def test_gy_substrate_inventory_rejects_ddm_as_pinned_route() -> None:
    validator = _validator()
    inventory = _load_inventory()
    ddm = _row(inventory, "polisyos.ddm")
    ddm["route_participation"] = "route_pinned_substrate"
    ddm["missing_labels"] = []
    _negative(
        inventory,
        "do_not_count_ddm_monitoring_as_gy_pinned_route_execution",
    )["assertion_holds"] = False

    codes = _codes(validator.validate(inventory))
    assert "ddm_route_greenwash" in codes
    assert "ddm_surface_scope_drift" in codes
    assert "negative_assertion_not_enforced" in codes


def test_gy_substrate_inventory_rejects_missing_package_row() -> None:
    validator = _validator()
    inventory = _load_inventory()
    inventory["package_inventory"] = [
        row
        for row in inventory["package_inventory"]
        if row.get("module") != "polisyos.calibration"
    ]

    codes = _codes(validator.validate(inventory))
    assert "missing_package_rows" in codes
    assert "summary_row_count_mismatch" in codes


def test_gy_substrate_inventory_rejects_count_drift() -> None:
    validator = _validator()
    inventory = _load_inventory()
    inventory["summary"]["total_python_files"] = 467
    _row(inventory, "polisyos.core")["python_files"] = 199

    codes = _codes(validator.validate(inventory))
    assert "summary_semantics_drift" in codes


def test_gy_substrate_inventory_rejects_methodology_and_acceptance_drift() -> None:
    validator = _validator()
    inventory = _load_inventory()
    inventory["methodology"]["runtime_execution"] = True
    inventory["classification"]["patterns"] = [
        pattern for pattern in inventory["classification"]["patterns"] if pattern != "P25"
    ]
    inventory["acceptance_signal"] = [
        item
        for item in inventory["acceptance_signal"]
        if "cannot be upgraded to GY route authority" not in item
    ]

    codes = _codes(validator.validate(inventory))
    assert "methodology_drift" in codes
    assert "pattern_coverage_drift" in codes
    assert "missing_acceptance_guardrail" in codes
