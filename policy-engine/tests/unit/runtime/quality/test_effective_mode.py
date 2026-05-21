# ruff: noqa: S101

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.runtime.quality.effective_mode import (
    EFFECTIVE_MODE_FIELDS,
    EffectiveModeLedger,
    ModePolicyViolation,
    assert_serious_mode_allowed,
    explain_mode_mismatch,
    mode_policy_failure_code,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


def _serious_requested() -> dict[str, object]:
    return {
        "execution_profile": "production",
        "validation_profile": "strict",
        "fallback_policy": "serious_fallback_fail_closed",
        "canary_kind": "serious_runtime",
        "matrix_lane_id": "production-live",
        "provider_mode": "live",
        "llm_simulation_mode": "disabled",
        "fixture_identity": None,
        "mock_fallback_allowed": False,
        "mock_fallback_used": False,
        "data_mode": "production",
        "state_store_backend": "runtime_control_plane_postgres",
        "local_control_waiver": None,
        "scorecard_warn_policy": "fail_serious",
        "evidence_overlay_mode": "disabled",
        "signed_exception_ref": None,
        "quarantine_status": "none",
    }


def _serious_ledger(**effective_overrides: object) -> EffectiveModeLedger:
    requested = _serious_requested()
    effective = dict(requested)
    effective.update(effective_overrides)
    return EffectiveModeLedger.from_requested_effective(
        requested=requested,
        effective=effective,
    )


def test_effective_mode_ledger_records_requested_and_effective_dimensions() -> None:
    requested = _serious_requested()
    effective = dict(requested)
    effective.update(
        {
            "provider_mode": "simulated",
            "llm_simulation_mode": "enabled",
            "fixture_identity": "tests/fixtures/runtime_quality/effective_mode.json",
        }
    )

    ledger = EffectiveModeLedger.from_requested_effective(
        requested=requested,
        effective=effective,
    )

    assert tuple(ledger.requested_values()) == EFFECTIVE_MODE_FIELDS
    assert tuple(ledger.effective_values()) == EFFECTIVE_MODE_FIELDS
    assert ledger.requested_values()["provider_mode"] == "live"
    assert ledger.effective_values()["provider_mode"] == "simulated"
    assert ledger.mismatched_fields() == (
        "provider_mode",
        "llm_simulation_mode",
        "fixture_identity",
    )


def test_production_live_effective_mode_fixture_satisfies_serious_policy() -> None:
    payload_path = (
        REPO_ROOT
        / "tests/fixtures/runtime_quality/effective_mode/production_live_mode_pass.json"
    )
    fixture = json.loads(payload_path.read_text(encoding="utf-8"))
    ledger = EffectiveModeLedger.from_mapping(fixture["payload"])

    assert mode_policy_failure_code(ledger) is None
    assert_serious_mode_allowed(ledger)


@pytest.mark.parametrize(
    ("ledger", "expected_code"),
    [
        (
            _serious_ledger(
                execution_profile="dev",
                canary_kind="dev_smoke",
                matrix_lane_id="local-dev-smoke",
            ),
            "mode_profile_mismatch",
        ),
        (
            _serious_ledger(
                canary_kind="dev_smoke",
                matrix_lane_id="local-dev-smoke",
            ),
            "mode_profile_mismatch",
        ),
        (
            _serious_ledger(
                fixture_identity="tests/fixtures/runtime_quality/effective_mode.json",
            ),
            "mode_fixture_identity_not_allowed",
        ),
        (
            _serious_ledger(provider_mode="simulated", llm_simulation_mode="enabled"),
            "mode_simulated_provider_not_allowed",
        ),
        (
            _serious_ledger(scorecard_warn_policy="warn_allowed"),
            "mode_warn_policy_not_allowed",
        ),
    ],
)
def test_disallowed_modes_cannot_satisfy_serious_closeout(
    ledger: EffectiveModeLedger,
    expected_code: str,
) -> None:
    assert mode_policy_failure_code(ledger) == expected_code
    explanation = explain_mode_mismatch(ledger)
    assert expected_code in explanation

    with pytest.raises(ModePolicyViolation) as exc_info:
        assert_serious_mode_allowed(ledger)

    assert exc_info.value.code == expected_code


def test_non_production_non_closeout_lane_may_use_dev_smoke_modes() -> None:
    requested = {
        "execution_profile": "dev",
        "canary_kind": "dev_smoke",
        "matrix_lane_id": "local-dev-smoke",
        "provider_mode": "simulated",
        "llm_simulation_mode": "enabled",
        "fixture_identity": "tests/fixtures/runtime_quality/effective_mode.json",
        "mock_fallback_allowed": True,
        "mock_fallback_used": True,
        "data_mode": "fixture",
        "state_store_backend": "in_memory_fixture",
        "local_control_waiver": "local-dev-waiver",
        "scorecard_warn_policy": "warn_allowed",
        "evidence_overlay_mode": "fixture_overlay",
        "signed_exception_ref": None,
        "quarantine_status": "quarantined",
    }
    ledger = EffectiveModeLedger.from_requested_effective(
        requested=requested,
        effective=requested,
    )

    assert mode_policy_failure_code(ledger) is None
    assert_serious_mode_allowed(ledger)
