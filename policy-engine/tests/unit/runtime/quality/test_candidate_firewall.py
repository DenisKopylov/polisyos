from __future__ import annotations

# ruff: noqa: S101
import pytest

from polisyos.runtime.quality.candidate_firewall import (
    CandidateFirewallError,
    assert_no_candidate_authority_laundering,
    candidate_firewall_issues_for_payload,
    candidate_refs_from_payload,
)
from polisyos.runtime.quality.hypothesis_ledger import HypothesisLedger


def _ledger() -> HypothesisLedger:
    return HypothesisLedger.model_validate(
        {
            "run_id": "run-wave6f",
            "job_id": "job-wave6f",
            "entries": [
                {
                    "candidate_id": "hypothesis-candidate:legal-reading-1",
                    "candidate_ref": "hypothesis-candidate:legal-reading-1",
                    "source_class": "llm_candidate",
                    "candidate_kind": "legal_reading",
                    "target_authority_slots": ["legal_authority"],
                    "target_claim_ids": ["claim-1"],
                    "prompt_fingerprint": "sha256:" + "1" * 64,
                    "tool_refs": ["tool-output:formulator"],
                    "repair_decision_lineage": ["repair:none"],
                    "authority_envelope": {
                        "authoritative_for": ["candidate_hypothesis"],
                        "may_not_use_for": [
                            "legal_authority",
                            "data_authority",
                            "method_authority",
                            "participation_authority",
                            "closeout_authority",
                            "projection_authority",
                            "claim_authority",
                            "obligation_authority",
                        ],
                    },
                    "admission_state": "candidate_unverified",
                }
            ],
        }
    )


def test_candidate_refs_are_discovered_only_from_candidate_authority_fields() -> None:
    refs = candidate_refs_from_payload(
        {
            "selected_norm_refs": ["hypothesis-candidate:legal-reading-1"],
            "ordinary_text": "candidate_legacy_text_is_not_a_runtime_ref",
        }
    )

    assert refs == ("hypothesis-candidate:legal-reading-1",)


def test_unverified_candidate_ref_is_blocked_at_consumer_read_surface() -> None:
    with pytest.raises(CandidateFirewallError, match="candidate_firewall_candidate_unverified"):
        assert_no_candidate_authority_laundering(
            {"selected_norm_refs": ["hypothesis-candidate:legal-reading-1"]},
            hypothesis_ledger=_ledger(),
            authority_slots=("legal_authority",),
            surface="claim_registry",
        )


def test_candidate_ref_without_runtime_ledger_fails_closed() -> None:
    issues = candidate_firewall_issues_for_payload(
        {"method_output_refs": ["hypothesis-candidate:method-1"]},
        authority_slots=("method_authority",),
        surface="claim_registry",
    )

    assert {issue["code"] for issue in issues} == {
        "candidate_firewall_hypothesis_ledger_missing"
    }
