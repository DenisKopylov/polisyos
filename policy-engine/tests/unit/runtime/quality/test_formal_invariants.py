# ruff: noqa: S101

from __future__ import annotations

import copy
import tomllib
from pathlib import Path

from polisyos.runtime.quality.formal_invariants import (
    FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH,
    REQUIRED_CLOSEOUT_INVARIANT_IDS,
    REQUIRED_TEMPORAL_LIVENESS_INVARIANT_IDS,
    build_formal_invariant_spec_report,
    check_bounded_liveness_deadline_consistency,
    model_check_formal_invariant_specs,
    validate_formal_invariant_specs_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


def _actual_payload() -> dict[str, object]:
    with (REPO_ROOT / FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH).open("rb") as handle:
        return tomllib.load(handle)


def test_phase_29_4_closeout_invariants_are_model_checked() -> None:
    report = build_formal_invariant_spec_report(repo_root=REPO_ROOT)

    assert report["status"] == "pass", report["issues"]
    assert (
        report["source"]["registry_path"]
        == FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH.as_posix()
    )
    assert report["summary"]["required_coverage_pct"] == 100.0
    assert set(report["required_closeout_invariants"]) == REQUIRED_CLOSEOUT_INVARIANT_IDS

    model_checks = report["model_checks"]
    assert model_checks["status"] == "pass", model_checks["checks"]
    assert {check["spec_id"] for check in model_checks["checks"]} >= {
        "authority_ordering",
        "phase_barriers",
        "same_input_closure",
        "cas_event_reconciliation",
        "terminal_readiness",
    }
    assert all(check["counterexamples"] == [] for check in model_checks["checks"])


def test_w10a_temporal_liveness_invariants_are_model_checked() -> None:
    report = build_formal_invariant_spec_report(repo_root=REPO_ROOT)

    assert report["status"] == "pass", report["issues"]
    assert set(report["required_temporal_liveness_invariants"]) == (
        REQUIRED_TEMPORAL_LIVENESS_INVARIANT_IDS
    )
    assert report["summary"]["temporal_liveness_coverage_pct"] == 100.0

    model_checks = report["model_checks"]
    assert {check["spec_id"] for check in model_checks["checks"]} >= {
        "bounded_liveness_producer_pipeline",
        "bounded_liveness_retry_lease",
        "bounded_liveness_escalation_authority",
        "bounded_liveness_reissue_flow",
    }
    assert all(check["counterexamples"] == [] for check in model_checks["checks"])


def test_bounded_liveness_flags_producer_wait_past_deadline_without_escalation() -> None:
    result = check_bounded_liveness_deadline_consistency(
        {
            "producer_pipeline": {
                "producer_handshake_records": [
                    {
                        "producer_component": "scholar",
                        "state": "waiting_on_peer",
                        "elapsed_s": 6.0,
                        "liveness": {
                            "deadline_s": 5.0,
                            "retry_ceiling": 1,
                            "config_id": "cfg",
                            "config_version": "v1",
                            "owner": "team-runtime-quality",
                            "feature_flag": "universal_pdc_bounded_liveness",
                        },
                        "wait_conditions": [
                            {
                                "peer_producer": "fabric",
                                "artifact_family": "source_contract",
                                "required_fields": ["source_ref"],
                                "deadline_s": 5.0,
                            }
                        ],
                        "blockers": [],
                    }
                ]
            }
        }
    )

    assert result["status"] == "fail"
    assert result["issues"][0]["code"] == (
        "bounded_liveness_wait_exceeded_without_escalation"
    )
    assert result["issues"][0]["producer_key"] == "scholar"


def test_bounded_liveness_flags_retry_lease_deadline_breach() -> None:
    result = check_bounded_liveness_deadline_consistency(
        {
            "retry_lease_records": [
                {
                    "producer_key": "scientist.node.scholar",
                    "state": "running",
                    "elapsed_s": 12.0,
                    "deadline_s": 10.0,
                    "attempts": 4,
                    "retry_ceiling": 2,
                    "lease_expires_at_s": 10.0,
                    "observed_at_s": 12.0,
                }
            ]
        }
    )

    assert result["status"] == "fail"
    assert {issue["code"] for issue in result["issues"]} >= {
        "bounded_liveness_retry_ceiling_exceeded",
        "bounded_liveness_lease_expired_without_escalation",
    }


def test_bounded_liveness_rejects_escalation_authority_and_late_reissue() -> None:
    result = check_bounded_liveness_deadline_consistency(
        {
            "escalation_records": [
                {
                    "producer_key": "fabric",
                    "state": "escalated",
                    "satisfies_authority": True,
                    "escalation_ref": "event://runtime-escalation/fabric",
                }
            ],
            "reissue_flows": [
                {
                    "case_id": "case-1",
                    "claim_id": "claim-1",
                    "status": "partial_reissue",
                    "elapsed_s": 121.0,
                    "deadline_s": 120.0,
                    "escalation_ref": None,
                    "resolution_ref": None,
                }
            ],
        }
    )

    assert result["status"] == "fail"
    assert {issue["code"] for issue in result["issues"]} >= {
        "bounded_liveness_escalation_cannot_satisfy_authority",
        "bounded_liveness_reissue_deadline_exceeded_without_escalation",
    }


def test_formal_invariant_registry_rejects_missing_required_closeout_spec() -> None:
    payload = _actual_payload()
    mutated = copy.deepcopy(payload)
    mutated["specs"] = [
        row for row in mutated["specs"] if row["spec_id"] != "terminal_readiness"
    ]

    validation = validate_formal_invariant_specs_payload(mutated, repo_root=REPO_ROOT)

    assert validation.status == "fail"
    assert "formal_invariant_required_spec_missing" in {
        issue.code for issue in validation.issues
    }


def test_substrate_critical_invariants_cannot_be_unit_test_only() -> None:
    payload = _actual_payload()
    mutated = copy.deepcopy(payload)
    mutated["specs"][0]["accepted_check_type"] = "unit_test_only"
    mutated["specs"][0]["model_property"] = None

    validation = validate_formal_invariant_specs_payload(mutated, repo_root=REPO_ROOT)

    assert validation.status == "fail"
    assert "formal_invariant_check_type_insufficient" in {
        issue.code for issue in validation.issues
    }


def test_model_checker_reports_unknown_model_property_as_counterexample() -> None:
    payload = _actual_payload()
    mutated = copy.deepcopy(payload)
    mutated["specs"][0]["model_property"] = "authority_ordering_all_roles_are_valid"

    result = model_check_formal_invariant_specs(mutated["specs"])

    assert result["status"] == "fail"
    assert result["checks"][0]["status"] == "fail"
    assert result["checks"][0]["counterexamples"] == [
        {"code": "formal_invariant_model_property_unknown"}
    ]
