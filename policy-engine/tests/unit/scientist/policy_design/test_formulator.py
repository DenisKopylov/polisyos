"""W6.E formulator producer tests."""

from __future__ import annotations

import pytest

from polisyos.runtime.quality.candidate_firewall import candidate_firewall_issues_for_payload
from polisyos.runtime.quality.hypothesis_ledger import HypothesisLedger
from polisyos.scientist.policy_design.formulator import (
    CandidateProvenance,
    InMemoryHypothesisLedger,
    LLMFormulator,
    LLMFormulatorInput,
)


def _msme_input() -> LLMFormulatorInput:
    return LLMFormulatorInput(
        intent=(
            "Design a working-capital credit guarantee for small retailers "
            "affected by flood disruption."
        ),
        authority_profile_ref="authority_profile.municipal_governed",
        concept_spine_refs=("concept_spine.msme_flood_recovery",),
        facets={
            "instrument_type": "credit_guarantee",
            "targeting_type": "means_tested_msme",
            "delivery_channel": "partner_banks",
            "funding_channel": "municipal_resilience_fund",
            "authority_type": "funding",
            "outcome_channel": "business_continuity",
            "population_predicate": "small retailers in flood affected wards",
            "geography_predicate": "river district",
            "risk_facet": ["elite_capture", "bank_exclusion"],
        },
        obligations=(
            {
                "obligation_id": "obl_legal_authority",
                "family": "legal",
                "description": "Verify municipal lending-guarantee authority.",
            },
        ),
        claim_decomposition=(
            {
                "claim_id": "claim_causal_liquidity",
                "claim_family": "causal",
                "claim_use": "support",
                "method_needs": ["quasi_experimental_comparison"],
            },
            {
                "claim_id": "claim_lived_experience_access",
                "claim_family": "lived_experience",
                "claim_use": "limitation",
            },
        ),
        source_refs=("intent.msme_credit", "facet_graph.msme_credit", "claim_decomp.msme_credit"),
    )


def test_formulator_emits_candidate_unverified_entries_into_ledger() -> None:
    payload = _msme_input()
    ledger = InMemoryHypothesisLedger()

    output = LLMFormulator().formulate(payload, ledger=ledger)

    assert {candidate.kind for candidate in output.candidates} >= {
        "field",
        "risk",
        "obligation",
        "missing_question",
        "method_need",
    }
    assert ledger.entries == output.ledger_entries
    assert {entry.source_class for entry in ledger.entries} == {"llm_candidate"}
    assert {entry.admission_state for entry in ledger.entries} == {"candidate_unverified"}
    assert all(entry.prompt_fingerprint for entry in ledger.entries)
    assert all(entry.tool_refs for entry in ledger.entries)
    assert all(entry.repair_decision_lineage for entry in ledger.entries)
    assert all(
        entry.authority_envelope.authoritative_for == ("candidate_hypothesis",)
        for entry in ledger.entries
    )
    assert all(
        {"legal_authority", "method_authority", "participation_authority"}
        <= set(entry.authority_envelope.may_not_use_for)
        for entry in ledger.entries
    )


def test_formulator_entries_are_canonical_hypothesis_ledger_inputs() -> None:
    output = LLMFormulator().formulate(_msme_input())
    runtime_ledger = HypothesisLedger.model_validate(
        {
            "run_id": "run-formulator-runtime-ledger",
            "job_id": "job-formulator-runtime-ledger",
            "entries": [
                entry.model_dump(mode="json", exclude_none=True)
                for entry in output.ledger_entries
            ],
        }
    )
    first_entry = runtime_ledger.entries[0]

    assert first_entry.candidate_ref.startswith("hypothesis-candidate:")
    assert first_entry.has_admission_lineage is True
    issues = candidate_firewall_issues_for_payload(
        {"selected_norm_refs": [first_entry.candidate_ref]},
        hypothesis_ledger=runtime_ledger,
        authority_slots=("legal_authority",),
        surface="claim_registry",
    )

    assert {issue["code"] for issue in issues} == {
        "candidate_firewall_candidate_unverified"
    }


def test_formulator_consumes_w6c_frontier_item_shape_without_duplicate_ledger_ids() -> None:
    payload = _msme_input().model_copy(
        update={
            "obligations": (
                {
                    "frontier_id": "frontier-001-legal-competence",
                    "obligation_text": "Verify legal competence before publication.",
                },
                {
                    "frontier_id": "frontier-002-data-lineage",
                    "obligation_text": "Bind production data lineage before publication.",
                },
            )
        }
    )

    output = LLMFormulator().formulate(payload)
    runtime_ledger = HypothesisLedger.model_validate(
        {
            "run_id": "run-formulator-frontier-ledger",
            "job_id": "job-formulator-frontier-ledger",
            "entries": [
                entry.model_dump(mode="json", exclude_none=True)
                for entry in output.ledger_entries
            ],
        }
    )
    obligation_entries = [
        entry for entry in runtime_ledger.entries if entry.candidate_kind == "obligation"
    ]

    assert {entry.target_claim_ids for entry in obligation_entries} == {()}
    assert {
        entry.content["obligation_refs"][0] for entry in obligation_entries
    } >= {
        "frontier-001-legal-competence",
        "frontier-002-data-lineage",
    }
    assert len({entry.candidate_id for entry in runtime_ledger.entries}) == len(
        runtime_ledger.entries
    )


def test_llm_candidate_provenance_requires_prompt_tool_and_repair_lineage() -> None:
    with pytest.raises(ValueError, match="tool_refs"):
        CandidateProvenance(
            producer="policy_design.llm_formulator",
            producer_version="1.0.0",
            source_class="llm_candidate",
            prompt_fingerprint="sha256:abc",
            tool_refs=(),
            repair_decision_lineage=("repair.none",),
            input_refs=("intent.msme_credit",),
        )

    with pytest.raises(ValueError, match="repair_decision_lineage"):
        CandidateProvenance(
            producer="policy_design.llm_formulator",
            producer_version="1.0.0",
            source_class="llm_candidate",
            prompt_fingerprint="sha256:abc",
            tool_refs=("tool.schema.formulator",),
            repair_decision_lineage=(),
            input_refs=("intent.msme_credit",),
        )
