from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy

from polisyos.lex.normpack.applicability_report import build_normative_applicability_report
from polisyos.runtime.quality.claim_registry import build_runtime_claim_registry
from polisyos.runtime.quality.semantic_binding import (
    SemanticBindingLedger,
    build_semantic_binding_ledger,
    evaluate_semantic_binding_ledger,
)
from tests._helpers.hds_quality import complete_quality_evidence


def _claim(**overrides: object) -> dict[str, object]:
    claim: dict[str, object] = {
        "claim_id": "rec_1",
        "major": True,
        "text": "Authorize a wartime credit guarantee for eligible MSMEs.",
        "legal_authority_required": True,
        "jurisdiction": "UA",
        "required_authority_types": ["implementing", "funding"],
        "policy_instrument": "credit_guarantee",
        "competent_actor_ref": "ministry_of_economy",
        "implementation_authority_ref": "ministry_program_office",
        "fiscal_authority_required": True,
        "fiscal_authority_ref": "ministry_of_finance",
        "implementation_period": {"start": "2026-01-01", "end": "2026-12-31"},
    }
    claim.update(overrides)
    return claim


def _norm() -> dict[str, object]:
    return {
        "norm_id": "norm.ua.credit_eligibility",
        "norm_version_ref": "norm.ua.credit_eligibility@2026-01-01",
        "source_provenance_ref": "lex-corpus:ua-credit-eligibility",
        "jurisdiction": "UA",
        "policy_domain": "wartime_msme_support",
        "effective_from": "2025-01-01",
        "source_authority": "Verkhovna Rada",
        "authority_level": "statute",
        "authority_basis": "statutory_program_authorization",
        "authority_types": ["implementing", "funding"],
        "competent_actor_ref": "ministry_of_economy",
        "instrument_types": ["credit_guarantee"],
        "implementation_authority_ref": "ministry_program_office",
        "fiscal_authority_ref": "ministry_of_finance",
        "hierarchy_position": "national",
        "legal_as_of": "2026-05-22",
        "legal_effective_window": {"start": "2025-01-01", "end": None},
        "rule_version_ref": "lex-legal-authority:v1",
        "provenance_kind": "deterministic_producer",
    }


def _legal_report() -> dict[str, object]:
    return build_normative_applicability_report(
        target_context={
            "jurisdiction": "UA",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-22",
            "authority_profile": "production",
        },
        candidate_norms=[_norm()],
        recommendation_claims=[_claim(norm_refs=["norm.ua.credit_eligibility"])],
    )


def test_runtime_claim_registry_preserves_lex_legal_authority_refs() -> None:
    report = _legal_report()
    anchor = report["claim_legal_anchors"][0]

    registry = build_runtime_claim_registry(
        run_id="run-w3b",
        normative_evidence=report,
        claims=[
            {
                "claim_id": "rec_1",
                "scenario_requirement_refs": ["scenario.req.credit_guarantee"],
                "data_refs": ["source.msme_panel"],
                "selected_norm_refs": anchor["selected_norm_refs"],
                "rejected_norm_refs": anchor["rejected_norm_refs"],
                "legal_authority_record_refs": anchor["legal_authority_record_refs"],
                "legal_authority_blocker_refs": anchor["legal_authority_blocker_refs"],
                "method_output_refs": ["method.did.msme_survival"],
                "portfolio_refs": ["portfolio.rec_1"],
                "argument_refs": ["argument.rec_1"],
                "warrant_refs": ["warrant.rec_1"],
                "rebuttal_refs": ["rebuttal.rec_1"],
                "counter_evidence_refs": ["counter.rec_1"],
                "limitation_refs": ["limit.legal_scope"],
                "accepted_deficit_refs": ["deficit.legal_scope"],
            }
        ],
    )

    row = registry["claims"][0]

    assert registry["status"] == "pass"
    assert row["legal_authority_record_refs"] == anchor["legal_authority_record_refs"]
    assert row["selected_producer_refs"]["lex"] == ["norm.ua.credit_eligibility"]
    assert row["selected_producer_refs"]["lex_legal_authority"] == (
        anchor["legal_authority_record_refs"]
    )


def test_semantic_binding_consumes_lex_legal_authority_records() -> None:
    evidence = complete_quality_evidence()
    report = _legal_report()

    ledger_payload = build_semantic_binding_ledger(
        runtime_refs={"policy_intent_ref": "sha256:" + "a" * 64},
        normative_evidence=report,
        fabric_retrieval_trace=evidence["fabric_retrieval_trace"],  # type: ignore[index]
        foundry_method_report=evidence["foundry_method_report"],  # type: ignore[index]
        policy_grounding_matrix=evidence["policy_grounding_matrix"],  # type: ignore[index]
        decision_artifact_contract={
            "statements": [{"statement_scope": "recommendations", "evidence_refs": ["rec_1"]}]
        },
    )
    ledger = SemanticBindingLedger.model_validate(ledger_payload)

    assert ledger.lex[0].legal_authority_record_refs
    assert ledger.lex[0].legal_admissibility_grades == (
        "selected_authority",
        "selected_authority",
    )
    assert ledger.lex[0].jurisdiction_fallback_policy_refs == ()
    assert ledger.lex[0].selected_norm_refs == ("norm.ua.credit_eligibility",)


def test_semantic_binding_blocks_selected_norm_without_claim_level_legal_authority() -> None:
    evidence = complete_quality_evidence()
    report = deepcopy(evidence["normative_evidence"])  # type: ignore[index]
    assert isinstance(report, dict)
    report["legal_authority_required"] = True
    report["legal_authority_records"] = []
    report["claim_legal_anchors"] = [
        {
            "claim_id": "rec_1",
            "legal_authority_required": True,
            "selected_norm_refs": ["norm.ua.credit_eligibility"],
            "legal_authority_record_refs": [],
        }
    ]

    ledger = build_semantic_binding_ledger(
        runtime_refs={"policy_intent_ref": "sha256:" + "a" * 64},
        normative_evidence=report,
        fabric_retrieval_trace=evidence["fabric_retrieval_trace"],  # type: ignore[index]
        foundry_method_report=evidence["foundry_method_report"],  # type: ignore[index]
        policy_grounding_matrix=evidence["policy_grounding_matrix"],  # type: ignore[index]
        decision_artifact_contract={
            "statements": [{"statement_scope": "recommendations", "evidence_refs": ["rec_1"]}]
        },
    )
    evaluation = evaluate_semantic_binding_ledger(ledger)

    assert evaluation.status == "fail"
    assert "semantic_lex_legal_authority_record_missing" in {
        issue.code for issue in evaluation.issues
    }
