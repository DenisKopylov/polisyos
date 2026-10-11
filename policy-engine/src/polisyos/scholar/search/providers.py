"""Search provider interfaces, concrete web providers, and failover routing."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Protocol

import httpx

from polisyos.common.async_tools import run_blocking_async
from polisyos.fabric.connectors import RateLimiter, RetryPolicy
from polisyos.scholar.search.models import (
    ProviderAttemptTrace,
    SearchConstraints,
    WebSearchHit,
    _ProviderTraceErrorType,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.ir.analytics.literature import OpenAlexWorkText


class WebSearchProvider(Protocol):
    """Async interface for one search backend."""

    name: str

    async def search(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float,
    ) -> list[WebSearchHit]:
        """Run one provider query and return normalized search hits."""


@dataclass(frozen=True)
class _ProviderSearchOutcome:
    """Concrete adapter observations kept separate from the public list ABI."""

    hits: tuple[WebSearchHit, ...]
    raw_result_count: int | None
    pre_filter_candidate_count: int | None
    eligible_candidate_count: int | None
    normalization_rejection_counts: tuple[tuple[str, int], ...]
    constraint_rejection_counts: tuple[tuple[str, int], ...]
    diagnostics_available: bool = True


class OpenAlexRateLimiter:
    """OpenAlex-specific wrapper around the shared connector rate limiter."""

    def __init__(self, *, rate_limit_rps: float = 9.0) -> None:
        self._limiter = RateLimiter(
            rate_limit_rps=rate_limit_rps,
            limiter_id="scholar.openalex",
        )

    async def acquire(self) -> None:
        await self._limiter.acquire()


def _provider_error_type(exc: Exception) -> _ProviderTraceErrorType:
    """Return a fixed, value-free category for one provider exception."""
    if isinstance(exc, httpx.HTTPStatusError):
        return "http_status_error"
    if isinstance(exc, httpx.TimeoutException):
        return "timeout_error"
    if isinstance(exc, httpx.ConnectError):
        return "connection_error"
    if isinstance(exc, httpx.RequestError):
        return "request_error"
    if isinstance(exc, (TypeError, ValueError)):
        return "provider_contract_error"
    return "provider_exception"


class ProviderFailoverPolicy:
    """Try providers in priority order and retain each observed attempt."""

    def __init__(self, providers: Sequence[WebSearchProvider]) -> None:
        if not providers:
            raise ValueError("at least one WebSearchProvider is required")
        self._providers = list(providers)

    @property
    def provider_names(self) -> list[str]:
        return [provider.name for provider in self._providers]

    async def search(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float = 10.0,
    ) -> tuple[str, list[WebSearchHit], str | None]:
        """Keep the legacy ``(provider_name, hits, error)`` result shape."""
        provider_name, hits, error, _attempts = await self.search_with_attempts(
            query,
            constraints=constraints,
            max_results=max_results,
            timeout_s=timeout_s,
        )
        return provider_name, hits, error

    async def search_with_attempts(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float = 10.0,
    ) -> tuple[str, list[WebSearchHit], str | None, list[ProviderAttemptTrace]]:
        """Return the legacy selection plus an ordered, source-backed attempt trace.

        Concrete adapters provide exact normalization and constraint counts. A
        third-party implementation of the historical list protocol remains usable,
        but its raw population and filtering cause are explicitly not established.
        """
        last_error: str | None = None
        attempts: list[ProviderAttemptTrace] = []
        for provider in self._providers:
            try:
                diagnostic_search = getattr(provider, "search_with_diagnostics", None)
                if callable(diagnostic_search):
                    observed = await diagnostic_search(
                        query,
                        constraints=constraints,
                        max_results=max_results,
                        timeout_s=timeout_s,
                    )
                    if not isinstance(observed, _ProviderSearchOutcome):
                        raise TypeError(
                            "provider search diagnostics have an invalid shape"
                        )
                    hits = list(observed.hits)
                    if not observed.diagnostics_available:
                        outcome = "returned_hits" if hits else "returned_no_hits"
                        reason = "not_established"
                        raw_result_count = None
                        candidate_count = None
                        eligible_count = None
                        normalization_rejections: dict[str, int] = {}
                        constraint_rejections: dict[str, int] = {}
                    else:
                        raw_result_count = observed.raw_result_count
                        candidate_count = observed.pre_filter_candidate_count
                        eligible_count = observed.eligible_candidate_count
                        normalization_rejections = dict(
                            observed.normalization_rejection_counts
                        )
                        constraint_rejections = dict(
                            observed.constraint_rejection_counts
                        )
                        if hits:
                            outcome = "returned_hits"
                            reason = "provider_returned_hits"
                        elif candidate_count and eligible_count == 0:
                            outcome = "all_candidates_filtered"
                            reason = "all_candidates_filtered"
                        elif normalization_rejections:
                            outcome = "returned_no_hits"
                            reason = "normalization_rejected_candidates"
                        elif raw_result_count is None and not candidate_count:
                            outcome = "returned_no_hits"
                            reason = "not_established"
                        else:
                            outcome = "returned_no_hits"
                            reason = "provider_returned_no_hits"
                else:
                    hits = await provider.search(
                        query,
                        constraints=constraints,
                        max_results=max_results,
                        timeout_s=timeout_s,
                    )
                    outcome = "returned_hits" if hits else "returned_no_hits"
                    reason = "not_established"
                    raw_result_count = None
                    candidate_count = None
                    eligible_count = None
                    normalization_rejections = {}
                    constraint_rejections = {}

                attempts.append(
                    ProviderAttemptTrace(
                        attempt_index=len(attempts),
                        provider=provider.name,
                        outcome=outcome,
                        reason=reason,
                        raw_result_count=raw_result_count,
                        pre_filter_candidate_count=candidate_count,
                        eligible_candidate_count=eligible_count,
                        returned_hit_count=len(hits),
                        normalization_rejection_counts=normalization_rejections,
                        constraint_rejection_counts=constraint_rejections,
                    )
                )
                if not hits:
                    continue
                return provider.name, hits, None, attempts
            except Exception as exc:
                last_error = f"{provider.name}: {exc}"
                attempts.append(
                    ProviderAttemptTrace(
                        attempt_index=len(attempts),
                        provider=provider.name,
                        outcome="error",
                        reason="provider_error",
                        error="provider_error",
                        error_type=_provider_error_type(exc),
                    )
                )
                continue
        return self._providers[-1].name, [], last_error, attempts


class BraveSearchProvider:
    """Query Brave Search's JSON API."""

    name = "brave"

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str = "https://api.search.brave.com/res/v1/web/search",
        user_agent: str = "polisyos-scholar-search/1.0",
    ) -> None:
        if not api_key.strip():
            raise ValueError("BraveSearchProvider requires api_key")
        self._api_key = api_key.strip()
        self._endpoint = endpoint.rstrip("/")
        self._user_agent = user_agent

    async def search(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float,
    ) -> list[WebSearchHit]:
        outcome = await self.search_with_diagnostics(
            query,
            constraints=constraints,
            max_results=max_results,
            timeout_s=timeout_s,
        )
        return list(outcome.hits)

    async def search_with_diagnostics(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float,
    ) -> _ProviderSearchOutcome:
        params = {
            "q": _apply_constraint_query_terms(query, constraints),
            "count": str(max(1, min(int(max_results), 20))),
            "safesearch": "moderate",
            "spellcheck": "1",
        }
        if constraints.locale:
            params["search_lang"] = constraints.locale.split("-", 1)[0].lower()
        if constraints.recency_days is not None:
            params["freshness"] = _brave_freshness(constraints.recency_days)

        url = f"{self._endpoint}?{urllib.parse.urlencode(params)}"
        headers = {
            "Accept": "application/json",
            "User-Agent": self._user_agent,
            "X-Subscription-Token": self._api_key,
        }
        payload = await _read_url_text(url, headers=headers, timeout_s=timeout_s)
        decoded = json.loads(payload or "{}")
        results = decoded.get("web", {}).get("results", []) if isinstance(decoded, dict) else []
        raw_result_count = len(results) if isinstance(results, list) else None
        normalization_rejections: Counter[str] = Counter()
        hits: list[WebSearchHit] = []
        for rank, item in enumerate(results, start=1):
            if not isinstance(item, dict):
                normalization_rejections["result_not_object"] += 1
                continue
            target_url = _coerce_http_url(item.get("url"))
            if target_url is None:
                normalization_rejections["result_url_invalid"] += 1
                continue
            hits.append(
                WebSearchHit(
                    url=target_url,
                    title=str(item.get("title") or ""),
                    snippet=str(item.get("description") or ""),
                    provider=self.name,
                    query=query,
                    rank=rank,
                    source_type=_infer_source_type(
                        target_url,
                        str(item.get("title") or ""),
                        str(item.get("description") or ""),
                    ),
                )
            )
        return _filter_hits_with_diagnostics(
            hits,
            constraints=constraints,
            max_results=max_results,
            raw_result_count=raw_result_count,
            normalization_rejection_counts=dict(normalization_rejections),
        )


@dataclass(frozen=True)
class OpenAlexWorksResult:
    """One actual full provider response with filtered hits and source work custody."""

    query: str
    hits: tuple[WebSearchHit, ...]
    works: tuple[OpenAlexWorkText, ...]
    raw_response: dict[str, object]
    response_sha256: str
    excluded_results: tuple[tuple[int, str], ...]
    raw_result_count: int | None = None
    pre_filter_hit_count: int | None = None
    filter_rejection_counts: tuple[tuple[str, int], ...] = ()
    diagnostics_available: bool = True


class OpenAlexWorksProvider:
    """Query the public OpenAlex works API and normalize works as academic search hits."""

    name = "openalex"

    def __init__(
        self,
        *,
        endpoint: str = "https://api.openalex.org/works",
        mailto: str = "",
        user_agent: str = "polisyos-scholar-search/1.0",
        rate_limiter: OpenAlexRateLimiter | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._mailto = mailto.strip()
        self._user_agent = user_agent
        self._rate_limiter = rate_limiter or OpenAlexRateLimiter()
        self._retry_policy = retry_policy or RetryPolicy(
            max_attempts=3,
            base_delay=0.25,
            backoff_factor=2.0,
            jitter_max=0.1,
            max_delay=2.0,
        )

    async def search(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float,
    ) -> list[WebSearchHit]:
        """Project ordinary search hits from the same complete provider response."""

        result = await self.search_with_works(
            query,
            constraints=constraints,
            max_results=max_results,
            timeout_s=timeout_s,
        )
        return list(result.hits)

    async def search_with_diagnostics(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float,
    ) -> _ProviderSearchOutcome:
        """Project one actual OpenAlex response into list-ABI diagnostics."""
        result = await self.search_with_works(
            query,
            constraints=constraints,
            max_results=max_results,
            timeout_s=timeout_s,
        )
        normalization_rejections = Counter(
            reason for _rank, reason in result.excluded_results
        )
        eligible_count = (
            result.pre_filter_hit_count
            - sum(dict(result.filter_rejection_counts).values())
            if result.pre_filter_hit_count is not None
            else None
        )
        return _ProviderSearchOutcome(
            hits=result.hits,
            raw_result_count=result.raw_result_count,
            pre_filter_candidate_count=result.pre_filter_hit_count,
            eligible_candidate_count=eligible_count,
            normalization_rejection_counts=tuple(
                sorted(normalization_rejections.items())
            ),
            constraint_rejection_counts=result.filter_rejection_counts,
            diagnostics_available=result.diagnostics_available,
        )

    async def search_with_works(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float,
    ) -> OpenAlexWorksResult:
        """Fetch once and preserve complete work content for candidate consumers."""

        from polisyos.ir.analytics.literature import OpenAlexWorkText

        if constraints.source_types and "academic" not in constraints.source_types:
            return OpenAlexWorksResult(
                query, (), (), {}, hashlib.sha256(b"{}").hexdigest(), (),
                diagnostics_available=False,
            )
        search_query = query.strip()
        if not search_query:
            return OpenAlexWorksResult(
                query, (), (), {}, hashlib.sha256(b"{}").hexdigest(), (),
                diagnostics_available=False,
            )
        params = {
            "search": search_query,
            "filter": ",".join(_openalex_filters(constraints)),
            "per-page": str(max(1, min(int(max_results), 50))),
            "select": ",".join(_OPENALEX_SELECT_FIELDS),
        }
        if self._mailto:
            params["mailto"] = self._mailto
        url = f"{self._endpoint}?{urllib.parse.urlencode(params)}"
        headers = {
            "Accept": "application/json",
            "User-Agent": _openalex_user_agent(self._user_agent, self._mailto),
        }
        payload = await _read_openalex_url_text(
            url,
            headers=headers,
            timeout_s=timeout_s,
            rate_limiter=self._rate_limiter,
            retry_policy=self._retry_policy,
        )
        decoded = json.loads(payload or "{}")
        if not isinstance(decoded, dict) or not isinstance(decoded.get("results"), list):
            raise ValueError("openalex_provider_result_population_invalid")
        results = decoded["results"]
        works = []
        excluded = []
        hits: list[WebSearchHit] = []
        for rank, item in enumerate(results, start=1):
            if not isinstance(item, dict):
                excluded.append((rank - 1, "result_not_object"))
                continue
            work_url = _coerce_http_url(item.get("id"))
            if work_url is None:
                excluded.append((rank - 1, "work_id_invalid"))
                continue
            title = str(item.get("display_name") or item.get("title") or "").strip()
            abstract = reconstruct_openalex_abstract(item.get("abstract_inverted_index"))
            if not title and not abstract:
                excluded.append((rank - 1, "source_text_missing"))
                continue
            works.append(OpenAlexWorkText.from_openalex_work(item))
            hits.append(
                WebSearchHit(
                    url=work_url,
                    title=title,
                    snippet=abstract[:900],
                    provider=self.name,
                    query=query,
                    rank=rank,
                    source_type="academic",
                    published_at=_openalex_published_at(item),
                    score=_openalex_score(item),
                )
            )
        filter_outcome = _filter_hits_with_diagnostics(
            hits,
            constraints=constraints,
            max_results=max_results,
            raw_result_count=len(results),
            normalization_rejection_counts=dict(
                Counter(reason for _rank, reason in excluded)
            ),
        )
        return OpenAlexWorksResult(
            query=query,
            hits=filter_outcome.hits,
            works=tuple(works),
            raw_response=decoded,
            response_sha256=hashlib.sha256(payload.encode()).hexdigest(),
            excluded_results=tuple(excluded),
            raw_result_count=len(results),
            pre_filter_hit_count=len(hits),
            filter_rejection_counts=filter_outcome.constraint_rejection_counts,
        )


class DuckDuckGoHtmlSearchProvider:
    """Scrape DuckDuckGo's HTML endpoint and normalize result links/snippets."""

    name = "duckduckgo_html"

    def __init__(
        self,
        *,
        endpoint: str = "https://html.duckduckgo.com/html/",
        user_agent: str = "polisyos-scholar-search/1.0",
    ) -> None:
        self._endpoint = endpoint
        self._user_agent = user_agent

    async def search(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float,
    ) -> list[WebSearchHit]:
        outcome = await self.search_with_diagnostics(
            query,
            constraints=constraints,
            max_results=max_results,
            timeout_s=timeout_s,
        )
        return list(outcome.hits)

    async def search_with_diagnostics(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float,
    ) -> _ProviderSearchOutcome:
        params = {"q": _apply_constraint_query_terms(query, constraints)}
        url = f"{self._endpoint}?{urllib.parse.urlencode(params)}"
        payload = await _read_url_text(
            url,
            headers={"User-Agent": self._user_agent},
            timeout_s=timeout_s,
        )
        parser = _DuckDuckGoParser(query=query)
        parser.feed(payload)
        return _filter_hits_with_diagnostics(
            parser.hits,
            constraints=constraints,
            max_results=max_results,
            raw_result_count=None,
        )


class WikipediaOpenSearchProvider:
    """Query the public Wikipedia search API as a fallback source of policy background links."""

    name = "wikipedia"

    def __init__(
        self,
        *,
        endpoint: str = "https://en.wikipedia.org/w/api.php",
        user_agent: str = "polisyos-scholar-search/1.0",
    ) -> None:
        self._endpoint = endpoint
        self._user_agent = user_agent

    async def search(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float,
    ) -> list[WebSearchHit]:
        outcome = await self.search_with_diagnostics(
            query,
            constraints=constraints,
            max_results=max_results,
            timeout_s=timeout_s,
        )
        return list(outcome.hits)

    async def search_with_diagnostics(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float,
    ) -> _ProviderSearchOutcome:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": str(max(1, min(int(max_results), 50))),
            "format": "json",
            "utf8": "1",
        }
        payload = await _read_url_text(
            f"{self._endpoint}?{urllib.parse.urlencode(params)}",
            headers={"User-Agent": self._user_agent},
            timeout_s=timeout_s,
        )
        decoded = json.loads(payload or "{}")
        search_hits = []
        if isinstance(decoded, dict):
            query_payload = decoded.get("query")
            if isinstance(query_payload, dict):
                search_hits = query_payload.get("search", [])
        raw_result_count = len(search_hits) if isinstance(search_hits, list) else None
        normalization_rejections: Counter[str] = Counter()
        hits: list[WebSearchHit] = []
        for rank, item in enumerate(search_hits, start=1):
            if not isinstance(item, dict):
                normalization_rejections["result_not_object"] += 1
                continue
            page_id = item.get("pageid")
            title = str(item.get("title") or "")
            if page_id is None or not title:
                normalization_rejections["result_missing_page_id_or_title"] += 1
                continue
            target_url = (
                f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
            )
            hits.append(
                WebSearchHit(
                    url=target_url,
                    title=title,
                    snippet=re.sub(r"<[^>]+>", "", str(item.get("snippet") or "")),
                    provider=self.name,
                    query=query,
                    rank=rank,
                    source_type="reference",
                )
            )
        return _filter_hits_with_diagnostics(
            hits,
            constraints=constraints,
            max_results=max_results,
            raw_result_count=raw_result_count,
            normalization_rejection_counts=dict(normalization_rejections),
        )


class _DuckDuckGoParser(HTMLParser):
    def __init__(self, *, query: str) -> None:
        super().__init__()
        self._query = query
        self._capture_title = False
        self._capture_snippet = False
        self._current_href: str | None = None
        self._current_title_parts: list[str] = []
        self._current_snippet_parts: list[str] = []
        self._pending_hit: WebSearchHit | None = None
        self.hits: list[WebSearchHit] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        css_class = attr_map.get("class", "")
        if tag == "a" and "result__a" in css_class:
            self._capture_title = True
            self._current_href = _decode_duckduckgo_url(attr_map.get("href", ""))
            self._current_title_parts = []
        elif tag in {"a", "div", "span"} and (
            "result__snippet" in css_class or "result-snippet" in css_class
        ):
            self._capture_snippet = True
            self._current_snippet_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self._current_title_parts.append(data)
        if self._capture_snippet:
            self._current_snippet_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture_title:
            self._capture_title = False
            if self._current_href:
                title = " ".join(part.strip() for part in self._current_title_parts if part.strip())
                self._pending_hit = WebSearchHit(
                    url=self._current_href,
                    title=title,
                    snippet="",
                    provider="duckduckgo_html",
                    query=self._query,
                    rank=len(self.hits) + 1,
                    source_type=_infer_source_type(self._current_href, title, ""),
                )
            self._current_href = None
            self._current_title_parts = []
        if tag in {"a", "div", "span"} and self._capture_snippet:
            self._capture_snippet = False
            snippet = " ".join(part.strip() for part in self._current_snippet_parts if part.strip())
            if self._pending_hit is not None:
                self.hits.append(
                    self._pending_hit.model_copy(
                        update={
                            "snippet": snippet,
                            "source_type": _infer_source_type(
                                str(self._pending_hit.url),
                                self._pending_hit.title,
                                snippet,
                            ),
                        }
                    )
                )
                self._pending_hit = None
            self._current_snippet_parts = []


def _apply_constraint_query_terms(query: str, constraints: SearchConstraints) -> str:
    terms = [query.strip()]
    if constraints.allowed_domains:
        terms.extend(f"site:{domain}" for domain in constraints.allowed_domains)
    if constraints.source_types:
        terms.extend(constraints.source_types)
    return " ".join(term for term in terms if term).strip()


def _filter_hits(
    hits: Sequence[WebSearchHit],
    *,
    constraints: SearchConstraints,
    max_results: int,
) -> list[WebSearchHit]:
    """Keep the historical list result while sharing its exact constraint rules."""
    return list(
        _filter_hits_with_diagnostics(
            hits,
            constraints=constraints,
            max_results=max_results,
            raw_result_count=None,
        ).hits
    )


def _filter_hits_with_diagnostics(
    hits: Sequence[WebSearchHit],
    *,
    constraints: SearchConstraints,
    max_results: int,
    raw_result_count: int | None,
    normalization_rejection_counts: dict[str, int] | None = None,
) -> _ProviderSearchOutcome:
    """Apply the existing filter and count each first actual rejection reason."""
    eligible: list[WebSearchHit] = []
    rejections: Counter[str] = Counter()
    for hit in hits:
        domain = urllib.parse.urlparse(str(hit.url)).hostname or ""
        if constraints.allowed_domains and not any(
            _domain_matches(domain, allowed) for allowed in constraints.allowed_domains
        ):
            rejections["allowed_domain_mismatch"] += 1
            continue
        if constraints.blocked_domains and any(
            _domain_matches(domain, blocked) for blocked in constraints.blocked_domains
        ):
            rejections["blocked_domain"] += 1
            continue
        if constraints.source_types and hit.source_type not in constraints.source_types:
            rejections["source_type_not_allowed"] += 1
            continue
        eligible.append(hit)

    # The legacy loop returns at most max_results hits; for zero/negative limits
    # it returns its first eligible hit because the first append satisfies len>=limit.
    returned = eligible[:max_results] if max_results > 0 else eligible[:1]
    return _ProviderSearchOutcome(
        hits=tuple(returned),
        raw_result_count=raw_result_count,
        pre_filter_candidate_count=len(hits),
        eligible_candidate_count=len(eligible),
        normalization_rejection_counts=tuple(
            sorted((normalization_rejection_counts or {}).items())
        ),
        constraint_rejection_counts=tuple(sorted(rejections.items())),
    )


def _decode_duckduckgo_url(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.endswith("duckduckgo.com"):
        query = urllib.parse.parse_qs(parsed.query)
        target = query.get("uddg", [""])[0]
        return _coerce_http_url(target)
    return _coerce_http_url(url)


def _coerce_http_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return text


def _infer_source_type(url: str, title: str, snippet: str) -> str:
    text = f"{url} {title} {snippet}".lower()
    host = urllib.parse.urlparse(url).hostname or ""
    if host.endswith(".gov") or "government" in text or "ministry" in text:
        return "government"
    if host.endswith(".edu") or "journal" in text or "doi" in text:
        return "academic"
    if "law" in text or "regulation" in text or "directive" in text:
        return "law"
    if host.endswith(".org"):
        return "organization"
    return "web"


_OPENALEX_SELECT_FIELDS = (
    "id",
    "doi",
    "display_name",
    "title",
    "abstract_inverted_index",
    "publication_year",
    "publication_date",
    "cited_by_count",
    "type",
    "is_retracted",
    "language",
    "open_access",
    "primary_location",
    "authorships",
)


def reconstruct_openalex_abstract(value: object) -> str:
    """Reconstruct an OpenAlex inverted-index abstract into source-text order."""

    if not isinstance(value, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, raw_positions in value.items():
        if not isinstance(raw_positions, list):
            continue
        for position in raw_positions:
            if isinstance(position, int):
                positions.append((position, str(word)))
    positions.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positions)


def _openalex_filters(constraints: SearchConstraints) -> list[str]:
    filters = ["has_abstract:true", "is_retracted:false"]
    language = constraints.locale.split("-", 1)[0].strip().lower()
    if language:
        filters.append(f"language:{language}")
    if constraints.recency_days is not None:
        since = datetime.now(UTC) - timedelta(days=int(constraints.recency_days))
        filters.append(f"from_publication_date:{since.date().isoformat()}")
    return filters


def _openalex_user_agent(user_agent: str, mailto: str) -> str:
    if mailto:
        return f"{user_agent} (mailto:{mailto})"
    return user_agent


def _openalex_published_at(item: dict[str, object]) -> datetime | None:
    published = str(item.get("publication_date") or "").strip()
    if published:
        try:
            return datetime.fromisoformat(published).replace(tzinfo=UTC)
        except ValueError:
            pass
    year = item.get("publication_year")
    if isinstance(year, int) and year > 0:
        return datetime(year, 1, 1, tzinfo=UTC)
    return None


def _openalex_score(item: dict[str, object]) -> float:
    cited_by = item.get("cited_by_count")
    try:
        return min(1.0, max(0.0, float(cited_by or 0.0) / 500.0))
    except (TypeError, ValueError):
        return 0.0


def _domain_matches(domain: str, pattern: str) -> bool:
    domain = domain.lower().strip(".")
    pattern = pattern.lower().strip(".")
    return (
        domain == pattern
        or domain.endswith(f".{pattern}")
        or (pattern.startswith(".") and domain.endswith(pattern.strip(".")))
    )


def _brave_freshness(recency_days: int) -> str:
    if recency_days <= 1:
        return "pd"
    if recency_days <= 7:
        return "pw"
    if recency_days <= 31:
        return "pm"
    return "py"


async def _read_url_text(
    url: str,
    *,
    headers: dict[str, str],
    timeout_s: float,
) -> str:
    def _read() -> str:
        with httpx.Client(
            timeout=httpx.Timeout(timeout_s),
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = client.get(url)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                exc.status_code = exc.response.status_code
                retry_after = _retry_after_seconds(exc.response.headers.get("Retry-After"))
                if retry_after is not None:
                    exc.retry_after_seconds = retry_after
                raise
            return response.text

    return await run_blocking_async(_read, timeout_seconds=timeout_s)


async def _read_openalex_url_text(
    url: str,
    *,
    headers: dict[str, str],
    timeout_s: float,
    rate_limiter: OpenAlexRateLimiter,
    retry_policy: RetryPolicy,
) -> str:
    async def _read_once() -> str:
        await rate_limiter.acquire()
        return await _read_url_text(url, headers=headers, timeout_s=timeout_s)

    return await retry_policy.execute(_read_once)


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if parsed >= 0.0 else None


__all__ = [
    "BraveSearchProvider",
    "DuckDuckGoHtmlSearchProvider",
    "OpenAlexRateLimiter",
    "OpenAlexWorksProvider",
    "ProviderFailoverPolicy",
    "WebSearchProvider",
    "WikipediaOpenSearchProvider",
    "reconstruct_openalex_abstract",
]
