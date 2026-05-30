from __future__ import annotations

# ruff: noqa: S101
import pytest

from polisyos.runtime.quality.hypothesis_ledger import (
    HypothesisLedger,
    HypothesisLedgerEntry,
    append_hypothesis_ledger_entry,
)


def _entry(
    candidate_id: str = "hypothesis-candidate:claim-1",
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "candidate_id": candidate_id,
        "candidate_ref": candidate_id,
        "source_class": "llm_candidate",
        "candidate_kind": "claim_candidate",
        "target_authority_slots": ["claim_authority"],
        "target_claim_ids": ["claim-1"],
        "prompt_fingerprint": "sha256:" + "1" * 64,
        "tool_refs": ["tool-output:formulator"],
        "repair_decision_lineage": ["repair:none"],
        "authority_envelope": {
            "authoritative_for": ["candidate_hypothesis"],
            "may_not_use_for": [
                "claim_authority",
                "legal_authority",
                "data_authority",
                "method_authority",
                "participation_authority",
                "closeout_authority",
                "projection_authority",
                "obligation_authority",
            ],
        },
        "admission_state": "candidate_unverified",
        "content": {"text": "Candidate claim text."},
        "provenance": {"producer": "test"},
    }
    payload.update(overrides)
    return payload


def test_hypothesis_ledger_entry_requires_prompt_tool_and_repair_lineage_for_admission() -> None:
    with pytest.raises(ValueError, match="admitted candidates require producer or reader"):
        HypothesisLedgerEntry.model_validate(
            _entry(
                admission_state="admitted_to_claim",
                authority_envelope={
                    "authoritative_for": ["claim_authority"],
                    "may_not_use_for": ["legal_authority"],
                },
            )
        )


def test_hypothesis_ledger_is_append_only_and_deduplicates_candidate_ids() -> None:
    ledger = HypothesisLedger.model_validate(
        {
            "run_id": "run-wave6f",
            "job_id": "job-wave6f",
            "entries": [_entry()],
        }
    )

    appended = append_hypothesis_ledger_entry(
        ledger,
        _entry("hypothesis-candidate:claim-2"),
    )

    assert [entry.candidate_id for entry in appended.entries] == [
        "hypothesis-candidate:claim-1",
        "hypothesis-candidate:claim-2",
    ]

    with pytest.raises(ValueError, match="duplicate hypothesis candidate ids"):
        append_hypothesis_ledger_entry(ledger, _entry())


def test_critic_consensus_candidate_remains_unverified_until_reviewer_and_producer_admit() -> None:
    ledger = HypothesisLedger.model_validate(
        {
            "run_id": "run-phase5",
            "job_id": "job-phase5",
            "entries": [
                _entry(
                    candidate_id="critic-consensus:firm_survival_construct",
                    candidate_ref="candidate-capability:firm_survival",
                    source_class="llm_critic_consensus",
                    candidate_kind="candidate_capability",
                    target_authority_slots=["data_authority", "method_authority"],
                    content={
                        "construct": "firm_survival",
                        "capability_candidate_ref": "candidate-capability:firm_survival",
                    },
                )
            ],
        }
    )

    entry = ledger.entries[0]

    assert entry.admission_state == "candidate_unverified"
    assert set(entry.authority_envelope.may_not_use_for) >= {
        "data_authority",
        "method_authority",
    }
    assert ledger.summary["candidate_unverified_count"] == 1

    with pytest.raises(ValueError, match="critic consensus admission requires reviewer"):
        HypothesisLedgerEntry.model_validate(
            _entry(
                candidate_id="critic-consensus:firm_survival_construct",
                candidate_ref="candidate-capability:firm_survival",
                source_class="llm_critic_consensus",
                candidate_kind="candidate_capability",
                target_authority_slots=["data_authority"],
                admission_state="admitted_to_claim",
                producer_validation_refs=["producer-admission:fabric:firm_survival"],
                authority_envelope={
                    "authoritative_for": ["data_authority"],
                    "may_not_use_for": [
                        "legal_authority",
                        "method_authority",
                        "participation_authority",
                        "closeout_authority",
                        "projection_authority",
                        "claim_authority",
                        "obligation_authority",
                    ],
                },
            )
        )


def test_llm_critic_consensus_cannot_skip_human_admission() -> None:
    """Required Phase 7 negative-test id for the W6.F candidate firewall."""

    test_critic_consensus_candidate_remains_unverified_until_reviewer_and_producer_admit()
