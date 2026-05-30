from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy

import polisyos.runtime.quality as runtime_quality
from polisyos.runtime.quality.capability_ratchet import (
    CAPABILITY_RATCHET_SCHEMA_VERSION,
    PURPOSE_MULTIPLIERS,
    REALITY_STATE_BASE_POINTS,
    REALITY_STATES,
    build_capability_reality_report,
    evaluate_capability_claim,
)


def _claim(**overrides: object) -> dict[str, object]:
    claim: dict[str, object] = {
        "capability_id": "w1a-capability-ratchet",
        "capability_name": "W1.A Capability Ratchet",
        "reality_state": "contract_only",
        "purpose": "evidence_producer",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2026-06-30",
        "hold_reason": "producer bridge scheduled in W1.A",
        "next_wave_target": "W1.A",
        "chain_id": "capability-ratchet",
        "typed_contract_ref": "repo://docs/reference/policy-design-case-failure-patterns.md",
    }
    claim.update(overrides)
    return claim


def test_contract_only_debt_uses_base_points_and_purpose_multiplier() -> None:
    record = evaluate_capability_claim(_claim(), as_of="2026-05-22")

    assert record["reality_state"] == "contract_only"
    assert record["base_points"] == REALITY_STATE_BASE_POINTS["contract_only"]
    assert record["purpose_multiplier"] == PURPOSE_MULTIPLIERS["evidence_producer"]
    assert record["serious_profile_premium"] == 1
    assert record["local_points"] == 4.0
    assert record["local_severity"] == "medium"
    assert record["release_blocker"] is False


def test_reality_states_stay_on_canonical_capability_labels() -> None:
    assert set(REALITY_STATES) == {
        "implemented",
        "surface_out_of_scope",
        "contract_only",
        "producer_missing",
        "artifact_missing",
        "bridge_missing",
        "consumer_missing",
        "verification_missing",
        "implemented_but_not_orchestrated",
        "surface_missing",
        "semantic_test_missing",
    }
    assert "projection_only" not in REALITY_STATES
    assert "compatibility_shim" not in REALITY_STATES


def test_implemented_claim_with_missing_producer_downgrades_to_contract_only() -> None:
    record = evaluate_capability_claim(
        _claim(
            reality_state="implemented",
            typed_contract_ref="repo://src/polisyos/runtime/quality/capability_ratchet.py",
            producer_ref="",
            artifact_ref="",
            bridge_ref="",
            consumer_ref="",
            verification_ref="",
            surface_ref="",
            semantic_test_ref="",
        ),
        as_of="2026-05-22",
    )

    assert record["reported_reality_state"] == "implemented"
    assert record["reality_state"] == "contract_only"
    assert "capability_implemented_chain_incomplete" in _issue_codes(record)
    assert record["graduation_allowed"] is False


def test_surface_out_of_scope_is_zero_only_with_full_governance() -> None:
    valid = evaluate_capability_claim(
        _claim(
            capability_id="internal-helper",
            reality_state="surface_out_of_scope",
            purpose="internal_helper",
            surface_out_of_scope={
                "rationale": "Pure internal helper; operator inspection uses runtime event log.",
                "owner": "team-runtime-quality",
                "review_date": "2026-07-01",
                "inspection_path": "runtime_event_log",
            },
        ),
        as_of="2026-05-22",
    )

    assert valid["reality_state"] == "surface_out_of_scope"
    assert valid["local_points"] == 0.0
    assert valid["release_blocker"] is False

    invalid = evaluate_capability_claim(
        _claim(
            capability_id="promised-reviewer-surface",
            reality_state="surface_out_of_scope",
            purpose="public_surface",
            promised_audiences=["reviewer"],
            surface_out_of_scope={"rationale": "not needed yet"},
        ),
        as_of="2026-05-22",
    )

    assert invalid["reality_state"] == "surface_missing"
    assert invalid["release_blocker"] is True
    assert "surface_out_of_scope_governance_missing" in _issue_codes(invalid)


def test_semantic_test_missing_blocks_serious_closeout_or_authority_paths() -> None:
    record = evaluate_capability_claim(
        _claim(
            capability_id="closeout-reader",
            reality_state="semantic_test_missing",
            purpose="closeout_input",
        ),
        as_of="2026-05-22",
    )

    assert record["release_blocker"] is True
    assert record["readiness_effect"] == "blocked"
    assert record["graduation_allowed"] is False
    assert record["burn_down_signal"]["required_evidence"] == "semantic_test_ref"


def test_report_promotes_clustered_debt_into_not_ready_readiness() -> None:
    report = build_capability_reality_report(
        [
            _claim(
                capability_id="producer-contract",
                reality_state="contract_only",
                purpose="evidence_producer",
                chain_id="claim-binding",
            ),
            _claim(
                capability_id="closeout-consumer",
                reality_state="consumer_missing",
                purpose="closeout_input",
                chain_id="claim-binding",
            ),
            _claim(
                capability_id="reviewer-surface",
                reality_state="surface_missing",
                purpose="diagnostic_only",
                chain_id="claim-binding",
            ),
        ],
        validation_profile="production",
        as_of="2026-05-22",
    )

    assert report["schema_version"] == CAPABILITY_RATCHET_SCHEMA_VERSION
    assert report["ratchet_integrity_status"] == "pass"
    assert report["readiness"]["band"] == "orange"
    assert report["readiness"]["decision"] == "not_ready"
    assert report["summary"]["chain_cluster_count"] == 1
    assert report["chain_clusters"][0]["chain_id"] == "claim-binding"


def test_report_exposes_templates_counts_and_public_runtime_api() -> None:
    report = build_capability_reality_report(
        [
            _claim(
                reality_state="implemented",
                producer_ref="repo://tools/quality/validation/check_policy_design_case_capability_ratchet.py",
                artifact_ref="repo://architecture/policy_design_case/capability_reality_report.json",
                bridge_ref="repo://tools/quality/validation/check_policy_design_case_capability_ratchet.py",
                consumer_ref="repo://docs/reference/policy-design-case-capability-ratchet.md",
                verification_ref="repo://tests/unit/runtime/quality/test_capability_ratchet.py",
                surface_ref="repo://docs/reference/policy-design-case-capability-ratchet.md",
                semantic_test_ref="repo://tests/unit/runtime/quality/test_capability_ratchet.py::test_implemented_claim_with_missing_producer_downgrades_to_contract_only",
            ),
            _claim(capability_id="semantic-fixtures", reality_state="semantic_test_missing"),
        ],
        validation_profile="production",
        as_of="2026-05-22",
    )

    assert report["summary"]["capability_claims_total"] == 2
    assert report["summary"]["state_counts"]["implemented"] == 1
    assert report["summary"]["state_counts"]["semantic_test_missing"] == 1
    assert "semantic_test_missing" in report["ratchet_templates"]
    assert (
        report["ratchet_templates"]["semantic_test_missing"]["required_evidence"]
        == "semantic_test_ref"
    )
    assert runtime_quality.CAPABILITY_RATCHET_SCHEMA_VERSION == CAPABILITY_RATCHET_SCHEMA_VERSION
    assert runtime_quality.build_capability_reality_report is build_capability_reality_report


def _issue_codes(record: dict[str, object]) -> set[str]:
    return {
        str(issue["code"])
        for issue in deepcopy(record)["issues"]  # type: ignore[index]
    }
