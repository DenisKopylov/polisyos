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
    / "layer3_gy_runtime_surface_audit.json"
)


def _validator() -> Any:
    return import_module("tools.quality.validation.check_layer3_gy_runtime_surface_audit")


def _load_audit() -> dict[str, Any]:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def _codes(violations: list[dict[str, Any]]) -> set[str]:
    return {str(item["code"]) for item in violations}


def _surface(audit: dict[str, Any], surface_id: str) -> dict[str, Any]:
    for row in audit["surface_rows"]:
        if row.get("surface_id") == surface_id:
            return row
    raise AssertionError(f"missing surface {surface_id}")


def test_gy_runtime_surface_audit_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_audit()) == []


def test_gy_runtime_surface_audit_rejects_lost_failed_fixture() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["probe"]["fixture"]["indexed_run_status"] = "completed"

    assert "fixture_semantics_drift" in _codes(validator.validate(audit))


def test_gy_runtime_surface_audit_rejects_lost_route_probe() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["probe"]["route_status_codes"]["workflow_openlineage_export"] = 500

    assert "probe_route_not_200" in _codes(validator.validate(audit))


def test_gy_runtime_surface_audit_rejects_downgraded_public_packet_risk() -> None:
    validator = _validator()
    audit = _load_audit()
    row = _surface(audit, "dashboard.public_packet_builder")
    row["laundering_risk"] = "medium"
    audit["summary"]["critical_count"] -= 1

    assert "required_critical_surface_downgraded" in _codes(validator.validate(audit))


def test_gy_runtime_surface_audit_rejects_lost_raw_secret_observation() -> None:
    validator = _validator()
    audit = _load_audit()
    row = _surface(audit, "runtime.api.artifacts.content")
    row["observed_projection"] = copy.deepcopy(row["observed_projection"])
    row["observed_projection"].pop("nested_secret_like_key_observed", None)

    assert "missing_raw_secret_observation" in _codes(validator.validate(audit))


def test_gy_runtime_surface_audit_rejects_lost_verified_failed_lineage() -> None:
    validator = _validator()
    audit = _load_audit()
    row = _surface(audit, "runtime.api.lineage.graph")
    row["observed_projection"] = copy.deepcopy(row["observed_projection"])
    row["observed_projection"]["status"] = "untraced"

    assert "missing_verified_failed_lineage_observation" in _codes(
        validator.validate(audit)
    )
