"""Deterministic source-quality scoring for deep-research evidence bundles."""

from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime

from polisyos.scholar.search.models import SourceMetadata, SourceQualitySignal, WebEvidenceBundle

_AUTHORITY_DOMAINS: dict[str, float] = {
    ".gov": 0.95,
    ".edu": 0.85,
    "europa.eu": 0.95,
    "who.int": 0.95,
    "oecd.org": 0.9,
    "worldbank.org": 0.88,
    "imf.org": 0.86,
    "un.org": 0.86,
}
_PRIMARY_SOURCE_TYPES = {"government", "law", "statute", "regulation", "official"}
_SECONDARY_SOURCE_TYPES = {"academic", "journal", "working_paper"}


def score_web_evidence_bundle_sources(bundle: WebEvidenceBundle) -> list[SourceQualitySignal]:
    """Return one heuristic quality signal per source in a bundle."""

    return [score_source_quality(source) for source in bundle.sources]


def score_source_quality(source: SourceMetadata, *, now: datetime | None = None) -> SourceQualitySignal:
    """Score source authority, freshness and anti-SEO posture without claiming truth."""

    clock = now or datetime.now(UTC)
    domain = source.domain or urllib.parse.urlparse(str(source.url)).hostname or ""
    source_type = source.source_type.lower().strip()
    reasons: list[str] = []

    authority = _authority_score(domain)
    if authority >= 0.85:
        reasons.append("recognized_authoritative_domain")
    elif domain.endswith(".org"):
        authority = max(authority, 0.62)
        reasons.append("nonprofit_or_institutional_domain")
    elif source.quality_score:
        authority = max(authority, min(0.8, source.quality_score))
        reasons.append("inherited_scholar_quality_score")

    primary = 0.25
    if source_type in _PRIMARY_SOURCE_TYPES or domain.endswith(".gov"):
        primary = 0.95
        reasons.append("primary_or_official_source_type")
    elif source_type in _SECONDARY_SOURCE_TYPES or domain.endswith(".edu"):
        primary = 0.72
        reasons.append("research_or_academic_source_type")
    elif source_type in {"news", "web"}:
        primary = 0.4
        reasons.append("general_web_source_type")

    freshness = _freshness_score(source, now=clock)
    if source.page_age_days is not None:
        reasons.append(f"page_age_days:{source.page_age_days}")
    elif source.published_at is None and source.fetched_at is None:
        reasons.append("freshness_unknown")

    anti_seo = max(0.0, min(1.0, 1.0 - float(source.anti_seo_score or 0.0)))
    if anti_seo < 0.75:
        reasons.append("seo_spam_risk")

    duplicate = 1.0 if source.duplicate_of_source_id else 0.0
    if duplicate:
        reasons.append(f"duplicate_of:{source.duplicate_of_source_id}")

    return SourceQualitySignal(
        source_id=source.source_id,
        authority_score=round(max(0.0, min(1.0, authority)), 6),
        freshness_score=round(max(0.0, min(1.0, freshness)), 6),
        primary_source_score=round(max(0.0, min(1.0, primary)), 6),
        anti_seo_score=round(anti_seo, 6),
        duplicate_score=duplicate,
        reasons=sorted(dict.fromkeys(reasons)),
    )


def _authority_score(domain: str) -> float:
    normalized = domain.lower().strip(".")
    score = 0.35
    for suffix, value in _AUTHORITY_DOMAINS.items():
        clean_suffix = suffix.strip(".")
        if normalized == clean_suffix or normalized.endswith(f".{clean_suffix}"):
            score = max(score, value)
    return score


def _freshness_score(source: SourceMetadata, *, now: datetime) -> float:
    if source.page_age_days is not None:
        age_days = max(0, source.page_age_days)
    elif source.published_at is not None:
        age_days = max(0, int((now - source.published_at).total_seconds() // 86_400))
    elif source.fetched_at is not None:
        age_days = max(0, int((now - source.fetched_at).total_seconds() // 86_400))
    else:
        return 0.35
    if age_days <= 30:
        return 1.0
    if age_days <= 365:
        return 0.85
    if age_days <= 1095:
        return 0.65
    if age_days <= 3650:
        return 0.45
    return 0.25


__all__ = [
    "score_source_quality",
    "score_web_evidence_bundle_sources",
]
