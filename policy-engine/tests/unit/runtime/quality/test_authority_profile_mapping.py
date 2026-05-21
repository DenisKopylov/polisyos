from __future__ import annotations

# ruff: noqa: S101
import pytest

from polisyos.core.contracts.control import (
    POLICY_AUTHORITY_PROFILES,
    policy_authority_profile_mapping,
)
from polisyos.core.governance.profiles import validation_profile_for_execution_profile
from polisyos.runtime.quality.assurance_case import (
    POLICY_INTENT_ENVELOPE_SCHEMA_VERSION,
    PolicyDesignCaseAuthorityError,
    build_policy_design_case_profile,
)
from polisyos.runtime.quality.effective_mode import (
    EffectiveModeLedger,
    assert_serious_mode_allowed,
    mode_policy_failure_code,
)
from tests._helpers.hds_quality import policy_design_capability_ledger, sha


def test_policy_authority_profiles_reuse_control_governance_and_effective_mode() -> None:
    assert POLICY_AUTHORITY_PROFILES == ("research", "governed", "production")

    for profile in POLICY_AUTHORITY_PROFILES:
        mapping = policy_authority_profile_mapping(profile)
        validation_profile = validation_profile_for_execution_profile(profile)

        assert mapping.execution_profile == profile
        assert validation_profile.level.value == mapping.validation_profile

        ledger = _ledger_for(profile)

        assert mode_policy_failure_code(ledger) is None
        assert_serious_mode_allowed(ledger)


@pytest.mark.parametrize("profile", ["research", "governed", "production"])
def test_serious_closeout_rejects_validation_profile_below_authority(
    profile: str,
) -> None:
    weaker_validation = "fast" if profile == "research" else "mvp"

    ledger = _ledger_for(profile, validation_profile=weaker_validation)

    assert mode_policy_failure_code(ledger) == "mode_validation_profile_mismatch"


def test_serious_closeout_rejects_dev_smoke_fallback_policy_leakage() -> None:
    ledger = _ledger_for("production", fallback_policy="dev_smoke")

    assert mode_policy_failure_code(ledger) == "mode_fallback_policy_mismatch"


def test_serious_closeout_rejects_fixture_mode_even_with_valid_profile_closure() -> None:
    ledger = _ledger_for(
        "production",
        fixture_identity="tests/fixtures/runtime_quality/effective_mode.json",
        data_mode="fixture",
    )

    assert mode_policy_failure_code(ledger) == "mode_fixture_identity_not_allowed"


def test_policy_design_case_reconciles_requested_and_effective_authority_profiles() -> None:
    intent = _intent_envelope(requested_authority_level="production")

    with pytest.raises(
        PolicyDesignCaseAuthorityError,
        match="policy_design_case_authority_profile_mismatch",
    ):
        build_policy_design_case_profile(
            case_id="pdc-authority-profile-mismatch",
            run_id="R_authority_profile",
            job_id="job-authority-profile",
            tenant_id="tenant-1",
            effective_execution_profile="governed",
            runtime_authority=_runtime_authority(),
            intent_envelope=intent,
            capability_ledger=policy_design_capability_ledger(),
        )


def test_policy_intent_rejects_dev_authority_level_for_serious_profile() -> None:
    intent = _intent_envelope(requested_authority_level="dev")

    with pytest.raises(
        PolicyDesignCaseAuthorityError,
        match="policy_intent_requested_authority_level_invalid",
    ):
        build_policy_design_case_profile(
            case_id="pdc-authority-profile-dev",
            run_id="R_authority_profile",
            job_id="job-authority-profile",
            tenant_id="tenant-1",
            effective_execution_profile="production",
            runtime_authority=_runtime_authority(),
            intent_envelope=intent,
            capability_ledger=policy_design_capability_ledger(),
        )


def _ledger_for(
    profile: str,
    *,
    validation_profile: str | None = None,
    fallback_policy: str | None = None,
    **effective_overrides: object,
) -> EffectiveModeLedger:
    mapping = policy_authority_profile_mapping(profile)
    requested = {
        "execution_profile": mapping.execution_profile,
        "validation_profile": validation_profile or mapping.validation_profile,
        "fallback_policy": fallback_policy or mapping.fallback_policy,
        "canary_kind": "serious_runtime",
        "matrix_lane_id": f"{mapping.execution_profile}-closeout",
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
    effective = dict(requested)
    effective.update(effective_overrides)
    return EffectiveModeLedger.from_requested_effective(
        requested=requested,
        effective=effective,
    )


def _intent_envelope(*, requested_authority_level: str) -> dict[str, object]:
    return {
        "schema_version": POLICY_INTENT_ENVELOPE_SCHEMA_VERSION,
        "intent_id": "intent-authority-profile",
        "run_id": "R_authority_profile",
        "job_id": "job-authority-profile",
        "tenant_id": "tenant-1",
        "policy_problem": "Wartime MSMEs face liquidity constraints.",
        "desired_outcome": "msme survival",
        "proposed_intervention": "targeted credit support",
        "jurisdiction": "UA",
        "target_population": "wartime MSMEs",
        "policy_time": "2026-05-15",
        "data_time": "2024-2026",
        "requester_preferred_conclusion": "expand credit support",
        "requested_authority_level": requested_authority_level,
        "authoring_provenance": {
            "submitted_by": "policy-operator",
            "source_surface": "runtime.control.nl_request",
        },
    }


def _runtime_authority() -> dict[str, str]:
    return {
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "cas_ref": sha("1"),
        "runtime_event_ref": sha("2"),
        "same_input_closure_ref": sha("3"),
        "effective_mode_ref": sha("4"),
        "schema_compatibility_ref": sha("5"),
    }
