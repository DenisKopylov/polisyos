from __future__ import annotations

import pytest

from polisyos.evidence.portfolio.conflict_records import (
    ConflictRecordError,
    ConflictResolutionRoute,
    PortfolioConflictType,
    build_conflict_portfolio_index,
    build_conflict_record,
    conflict_refs_by_claim,
    validate_conflict_record,
)


def test_conflict_record_is_typed_counterevidence_not_support_mass() -> None:
    record = build_conflict_record(
        conflict_id="conflict.legal.credit_guarantee",
        run_id="run-w8e",
        claim_ids=["rec_credit_guarantee"],
        conflict_type=PortfolioConflictType.LEGAL,
        resolution_route=ConflictResolutionRoute.LEGAL_HIERARCHY,
        severity="high",
        conflicting_source_refs=["lex:blocker:credit_guarantee", "scholar:study:msme_credit"],
        description="Legal hierarchy blocks the intervention despite empirical support.",
        need_id="legal_applicability_need:credit_guarantee",
        detected_by="conflict_detector",
        detection_phase="post_hoc_backstop",
        producer_handshake_refs=["producer-handshake:run-w8e"],
    )

    validated = validate_conflict_record(record)

    assert validated["conflict_type"] == "legal"
    assert validated["resolution_route"] == "legal_hierarchy"
    assert validated["claim_ids"] == ["rec_credit_guarantee"]
    assert validated["support_count_effect"] == "not_supporting_evidence"
    assert validated["claim_registry_effect"] == "add_conflict_ref_and_counterevidence"
    assert validated["closeout_effect"] == "blocks_until_resolved"
    assert validated["authority_envelope"]["authoritative_for"] == ["conflict_materialization"]
    assert "claim_authority" in validated["authority_envelope"]["may_not_use_for"]


def test_conflict_record_supports_required_types_and_default_resolution_routes() -> None:
    expected_routes = {
        "empirical": "new_evidence",
        "methodological": "method_arbitration",
        "legal": "legal_hierarchy",
        "scope": "scope_narrowing",
        "normative": "governance_decision",
        "participation": "governance_decision",
        "implementation": "new_evidence",
        "authority_provenance": "persistent_contested_state",
    }

    for conflict_type, expected_route in expected_routes.items():
        record = build_conflict_record(
            conflict_id=f"conflict.{conflict_type}.rec",
            run_id="run-w8e",
            claim_ids=["rec"],
            conflict_type=conflict_type,
            severity="medium",
            conflicting_source_refs=[f"{conflict_type}:source:a", f"{conflict_type}:source:b"],
            description=f"{conflict_type} conflict",
        )

        assert record["resolution_route"] == expected_route


def test_conflict_record_rejects_unbound_claim_conflict() -> None:
    with pytest.raises(ConflictRecordError) as exc:
        validate_conflict_record(
            {
                "schema_version": "policyos.evidence.portfolio.conflict_record.v1",
                "conflict_id": "conflict.unbound",
                "run_id": "run-w8e",
                "claim_ids": [],
                "conflict_type": "empirical",
                "resolution_route": "new_evidence",
                "severity": "medium",
                "conflicting_source_refs": ["source:a", "source:b"],
                "description": "Detached detector output.",
                "support_count_effect": "not_supporting_evidence",
                "claim_registry_effect": "add_conflict_ref_and_counterevidence",
                "closeout_effect": "requires_review",
                "authority_envelope": {
                    "authoritative_for": ["conflict_materialization"],
                    "may_not_use_for": ["claim_authority", "support_strength"],
                },
            }
        )

    assert exc.value.code == "policy_design_conflict_claim_binding_missing"


def test_conflict_portfolio_index_groups_records_by_claim_and_portfolio() -> None:
    record = build_conflict_record(
        conflict_id="conflict.empirical.msme_survival",
        run_id="run-w8e",
        claim_ids=["rec_credit_guarantee"],
        conflict_type="empirical",
        severity="medium",
        conflicting_source_refs=["scholar:positive", "scholar:negative"],
        description="Mixed empirical direction.",
    )

    index = build_conflict_portfolio_index(
        [record],
        index_id="portfolio-conflicts.run-w8e",
        run_id="run-w8e",
        portfolio_designs=[
            {
                "portfolio_id": "portfolio.rec_credit_guarantee",
                "claim_ids": ["rec_credit_guarantee"],
            }
        ],
    )

    assert conflict_refs_by_claim(index["conflict_records"]) == {
        "rec_credit_guarantee": ["conflict.empirical.msme_survival"]
    }
    assert index["conflict_refs_by_portfolio"] == {
        "portfolio.rec_credit_guarantee": ["conflict.empirical.msme_survival"]
    }
    assert index["summary"] == {
        "conflict_count": 1,
        "claim_count": 1,
        "portfolio_count": 1,
        "closeout_blocking_count": 0,
    }
