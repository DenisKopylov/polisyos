"""Deterministic source-quality scoring for deep-research evidence bundles."""

from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scholar.search.models import SourceMetadata, SourceQualitySignal, WebEvidenceBundle

ClaimFamily = Literal[
    "recommendation",
    "factual",
    "empirical",
    "numerical",
    "causal",
    "legal",
    "normative",
    "forecast",
    "distributional",
    "welfare",
    "implementation",
    "caveat",
]
SourceClass = Literal["primary", "academic", "institutional", "news", "web"]
SourceInvalidationType = Literal[
    "none",
    "stale",
    "withdrawn",
    "contradicted",
    "unavailable",
    "superseded",
]
SourceInvalidationState = Literal["publishable", "stale", "review", "withdraw"]
SourceFreshnessState = Literal["fresh", "stale", "unknown"]
SourceConflictLevel = Literal["none", "minor", "material", "blocking"]
ScoreCalibration = Literal["advisory"]

SOURCE_QUALITY_REPORT_SCHEMA_VERSION = "policyos.scientist.source_quality_report.v1"

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
_NEWS_SOURCE_TYPES = {"news", "press", "media"}
_SCORE_CALIBRATION_REASON = "score_calibration:advisory_v1"
_ADVISORY_SCORE_WEIGHTS = {
    "authority": 0.32,
    "freshness": 0.22,
    "primary_source": 0.22,
    "anti_seo": 0.16,
    "independent": 0.08,
}
_FRESHNESS_TTL_DAYS: dict[str, dict[SourceClass, int]] = {
    "recommendation": {
        "primary": 730,
        "academic": 1095,
        "institutional": 365,
        "news": 90,
        "web": 180,
    },
    "empirical": {
        "primary": 730,
        "academic": 1095,
        "institutional": 365,
        "news": 90,
        "web": 180,
    },
    "numerical": {
        "primary": 365,
        "academic": 730,
        "institutional": 180,
        "news": 30,
        "web": 90,
    },
    "causal": {
        "primary": 730,
        "academic": 1825,
        "institutional": 365,
        "news": 60,
        "web": 90,
    },
    "normative": {
        "primary": 3650,
        "academic": 1825,
        "institutional": 1095,
        "news": 90,
        "web": 180,
    },
    "forecast": {
        "primary": 180,
        "academic": 365,
        "institutional": 90,
        "news": 30,
        "web": 45,
    },
    "distributional": {
        "primary": 365,
        "academic": 1095,
        "institutional": 180,
        "news": 60,
        "web": 90,
    },
    "implementation": {
        "primary": 365,
        "academic": 365,
        "institutional": 180,
        "news": 60,
        "web": 90,
    },
    "caveat": {
        "primary": 365,
        "academic": 730,
        "institutional": 180,
        "news": 90,
        "web": 180,
    },
}
_CLAIM_FAMILY_ALIASES: dict[str, str] = {
    "claim": "empirical",
    "empirical": "empirical",
    "evidence": "empirical",
    "fact": "empirical",
    "factual": "empirical",
    "legal": "normative",
    "normative": "normative",
    "statute": "normative",
    "statutory": "normative",
    "compliance": "normative",
    "welfare": "causal",
    "cost_benefit": "causal",
    "benefit_cost": "causal",
    "equity": "distributional",
    "distribution": "distributional",
    "distributional": "distributional",
}
_DEFAULT_FRESHNESS_TTL_DAYS: dict[SourceClass, int] = {
    "primary": 365,
    "academic": 730,
    "institutional": 180,
    "news": 60,
    "web": 90,
}
_INVALIDATION_STATES: dict[str, SourceInvalidationState] = {
    "none": "publishable",
    "stale": "stale",
    "withdrawn": "withdraw",
    "contradicted": "review",
    "unavailable": "review",
    "superseded": "review",
}
_CONFLICT_STATES: dict[str, SourceInvalidationState] = {
    "none": "publishable",
    "minor": "publishable",
    "material": "review",
    "blocking": "review",
}
_STATE_PRIORITY: dict[SourceInvalidationState, int] = {
    "publishable": 0,
    "stale": 1,
    "review": 2,
    "withdraw": 3,
}


class SourceQualityAssessment(BaseModel):
    """Decision-facing source-quality assessment with explicit advisory scoring."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    claim_family: str
    source_class: SourceClass
    score_calibration: ScoreCalibration = "advisory"
    overall_quality_score: float = Field(ge=0.0, le=1.0)
    freshness_ttl_days: int = Field(ge=1)
    freshness_state: SourceFreshnessState
    invalidation_state: SourceInvalidationState
    publishable: bool
    independent_evidence: bool
    duplicate_of_source_id: str | None = None
    conflict_level: SourceConflictLevel = "none"
    quality_signal: SourceQualitySignal
    reasons: list[str] = Field(default_factory=list)


def score_web_evidence_bundle_sources(bundle: WebEvidenceBundle) -> list[SourceQualitySignal]:
    """Return one heuristic quality signal per source in a bundle."""

    return [score_source_quality(source) for source in bundle.sources]


def score_source_quality(
    source: SourceMetadata,
    *,
    now: datetime | None = None,
) -> SourceQualitySignal:
    """Score source authority, freshness and anti-SEO posture without claiming truth."""

    clock = now or datetime.now(UTC)
    domain = source.domain or urllib.parse.urlparse(str(source.url)).hostname or ""
    source_type = _normalize_token(source.source_type)
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
    reasons.append(_SCORE_CALIBRATION_REASON)

    return SourceQualitySignal(
        source_id=source.source_id,
        authority_score=round(max(0.0, min(1.0, authority)), 6),
        freshness_score=round(max(0.0, min(1.0, freshness)), 6),
        primary_source_score=round(max(0.0, min(1.0, primary)), 6),
        anti_seo_score=round(anti_seo, 6),
        duplicate_score=duplicate,
        reasons=sorted(dict.fromkeys(reasons)),
    )


def evaluate_source_quality(
    source: SourceMetadata,
    *,
    claim_family: str,
    now: datetime | None = None,
    invalidation_type: str | None = None,
    conflict_level: SourceConflictLevel = "none",
) -> SourceQualityAssessment:
    """Return the decision-facing source quality posture for one claim/source pair."""

    clock = now or datetime.now(UTC)
    signal = score_source_quality(source, now=clock)
    source_class = classify_source_class(source)
    ttl_days = source_freshness_ttl_days(claim_family, source_class)
    freshness_state = _freshness_state(source, ttl_days=ttl_days, now=clock)
    invalidation_state = source_invalidation_state(invalidation_type)
    conflict_state = _conflict_invalidation_state(conflict_level)
    reasons = list(signal.reasons)

    if freshness_state == "stale":
        invalidation_state = _stricter_state(invalidation_state, "stale")
        reasons.append(f"freshness_ttl_exceeded:{ttl_days}")
    elif freshness_state == "unknown":
        reasons.append("freshness_ttl_unassessed")

    if invalidation_type:
        normalized_invalidation = _normalize_token(invalidation_type)
        reasons.append(f"source_invalidation:{normalized_invalidation}")
        if normalized_invalidation == "withdrawn":
            reasons.append("withdrawn_source_blocks_publication")
            if source_class == "primary":
                reasons.append("withdrawn_primary_source_blocks_publication")

    if conflict_level == "minor":
        reasons.append("minor_source_conflict_advisory")
    elif conflict_level == "material":
        reasons.append("material_source_conflict_requires_review")
    elif conflict_level == "blocking":
        reasons.append("blocking_source_conflict_requires_review")

    invalidation_state = _stricter_state(invalidation_state, conflict_state)
    duplicate = bool(source.duplicate_of_source_id)
    if duplicate:
        reasons.append("duplicate_not_independent_evidence")

    return SourceQualityAssessment(
        source_id=source.source_id,
        claim_family=_normalize_claim_family(claim_family),
        source_class=source_class,
        overall_quality_score=advisory_quality_score(signal),
        freshness_ttl_days=ttl_days,
        freshness_state=freshness_state,
        invalidation_state=invalidation_state,
        publishable=invalidation_state == "publishable",
        independent_evidence=(invalidation_state == "publishable" and not duplicate),
        duplicate_of_source_id=source.duplicate_of_source_id,
        conflict_level=conflict_level,
        quality_signal=signal,
        reasons=sorted(dict.fromkeys(reasons)),
    )


def build_source_quality_report(
    *,
    sources: Sequence[Mapping[str, Any] | SourceMetadata],
    claim_families: Sequence[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a deterministic report for source authority, freshness, and invalidation."""

    clock = now or datetime.now(UTC)
    families = [_normalize_claim_family(family) for family in (claim_families or [])]
    claim_family = families[0] if families else "recommendation"
    assessments: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    for index, item in enumerate(sources):
        source = _coerce_source_metadata(item, index=index)
        if source is None:
            issues.append(
                _source_quality_issue(
                    code="source_quality_source_unreadable",
                    severity="fail",
                    source_id=f"source_{index + 1}",
                    message="Source quality input could not be normalized to source metadata.",
                    next_action="Persist source_id, url, domain, and source_type for each evidence source.",
                )
            )
            continue
        raw = item if isinstance(item, Mapping) else {}
        assessment = evaluate_source_quality(
            source,
            claim_family=claim_family,
            now=clock,
            invalidation_type=_source_invalidation_type(raw),
            conflict_level=_source_conflict_level(raw),
        )
        assessments.append(assessment.model_dump(mode="json"))
        if not assessment.publishable:
            issues.append(
                _source_quality_issue(
                    code="source_quality_not_publishable",
                    severity="fail",
                    source_id=assessment.source_id,
                    message=(
                        f"Source {assessment.source_id} is in "
                        f"{assessment.invalidation_state} state for {assessment.claim_family} claims."
                    ),
                    next_action=(
                        "Replace withdrawn/blocked sources, refresh stale sources, "
                        "or route the claim for human review."
                    ),
                    invalidation_state=assessment.invalidation_state,
                    source_class=assessment.source_class,
                )
            )
        elif not assessment.independent_evidence:
            issues.append(
                _source_quality_issue(
                    code="source_quality_duplicate_not_independent",
                    severity="warn",
                    source_id=assessment.source_id,
                    message=(
                        f"Source {assessment.source_id} duplicates "
                        f"{assessment.duplicate_of_source_id} and cannot add independent evidence."
                    ),
                    next_action="Deduplicate sources before counting independent evidence hits.",
                    duplicate_of_source_id=assessment.duplicate_of_source_id,
                )
            )
        elif assessment.freshness_state == "unknown":
            issues.append(
                _source_quality_issue(
                    code="source_quality_freshness_unknown",
                    severity="warn",
                    source_id=assessment.source_id,
                    message=f"Source {assessment.source_id} has no machine-readable freshness timestamp.",
                    next_action="Attach published_at, fetched_at, or page_age_days for source freshness review.",
                    source_class=assessment.source_class,
                )
            )

    return {
        "schema_version": SOURCE_QUALITY_REPORT_SCHEMA_VERSION,
        "status": _source_quality_status(issues),
        "score_calibration": "advisory",
        "claim_families": sorted(dict.fromkeys(families or [claim_family])),
        "assessments": assessments,
        "issues": issues,
        "blocking_issue_count": sum(1 for issue in issues if issue.get("severity") == "fail"),
        "summary": {
            "source_count": len(assessments),
            "publishable_source_count": sum(
                1 for assessment in assessments if assessment.get("publishable") is True
            ),
            "independent_source_count": sum(
                1 for assessment in assessments if assessment.get("independent_evidence") is True
            ),
        },
    }


def classify_source_class(source: SourceMetadata) -> SourceClass:
    """Map source metadata into the freshness/authority calibration classes."""

    domain = source.domain or urllib.parse.urlparse(str(source.url)).hostname or ""
    normalized_domain = domain.lower()
    source_type = _normalize_token(source.source_type)
    if source_type in _PRIMARY_SOURCE_TYPES or normalized_domain.endswith(".gov"):
        return "primary"
    if source_type in _SECONDARY_SOURCE_TYPES or normalized_domain.endswith(".edu"):
        return "academic"
    if source_type in _NEWS_SOURCE_TYPES:
        return "news"
    if _authority_score(domain) >= 0.75 or normalized_domain.endswith(".org"):
        return "institutional"
    return "web"


def source_freshness_ttl_days(claim_family: str, source_class: str) -> int:
    """Return the freshness TTL for a claim family and source class."""

    normalized_family = _normalize_claim_family(claim_family)
    normalized_class = _normalize_source_class(source_class)
    family_policy = _FRESHNESS_TTL_DAYS.get(normalized_family)
    if family_policy is not None:
        return family_policy.get(
            normalized_class,
            _DEFAULT_FRESHNESS_TTL_DAYS[normalized_class],
        )
    return _DEFAULT_FRESHNESS_TTL_DAYS[normalized_class]


def source_invalidation_state(invalidation_type: str | None) -> SourceInvalidationState:
    """Map a source invalidation signal to decision-validity state semantics."""

    normalized = _normalize_token(invalidation_type or "none")
    return _INVALIDATION_STATES.get(normalized, "review")


def advisory_quality_score(signal: SourceQualitySignal) -> float:
    """Combine component scores into a transparent advisory score."""

    independent_score = 1.0 - signal.duplicate_score
    score = (
        signal.authority_score * _ADVISORY_SCORE_WEIGHTS["authority"]
        + signal.freshness_score * _ADVISORY_SCORE_WEIGHTS["freshness"]
        + signal.primary_source_score * _ADVISORY_SCORE_WEIGHTS["primary_source"]
        + signal.anti_seo_score * _ADVISORY_SCORE_WEIGHTS["anti_seo"]
        + independent_score * _ADVISORY_SCORE_WEIGHTS["independent"]
    )
    return round(max(0.0, min(1.0, score)), 6)


def _authority_score(domain: str) -> float:
    normalized = domain.lower().strip(".")
    score = 0.35
    for suffix, value in _AUTHORITY_DOMAINS.items():
        clean_suffix = suffix.strip(".")
        if normalized == clean_suffix or normalized.endswith(f".{clean_suffix}"):
            score = max(score, value)
    return score


def _freshness_score(source: SourceMetadata, *, now: datetime) -> float:
    age_days = _source_age_days(source, now=now)
    if age_days is None:
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


def _freshness_state(
    source: SourceMetadata,
    *,
    ttl_days: int,
    now: datetime,
) -> SourceFreshnessState:
    age_days = _source_age_days(source, now=now)
    if age_days is None:
        return "unknown"
    return "fresh" if age_days <= ttl_days else "stale"


def _source_age_days(source: SourceMetadata, *, now: datetime) -> int | None:
    if source.page_age_days is not None:
        return max(0, source.page_age_days)
    timestamp = source.published_at or source.fetched_at
    if timestamp is None:
        return None
    clock = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    observed_at = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=UTC)
    return max(0, int((clock - observed_at).total_seconds() // 86_400))


def _conflict_invalidation_state(conflict_level: SourceConflictLevel) -> SourceInvalidationState:
    return _CONFLICT_STATES[conflict_level]


def _stricter_state(
    left: SourceInvalidationState,
    right: SourceInvalidationState,
) -> SourceInvalidationState:
    return left if _STATE_PRIORITY[left] >= _STATE_PRIORITY[right] else right


def _normalize_claim_family(claim_family: str) -> str:
    normalized = _normalize_token(claim_family) or "recommendation"
    return _CLAIM_FAMILY_ALIASES.get(normalized, normalized)


def _coerce_source_metadata(
    item: Mapping[str, Any] | SourceMetadata,
    *,
    index: int,
) -> SourceMetadata | None:
    if isinstance(item, SourceMetadata):
        return item
    if not isinstance(item, Mapping):
        return None
    source_id = _source_id(item, index=index)
    url = _source_url(item, source_id=source_id)
    domain = _source_domain(item, url=url)
    source_type = _source_type(item)
    try:
        return SourceMetadata(
            source_id=source_id,
            url=url,
            title=str(item.get("title") or item.get("name") or ""),
            domain=domain,
            source_type=source_type,
            provider=str(item.get("provider") or ""),
            search_query=str(item.get("search_query") or ""),
            search_rank=int(item.get("search_rank") or 0),
            fetched_at=item.get("fetched_at") if isinstance(item.get("fetched_at"), datetime) else None,
            published_at=(
                item.get("published_at") if isinstance(item.get("published_at"), datetime) else None
            ),
            page_age_days=_optional_int(item.get("page_age_days") or item.get("age_days")),
            fetch_status=str(item.get("fetch_status") or item.get("status") or "ok"),
            content_type=str(item.get("content_type") or "application/octet-stream"),
            content_sha256=(
                str(item.get("content_sha256")) if item.get("content_sha256") else None
            ),
            quality_score=float(item.get("quality_score") or 0.0),
            anti_seo_score=float(item.get("anti_seo_score") or 0.0),
            duplicate_of_source_id=(
                str(item.get("duplicate_of_source_id"))
                if item.get("duplicate_of_source_id")
                else None
            ),
            paywalled=bool(item.get("paywalled") or False),
            error=str(item.get("error") or ""),
        )
    except Exception:
        return None


def _source_id(item: Mapping[str, Any], *, index: int) -> str:
    for key in (
        "source_id",
        "norm_id",
        "id",
        "data_snapshot_ref",
        "artifact_id",
        "url",
        "source_family",
    ):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return f"source_{index + 1}"


def _source_url(item: Mapping[str, Any], *, source_id: str) -> str:
    for key in ("url", "final_url", "canonical_url"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    safe_id = urllib.parse.quote(source_id, safe="")
    return f"https://policyos.example/sources/{safe_id}"


def _source_domain(item: Mapping[str, Any], *, url: str) -> str:
    domain = str(item.get("domain") or item.get("host") or "").strip()
    if domain:
        return domain
    return urllib.parse.urlparse(url).hostname or "policyos.example"


def _source_type(item: Mapping[str, Any]) -> str:
    source_type = _normalize_token(str(item.get("source_type") or item.get("source_kind") or ""))
    if source_type:
        return source_type
    if item.get("norm_id"):
        return "law"
    if item.get("source_family"):
        return "official"
    return "web"


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _source_invalidation_type(item: Mapping[str, Any]) -> str | None:
    if not isinstance(item, Mapping):
        return None
    for key in ("invalidation_type", "source_invalidation", "validity_state"):
        value = _normalize_token(str(item.get(key) or ""))
        if value:
            return value
    if item.get("withdrawn") is True:
        return "withdrawn"
    if item.get("superseded") is True:
        return "superseded"
    return None


def _source_conflict_level(item: Mapping[str, Any]) -> SourceConflictLevel:
    value = _normalize_token(str(item.get("conflict_level") or "none"))
    if value in {"none", "minor", "material", "blocking"}:
        return value  # type: ignore[return-value]
    return "none"


def _source_quality_issue(
    *,
    code: str,
    severity: str,
    source_id: str,
    message: str,
    next_action: str,
    **extra: object,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "layer": "scientist_policy_artifacts",
        "phase": "source_quality",
        "source_id": source_id,
        "message": message,
        "next_action": next_action,
        **extra,
    }


def _source_quality_status(issues: Sequence[Mapping[str, Any]]) -> str:
    if any(issue.get("severity") == "fail" for issue in issues):
        return "fail"
    if any(issue.get("severity") == "warn" for issue in issues):
        return "warn"
    return "pass"


def _normalize_source_class(source_class: str) -> SourceClass:
    normalized = _normalize_token(source_class)
    if normalized in {"primary", "official", "government", "law", "statute", "regulation"}:
        return "primary"
    if normalized in {"academic", "journal", "working_paper", "research"}:
        return "academic"
    if normalized in {"institutional", "nonprofit", "ngo", "organization"}:
        return "institutional"
    if normalized in _NEWS_SOURCE_TYPES:
        return "news"
    return "web"


def _normalize_token(value: str | None) -> str:
    return str(value or "").strip().lower().replace("-", "_")


__all__ = [
    "SOURCE_QUALITY_REPORT_SCHEMA_VERSION",
    "SourceQualityAssessment",
    "advisory_quality_score",
    "build_source_quality_report",
    "classify_source_class",
    "evaluate_source_quality",
    "score_source_quality",
    "score_web_evidence_bundle_sources",
    "source_freshness_ttl_days",
    "source_invalidation_state",
]
