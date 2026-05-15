from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = REPO_ROOT / "architecture" / "production_quality" / "invariant_registry.toml"

REQUIRED_INVARIANT_FIELDS = {
    "invariant_id",
    "minimum_closeout_gate",
    "pql_id",
    "final_owner",
    "producer_owners",
    "runtime_event_names",
    "required_artifact_kinds",
    "required_ref_keys",
    "evidence_classes",
    "allowed_provenance_kinds",
    "required_schema_contracts",
    "scorecard_gate_names",
    "readiness_check",
    "approval_policy",
    "override_policy",
    "non_overridable_blockers",
    "dashboard_projection_policy",
    "public_artifact_policy",
    "conflict_policy",
    "failure_code",
    "diagnostic_owner",
    "dependencies",
    "consumers",
    "next_diagnostic_command",
    "negative_tests",
}
REQUIRED_STRING_FIELDS = {
    "invariant_id",
    "minimum_closeout_gate",
    "pql_id",
    "final_owner",
    "readiness_check",
    "approval_policy",
    "override_policy",
    "dashboard_projection_policy",
    "public_artifact_policy",
    "conflict_policy",
    "failure_code",
    "diagnostic_owner",
    "next_diagnostic_command",
}
REQUIRED_NON_EMPTY_LIST_FIELDS = {
    "producer_owners",
    "runtime_event_names",
    "required_artifact_kinds",
    "required_ref_keys",
    "evidence_classes",
    "allowed_provenance_kinds",
    "required_schema_contracts",
    "scorecard_gate_names",
    "non_overridable_blockers",
    "consumers",
    "negative_tests",
}
OPTIONAL_LIST_FIELDS = {"dependencies"}


def test_every_production_invariant_declares_implementation_ownership() -> None:
    registry = _load_registry()
    invariants = registry.get("invariants")

    assert isinstance(invariants, list)
    assert invariants, "architecture/production_quality/invariant_registry.toml is empty"

    non_table_rows = [
        f"invariants[{index}]"
        for index, invariant in enumerate(invariants, start=1)
        if not isinstance(invariant, dict)
    ]
    assert non_table_rows == []

    missing_by_invariant = {
        _invariant_label(invariant, index): sorted(
            REQUIRED_INVARIANT_FIELDS - set(invariant)
        )
        for index, invariant in enumerate(invariants, start=1)
        if REQUIRED_INVARIANT_FIELDS - set(invariant)
    }

    assert missing_by_invariant == {}

    invalid_shape_by_invariant = {
        _invariant_label(invariant, index): _invalid_shape_fields(invariant)
        for index, invariant in enumerate(invariants, start=1)
        if _invalid_shape_fields(invariant)
    }
    assert invalid_shape_by_invariant == {}

    missing_negative_tests = {
        _invariant_label(invariant, index): _missing_negative_test_refs(invariant)
        for index, invariant in enumerate(invariants, start=1)
        if _missing_negative_test_refs(invariant)
    }
    assert missing_negative_tests == {}


def test_production_invariant_registry_rejects_empty_or_wrong_shaped_rows() -> None:
    invalid = {
        field: "value"
        for field in REQUIRED_INVARIANT_FIELDS
        if field
        not in REQUIRED_NON_EMPTY_LIST_FIELDS
        | OPTIONAL_LIST_FIELDS
        | {"invariant_id"}
    }
    invalid["invariant_id"] = ""
    for field in REQUIRED_NON_EMPTY_LIST_FIELDS:
        invalid[field] = []
    for field in OPTIONAL_LIST_FIELDS:
        invalid[field] = "not-a-list"

    invalid_fields = _invalid_shape_fields(invalid)

    assert "invariant_id" in invalid_fields
    assert REQUIRED_NON_EMPTY_LIST_FIELDS <= set(invalid_fields)
    assert OPTIONAL_LIST_FIELDS <= set(invalid_fields)


def _load_registry() -> dict[str, Any]:
    with REGISTRY_PATH.open("rb") as stream:
        return tomllib.load(stream)


def _invariant_label(invariant: dict[str, Any], index: int) -> str:
    invariant_id = invariant.get("invariant_id")
    if isinstance(invariant_id, str) and invariant_id:
        return invariant_id
    return f"invariants[{index}]"


def _invalid_shape_fields(invariant: dict[str, Any]) -> list[str]:
    invalid: list[str] = []
    for field in REQUIRED_STRING_FIELDS:
        if not _non_empty_string(invariant.get(field)):
            invalid.append(field)
    for field in REQUIRED_NON_EMPTY_LIST_FIELDS:
        if not _non_empty_string_list(invariant.get(field)):
            invalid.append(field)
    for field in OPTIONAL_LIST_FIELDS:
        if not _string_list(invariant.get(field)):
            invalid.append(field)
    return sorted(invalid)


def _missing_negative_test_refs(invariant: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    negative_tests = invariant.get("negative_tests")
    if not isinstance(negative_tests, list):
        return ["negative_tests"]
    for raw_ref in negative_tests:
        ref = str(raw_ref)
        path_text, separator, node = ref.partition("::")
        path = REPO_ROOT / path_text
        if separator != "::" or not node.startswith("test_") or not path.is_file():
            missing.append(ref)
            continue
        source = path.read_text(encoding="utf-8")
        if f"def {node}" not in source and f"async def {node}" not in source:
            missing.append(ref)
    return missing


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _non_empty_string_list(value: Any) -> bool:
    return _string_list(value) and bool(value)


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(_non_empty_string(item) for item in value)
