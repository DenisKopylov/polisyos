"""Behavioral controls for scope refusal at construction and canonical replay.

Removing any guarded property while keeping its message must fail its control.
The fixture deliberately has no CG2 grant; this seam tests honest refusal, not a
synthetic positive candidate or an obsolete contract-only grounding fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.pdc import PromotionObligationClass, PromotionObligationStatus, gy_content_hash
from polisyos.runtime.quality import promotion_sequence as owner
from polisyos.runtime.quality.confidence_ledger import ConfidenceLedgerSession
from polisyos.runtime.quality.generation_cycle import CandidateSummary

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def refusal(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[owner.CanonicalPromotionReceipt, ConfidenceLedgerSession]:
    """Run canonical N9 on a real typed input missing its authority prerequisites."""
    attempt = owner.CanonicalPromotionInput(
        design_problem_binding=owner.N9DesignProblemBinding(
            design_problem_id="scope-guard-removal",
            problem_content_hash=gy_content_hash({"synthetic": True, "case": "scope-guard"}),
            problem_schema_version="scope-guard.synthetic.v1",
        ),
        candidate_summary=CandidateSummary(
            candidate_id="scope-guard-candidate",
            content_hash=gy_content_hash({"synthetic": True, "candidate": "scope-guard"}),
            cycle_index=0,
            generation_channel="n4_owner",
            proxy_score=0.2,
            voi_estimate=0.1,
            grounding_status="grounding_failed",
            grounding_score=0.0,
            current_valid=False,
            front="research",
            high_proxy=False,
            low_grounding=True,
        ),
        value_receipt=None,
        g4_governed_promotion_ref=None,
    )
    scratch = tmp_path_factory.mktemp("scope-guard")
    session = ConfidenceLedgerSession._for_verification(
        ROOT,
        risk_scope=owner.confidence_risk_scope_for_problem(attempt.design_problem_binding),
        artifact_store=FileSystemCAS(scratch / "cas"),
        state_root=scratch / "state",
    )
    receipt = owner._run_canonical_promotion_sequence_for_verification(
        attempt,
        confidence_ledger_session=session,
    )
    assert receipt.promoted is False
    assert any(
        row.status == PromotionObligationStatus.SCOPE_INSUFFICIENT for row in receipt.obligations
    )
    return receipt, session


def _pretend_promoted(
    receipt: owner.CanonicalPromotionReceipt,
    session: ConfidenceLedgerSession,
) -> owner.CanonicalPromotionReceipt:
    """Keep all real refusal markers while changing the claimed authority outcome."""
    attempt = owner._input_from_owner_projection(receipt.owner_projection, repo_root=ROOT)
    trace = owner._authority_derivation_trace(
        attempt,
        obligations=receipt.obligations,
        boundary=receipt.computed_authority_boundary,
        gate_hash=receipt.gate_outcome_hash,
        risk_spend=receipt.risk_spend,
        confidence_ledger_receipt=session.receipt(),
        confidence_ledger_projection=receipt.confidence_ledger_projection,
    )
    return receipt.model_copy(
        update={
            "promoted": True,
            "status": "grounded_partial_admissible",
            "promotion_lane": "production",
            "authority_derivation_trace": trace,
        }
    )


def test_constructor_refuses_authority_with_retained_scope_markers(refusal) -> None:
    """Construction must refuse even with a trace and all message-bearing markers."""
    receipt, session = refusal
    forged = _pretend_promoted(receipt, session)
    with pytest.raises(ValueError, match="scope_insufficient_cannot_mint_authoritative_promotion"):
        owner.CanonicalPromotionReceipt.model_validate(forged.model_dump(mode="python"))


def test_replay_refuses_scope_status_with_removed_semantic_scope(refusal) -> None:
    """Semantic replay must reject the property loss, not merely read scope status."""
    receipt, session = refusal
    obligations = tuple(
        row.model_copy(update={"semantic_scope": "real_semantics"})
        if row.obligation_role == "class_gate"
        and row.obligation_class == PromotionObligationClass.PARAM
        else row
        for row in receipt.obligations
    )
    forged = receipt.model_copy(update={"obligations": obligations})
    issues = owner._validate_canonical_promotion_receipt_for_verification(
        forged,
        repo_root=ROOT,
        confidence_ledger_session=session,
    )
    assert "scope_insufficient_semantic_scope_mismatch" in {issue["code"] for issue in issues}


def test_replay_refuses_authority_with_retained_scope_markers(refusal) -> None:
    """Independent replay must catch construction-bypassing authority laundering."""
    receipt, session = refusal
    forged = _pretend_promoted(receipt, session)
    issues = owner._validate_canonical_promotion_receipt_for_verification(
        forged,
        repo_root=ROOT,
        confidence_ledger_session=session,
    )
    assert "scope_insufficient_authority_laundering" in {issue["code"] for issue in issues}


def test_replay_refuses_success_marker_without_scope_property(refusal) -> None:
    """The inverse status forgery cannot turn a scope gap into satisfaction."""
    receipt, session = refusal
    obligations = tuple(
        row.model_copy(update={"status": PromotionObligationStatus.SATISFIED, "reason": None})
        if row.obligation_role == "class_gate"
        and row.obligation_class == PromotionObligationClass.PARAM
        else row
        for row in receipt.obligations
    )
    forged = receipt.model_copy(update={"obligations": obligations})
    issues = owner._validate_canonical_promotion_receipt_for_verification(
        forged,
        repo_root=ROOT,
        confidence_ledger_session=session,
    )
    assert "obligation_class_vacuously_passed" in {issue["code"] for issue in issues}
