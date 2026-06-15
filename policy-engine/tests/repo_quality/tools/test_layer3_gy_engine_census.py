from __future__ import annotations

import copy
import json
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
CENSUS_PATH = (
    REPO_ROOT
    / "architecture"
    / "policy_design_case"
    / "layer3_gy_task0_audit"
    / "layer3_gy_engine_census.json"
)


def _validator() -> Any:
    return import_module("tools.quality.validation.check_layer3_gy_engine_census")


def _load_census() -> dict[str, Any]:
    return json.loads(CENSUS_PATH.read_text(encoding="utf-8"))


def _codes(violations: list[dict[str, Any]]) -> set[str]:
    return {str(v["code"]) for v in violations}


def _first_row_with(census: dict[str, Any], **criteria: str) -> dict[str, Any]:
    for row in census["rows"]:
        if all(row.get(key) == value for key, value in criteria.items()):
            return row
    raise AssertionError(f"no row matched {criteria}")


def _refresh_digest(census: dict[str, Any]) -> None:
    validator = _validator()
    census["row_count"] = len(census["rows"])
    census["census_digest"] = validator._canonical_rows_digest(census["rows"])


def test_gy_census_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_census()) == []


def test_gy_census_validator_rejects_non_sha_execution_hash() -> None:
    validator = _validator()
    census = _load_census()
    row = _first_row_with(census, execution_status="runs_e2e_on_real")
    row["execution_evidence"]["output_hash"] = "n/a"
    _refresh_digest(census)

    assert "bad_output_hash" in _codes(validator.validate(census))


def test_gy_census_validator_rejects_connector_without_probe_hash() -> None:
    validator = _validator()
    census = _load_census()
    row = _first_row_with(census, execution_status="not_exercised_network")
    row["execution_evidence"]["output_hash"] = "n/a"
    _refresh_digest(census)

    assert "bad_output_hash" in _codes(validator.validate(census))


def test_gy_census_validator_rejects_blocked_upstream_without_blocker() -> None:
    validator = _validator()
    census = _load_census()
    row = _first_row_with(census, gap_class="blocked_upstream")
    row.pop("blocked_by", None)
    row["notes"] = "Never invoked because an upstream node failed."
    _refresh_digest(census)

    assert "blocked_upstream_without_blocker" in _codes(validator.validate(census))


def test_gy_census_validator_rejects_tools_only_wired_and_works_claim() -> None:
    validator = _validator()
    census = _load_census()
    source = _first_row_with(census, execution_status="runs_e2e_on_real")
    row = copy.deepcopy(source)
    row["asset_id"] = "test.tools_only.claim"
    row["gap_class"] = "wired_and_works"
    row["recommended_gy_action"] = "none"
    row["reachability"] = {"imported_by": ["test.py:1"], "called_from_production": "tools-only"}
    row["output_destination"] = "dropped (direct smoke)"
    census["rows"].append(row)
    _refresh_digest(census)

    codes = _codes(validator.validate(census))
    assert "wired_and_works_not_production" in codes
    assert "wired_and_works_no_consumer" in codes


def test_gy_census_validator_rejects_stale_row_count_and_digest() -> None:
    validator = _validator()
    census = _load_census()
    census["row_count"] = len(census["rows"]) - 1
    census["census_digest"] = "sha256:" + "0" * 64

    codes = _codes(validator.validate(census))
    assert "row_count_mismatch" in codes
    assert "census_digest_mismatch" in codes
