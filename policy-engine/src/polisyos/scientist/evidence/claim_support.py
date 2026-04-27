"""Claim-to-source support mapping over Scholar snippets."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Literal

from polisyos.scholar.search.models import ClaimSupportLink, SourceSnippet, WebEvidenceBundle
from polisyos.scholar.search.scoring import detect_conflict_score, lexical_support_score
from polisyos.scientist.claims.models import ClaimRecord

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


__all__ = [
    "build_claim_support_links",
    "claim_support_status",
    "validate_claim_support_links",
]
