from __future__ import annotations

from polisyos.lex.normpack.conflict_check import (
    build_policy_conflict_check_report,
    normalize_policy_conflict_check_report,
)


def test_conflict_check_passes_when_no_constraints_are_violated() -> None:
    report = build_policy_conflict_check_report(
        policy_claims=[
            {
                "claim_id": "rec_1",
                "action": "targeted_credit_support",
                "eligibility_tags": ["registered_msme", "active_tax_record"],
                "budget_usd": 750_000,
            }
        ],
        corpus_constraints=[
            {
                "constraint_id": "budget_cap_1",
                "constraint_type": "budget_rule",
                "norm_ref": "norm.ua.budget_cap",
                "max_budget_usd": 1_000_000,
            }
        ],
    )

    assert report["status"] == "pass"
    assert report["conflicts"] == []
    assert report["blocking_conflict_count"] == 0


def test_conflict_check_blocks_direct_prohibition_conflict() -> None:
    report = build_policy_conflict_check_report(
        policy_claims=[
            {
                "claim_id": "rec_direct",
                "text": "Launch an uncapped credit subsidy immediately.",
                "action": "uncapped_credit_subsidy",
            }
        ],
        corpus_constraints=[
            {
                "constraint_id": "no_uncapped_subsidy",
                "constraint_type": "direct_prohibition",
                "norm_ref": "norm.ua.subsidy_prohibition",
                "prohibited_actions": ["uncapped_credit_subsidy"],
                "severity": "critical",
            }
        ],
    )

    conflict = report["conflicts"][0]
    assert report["status"] == "fail"
    assert conflict["code"] == "direct_prohibition_conflict"
    assert conflict["severity"] == "critical"
    assert conflict["claim_text"] == "Launch an uncapped credit subsidy immediately."
    assert conflict["next_action"]


def test_conflict_check_flattens_active_norm_constraints() -> None:
    report = build_policy_conflict_check_report(
        policy_claims=[
            {
                "claim_id": "rec_direct",
                "text": "Launch an uncapped credit subsidy immediately.",
                "action": "uncapped_credit_subsidy",
                "norm_refs": ["norm.ua.active_subsidy_rules"],
            }
        ],
        corpus_constraints=[
            {
                "norm_id": "norm.ua.active_subsidy_rules",
                "fact_class": "subsidy_control_rule",
                "jurisdiction": "UA",
                "constraints": [
                    {
                        "constraint_id": "no_uncapped_subsidy",
                        "constraint_type": "direct_prohibition",
                        "prohibited_actions": ["uncapped_credit_subsidy"],
                        "severity": "critical",
                    }
                ],
            }
        ],
    )

    conflict = report["conflicts"][0]
    assert report["status"] == "fail"
    assert conflict["constraint_id"] == "no_uncapped_subsidy"
    assert conflict["norm_refs"] == ["norm.ua.active_subsidy_rules"]


def test_conflict_check_blocks_eligibility_mismatch() -> None:
    report = build_policy_conflict_check_report(
        policy_claims=[
            {
                "claim_id": "rec_eligibility",
                "action": "targeted_credit_support",
                "eligibility_tags": ["all_businesses"],
            }
        ],
        corpus_constraints=[
            {
                "constraint_id": "msme_only",
                "constraint_type": "eligibility_constraint",
                "norm_ref": "norm.ua.credit_eligibility",
                "allowed_eligibility_tags": ["registered_msme", "active_tax_record"],
                "severity": "high",
            }
        ],
    )

    issue_codes = {conflict["code"] for conflict in report["conflicts"]}
    assert report["status"] == "fail"
    assert "eligibility_mismatch" in issue_codes


def test_conflict_check_blocks_budget_rule_mismatch() -> None:
    report = build_policy_conflict_check_report(
        policy_claims=[
            {
                "claim_id": "rec_budget",
                "action": "targeted_credit_support",
                "budget_usd": 3_000_000,
            }
        ],
        corpus_constraints=[
            {
                "constraint_id": "budget_cap_1",
                "constraint_type": "budget_rule",
                "norm_ref": "norm.ua.budget_cap",
                "max_budget_usd": 1_000_000,
                "severity": "high",
            }
        ],
    )

    issue_codes = {conflict["code"] for conflict in report["conflicts"]}
    assert report["status"] == "fail"
    assert "budget_rule_mismatch" in issue_codes


def test_conflict_check_warns_for_reviewable_indirect_conflict() -> None:
    report = build_policy_conflict_check_report(
        policy_claims=[
            {
                "claim_id": "rec_review",
                "text": "Provide bridge credit guarantees through regional banks.",
                "action": "bridge_credit_guarantee",
                "norm_refs": ["norm.ua.state_aid_review"],
            }
        ],
        corpus_constraints=[
            {
                "constraint_id": "state_aid_review",
                "constraint_type": "indirect_policy_conflict",
                "norm_ref": "norm.ua.state_aid_review",
                "related_actions": ["bridge_credit_guarantee"],
                "severity": "medium",
                "message": "State-aid compatibility depends on operator review.",
            }
        ],
    )

    conflict = report["conflicts"][0]
    assert report["status"] == "warn"
    assert report["review_required"] is True
    assert report["operator_action_required"] is True
    assert conflict["code"] == "indirect_policy_conflict"
    assert conflict["classification"] == "indirect_reviewable_conflict"
    assert conflict["blocking"] is False
    assert conflict["requires_operator_action"] is True
    assert "operator" in conflict["next_action"].casefold()


def test_conflict_check_records_informational_overlap_without_quality_warning() -> None:
    report = build_policy_conflict_check_report(
        policy_claims=[
            {
                "claim_id": "rec_overlap",
                "text": "Publish monitoring metrics for wartime MSME credit support.",
                "action": "publish_monitoring_metrics",
                "norm_refs": ["norm.ua.reporting_guidance"],
            }
        ],
        corpus_constraints=[
            {
                "constraint_id": "reporting_guidance_overlap",
                "constraint_type": "informational_overlap",
                "norm_ref": "norm.ua.reporting_guidance",
                "related_actions": ["publish_monitoring_metrics"],
                "severity": "info",
            }
        ],
    )

    assert report["status"] == "pass"
    assert report["conflicts"] == []
    overlap = report["informational_overlaps"][0]
    assert overlap["code"] == "informational_overlap"
    assert overlap["classification"] == "informational_overlap"
    assert overlap["requires_operator_action"] is False


def test_conflict_check_classifies_equity_access_conflict_by_severity() -> None:
    report = build_policy_conflict_check_report(
        policy_claims=[
            {
                "claim_id": "rec_equity",
                "action": "targeted_credit_support",
                "equity_access_impact": {
                    "status": "fail",
                    "affected_groups": ["women_owned_msme"],
                },
            }
        ],
        corpus_constraints=[
            {
                "constraint_id": "equity_access_1",
                "constraint_type": "equity_access_requirement",
                "norm_ref": "norm.ua.equal_access",
                "protected_groups": ["women_owned_msme"],
                "severity": "medium",
            }
        ],
    )

    conflict = report["conflicts"][0]
    assert report["status"] == "warn"
    assert conflict["code"] == "equity_access_conflict"
    assert conflict["severity"] == "medium"
    assert conflict["blocking"] is False


def test_normalize_report_refuses_raw_pass_with_direct_conflict() -> None:
    normalized = normalize_policy_conflict_check_report(
        {
            "status": "pass",
            "conflicts": [
                {
                    "conflict_id": "c1",
                    "code": "direct_prohibition_conflict",
                    "conflict_type": "direct_prohibition",
                    "severity": "critical",
                    "claim_id": "rec_direct",
                    "norm_refs": ["norm.ua.subsidy_prohibition"],
                }
            ],
        }
    )

    assert normalized["status"] == "fail"
    assert normalized["conflicts"][0]["blocking"] is True
    assert normalized["blocking_conflict_count"] == 1
