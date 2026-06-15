from __future__ import annotations

import copy
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
    / "layer3_gy_catalog_fetch_audit.json"
)


def _validator() -> Any:
    return import_module("tools.quality.validation.check_layer3_gy_catalog_fetch_audit")


def _load_audit() -> dict[str, Any]:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def _codes(violations: list[dict[str, Any]]) -> set[str]:
    return {str(item["code"]) for item in violations}


def _row(audit: dict[str, Any], route_id: str) -> dict[str, Any]:
    for item in audit["route_rows"]:
        if item.get("route_id") == route_id:
            return item
    raise AssertionError(f"missing row {route_id}")


def test_gy_catalog_fetch_audit_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_audit()) == []


def test_gy_catalog_fetch_audit_rejects_lost_catalog_plan_probe() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["probe"]["catalog_to_fetch_plan"] = copy.deepcopy(
        audit["probe"]["catalog_to_fetch_plan"]
    )
    audit["probe"]["catalog_to_fetch_plan"]["fetch_plan_count"] = 0

    assert "catalog_fetch_plan_not_proven" in _codes(validator.validate(audit))


def test_gy_catalog_fetch_audit_rejects_hidden_persist_payload_noop_change() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["probe"]["fake_connector_persist_payload_true"] = copy.deepcopy(
        audit["probe"]["fake_connector_persist_payload_true"]
    )
    audit["probe"]["fake_connector_persist_payload_true"]["cas_file_delta_count"] = 1

    assert "fake_persist_payload_wrote_cas" in _codes(validator.validate(audit))


def test_gy_catalog_fetch_audit_rejects_lost_metric_surface_gap() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["probe"]["fake_connector_persist_payload_true"] = copy.deepcopy(
        audit["probe"]["fake_connector_persist_payload_true"]
    )
    audit["probe"]["fake_connector_persist_payload_true"][
        "data_context_metric_has_artifact_ref"
    ] = True

    assert "data_context_metric_artifact_ref_changed" in _codes(
        validator.validate(audit)
    )


def test_gy_catalog_fetch_audit_rejects_default_runtime_catalog_upgrade_without_evidence() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["default_runtime_injects_dataset_catalog"] = True
    row = _row(audit, "runtime.control.data_resolve.default_composition")
    row["capability_state"] = "runs_on_real_catalog"

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "required_route_state_changed" in codes


def test_gy_catalog_fetch_audit_rejects_ingestion_bridge_laundering() -> None:
    validator = _validator()
    audit = _load_audit()
    row = _row(audit, "ingest.fetch_plan_root_producer")
    row["gap_labels"] = [
        label for label in row["gap_labels"] if label != "bridge_missing"
    ]

    assert "ingestion_bridge_gap_missing" in _codes(validator.validate(audit))


def test_gy_catalog_fetch_audit_rejects_missing_persist_payload_row() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["route_rows"] = [
        row
        for row in audit["route_rows"]
        if row.get("route_id") != "fetch.executor.persist_payload_true"
    ]

    assert "missing_required_route_row" in _codes(validator.validate(audit))
