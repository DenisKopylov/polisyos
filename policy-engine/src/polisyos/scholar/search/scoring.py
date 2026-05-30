"""Source-quality, anti-SEO, and snippet relevance heuristics."""

from __future__ import annotations

import math
import re
import urllib.parse
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from polisyos.scholar.search.models import FetchResult, SourceMetadata, SourceSnippet, WebSearchHit

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

_QUALITY_DOMAIN_BOOSTS = {
    ".gov": 0.40,
    ".edu": 0.35,
    ".org": 0.12,
    "who.int": 0.42,
    "oecd.org": 0.38,
    "worldbank.org": 0.38,
    "imf.org": 0.36,
    "europa.eu": 0.36,
}

_SEO_SPAM_TERMS = [
    "best",
    "coupon",
    "promo",
    "cheap",
    "casino",
    "login",
    "signup",
    "top 10",
    "ultimate guide",
    "sponsored",
]

_NEGATION_TERMS = {"not", "no", "without", "decline", "decrease", "fell", "lower"}
_POSITIVE_TERMS = {"increase", "improve", "raise", "growth", "higher", "expand"}


def score_search_hit(hit: WebSearchHit) -> float:
    """Estimate source usefulness before fetch using ranking + domain/source heuristics."""
    domain = urllib.parse.urlparse(str(hit.url)).hostname or ""
    rank_score = 1.0 / math.log2(hit.rank + 2.0)
    quality = rank_score + _domain_quality_boost(domain)
    if hit.source_type in {"government", "academic", "law"}:
        quality += 0.20
    quality -= anti_seo_score(str(hit.url), title=hit.title, text=hit.snippet)
    return round(max(0.0, quality), 6)


def build_source_metadata(
    *,
    source_id: str,
    hit: WebSearchHit,
    fetch: FetchResult,
    duplicate_of_source_id: str | None = None,
) -> SourceMetadata:
    domain = urllib.parse.urlparse(str(hit.url)).hostname or ""
    published_at = hit.published_at
    page_age_days: int | None = None
    if published_at is not None:
        page_age_days = max(
            0,
            int((datetime.now(UTC) - published_at).total_seconds() // 86400),
        )
    anti_seo = anti_seo_score(str(hit.url), title=fetch.title or hit.title, text=fetch.text)
    quality = max(
        0.0,
        score_search_hit(hit)
        + _domain_quality_boost(domain)
        + (0.15 if not fetch.paywalled else -0.3)
        - anti_seo,
    )
    return SourceMetadata(
        source_id=source_id,
        url=hit.url,
        title=fetch.title or hit.title,
        domain=domain,
        source_type=fetch.source_type or hit.source_type,
        provider=hit.provider,
        search_query=hit.query,
        search_rank=hit.rank,
        fetched_at=fetch.fetched_at,
        published_at=published_at,
        page_age_days=page_age_days,
        fetch_status=fetch.status,
        content_type=fetch.content_type,
        content_sha256=fetch.content_sha256,
        publication_tier=_publication_tier_for_source(hit.source_type, domain),
        underlying_study_id=fetch.content_sha256,
        quality_score=round(quality, 6),
        anti_seo_score=round(anti_seo, 6),
        duplicate_of_source_id=duplicate_of_source_id,
        paywalled=fetch.paywalled,
        error=fetch.error,
    )


def detect_duplicate_source_id(
    *,
    seen_by_hash: dict[str, str],
    fetch: FetchResult,
) -> str | None:
    """Return canonical source ID if the fetched payload is a duplicate."""
    if not fetch.content_sha256:
        return None
    return seen_by_hash.get(fetch.content_sha256)


def source_rank_key(source: SourceMetadata) -> tuple[float, float, int]:
    """Sort better sources first."""
    return (
        -source.quality_score,
        source.anti_seo_score,
        source.page_age_days if source.page_age_days is not None else 10_000,
    )


def compress_page_to_snippets(
    *,
    source_id: str,
    url: str,
    text: str,
    query_node_id: str,
    perspective: str,
    query_terms: Sequence[str],
    max_snippets: int = 3,
    window_chars: int = 480,
) -> list[SourceSnippet]:
    """Extract top text windows around query terms and return stable citation spans."""
    if not text.strip():
        return []

    lowered = text.lower()
    scored_windows: list[tuple[float, int, int]] = []
    for term in dict.fromkeys(term.lower().strip() for term in query_terms if term.strip()):
        start = 0
        while True:
            idx = lowered.find(term, start)
            if idx < 0:
                break
            left = max(0, idx - window_chars // 2)
            right = min(len(text), left + window_chars)
            left = max(0, right - window_chars)
            window = text[left:right]
            score = _lexical_overlap(window, query_terms) + min(len(term) / 12.0, 1.0)
            scored_windows.append((score, left, right))
            start = idx + max(1, len(term))

    if not scored_windows:
        right = min(len(text), window_chars)
        scored_windows.append((_lexical_overlap(text[:right], query_terms), 0, right))

    snippets: list[SourceSnippet] = []
    occupied: list[tuple[int, int]] = []
    for score, left, right in sorted(scored_windows, key=lambda item: (-item[0], item[1])):
        if any(
            not (right <= used_left or left >= used_right) for used_left, used_right in occupied
        ):
            continue
        snippet_id = f"snip.{source_id}.{len(snippets) + 1}"
        snippets.append(
            SourceSnippet(
                snippet_id=snippet_id,
                source_id=source_id,
                url=url,
                query_node_id=query_node_id,
                perspective=perspective,
                text=text[left:right].strip(),
                start_char=left,
                end_char=right,
                relevance_score=round(max(score, 0.0), 6),
            )
        )
        occupied.append((left, right))
        if len(snippets) >= max_snippets:
            break
    return snippets


def lexical_support_score(claim_text: str, snippet_text: str) -> float:
    """Score claim/snippet overlap using token Jaccard similarity."""
    claim_terms = _tokenize(claim_text)
    snippet_terms = _tokenize(snippet_text)
    if not claim_terms or not snippet_terms:
        return 0.0
    overlap = len(set(claim_terms) & set(snippet_terms))
    union = len(set(claim_terms) | set(snippet_terms))
    return overlap / max(union, 1)


def detect_conflict_score(
    claim_text: str, snippet_texts: Iterable[str]
) -> tuple[float, str | None]:
    """Return a simple contradiction score and uncertainty note for mixed-polarity evidence."""
    claim_polarity = _polarity(claim_text)
    snippet_polarities = [_polarity(text) for text in snippet_texts]
    counts = Counter(snippet_polarities)
    if counts[1] and counts[-1]:
        return 0.75, "Evidence snippets contain both positive and negative directional language."
    if claim_polarity != 0 and counts[-claim_polarity]:
        return (
            0.5,
            "At least one source snippet appears directionally inconsistent with the claim text.",
        )
    return 0.0, None


def anti_seo_score(url: str, *, title: str, text: str) -> float:
    """Penalize SEO spam, doorway pages, and low-signal marketing content."""
    combined = f"{url} {title} {text[:5000]}".lower()
    score = 0.0
    score += 0.1 * sum(1 for term in _SEO_SPAM_TERMS if term in combined)
    if re.search(r"/(tag|category|search|author)/", url.lower()):
        score += 0.25
    if combined.count("!") >= 6:
        score += 0.15
    words = re.findall(r"[a-z0-9]{3,}", title.lower())
    if len(words) >= 8:
        repeated = sum(1 for count in Counter(words).values() if count >= 2)
        score += min(0.35, 0.08 * repeated)
    return round(min(score, 1.0), 6)


def _domain_quality_boost(domain: str) -> float:
    domain = domain.lower()
    score = 0.0
    for suffix, boost in _QUALITY_DOMAIN_BOOSTS.items():
        if domain == suffix or domain.endswith(suffix):
            score = max(score, boost)
    return score


def _publication_tier_for_source(source_type: str, domain: str) -> str:
    normalized = source_type.strip().casefold()
    if normalized in {"academic", "journal", "peer_reviewed", "systematic_review"}:
        return "peer_reviewed"
    if normalized in {"working_paper", "preprint"}:
        return "working_paper"
    if normalized in {"government", "law"} or domain.endswith(".gov"):
        return "government_report"
    return "grey_literature"


def _lexical_overlap(text: str, query_terms: Sequence[str]) -> float:
    text_terms = set(_tokenize(text))
    query = [term.lower().strip() for term in query_terms if term.strip()]
    if not text_terms or not query:
        return 0.0
    return sum(1 for term in query if term in text_terms) / len(query)


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[\w'-]+", text.lower()) if len(token) >= 3]


def _polarity(text: str) -> int:
    terms = set(_tokenize(text))
    pos = len(terms & _POSITIVE_TERMS)
    neg = len(terms & _NEGATION_TERMS)
    if pos > neg:
        return 1
    if neg > pos:
        return -1
    return 0


__all__ = [
    "anti_seo_score",
    "build_source_metadata",
    "compress_page_to_snippets",
    "detect_conflict_score",
    "detect_duplicate_source_id",
    "lexical_support_score",
    "score_search_hit",
    "source_rank_key",
]
