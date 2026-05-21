from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy
from typing import Any

from tests.unit.runtime.quality.test_policy_design_case_false_passes import (
    _policy_design_case,
    _scorecard_blocking_codes_for_case,
    sha,
)


def test_implementation_monitoring_record_wires_ddm_events_to_claims() -> None:
    from polisyos.runtime.quality.ddm_monitoring import (
        build_implementation_monitoring_evaluation_record,
        validate_implementation_monitoring_evaluation_record,
    )

    record = build_implementation_monitoring_evaluation_record(
        record_id="implementation-monitoring-rec-1",
        case_id="pdc-R_hds_red_control",
        claim_ids=["rec_1"],
        implementation_contract=_implementation_contract(),
        monitoring_plan=_monitoring_plan(),
        evaluation_design=_evaluation_design(),
        ddm_events=_ddm_events(),
        publication_authority_ref=sha("p"),
        created_before_publication_authority=True,
        evidence_ref=sha("1"),
        runtime_event_ref="event://policy-design-case/implementation-monitoring/1",
    )

    validated = validate_implementation_monitoring_evaluation_record(
        record,
        required_claim_ids=["rec_1"],
    )

    assert validated["publication_order"]["created_before_publication_authority"] is True
    assert validated["ddm_monitoring"]["shift_events"][0]["affected_claim_ids"] == ["rec_1"]
    assert validated["ddm_monitoring"]["degradation_events"][0]["affected_evidence_line_refs"] == [
        "line-data"
    ]
    assert validated["ddm_monitoring"]["readiness_events"][0]["downstream_status"] == (
        "publication_review_required"
    )
    assert validated["ddm_monitoring"]["incident_events"][0]["root_cause_event_ids"] == [
        "root-cause-1"
    ]


def test_scorecard_blocks_missing_ddm_evidence_when_monitoring_is_in_scope() -> None:
    case = _phase27_case()
    record = deepcopy(case["implementation_monitoring_evaluation"])
    record["ddm_monitoring"]["shift_events"] = []
    case["implementation_monitoring_evaluation"] = record

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_ddm_evidence_missing" in codes


def test_scorecard_blocks_stale_published_case_without_lifecycle_resolution() -> None:
    case = _phase27_case()
    lifecycle = deepcopy(case["case_lifecycle"])
    lifecycle["current_state"] = "stale"
    lifecycle["events"].append(
        {
            "event_id": "lifecycle-stale-unresolved",
            "event_type": "stale",
            "previous_state": "published",
            "new_state": "stale",
            "evidence_refs": [sha("1")],
            "runtime_event_ref": "event://policy-design-case/lifecycle/stale",
        }
    )
    lifecycle["resolution_event_refs"] = []
    case["case_lifecycle"] = lifecycle

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_published_case_stale" in codes


def test_scorecard_blocks_contaminated_ex_post_learning() -> None:
    case = _phase27_case()
    learning = deepcopy(case["ex_post_learning"])
    learning["memory_contamination_check"] = {
        "status": "contaminated",
        "policy": {"hidden_ref_ids": ["hidden_eval_42"]},
        "findings": [
            {
                "token_kind": "hidden_eval",
                "token": "hidden_eval_42",
                "severity": "block",
                "message": "hidden eval id appeared in reusable learning",
            }
        ],
        "evidence_ref": sha("2"),
        "runtime_event_ref": "event://policy-design-case/ex-post/contamination",
    }
    learning["learning_records"][0]["scope"] = "hidden_eval_42 leakage"
    case["ex_post_learning"] = learning

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_learning_contamination_detected" in codes


def _phase27_case() -> dict[str, Any]:
    case = _policy_design_case()
    case["implementation_monitoring_evaluation"] = _implementation_monitoring_record()
    case["case_lifecycle"] = _case_lifecycle_record()
    case["ex_post_learning"] = _ex_post_learning_record()
    case["final_major_claims"][0]["prediction_refs"] = ["prediction-rec-1"]
    case["final_major_claims"][0]["observed_outcome_refs"] = ["outcome-link-rec-1"]
    case["final_major_claims"][0]["reassessment_refs"] = ["reassessment-rec-1"]
    case["final_major_claims"][0]["future_prior_refs"] = ["future-prior-rec-1"]
    return case


def _implementation_monitoring_record() -> dict[str, Any]:
    return {
        "schema_version": (
            "policyos.runtime.policy_design_case."
            "implementation_monitoring_evaluation.v1"
        ),
        "record_id": "implementation-monitoring-rec-1",
        "case_id": "pdc-R_hds_red_control",
        "claim_ids": ["rec_1"],
        "implementation_contract": _implementation_contract(),
        "monitoring_plan": _monitoring_plan(),
        "evaluation_design": _evaluation_design(),
        "publication_order": {
            "publication_authority_ref": sha("p"),
            "created_before_publication_authority": True,
        },
        "ddm_monitoring": _ddm_events(),
        "evidence_ref": sha("1"),
        "runtime_event_ref": "event://policy-design-case/implementation-monitoring/1",
    }


def _implementation_contract() -> dict[str, Any]:
    return {
        "contract_id": "implementation-contract-rec-1",
        "intervention_ref": "option-targeted-credit",
        "responsible_owner": "team-policy-implementation",
        "start_date": "2026-06-01",
        "affected_claim_ids": ["rec_1"],
        "assumption_refs": ["assumption-parallel-trends"],
        "evidence_ref": sha("a"),
    }


def _monitoring_plan() -> dict[str, Any]:
    return {
        "plan_id": "monitoring.plan.rec_1",
        "indicators": [
            {
                "indicator_id": "msme_survival_rate",
                "claim_id": "rec_1",
                "data_source_refs": ["production-msme-panel"],
                "thresholds": {"degradation_budget": 0.2},
            }
        ],
        "observation_windows": [
            {
                "window_id": "post-publication-q1",
                "start": "2026-06-01T00:00:00+00:00",
                "end": "2026-09-01T00:00:00+00:00",
            }
        ],
        "review_cadence": "monthly",
        "trigger_thresholds": ["ddm_readiness_R2", "survival_rate_drop_gt_5pp"],
        "responsible_owners": ["team-ddm", "team-policy-implementation"],
        "evidence_ref": sha("b"),
    }


def _evaluation_design() -> dict[str, Any]:
    return {
        "design_id": "evaluation-design-rec-1",
        "design_type": "difference_in_differences_reassessment",
        "estimand": "ATT",
        "outcome_metrics": ["msme_survival_rate"],
        "comparison_strategy": "matched eligible non-recipients",
        "observation_windows": ["post-publication-q1"],
        "evidence_ref": sha("c"),
    }


def _ddm_events() -> dict[str, list[dict[str, Any]]]:
    return {
        "shift_events": [
            {
                "event_id": "shift-risk-1",
                "event_type": "ml.problem_15_7.shift_risk.v1",
                "affected_claim_ids": ["rec_1"],
                "affected_evidence_line_refs": ["line-data"],
                "downstream_status": "publication_review_required",
                "evidence_ref": sha("d"),
                "runtime_event_ref": "event://ddm/shift-risk-1",
            }
        ],
        "degradation_events": [
            {
                "event_id": "degradation-1",
                "event_type": "ml.problem_15_7.degradation.v1",
                "affected_claim_ids": ["rec_1"],
                "affected_evidence_line_refs": ["line-data"],
                "readiness_event_ids": ["readiness-1"],
                "downstream_status": "publication_review_required",
                "evidence_ref": sha("e"),
                "runtime_event_ref": "event://ddm/degradation-1",
            }
        ],
        "readiness_events": [
            {
                "event_id": "readiness-1",
                "event_type": "ml.problem_15_7.readiness_state.v1",
                "affected_claim_ids": ["rec_1"],
                "affected_evidence_line_refs": ["line-data"],
                "readiness_state": "R2",
                "downstream_status": "publication_review_required",
                "evidence_ref": sha("f"),
                "runtime_event_ref": "event://ddm/readiness-1",
            }
        ],
        "incident_events": [
            {
                "event_id": "incident-1",
                "event_type": "ml.problem_15_7.incident_payload.v1",
                "affected_claim_ids": ["rec_1"],
                "affected_evidence_line_refs": ["line-data"],
                "root_cause_event_ids": ["root-cause-1"],
                "downstream_status": "publication_review_required",
                "evidence_ref": sha("8"),
                "runtime_event_ref": "event://ddm/incident-1",
            }
        ],
        "root_cause_events": [
            {
                "event_id": "root-cause-1",
                "event_type": "ml.problem_15_7.root_cause_bundle.v1",
                "affected_claim_ids": ["rec_1"],
                "affected_evidence_line_refs": ["line-data"],
                "downstream_status": "publication_review_required",
                "evidence_ref": sha("9"),
                "runtime_event_ref": "event://ddm/root-cause-1",
            }
        ],
    }


def _case_lifecycle_record() -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.case_lifecycle.v1",
        "ledger_id": "case-lifecycle-rec-1",
        "case_id": "pdc-R_hds_red_control",
        "current_state": "published",
        "events": [
            {
                "event_id": "lifecycle-published",
                "event_type": "published",
                "previous_state": "approved",
                "new_state": "published",
                "evidence_refs": [sha("1")],
                "runtime_event_ref": "event://policy-design-case/lifecycle/published",
            },
            {
                "event_id": "lifecycle-validity-confirmed",
                "event_type": "confirmed",
                "previous_state": "published",
                "new_state": "confirmed",
                "evidence_refs": [sha("2")],
                "runtime_event_ref": "event://policy-design-case/lifecycle/confirmed",
            },
        ],
        "continuous_governance_reports": {
            "reissue": sha("3"),
            "supersede": sha("4"),
            "withdraw": sha("5"),
            "validity": sha("6"),
        },
        "resolution_event_refs": ["lifecycle-validity-confirmed"],
        "evidence_ref": sha("7"),
        "runtime_event_ref": "event://policy-design-case/lifecycle",
    }


def _ex_post_learning_record() -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.ex_post_learning.v1",
        "record_id": "ex-post-learning-rec-1",
        "case_id": "pdc-R_hds_red_control",
        "claim_prediction_links": [
            {
                "link_id": "outcome-link-rec-1",
                "claim_id": "rec_1",
                "prediction_ref": "prediction-rec-1",
                "observed_outcome_ref": "observed-outcome-rec-1",
                "reassessment_ref": "reassessment-rec-1",
                "reassessment_status": "confirmed",
                "future_method_prior_ref": "future-prior-rec-1",
                "future_uncertainty_prior_ref": "future-prior-rec-1",
                "evidence_ref": sha("a"),
                "runtime_event_ref": "event://policy-design-case/ex-post/outcome-link",
            }
        ],
        "calibration": {
            "calibration_report_refs": [sha("b")],
            "backtesting_report_refs": [sha("c")],
            "calibration_leaderboard_ref": sha("d"),
            "track_record_ref": sha("e"),
        },
        "memory_contamination_check": {
            "status": "clean",
            "policy": {"hidden_ref_ids": [], "hidden_suite_ids": [], "canary_tokens": []},
            "findings": [],
            "evidence_ref": sha("f"),
            "runtime_event_ref": "event://policy-design-case/ex-post/memory-clean",
        },
        "learning_records": [
            {
                "learning_id": "learning-rec-1",
                "scope": "wartime_msme_support",
                "applicability": ["UA", "production_msme_panel"],
                "revocation_conditions": ["new legal regime", "data schema change"],
                "memory_contamination_controls": ["hidden_eval_scan_clean"],
                "evidence_ref": sha("0"),
            }
        ],
        "evidence_ref": sha("1"),
        "runtime_event_ref": "event://policy-design-case/ex-post",
    }
