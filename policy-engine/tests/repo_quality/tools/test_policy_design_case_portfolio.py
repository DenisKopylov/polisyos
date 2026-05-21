# ruff: noqa: S101
"""Compatibility entrypoint for the archived portfolio validation loop."""

from __future__ import annotations

from tests.repo_quality.tools.test_policy_design_case_contract_fixtures import (
    CONTRACTS,
    FIXTURE_ROOT,
    _read_fixture,
)


def test_policy_design_case_portfolio_contract_fixtures_bind_runtime_authority() -> None:
    contract = CONTRACTS["portfolio_synthesis_contract"]
    fixture_dir = FIXTURE_ROOT / "portfolio_synthesis_contract"

    assert fixture_dir.is_dir()
    assert {path.name for path in fixture_dir.glob("*.json")} >= contract["fixtures"]

    for path in sorted(fixture_dir.glob("*.json")):
        fixture = _read_fixture(path)
        envelope = fixture["runtime_authority_envelope"]

        assert fixture["contract_name"] == contract["contract_name"]
        assert set(fixture["sdd_record_families"]) <= contract["families"]
        assert set(fixture["sdd_record_families"]) & contract["families"]
        if fixture["expected_status"] == "pass":
            assert envelope["authority_role"] == "producer_authority"
            assert envelope["provenance_kind"] == "runtime_emitted"
            assert envelope["validation_status"] == "pass"
            assert envelope["cas_ref"].startswith("cas://sha256/")
        else:
            assert fixture["expected_failure_code"]
            assert envelope["authority_role"] == "not_authoritative"
            assert envelope["provenance_kind"] == "static_inventory"
            assert envelope["validation_status"] in {"blocked", "fail"}
            assert envelope["cas_ref"] is None
