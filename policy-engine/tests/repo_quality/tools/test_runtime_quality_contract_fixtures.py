# ruff: noqa: S101

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "runtime_quality"

CONTRACT_DIRS = {
    "authority_envelopes": "runtime_quality.evidence_authority_envelope.v1",
    "diagnostic_events": "runtime_quality.diagnostic_event.v1",
    "effective_mode": "runtime_quality.effective_mode_ledger.v1",
    "degradation_ledgers": "runtime_quality.degradation_ledger.v1",
    "invariant_registry": "runtime_quality.invariant_registry_entry.v1",
}

STATUS_TOKENS = frozenset({"pass", "rejected", "quarantined"})
NEGATIVE_STATUSES = frozenset({"rejected", "quarantined"})

REQUIRED_FIXTURES = {
    "authority_envelopes": {
        "serious_runtime_emitted_pass.json",
        "bundle_overlay_rejected.json",
        "legacy_unknown_schema_quarantined.json",
    },
    "diagnostic_events": {
        "runtime_producer_event_pass.json",
        "bundle_packaging_event_rejected.json",
        "legacy_unknown_event_schema_quarantined.json",
    },
    "effective_mode": {
        "production_live_mode_pass.json",
        "dev_profile_leakage_rejected.json",
        "fixture_overlay_quarantined.json",
    },
    "degradation_ledgers": {
        "declared_allowed_fallback_pass.json",
        "silent_generated_substitute_rejected.json",
        "legacy_fallback_record_quarantined.json",
    },
    "invariant_registry": {
        "runtime_authority_invariant_pass.json",
        "projection_owner_rejected.json",
        "legacy_unknown_schema_quarantined.json",
    },
}


def _fixture_status(path: Path) -> str:
    for status in STATUS_TOKENS:
        if path.stem.endswith(f"_{status}"):
            return status
    raise AssertionError(
        f"{path.relative_to(REPO_ROOT)} must end with one of: "
        f"{sorted(STATUS_TOKENS)}"
    )


def _read_fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{path.relative_to(REPO_ROOT)} must be a JSON object"
    return payload


def test_phase_02_runtime_quality_contract_fixtures_are_frozen() -> None:
    assert FIXTURE_ROOT.is_dir()

    for dir_name, contract_name in CONTRACT_DIRS.items():
        fixture_dir = FIXTURE_ROOT / dir_name
        assert fixture_dir.is_dir(), (
            f"missing fixture directory: {fixture_dir.relative_to(REPO_ROOT)}"
        )

        fixture_paths = sorted(fixture_dir.glob("*.json"))
        assert {path.name for path in fixture_paths} >= REQUIRED_FIXTURES[dir_name]

        seen_statuses: set[str] = set()
        seen_ids: set[str] = set()
        for path in fixture_paths:
            status_from_name = _fixture_status(path)
            payload = _read_fixture(path)
            seen_statuses.add(status_from_name)
            seen_ids.add(str(payload.get("fixture_id")))

            assert payload["fixture_id"] == path.stem
            assert payload["contract_name"] == contract_name
            assert payload["expected_status"] == status_from_name
            assert isinstance(payload["hds_invariants"], list)
            assert payload["hds_invariants"]
            assert isinstance(payload["payload"], dict)

            if status_from_name == "pass":
                assert payload["expected_failure_code"] is None
            else:
                assert isinstance(payload["expected_failure_code"], str)
                assert payload["expected_failure_code"]

        assert "pass" in seen_statuses
        assert seen_statuses & NEGATIVE_STATUSES
        assert len(seen_ids) == len(fixture_paths)
