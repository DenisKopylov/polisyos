"""Public conflicts score docs module API."""
from __future__ import annotations

from datetime import timezone
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlparse

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.claims.persist import load_doc_meta
from polisyos.ir.world.ids import trust_assessment_id_from_payload
from polisyos.ir.world.trust import TrustAssessment, TrustTier

from .policies import ConflictPolicy

_Q4 = Decimal("0.0001")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_Q4, rounding=ROUND_HALF_UP)


def _freshness_score(days: int) -> Decimal:
    if days <= 7:
        return Decimal("1.00")
    if days <= 30:
        return Decimal("0.85")
    if days <= 90:
        return Decimal("0.70")
    if days <= 180:
        return Decimal("0.55")
    return Decimal("0.40")


def _tier(score: Decimal) -> TrustTier:
    if score >= Decimal("0.75"):
        return TrustTier.HIGH
    if score >= Decimal("0.55"):
        return TrustTier.MEDIUM
    return TrustTier.LOW


def _host_suffix(canonical_url: str | None) -> str | None:
    if canonical_url is None:
        return None
    host = urlparse(canonical_url).hostname
    if not host:
        return None
    parts = host.split(".")
    if len(parts) < 2:
        return None
    return "." + parts[-1]


def score_doc_trust_assessments(
    *,
    cas: FileSystemCAS,
    doc_meta_artifact_ids: list[str],
    policy: ConflictPolicy,
    policy_id: str,
    algorithm_version: str,
) -> dict[str, TrustAssessment]:
    """Score doc trust assessments helper."""
    unique_artifacts = sorted(set(doc_meta_artifact_ids))
    if not unique_artifacts:
        return {}

    metas = [load_doc_meta(cas, artifact_id) for artifact_id in unique_artifacts]
    reference_time = max(meta.retrieved_at for meta in metas)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)

    assessments: dict[str, TrustAssessment] = {}
    for meta in metas:
        source_type = str(meta.props.get("source_type", "")).strip().lower()
        source_score = policy.source_type_weights.get(
            source_type, policy.default_doc_trust
        )

        suffix = _host_suffix(meta.canonical_url)
        host_score = (
            policy.host_suffix_weights.get(suffix, policy.default_doc_trust)
            if suffix is not None
            else policy.default_doc_trust
        )

        license_value = (meta.license or "").strip().lower()
        license_score = policy.license_weights.get(license_value, policy.default_doc_trust)

        retrieved_at = meta.retrieved_at
        if retrieved_at.tzinfo is None:
            retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)
        freshness_days = int((reference_time - retrieved_at).total_seconds() // 86_400)
        freshness = _freshness_score(max(0, freshness_days))

        score = _quantize((source_score + host_score + license_score + freshness) / Decimal("4"))
        tier = _tier(score)

        rationale = [
            {"feature": "source_type", "value": source_type or "unknown"},
            {"feature": "host_suffix", "value": suffix or "unknown"},
            {"feature": "license", "value": license_value or "unknown"},
            {"feature": "freshness_days", "value": freshness_days},
        ]
        features = {
            "source_type": source_type or "unknown",
            "host_suffix": suffix or "unknown",
            "license": license_value or "unknown",
            "freshness_days": freshness_days,
            "source_score": str(_quantize(source_score)),
            "host_score": str(_quantize(host_score)),
            "license_score": str(_quantize(license_score)),
            "freshness_score": str(_quantize(freshness)),
        }
        props = {"reference_time": reference_time.isoformat().replace("+00:00", "Z")}
        id_payload = {
            "policy_id": policy_id,
            "algorithm_version": algorithm_version,
            "target_world_id": meta.doc_version_id,
            "score": score,
            "tier": tier.value,
            "features": features,
            "rationale": rationale,
            "props": props,
        }
        assessment = TrustAssessment(
            trust_assessment_id=trust_assessment_id_from_payload(payload=id_payload),
            policy_id=policy_id,
            algorithm_version=algorithm_version,
            target_world_id=meta.doc_version_id,
            score=score,
            tier=tier,
            features=features,
            rationale=rationale,
            props=props,
        )
        assessments[meta.doc_version_id] = assessment

    return assessments


__all__ = ["score_doc_trust_assessments"]
