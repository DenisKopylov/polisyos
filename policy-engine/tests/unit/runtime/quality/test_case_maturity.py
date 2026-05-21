from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy

from polisyos.runtime.quality.case_maturity import (
    CASE_MATURITY_PROFILE_SCHEMA_VERSION,
    RECORD_FAMILY_MATURITY_LEVELS,
    build_case_maturity_profile,
    policy_design_case_maturity_scorecard_gates,
    validate_case_maturity_profile,
)
from polisyos.runtime.quality.policy_design_case import (
    POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES,
)
from tests.unit.runtime.quality.test_policy_design_case_false_passes import (
    _policy_design_case,
    _scorecard_blocking_codes_for_case,
    sha,
)

EXPECTED_MATURITY_LEVELS = (
    "missing",
    "stub",
    "partial",
    "argument_complete",
    "evidence_complete",
    "independently_challenged",
    "externally_auditable",
    "validated_ex_post",
)


def test_case_maturity_profile_covers_every_record_family_with_ordered_levels() -> None:
    profile = build_case_maturity_profile(
        record_id="case-maturity-rec-1",
        case_id="pdc-R_hds_red_control",
        run_id="R_hds_red_control",
        job_id="job-hds-red-control",
        tenant_id="tenant-prod",
        family_maturities=_complete_family_maturities(),
        evidence_ref=sha("1"),
        runtime_event_ref="event://policy-design-case/case-maturity/1",
    )

    result = validate_case_maturity_profile(profile)

    assert RECORD_FAMILY_MATURITY_LEVELS == EXPECTED_MATURITY_LEVELS
    assert profile["schema_version"] == CASE_MATURITY_PROFILE_SCHEMA_VERSION
    assert set(profile["maturity_levels"]) == set(EXPECTED_MATURITY_LEVELS)
    assert {
        row["family_id"] for row in profile["record_family_maturities"]
    } == set(POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES)
    assert result.status == "pass"
    assert result.as_dict()["summary"]["record_family_count"] == len(
        POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES
    )


def test_case_maturity_rejects_evidence_complete_without_evidence_refs() -> None:
    maturities = _complete_family_maturities()
    inflated = deepcopy(maturities["claim_argument_evidence_case.v1"])
    inflated["maturity"] = "evidence_complete"
    inflated["evidence_refs"] = []
    maturities["claim_argument_evidence_case.v1"] = inflated
    profile = build_case_maturity_profile(
        record_id="case-maturity-rec-1",
        case_id="pdc-R_hds_red_control",
        run_id="R_hds_red_control",
        job_id="job-hds-red-control",
        tenant_id="tenant-prod",
        family_maturities=maturities,
        evidence_ref=sha("1"),
        runtime_event_ref="event://policy-design-case/case-maturity/1",
    )

    result = validate_case_maturity_profile(profile)

    assert result.status == "fail"
    assert "policy_design_case_maturity_evidence_refs_missing" in _issue_codes(
        result.as_dict()
    )


def test_case_maturity_rejects_evidence_complete_with_non_runtime_evidence_refs() -> None:
    maturities = _complete_family_maturities()
    inflated = deepcopy(maturities["claim_argument_evidence_case.v1"])
    inflated["maturity"] = "evidence_complete"
    inflated["evidence_refs"] = ["decorative-evidence-id"]
    maturities["claim_argument_evidence_case.v1"] = inflated
    profile = build_case_maturity_profile(
        record_id="case-maturity-rec-1",
        case_id="pdc-R_hds_red_control",
        run_id="R_hds_red_control",
        job_id="job-hds-red-control",
        tenant_id="tenant-prod",
        family_maturities=maturities,
        evidence_ref=sha("1"),
        runtime_event_ref="event://policy-design-case/case-maturity/1",
    )

    result = validate_case_maturity_profile(profile)

    assert result.status == "fail"
    assert "policy_design_case_maturity_evidence_refs_invalid" in _issue_codes(
        result.as_dict()
    )


def test_scorecard_blocks_case_maturity_inflated_without_evidence() -> None:
    case = _policy_design_case()
    profile = deepcopy(case["case_maturity_profile"])
    row = next(
        row
        for row in profile["record_family_maturities"]
        if row["family_id"] == "claim_argument_evidence_case.v1"
    )
    row["maturity"] = "evidence_complete"
    row["evidence_refs"] = []
    case["case_maturity_profile"] = profile

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_case_maturity_evidence_refs_missing" in codes


def test_phase29_maturity_gates_reject_status_pass_without_record_families() -> None:
    case = {
        "status": "pass",
        "case_maturity_profile": build_case_maturity_profile(
            record_id="case-maturity-rec-1",
            case_id="pdc-R_hds_red_control",
            run_id="R_hds_red_control",
            job_id="job-hds-red-control",
            tenant_id="tenant-prod",
            family_maturities=_complete_family_maturities(),
            evidence_ref=sha("1"),
            runtime_event_ref="event://policy-design-case/case-maturity/1",
        ),
    }

    gates = policy_design_case_maturity_scorecard_gates(case)

    codes = {gate["code"] for gate in gates}
    assert {
        "policy_design_case_records_missing",
        "policy_design_case_record_families_missing",
    } <= codes
    assert {
        gate["phase"]
        for gate in gates
        if gate["code"]
        in {
            "policy_design_case_records_missing",
            "policy_design_case_record_families_missing",
        }
    } == {"policy_design_case_maturity_profile"}


def test_runtime_record_family_compiler_binds_case_maturity_profile() -> None:
    from polisyos.runtime.quality.policy_design_case import (
        compile_policy_design_case_runtime_record_families,
        validate_policy_design_case_record_family_coverage,
    )

    case = _policy_design_case()
    case.pop("records", None)
    case.pop("record_families", None)
    case["status"] = "pass"

    compiled = compile_policy_design_case_runtime_record_families(case)
    result = validate_policy_design_case_record_family_coverage(compiled)

    assert result.status == "pass"
    assert any(
        record["family_id"] == "integrity_self_fmea_and_maturity.v1"
        and "case_maturity_profile" in record.get("source_keys", [])
        for record in compiled["records"]
    )


def test_scorecard_blocks_case_maturity_inflated_with_decorative_evidence_ref() -> None:
    case = _policy_design_case()
    profile = deepcopy(case["case_maturity_profile"])
    row = next(
        row
        for row in profile["record_family_maturities"]
        if row["family_id"] == "claim_argument_evidence_case.v1"
    )
    row["maturity"] = "evidence_complete"
    row["evidence_refs"] = ["decorative-evidence-id"]
    case["case_maturity_profile"] = profile

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_case_maturity_evidence_refs_invalid" in codes


def _complete_family_maturities() -> dict[str, dict[str, object]]:
    return {
        family_id: {
            "maturity": "evidence_complete",
            "record_refs": [sha("1")],
            "argument_refs": [sha("2")],
            "evidence_refs": [sha("3")],
            "challenge_refs": [],
            "audit_refs": [],
            "ex_post_refs": [],
        }
        for family_id in POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES
    }


def _issue_codes(report: dict[str, object]) -> set[str]:
    return {
        str(issue["code"])
        for issue in report.get("issues", [])
        if isinstance(issue, dict)
    }
