"""Claim-to-source support mapping over Scholar snippets."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Literal

from polisyos.scholar.search.models import ClaimSupportLink, SourceSnippet, WebEvidenceBundle
from polisyos.scholar.search.scoring import detect_conflict_score, lexical_support_score
from polisyos.scientist.evidence.claims.models import (
    ClaimRecord,
)
from polisyos.scientist.evidence.claims.models import (
    ClaimSupportStatus as RuntimeClaimSupportStatus,
)
from polisyos.scientist.methods.search.voi_models import (
    VOIDecisionRecord,
    VOIDecisionType,
    stable_voi_decision_id,
)

ClaimSupportStatus = Literal["unsupported", "weakly_supported", "supported", "contested"]


def build_claim_support_links(
    claims: Sequence[ClaimRecord | dict[str, Any] | str],
    snippets: Sequence[SourceSnippet],
    *,
    max_snippets_per_claim: int = 8,
    score_threshold: float = 0.01,
) -> list[ClaimSupportLink]:
    """Map claims to ranked snippet-level support links."""

    links: list[ClaimSupportLink] = []
    for index, claim in enumerate(claims):
        claim_id, claim_text, namespace = _claim_identity(claim, index=index)
        ranked = sorted(
            ((lexical_support_score(claim_text, snippet.text), snippet) for snippet in snippets),
            key=lambda item: (-item[0], item[1].source_id, item[1].snippet_id),
        )
        selected = [
            (score, snippet)
            for score, snippet in ranked
            if score >= score_threshold
        ][:max_snippets_per_claim]
        snippet_ids = [snippet.snippet_id for _, snippet in selected]
        source_ids = sorted(dict.fromkeys(snippet.source_id for _, snippet in selected))
        support_score = sum(score for score, _ in selected) / max(len(selected), 1)
        conflict_score, uncertainty_note = detect_conflict_score(
            claim_text,
            [snippet.text for _, snippet in selected],
        )
        status = claim_support_status(
            support_score=support_score,
            conflict_score=conflict_score,
            snippet_count=len(snippet_ids),
        )
        links.append(
            ClaimSupportLink(
                claim_id=claim_id,
                claim_text=claim_text,
                snippet_ids=snippet_ids,
                source_ids=source_ids,
                support_score=round(support_score, 6),
                conflict_score=round(conflict_score, 6),
                uncertainty_note=uncertainty_note,
                metadata={
                    "claim_id_namespace": namespace,
                    "support_status": status,
                },
            )
        )
    return links


def claim_support_status(
    *,
    support_score: float,
    conflict_score: float = 0.0,
    snippet_count: int = 0,
) -> ClaimSupportStatus:
    """Convert heuristic support/conflict scores to a coarse support state."""

    if snippet_count <= 0 or support_score <= 0:
        return "unsupported"
    if conflict_score >= 0.5:
        return "contested"
    if support_score >= 0.12:
        return "supported"
    return "weakly_supported"


def validate_claim_support_links(bundle: WebEvidenceBundle) -> list[str]:
    """Return validation violations for claim-support snippet/source references."""

    violations: list[str] = []
    snippet_ids = {snippet.snippet_id for snippet in bundle.snippets}
    source_ids = {source.source_id for source in bundle.sources}
    for support in bundle.claim_supports:
        support_status = str(support.metadata.get("support_status", "")).lower()
        missing_snippets = [item for item in support.snippet_ids if item not in snippet_ids]
        if missing_snippets:
            violations.append(f"missing_snippet_id:{support.claim_id}:{missing_snippets[0]}")
        missing_sources = [item for item in support.source_ids if source_ids and item not in source_ids]
        if missing_sources:
            violations.append(f"missing_source_id:{support.claim_id}:{missing_sources[0]}")
        if (
            (support.support_score > 0 or support.source_ids)
            and not support.snippet_ids
            and support_status != "unsupported"
        ):
            violations.append(f"web_supported_claim_without_snippet:{support.claim_id}")
        if not support.snippet_ids and support_status not in {"unsupported", ""}:
            violations.append(f"unsupported_claim_misclassified:{support.claim_id}")
    return violations


def build_source_verification_voi_decisions(
    claims: Sequence[ClaimRecord],
    *,
    run_id: str,
    expected_verification_cost: float = 0.05,
    max_decisions: int | None = None,
) -> list[VOIDecisionRecord]:
    """Prioritize source verification for unsupported, weak or contested claims."""

    ranked = sorted(
        (
            (_source_verification_risk(claim), index, claim)
            for index, claim in enumerate(claims)
        ),
        key=lambda item: (-item[0], item[1]),
    )
    decisions: list[VOIDecisionRecord] = []
    for sequence, (risk, _index, claim) in enumerate(ranked[:max_decisions]):
        expected_risk_reduction = risk
        expected_value = expected_risk_reduction - max(expected_verification_cost, 0.0)
        action = "verify_sources" if expected_value > 0.0 and risk >= 0.4 else "defer"
        if expected_value < 0.0:
            action = "defer"
        decisions.append(
            VOIDecisionRecord(
                decision_id=stable_voi_decision_id(
                    run_id=run_id,
                    decision_type=VOIDecisionType.SOURCE_VERIFICATION,
                    subject_id=claim.claim_id,
                    sequence=sequence,
                ),
                run_id=run_id,
                decision_type=VOIDecisionType.SOURCE_VERIFICATION,
                recommended_action=action,
                expected_value=expected_value,
                expected_cost=max(expected_verification_cost, 0.0),
                expected_risk_reduction=expected_risk_reduction,
                explanation=(
                    f"{action} for claim {claim.claim_id}: support={claim.support_status.value}, "
                    f"evidence_refs={len(claim.evidence_refs)}, "
                    f"counterevidence_refs={len(claim.counterevidence_refs)}."
                ),
                input_refs=[*claim.evidence_refs, *claim.counterevidence_refs],
                metadata={
                    "claim_id": claim.claim_id,
                    "support_status": claim.support_status.value,
                    "publishability": claim.publishability.value,
                    "blocked_reasons": list(claim.blocked_reasons),
                },
            )
        )
    return decisions


def _claim_identity(
    claim: ClaimRecord | dict[str, Any] | str,
    *,
    index: int,
) -> tuple[str, str, str]:
    if isinstance(claim, ClaimRecord):
        return claim.claim_id, claim.text, "phase1_1"
    if isinstance(claim, dict):
        claim_id = str(claim.get("claim_id") or f"claim.{index + 1}")
        claim_text = str(claim.get("text") or claim.get("claim_text") or "")
        namespace = str(claim.get("claim_id_namespace") or "legacy_local")
        return claim_id, claim_text, namespace
    return f"claim.{index + 1}", str(claim), "legacy_local"


def _source_verification_risk(claim: ClaimRecord) -> float:
    base = {
        RuntimeClaimSupportStatus.UNSUPPORTED: 1.0,
        RuntimeClaimSupportStatus.CONTESTED: 0.9,
        RuntimeClaimSupportStatus.REFUTED: 0.85,
        RuntimeClaimSupportStatus.WEAKLY_SUPPORTED: 0.55,
        RuntimeClaimSupportStatus.NOT_EVALUABLE: 0.4,
        RuntimeClaimSupportStatus.SUPPORTED: 0.05,
    }[claim.support_status]
    if claim.counterevidence_refs:
        base += 0.2
    if not claim.evidence_refs:
        base += 0.15
    if claim.blocked_reasons:
        base += 0.1
    return max(0.0, min(1.0, base))


__all__ = [
    "build_claim_support_links",
    "build_source_verification_voi_decisions",
    "claim_support_status",
    "validate_claim_support_links",
]
