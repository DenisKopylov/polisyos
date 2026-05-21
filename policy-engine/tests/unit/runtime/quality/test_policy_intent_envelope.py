from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import pytest

from polisyos.runtime.quality.assurance_case import (
    POLICY_INTENT_ENVELOPE_SCHEMA_VERSION,
    PolicyDesignCaseAuthorityError,
    build_policy_design_case_profile,
    build_policy_intent_envelope,
    validate_policy_intent_envelope,
)
from tests._helpers.hds_quality import (
    blocking_codes,
    policy_design_capability_ledger,
    scorecard_for,
    sha,
)


def test_policy_intent_envelope_separates_requester_preference_from_independent_analysis() -> None:
    envelope = build_policy_intent_envelope(
        intent_id="intent-R-policy-design",
        run_id="R_policy_design",
        job_id="job-policy-design",
        tenant_id="tenant-1",
        policy_problem="Wartime MSMEs face liquidity constraints.",
        desired_outcome="msme survival",
        proposed_intervention="targeted credit support",
        jurisdiction="UA",
        target_population="wartime MSMEs",
        policy_time="2026-05-15",
        data_time="2024-2026",
        requester_preferred_conclusion="expand credit support",
        requested_authority_level="production",
        authoring_provenance={
            "submitted_by": "policy-operator",
            "source_surface": "runtime.control.nl_request",
        },
        generated_at=datetime(2026, 5, 17, 8, 30, tzinfo=UTC),
    )

    assert envelope["schema_version"] == POLICY_INTENT_ENVELOPE_SCHEMA_VERSION
    assert envelope["requester_preferred_conclusion"] == "expand credit support"
    assert envelope["requester_preference"]["preferred_conclusion"] == (
        "expand credit support"
    )
    assert envelope["analysis_independence"]["independent_analysis_required"] is True
    assert (
        envelope["analysis_independence"][
            "requester_preference_may_not_determine_conclusion"
        ]
        is True
    )
    assert envelope["requester_capture_risk"]["preferred_conclusion_present"] is True
    assert envelope["requester_capture_risk"]["risk_level"] == "high"
    assert envelope["challenge_depth_policy"]["depth"] == "heightened"
    assert envelope["challenge_depth_policy"]["minimum_alternative_count"] >= 2
    assert envelope["challenge_depth_policy"]["requires_disconfirming_evidence"] is True


@pytest.mark.parametrize(
    ("field_name", "expected_code"),
    [
        ("jurisdiction", "policy_intent_jurisdiction_missing"),
        ("target_population", "policy_intent_target_population_missing"),
        ("policy_time", "policy_intent_policy_time_missing"),
        ("data_time", "policy_intent_data_time_missing"),
        ("desired_outcome", "policy_intent_desired_outcome_missing"),
        (
            "requester_preferred_conclusion",
            "policy_intent_requester_preferred_conclusion_missing",
        ),
    ],
)
def test_policy_intent_envelope_rejects_missing_required_capture_fields(
    field_name: str,
    expected_code: str,
) -> None:
    payload = _valid_intent_payload()
    payload.pop(field_name)

    with pytest.raises(PolicyDesignCaseAuthorityError, match=expected_code):
        validate_policy_intent_envelope(payload)


def test_policy_design_case_profile_requires_valid_intent_envelope() -> None:
    intent = _valid_intent_payload()
    intent.pop("data_time")

    with pytest.raises(PolicyDesignCaseAuthorityError, match="policy_intent_data_time_missing"):
        build_policy_design_case_profile(
            case_id="pdc-R-policy-design",
            run_id="R_policy_design",
            job_id="job-policy-design",
            tenant_id="tenant-1",
            effective_execution_profile="production",
            runtime_authority=_runtime_authority(),
            intent_envelope=intent,
        )


def test_serious_scorecard_blocks_invalid_policy_intent_envelope() -> None:
    case = build_policy_design_case_profile(
        case_id="pdc-R_hds_red_control",
        run_id="R_hds_red_control",
        job_id="job-hds-red-control",
        tenant_id="tenant-1",
        effective_execution_profile="production",
        runtime_authority=_runtime_authority(),
        intent_envelope=_valid_intent_payload(
            run_id="R_hds_red_control",
            job_id="job-hds-red-control",
        ),
        capability_ledger=policy_design_capability_ledger(),
    )
    broken_case = deepcopy(case)
    broken_intent = dict(broken_case["intent_envelope"])
    broken_intent.pop("jurisdiction")
    broken_case["intent_envelope"] = broken_intent

    scorecard = scorecard_for(
        quality_evidence={"policy_design_case": broken_case},
        normalize=False,
    )

    assert "policy_intent_jurisdiction_missing" in blocking_codes(scorecard)


def _valid_intent_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": POLICY_INTENT_ENVELOPE_SCHEMA_VERSION,
        "intent_id": "intent-R-policy-design",
        "run_id": "R_policy_design",
        "job_id": "job-policy-design",
        "tenant_id": "tenant-1",
        "policy_problem": "Wartime MSMEs face liquidity constraints.",
        "desired_outcome": "msme survival",
        "proposed_intervention": "targeted credit support",
        "jurisdiction": "UA",
        "target_population": "wartime MSMEs",
        "policy_time": "2026-05-15",
        "data_time": "2024-2026",
        "requester_preferred_conclusion": "expand credit support",
        "requested_authority_level": "production",
        "affected_stakeholders": ["MSMEs", "lenders", "workers"],
        "constraints": ["wartime fiscal limits"],
        "objectives": ["increase survival", "bound fiscal risk"],
        "assumptions": ["credit access affects short-term survival"],
        "evidence_expectations": ["legal", "production_data", "literature", "method"],
        "authoring_provenance": {
            "submitted_by": "policy-operator",
            "source_surface": "runtime.control.nl_request",
        },
    }
    payload.update(overrides)
    return payload


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
