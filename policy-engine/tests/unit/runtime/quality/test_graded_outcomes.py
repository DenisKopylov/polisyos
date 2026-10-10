from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime

from polisyos.runtime.quality.graded_outcomes import (
    GradedOutcomeEvidenceInput,
    compose_graded_outcome,
    graded_outcome_closeout_record,
)


def _decision_input(
    *, claim_id: str, requested_outcome: str, evidence_profile: str
) -> GradedOutcomeEvidenceInput:
    return GradedOutcomeEvidenceInput(
        schema_version="policyos.runtime.layer2.graded_outcome.v1",
        case_id="case-mixed-closeout",
        claim_id=claim_id,
        authority_level="production",
        requested_outcome=requested_outcome,  # type: ignore[arg-type]
        evidence_profile=evidence_profile,  # type: ignore[arg-type]
        proxy_evidence_refs=(),
        partial_evidence_refs=(),
        limitation_reason_codes=(),
        mandatory_gate_state="none",
        owner="runtime-quality-owner",
        decision_owner_ref=None,
        authority_profile_ref="profile://production",
        review_refs=(),
        ttl_expires_at=datetime(2026, 10, 11, tzinfo=UTC),
        public_limitation_note=None,
        rule_version_ref="rules://graded-outcome-v1",
    )


def test_one_blocked_claim_keeps_mixed_closeout_blocked_alongside_a_pass() -> None:
    exact = compose_graded_outcome(
        _decision_input(
            claim_id="claim-exact",
            requested_outcome="pass",
            evidence_profile="exact",
        )
    )
    unsupported = compose_graded_outcome(
        _decision_input(
            claim_id="claim-unsupported",
            requested_outcome="pass",
            evidence_profile="unsupported",
        )
    )

    closeout = graded_outcome_closeout_record(
        (exact, unsupported),
        generated_at=datetime(2026, 10, 10, 9, 0, tzinfo=UTC),
    )

    assert exact.outcome == "pass"
    assert unsupported.outcome == "typed_blocker"
    assert closeout["status"] == "blocked"
    assert [row["claim_id"] for row in closeout["issues"]] == ["claim-unsupported"]
    assert any(row["severity"] == "fail" for row in closeout["issues"])
