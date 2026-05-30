from __future__ import annotations

from pathlib import Path

# ruff: noqa: S101
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.runtime.quality.candidate_firewall import (
    CandidateFirewallError,
    assert_no_candidate_authority_laundering,
    candidate_firewall_issues_for_payload,
)
from polisyos.runtime.quality.hypothesis_ledger import (
    HYPOTHESIS_LEDGER_REF_KEY,
    HYPOTHESIS_LEDGER_SCHEMA_VERSION,
    HypothesisLedger,
    build_hypothesis_ledger_from_prompt_tool_ledger,
    persist_hypothesis_ledger,
    serialize_hypothesis_ledger,
)
from polisyos.runtime.quality.prompt_tool_ledger import PromptToolParserAuthorityLedger
from tests.unit.runtime.quality.test_prompt_tool_ledger import _authority_step


def _candidate_entry(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "candidate_id": "hypothesis-candidate:legal-reading-1",
        "candidate_ref": "hypothesis-candidate:legal-reading-1",
        "source_class": "llm_candidate",
        "candidate_kind": "legal_reading",
        "target_authority_slots": ["legal_authority"],
        "target_claim_ids": ["rec_credit_guarantee"],
        "prompt_fingerprint": "sha256:" + "1" * 64,
        "tool_refs": ["tool-output:lex-probe"],
        "repair_decision_lineage": ["repair:none"],
        "prompt_tool_ledger_ref": "sha256:" + "2" * 64,
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
        "content": {"summary": "LLM suggested that a statute authorizes the program."},
        "provenance": {
            "producer": "scientist.policy_design.formulator",
            "basis": "model_output",
        },
    }
    payload.update(overrides)
    return payload


def test_hypothesis_ledger_persists_append_only_candidates_with_prompt_tool_lineage(
    tmp_path: Path,
) -> None:
    prompt_ledger = PromptToolParserAuthorityLedger.model_validate(
        {
            "run_id": "R_hypothesis",
            "job_id": "job-hypothesis",
            "model_variant_id": "qwen_1",
            "prompt_tool_ledger_ref": "sha256:" + "2" * 64,
            "steps": [_authority_step()],
        }
    )
    ledger = build_hypothesis_ledger_from_prompt_tool_ledger(
        run_id="R_hypothesis",
        job_id="job-hypothesis",
        prompt_tool_ledger=prompt_ledger,
        candidates=[_candidate_entry()],
    )

    assert ledger.schema_version == HYPOTHESIS_LEDGER_SCHEMA_VERSION
    assert ledger.summary["entry_count"] == 1
    assert ledger.summary["source_classes"] == ["llm_candidate"]
    assert ledger.entries[0].prompt_fingerprint.startswith("sha256:")
    assert ledger.entries[0].tool_refs == ("tool-output:lex-probe",)

    store = FileSystemCAS(tmp_path / "cas")
    ref = persist_hypothesis_ledger(ledger, store=store)
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))

    assert payload["schema_version"] == HYPOTHESIS_LEDGER_SCHEMA_VERSION
    assert payload["entries"][0]["candidate_id"] == "hypothesis-candidate:legal-reading-1"
    assert payload["entries"][0]["admission_state"] == "candidate_unverified"


def test_unverified_llm_candidate_cannot_satisfy_legal_authority_slot() -> None:
    ledger = HypothesisLedger.model_validate(
        {
            "run_id": "R_hypothesis",
            "job_id": "job-hypothesis",
            "entries": [_candidate_entry()],
        }
    )

    with pytest.raises(CandidateFirewallError, match="candidate_firewall_candidate_unverified"):
        assert_no_candidate_authority_laundering(
            {
                HYPOTHESIS_LEDGER_REF_KEY: "sha256:" + "3" * 64,
                "selected_norm_refs": ["hypothesis-candidate:legal-reading-1"],
            },
            hypothesis_ledger=ledger,
            authority_slots=("legal_authority",),
            surface="claim_registry",
        )


def test_admitted_candidate_without_prompt_tool_repair_lineage_is_blocked() -> None:
    ledger = HypothesisLedger.model_validate(
        {
            "run_id": "R_hypothesis",
            "job_id": "job-hypothesis",
            "entries": [
                _candidate_entry(
                    target_authority_slots=["claim_authority"],
                    admission_state="admitted_to_claim",
                    prompt_fingerprint=None,
                    tool_refs=[],
                    repair_decision_lineage=[],
                    producer_validation_refs=["claim-producer-validation:rec_credit_guarantee"],
                    authority_envelope={
                        "authoritative_for": ["claim_authority"],
                        "may_not_use_for": [
                            "legal_authority",
                            "data_authority",
                            "method_authority",
                            "participation_authority",
                            "closeout_authority",
                            "projection_authority",
                        ],
                    },
                )
            ],
        }
    )

    issues = candidate_firewall_issues_for_payload(
        {
            "claim_refs": ["hypothesis-candidate:legal-reading-1"],
        },
        hypothesis_ledger=serialize_hypothesis_ledger(ledger),
        authority_slots=("claim_authority",),
        surface="claim_registry",
    )

    assert {issue["code"] for issue in issues} == {
        "candidate_firewall_admission_lineage_missing"
    }
    assert issues[0]["candidate_id"] == "hypothesis-candidate:legal-reading-1"
