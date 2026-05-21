from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy
from datetime import UTC, datetime

import pytest

from polisyos.runtime.quality.assurance_case import (
    ASSURANCE_CASE_REQUIRED_FIELDS,
    POLICY_DESIGN_CASE_CORE_NODE_TYPES,
    POLICY_DESIGN_CASE_PROFILE_METADATA,
    POLICY_DESIGN_CASE_RESERVED_NODE_FAMILIES,
    POLICY_DESIGN_WALKING_SKELETON_CONTRACT_ID,
    PolicyDesignCaseAuthorityError,
    build_assurance_case_for_scorecard,
    build_policy_design_case_profile,
    build_policy_design_case_walking_skeleton,
    build_policy_intent_envelope,
    validate_capability_selection_ledger,
    validate_policy_design_case_profile,
)
from tests._helpers.hds_quality import blocking_codes, complete_quality_evidence, scorecard_for


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _runtime_authority() -> dict[str, object]:
    return {
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "cas_ref": _sha("1"),
        "runtime_event_ref": "evt-runtime-quality-case",
        "same_input_closure_ref": _sha("3"),
        "effective_mode_ref": _sha("e"),
        "schema_compatibility_ref": _sha("c"),
    }


def _capability_duty(
    capability: str,
    state: str = "selected",
    **overrides: object,
) -> dict[str, object]:
    duty: dict[str, object] = {
        "capability": capability,
        "state": state,
        "owner": f"team-{capability}",
        "evidence_ref": _sha(capability[0]),
        "runtime_event_ref": f"evt-{capability}",
        "required": True,
    }
    duty.update(overrides)
    return duty


def _capability_ledger(*duties: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.capability_ledger.v1",
        "ledger_ref": _sha("5"),
        "literature_evidence_required": True,
        "duties": list(duties),
    }


def _intent_envelope() -> dict[str, object]:
    return build_policy_intent_envelope(
        intent_id="intent-run-1",
        run_id="run-1",
        job_id="job-1",
        tenant_id="tenant-1",
        policy_problem="Wartime MSME credit access is constrained.",
        desired_outcome="Improve MSME survival.",
        proposed_intervention="Target wartime credit support to eligible MSMEs.",
        jurisdiction="UA",
        target_population="wartime MSMEs",
        policy_time="2026-05-15",
        data_time="2024-2026",
        requester_preferred_conclusion="expand credit support",
        requested_authority_level="production",
        authoring_provenance={"captured_by": "test", "capture_ref": _sha("4")},
    )


def _all_capability_duties() -> list[dict[str, object]]:
    return [
        _capability_duty("lex"),
        _capability_duty("fabric"),
        _capability_duty("scholar"),
        _capability_duty("foundry"),
        _capability_duty("scientist"),
        _capability_duty("compiler"),
        _capability_duty("review"),
        _capability_duty("publication"),
        _capability_duty("audit"),
    ]


def _policy_design_case(
    *,
    capability_ledger: dict[str, object] | None = None,
    effective_execution_profile: str = "production",
) -> dict[str, object]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.v1",
        "profile": "policy_design",
        "case_id": "pdc-run-1",
        "run_id": "run-1",
        "job_id": "job-1",
        "tenant_id": "tenant-1",
        "effective_execution_profile": effective_execution_profile,
        "owner": "team-runtime-quality",
        "runtime_authority": _runtime_authority(),
        "intent_envelope": _intent_envelope(),
        "capability_ledger": capability_ledger
        or _capability_ledger(*_all_capability_duties()),
    }


def test_assurance_case_explains_serious_scorecard_with_required_fields() -> None:
    scorecard = scorecard_for()

    assurance_case = build_assurance_case_for_scorecard(
        scorecard,
        owner="team-assurance",
        reviewer_attribution={
            "reviewer_id": "runtime-quality-reviewer",
            "reviewed_at": "2026-05-15T08:45:00+00:00",
        },
        now=datetime(2026, 5, 15, 8, 45, tzinfo=UTC),
    )

    assert set(assurance_case) >= ASSURANCE_CASE_REQUIRED_FIELDS
    assert assurance_case["claim"]["run_id"] == "R_hds_red_control"
    assert assurance_case["claim"]["canary_kind"] == "production"
    assert assurance_case["argument_strategy"] == "runtime_authority_graph"
    assert assurance_case["owner"] == "team-assurance"
    assert assurance_case["reviewer_attribution"]["reviewer_id"] == (
        "runtime-quality-reviewer"
    )
    assert assurance_case["evidence"]
    assert isinstance(assurance_case["next_diagnostic_command"], str)
    assert assurance_case["next_diagnostic_command"].startswith("uv run ")


def test_assurance_case_preserves_non_overridable_blockers_and_uncertainty() -> None:
    scorecard = scorecard_for()
    scorecard["blocking_quality_failures"] = [
        {
            "code": "diagnostic_slo_error_budget_burned",
            "message": "False-pass controls burned budget.",
            "evidence_ref": "quality_evidence/diagnostic_slo_report.json",
            "next_action": "Run SLO diagnostics.",
        }
    ]
    scorecard["quality_status"] = "fail"

    assurance_case = build_assurance_case_for_scorecard(
        scorecard,
        owner="team-assurance",
        now=datetime(2026, 5, 15, 8, 45, tzinfo=UTC),
    )

    assert assurance_case["claim"]["status"] == "blocked"
    assert assurance_case["non_overridable_blockers"] == [
        "diagnostic_slo_error_budget_burned"
    ]
    assert assurance_case["blockers"][0]["code"] == "diagnostic_slo_error_budget_burned"
    assert assurance_case["unresolved_uncertainty"]
    assert assurance_case["confidence_limits"]["upper_bound"] < 1.0


def test_serious_scorecard_requires_assurance_case_evidence() -> None:
    evidence = complete_quality_evidence()
    evidence.pop("assurance_case", None)

    scorecard = scorecard_for(quality_evidence=evidence)

    assert "assurance_case_missing" in blocking_codes(scorecard)


def test_policy_design_case_profile_metadata_is_runtime_quality_owned() -> None:
    expected_core_nodes = {
        "policy_intent",
        "capability_duty",
        "concept_spine",
        "jurisdiction_spine",
        "producer_evidence",
        "portfolio",
        "claim",
        "argument",
        "warrant",
        "rebuttal",
        "counter_evidence",
        "deficit",
    }
    expected_reserved_families = {
        "oversight_effectiveness",
        "lifecycle_event",
        "audit_attestation",
        "publication_trust",
        "run_cost_proportionality",
        "ex_post_outcome",
        "calibration",
        "formal_invariant",
    }

    assert POLICY_DESIGN_CASE_PROFILE_METADATA["profile"] == "policy_design"
    assert POLICY_DESIGN_CASE_PROFILE_METADATA["owner"] == "team-runtime-quality"
    assert POLICY_DESIGN_CASE_PROFILE_METADATA["extends_schema_version"] == (
        "policyos.runtime.assurance_case.v1"
    )
    assert set(POLICY_DESIGN_CASE_CORE_NODE_TYPES) == expected_core_nodes
    assert set(POLICY_DESIGN_CASE_RESERVED_NODE_FAMILIES) == expected_reserved_families
    assert set(POLICY_DESIGN_CASE_PROFILE_METADATA["core_node_types"]) == expected_core_nodes
    assert (
        set(POLICY_DESIGN_CASE_PROFILE_METADATA["reserved_node_families"])
        == expected_reserved_families
    )
    assert (
        POLICY_DESIGN_CASE_PROFILE_METADATA["mapping"]["counter_evidence"]
        == "CAE.defeater"
    )


def test_policy_design_case_profile_requires_runtime_quality_authority_chain() -> None:
    case = build_policy_design_case_profile(
        case_id="pdc-run-1",
        run_id="run-1",
        job_id="job-1",
        tenant_id="tenant-1",
        effective_execution_profile="production",
        intent_envelope=_intent_envelope(),
        capability_ledger=_capability_ledger(*_all_capability_duties()),
        runtime_authority={
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_emitted",
            "cas_ref": "sha256:" + "a" * 64,
            "runtime_event_ref": "evt-runtime-quality-case",
            "same_input_closure_ref": "sha256:" + "b" * 64,
            "effective_mode_ref": "sha256:" + "c" * 64,
            "schema_compatibility_ref": "sha256:" + "d" * 64,
        },
    )

    validated = validate_policy_design_case_profile(case)

    assert validated["profile"] == "policy_design"
    assert validated["owner"] == "team-runtime-quality"
    assert validated["authority_chain"]["runtime_quality_authority"] is True
    assert validated["core_node_types"] == list(POLICY_DESIGN_CASE_CORE_NODE_TYPES)
    assert validated["reserved_node_families"] == list(
        POLICY_DESIGN_CASE_RESERVED_NODE_FAMILIES
    )


def test_policy_design_case_walking_skeleton_carries_intent_to_claim_refs() -> None:
    case = build_policy_design_case_walking_skeleton(
        generated_at=datetime(2026, 5, 17, 8, 30, tzinfo=UTC),
    )

    validated = validate_policy_design_case_profile(case)

    contract = validated["walking_skeleton_contract"]
    assert contract["contract_id"] == POLICY_DESIGN_WALKING_SKELETON_CONTRACT_ID
    assert contract["non_production"] is True
    assert validated["effective_execution_profile"] == "research"

    nodes = {str(node["node_type"]): node for node in validated["nodes"]}
    assert set(nodes) >= {
        "policy_intent",
        "concept_spine",
        "producer_evidence",
        "claim",
        "deficit",
    }
    for node in nodes.values():
        envelope = node["runtime_authority_envelope"]
        assert envelope["authority_role"] == "producer_authority"
        assert envelope["provenance_kind"] == "runtime_emitted"
        assert node["cas_ref"].startswith("cas://sha256/")
        assert node["runtime_event_ref"].startswith("event://")
        assert node["diagnostic_event_ref"] == node["runtime_event_ref"]
        assert node["schema_compatibility_ref"].startswith("cas://sha256/")
        assert node["effective_mode_ref"].startswith("cas://sha256/")
        assert node["same_input_closure_ref"].startswith("cas://sha256/")

    intent = nodes["policy_intent"]
    concept = nodes["concept_spine"]
    producer = nodes["producer_evidence"]
    claim = nodes["claim"]
    deficit = nodes["deficit"]

    assert concept["intent_ref"] == intent["cas_ref"]
    assert producer["intent_ref"] == intent["cas_ref"]
    assert producer["concept_ref"] == concept["concept_ref"]
    assert producer["jurisdiction_ref"] == concept["jurisdiction_ref"]
    assert producer["stub_record"] is True
    assert claim["major"] is True
    assert producer["cas_ref"] in claim["producer_evidence_refs"]
    assert concept["concept_ref"] in claim["concept_refs"]
    assert concept["jurisdiction_ref"] in claim["jurisdiction_refs"]
    assert claim["accepted_deficit_refs"] == [deficit["cas_ref"]]
    assert deficit["deficit_kind"] == "single_line_evidence_deficit"
    assert deficit["status"] == "accepted"


@pytest.mark.parametrize("profile", ["governed", "production"])
def test_policy_design_case_walking_skeleton_single_line_deficit_is_research_only(
    profile: str,
) -> None:
    with pytest.raises(
        PolicyDesignCaseAuthorityError,
        match="policy_design_skeleton_single_line_deficit_not_allowed",
    ):
        build_policy_design_case_walking_skeleton(
            requested_authority_level=profile,
            effective_execution_profile=profile,
        )


@pytest.mark.parametrize(
    ("node_patch", "envelope_patch", "expected_code"),
    [
        (
            {},
            {
                "provenance_kind": "static_inventory",
                "static_inventory_ref": "repo://architecture/policy_design_case.yml",
            },
            "policy_design_skeleton_static_inventory_not_authority",
        ),
        (
            {"cas_ref": "/opt/policyos/walking-skeleton.json"},
            {"cas_ref": "/opt/policyos/walking-skeleton.json"},
            "policy_design_skeleton_local_ref_not_authority",
        ),
        (
            {},
            {"source_surface": "public_export"},
            "policy_design_skeleton_public_export_not_authority",
        ),
        (
            {},
            {"source_surface": "dashboard_state"},
            "policy_design_skeleton_dashboard_state_not_authority",
        ),
        (
            {"cas_ref": "quality_evidence/policy_design_case.json"},
            {"cas_ref": "quality_evidence/policy_design_case.json"},
            "policy_design_skeleton_bundle_local_ref_not_authority",
        ),
    ],
)
def test_policy_design_case_walking_skeleton_rejects_non_runtime_authority_surfaces(
    node_patch: dict[str, object],
    envelope_patch: dict[str, object],
    expected_code: str,
) -> None:
    case = build_policy_design_case_walking_skeleton()
    mutated = deepcopy(case)
    producer = next(
        node for node in mutated["nodes"] if node["node_type"] == "producer_evidence"
    )
    producer.update(node_patch)
    producer["runtime_authority_envelope"].update(envelope_patch)

    with pytest.raises(PolicyDesignCaseAuthorityError, match=expected_code):
        validate_policy_design_case_profile(mutated)


def test_policy_design_case_capability_ledger_rejects_silent_skips() -> None:
    duties = _all_capability_duties()
    duties[2] = _capability_duty(
        "scholar",
        "skipped",
        evidence_ref=None,
        runtime_event_ref=None,
    )
    case = _policy_design_case(capability_ledger=_capability_ledger(*duties))

    with pytest.raises(
        PolicyDesignCaseAuthorityError,
        match="policy_design_capability_silent_skip_blocked",
    ):
        validate_policy_design_case_profile(case)


def test_policy_design_case_capability_skip_with_blocker_blocks_closeout() -> None:
    duties = _all_capability_duties()
    duties[0] = _capability_duty(
        "lex",
        "skipped",
        evidence_ref=None,
        runtime_event_ref=None,
        blocker_ref=_sha("b"),
    )
    case = _policy_design_case(capability_ledger=_capability_ledger(*duties))

    with pytest.raises(
        PolicyDesignCaseAuthorityError,
        match="policy_design_capability_duty_blocked",
    ):
        validate_policy_design_case_profile(case)


def test_policy_design_capability_ledger_rejects_wrong_schema_version() -> None:
    ledger = _capability_ledger(*_all_capability_duties())
    ledger["schema_version"] = "policyos.runtime.policy_design_case.capability_ledger.v0"

    with pytest.raises(
        PolicyDesignCaseAuthorityError,
        match="policy_design_capability_ledger_schema_version_invalid",
    ):
        validate_capability_selection_ledger(
            ledger,
            effective_execution_profile="production",
        )


def test_scorecard_blocks_when_scholar_is_omitted_from_literature_required_ledger() -> None:
    duties = [
        duty
        for duty in _all_capability_duties()
        if duty["capability"] != "scholar"
    ]
    case = _policy_design_case(capability_ledger=_capability_ledger(*duties))
    evidence = complete_quality_evidence()
    evidence["policy_design_case"] = case

    scorecard = scorecard_for(quality_evidence=evidence)

    assert "policy_design_scholar_literature_duty_missing" in blocking_codes(scorecard)


@pytest.mark.parametrize(
    ("authority_patch", "expected_code"),
    [
        (
            {"authority_role": "projection_only"},
            "policy_design_case_authority_role_invalid",
        ),
        (
            {"provenance_kind": "fixture_input"},
            "policy_design_case_provenance_invalid",
        ),
        (
            {"runtime_event_ref": ""},
            "policy_design_case_runtime_event_ref_missing",
        ),
    ],
)
def test_policy_design_case_profile_rejects_cases_outside_runtime_quality_authority_chain(
    authority_patch: dict[str, object],
    expected_code: str,
) -> None:
    runtime_authority = {
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "cas_ref": "sha256:" + "a" * 64,
        "runtime_event_ref": "evt-runtime-quality-case",
        "same_input_closure_ref": "sha256:" + "b" * 64,
        "effective_mode_ref": "sha256:" + "c" * 64,
        "schema_compatibility_ref": "sha256:" + "d" * 64,
    }
    runtime_authority.update(authority_patch)

    with pytest.raises(PolicyDesignCaseAuthorityError, match=expected_code):
        build_policy_design_case_profile(
            case_id="pdc-run-1",
            run_id="run-1",
            job_id="job-1",
            tenant_id="tenant-1",
            effective_execution_profile="production",
            runtime_authority=runtime_authority,
        )
