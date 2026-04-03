"""Public conflicts score claims module API."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from polisyos.ir.world.claim import Claim
from polisyos.ir.world.conflict import ConflictSet
from polisyos.ir.world.ids import trust_assessment_id_from_payload
from polisyos.ir.world.trust import TrustAssessment, TrustTier

from .key import value_signature_v1
from .policies import ConflictPolicy

_Q4 = Decimal("0.0001")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_Q4, rounding=ROUND_HALF_UP)


def _tier(score: Decimal) -> TrustTier:
    if score >= Decimal("0.75"):
        return TrustTier.HIGH
    if score >= Decimal("0.55"):
        return TrustTier.MEDIUM
    return TrustTier.LOW


def _aggregate_doc_trust(
    claim: Claim,
    doc_trust_by_doc_version: dict[str, TrustAssessment],
    default_doc_trust: Decimal,
) -> Decimal:
    cited_scores: list[Decimal] = []
    for citation in claim.citations:
        doc_version_id = citation.doc.doc_version_id
        if doc_version_id is None:
            continue
        assessment = doc_trust_by_doc_version.get(doc_version_id)
        if assessment is not None:
            cited_scores.append(assessment.score)
    if not cited_scores:
        return default_doc_trust
    return _quantize(sum(cited_scores) / Decimal(len(cited_scores)))


def _evidence_density(
    claim: Claim,
    *,
    fragment_anchor_kind_by_id: dict[str, str],
    divisor: Decimal,
) -> Decimal:
    citations_count = len(claim.citations)
    bonus = 0
    for citation in claim.citations:
        fragment_id = citation.fragment_id
        if fragment_id is None:
            continue
        anchor_kind = fragment_anchor_kind_by_id.get(fragment_id, "")
        if anchor_kind in {"table", "section"}:
            bonus += 1
        elif anchor_kind in {"page", "chunk"}:
            bonus += 0
    raw = Decimal(citations_count + bonus)
    if divisor <= 0:
        return Decimal("1")
    return min(Decimal("1"), _quantize(raw / divisor))


def score_claim_trust_assessments(
    *,
    claims_by_id: dict[str, Claim],
    conflict_sets: list[ConflictSet],
    doc_trust_by_doc_version: dict[str, TrustAssessment],
    extractor_id_by_claim: dict[str, str],
    agent_id_by_claim: dict[str, str],
    fragment_anchor_kind_by_id: dict[str, str],
    policy: ConflictPolicy,
    policy_id: str,
    algorithm_version: str,
) -> tuple[dict[str, TrustAssessment], dict[str, dict[str, Decimal]]]:
    """Score claim trust assessments helper."""
    consensus_by_claim: dict[str, Decimal] = {}
    for conflict_set in conflict_sets:
        signatures = {
            claim_id: value_signature_v1(claims_by_id[claim_id])
            for claim_id in conflict_set.member_claim_ids
            if claim_id in claims_by_id
        }
        total = len(signatures)
        if total <= 1:
            for claim_id in signatures:
                consensus_by_claim[claim_id] = Decimal("1.0")
            continue
        for claim_id, signature in signatures.items():
            support = sum(
                1
                for other_id, other_signature in signatures.items()
                if other_id != claim_id and other_signature == signature
            )
            contradict = max(0, total - 1 - support)
            consensus = Decimal(support) / Decimal(max(1, total - 1))
            if contradict > support:
                consensus = max(Decimal("0"), consensus - Decimal("0.10"))
            consensus_by_claim[claim_id] = _quantize(consensus)

    assessments: dict[str, TrustAssessment] = {}
    breakdown_by_claim: dict[str, dict[str, Decimal]] = {}
    weights = policy.score_weights
    denom = sum(weights.values()) if weights else Decimal("1")
    if denom <= 0:
        denom = Decimal("1")

    for claim_id in sorted(claims_by_id):
        claim = claims_by_id[claim_id]
        doc_trust = _aggregate_doc_trust(claim, doc_trust_by_doc_version, policy.default_doc_trust)
        density = _evidence_density(
            claim,
            fragment_anchor_kind_by_id=fragment_anchor_kind_by_id,
            divisor=policy.evidence_density_divisor,
        )

        extractor_id = extractor_id_by_claim.get(claim_id)
        if extractor_id is not None:
            extractor_score = policy.extractor_reliability.get(
                extractor_id, policy.default_claim_trust
            )
        else:
            agent_id = agent_id_by_claim.get(claim_id)
            extractor_score = policy.agent_reliability.get(
                agent_id or "", policy.default_claim_trust
            )

        consensus = consensus_by_claim.get(claim_id, Decimal("0.50"))
        score_total = _quantize(
            (
                weights.get("doc_trust", Decimal("0")) * doc_trust
                + weights.get("evidence_density", Decimal("0")) * density
                + weights.get("extractor_reliability", Decimal("0")) * extractor_score
                + weights.get("consensus", Decimal("0")) * consensus
            )
            / denom
        )

        breakdown = {
            "consensus": _quantize(consensus),
            "doc_trust": _quantize(doc_trust),
            "evidence_density": _quantize(density),
            "extractor_reliability": _quantize(extractor_score),
        }
        tier = _tier(score_total)
        rationale = [
            {"feature": "doc_trust", "value": str(breakdown["doc_trust"])},
            {"feature": "evidence_density", "value": str(breakdown["evidence_density"])},
            {
                "feature": "extractor_reliability",
                "value": str(breakdown["extractor_reliability"]),
            },
            {"feature": "consensus", "value": str(breakdown["consensus"])},
        ]
        features = {
            "citations_count": len(claim.citations),
            "extractor_id": extractor_id or "unknown",
            "agent_id": agent_id_by_claim.get(claim_id, "unknown"),
            "doc_trust": str(breakdown["doc_trust"]),
            "evidence_density": str(breakdown["evidence_density"]),
            "extractor_reliability": str(breakdown["extractor_reliability"]),
            "consensus": str(breakdown["consensus"]),
        }
        props = {"value_signature_v1": value_signature_v1(claim)}
        id_payload = {
            "policy_id": policy_id,
            "algorithm_version": algorithm_version,
            "target_world_id": claim_id,
            "score": score_total,
            "tier": tier.value,
            "features": features,
            "rationale": rationale,
            "props": props,
        }
        assessment = TrustAssessment(
            trust_assessment_id=trust_assessment_id_from_payload(payload=id_payload),
            policy_id=policy_id,
            algorithm_version=algorithm_version,
            target_world_id=claim_id,
            score=score_total,
            tier=tier,
            features=features,
            rationale=rationale,
            props=props,
        )
        assessments[claim_id] = assessment
        breakdown_by_claim[claim_id] = breakdown

    return assessments, breakdown_by_claim


__all__ = ["score_claim_trust_assessments"]
