"""Cache-first page fetching, safe extraction, and in-page snippet lookup."""

from __future__ import annotations

import hashlib
import math
import re
import urllib.parse
from html.parser import HTMLParser
from io import BytesIO
from typing import TYPE_CHECKING

from polisyos.common.async_tools import run_blocking_async
from polisyos.core.canon import content_hash
from polisyos.scholar.discover.transport import RawFetchSizeError, _fetch_raw_with_target
from polisyos.scholar.search.models import FetchResult, SearchConstraints, SourceSnippet
from polisyos.scholar.search.scoring import compress_page_to_snippets
from polisyos.scholar.search.security import (
    _resolve_fetch_target,
    _validate_fetch_url_offline,
    detect_paywall,
    sanitize_untrusted_text,
    validate_content_type,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.scholar.search.cache import CachedPageRecord, UrlFetchCache
    from polisyos.scholar.search.security import _ResolvedFetchTarget


async def fetch_open_page(
    url: str,
    *,
    constraints: SearchConstraints,
    cache: UrlFetchCache | None = None,
    timeout_s: float = 10.0,
    user_agent: str = "polisyos-scholar-search/1.0",
    max_bytes: int = 2_000_000,
    source_type_hint: str = "web",
) -> FetchResult:
    """Fetch one URL safely, reuse cache when fresh, and extract normalized page text."""
    # Freeze the actual acquisition policy before an asynchronous handoff. A caller
    # mutating its DTO while the request runs cannot change the recorded profile.
    constraints = SearchConstraints.model_validate(constraints.model_dump(mode="python"))
    normalized_mimes = sorted(
        {mime.strip().lower() for mime in constraints.allowed_content_types if mime.strip()}
    )
    # A nonempty but all-blank allowlist means deny all, not unrestricted MIME.
    if normalized_mimes or not constraints.allowed_content_types:
        constraints.allowed_content_types = normalized_mimes
    _validate_fetch_url_offline(url, constraints)
    cached = cache.get(url) if cache is not None else None
    if cached is not None:
        try:
            _admit_cached_page(cached, url=url, constraints=constraints, max_bytes=max_bytes)
        except ValueError as exc:
            return FetchResult(
                url=url, final_url=url, status="error", error=str(exc), source_type=source_type_hint
            )
        return cached.to_fetch_result()

    resolved_target = _resolve_fetch_target(url, constraints)
    try:
        (
            raw_bytes,
            final_url,
            content_type,
            response_headers,
            redirect_chain,
        ) = await run_blocking_async(
            _fetch_url_bytes_sync,
            url,
            constraints,
            resolved_target,
            timeout_s,
            user_agent,
            max_bytes,
            timeout_seconds=timeout_s,
        )
        mime = validate_content_type(content_type, constraints)
        title, text = _extract_title_and_text(raw_bytes, mime=mime, final_url=final_url)
        text = sanitize_untrusted_text(text)
        paywalled = detect_paywall(text)
        status = "blocked" if paywalled else "ok"
        error = "paywall detected" if paywalled else None
        result = FetchResult(
            url=url,
            final_url=final_url,
            title=title,
            text=text,
            content_type=mime,
            status=status,
            content_sha256=content_hash(raw_bytes),
            etag=response_headers.get("ETag") or response_headers.get("etag"),
            last_modified=response_headers.get("Last-Modified")
            or response_headers.get("last-modified"),
            redirect_chain=redirect_chain,
            byte_size=len(raw_bytes),
            fetch_profile={
                "profile_version": "1.0",
                "transport": "polisyos.scholar.discover.transport",
                "transport_version": "1.0",
                "constraints": constraints.model_dump(mode="json"),
                "max_bytes": max_bytes,
                "timeout_s": float(timeout_s),
                "user_agent": user_agent,
            },
            paywalled=paywalled,
            error=error,
            source_type=_infer_source_type(
                final_url,
                title=title,
                text=text,
                source_type_hint=source_type_hint,
            ),
        )
        if cache is not None:
            cache.put(result, raw_bytes=raw_bytes)
        return result
    except Exception as exc:
        result = FetchResult(
            url=url,
            final_url=url,
            text="",
            status="error",
            error=str(exc),
            source_type=source_type_hint,
        )
        return result


def _admit_cached_page(
    cached: CachedPageRecord, *, url: str, constraints: SearchConstraints, max_bytes: int
) -> None:
    """Admit saved content using current offline policy and known acquisition facts.

    Acquisition settings are provenance, not a demand that a later reader use the
    same timeout/user agent. Missing historical facts require an explicit refresh,
    never a hidden network call or a retroactively invented profile.
    """
    profile = cached.fetch_profile
    if (
        profile.get("profile_version") != "1.0"
        or profile.get("transport") != "polisyos.scholar.discover.transport"
        or profile.get("transport_version") != "1.0"
    ):
        raise ValueError("cache-ineligible: acquisition profile unknown or unsupported")
    saved_constraints = profile.get("constraints")
    if not isinstance(saved_constraints, dict) or set(saved_constraints) != set(
        SearchConstraints.model_fields
    ):
        raise ValueError("cache-ineligible: acquisition constraints unknown")
    try:
        acquisition = SearchConstraints.model_validate(saved_constraints, strict=True)
    except ValueError as exc:
        raise ValueError("cache-ineligible: acquisition constraints invalid") from exc
    timeout = profile.get("timeout_s")
    saved_max_bytes = profile.get("max_bytes")
    try:
        valid_timeout = (
            isinstance(timeout, (int, float))
            and not isinstance(timeout, bool)
            and math.isfinite(timeout)
            and timeout > 0
        )
    except OverflowError:
        valid_timeout = False
    if (
        not valid_timeout
        or not isinstance(profile.get("user_agent"), str)
        or not isinstance(saved_max_bytes, int)
        or isinstance(saved_max_bytes, bool)
        or saved_max_bytes < 0
    ):
        raise ValueError("cache-ineligible: acquisition bounds unknown")
    if cached.url != url:
        raise ValueError("cache-ineligible: saved initial URL mismatch")
    if cached.final_url != cached.url and (
        not cached.redirect_chain or cached.redirect_chain[-1] != cached.final_url
    ):
        raise ValueError("cache-ineligible: redirect facts incomplete")
    for saved_url in [cached.url, *cached.redirect_chain, cached.final_url]:
        _validate_fetch_url_offline(saved_url, constraints)
    if not constraints.allow_private_networks and acquisition.allow_private_networks:
        raise ValueError("cache-ineligible: saved public-destination assurance not established")
    validate_content_type(cached.content_type, constraints)
    if cached.byte_size is None:
        raise ValueError("cache-ineligible: raw byte_size unknown")
    if cached.byte_size > saved_max_bytes:
        raise ValueError("cache-ineligible: raw byte_size exceeds acquisition bounds")
    if cached.byte_size > max_bytes:
        raise ValueError(f"cached page exceeds max_bytes={max_bytes}")


def find_in_page(
    fetch_result: FetchResult,
    *,
    pattern: str,
    query_node_id: str = "manual",
    perspective: str = "manual",
    max_snippets: int = 5,
    window_chars: int = 400,
) -> list[SourceSnippet]:
    """Return stable text spans around a pattern from one fetched page."""
    query_terms = [token for token in re.findall(r"[\w'-]+", pattern) if token]
    return compress_page_to_snippets(
        source_id=source_id_from_url(fetch_result.final_url, fetch_result.content_sha256),
        url=str(fetch_result.url),
        text=fetch_result.text,
        query_node_id=query_node_id,
        perspective=perspective,
        query_terms=query_terms or [pattern],
        max_snippets=max_snippets,
        window_chars=window_chars,
    )


async def fetch_and_find_in_page(
    url: str,
    *,
    pattern: str,
    constraints: SearchConstraints,
    cache: UrlFetchCache | None = None,
    timeout_s: float = 10.0,
    user_agent: str = "polisyos-scholar-search/1.0",
    max_bytes: int = 2_000_000,
    source_type_hint: str = "web",
    max_snippets: int = 5,
    window_chars: int = 400,
) -> tuple[FetchResult, list[SourceSnippet]]:
    """Fetch a URL and return matching snippets in one call."""
    fetched = await fetch_open_page(
        url,
        constraints=constraints,
        cache=cache,
        timeout_s=timeout_s,
        user_agent=user_agent,
        max_bytes=max_bytes,
        source_type_hint=source_type_hint,
    )
    if fetched.status in {"error", "blocked"}:
        return fetched, []
    snippets = find_in_page(
        fetched,
        pattern=pattern,
        max_snippets=max_snippets,
        window_chars=window_chars,
    )
    return fetched, snippets


def source_id_from_url(url: str, content_sha256: str | None = None) -> str:
    payload = f"{url}|{content_sha256 or ''}".encode()
    return f"src.{hashlib.sha256(payload).hexdigest()[:24]}"


def _fetch_url_bytes_sync(
    url: str,
    constraints: SearchConstraints,
    resolved_target: _ResolvedFetchTarget,
    timeout_s: float,
    user_agent: str,
    max_bytes: int,
) -> tuple[bytes, str, str, dict[str, str], list[str]]:
    try:
        raw = _fetch_raw_with_target(
            url,
            constraints=constraints,
            timeout_s=timeout_s,
            user_agent=user_agent,
            max_bytes=max_bytes,
            target=resolved_target,
        )
    except RawFetchSizeError as exc:
        raise ValueError(f"page exceeds max_bytes={exc.max_bytes}") from exc
    return (
        raw.raw_bytes,
        raw.final_url,
        raw.content_type,
        raw.headers,
        raw.redirect_chain,
    )


def _extract_title_and_text(raw_bytes: bytes, *, mime: str, final_url: str) -> tuple[str, str]:
    if mime == "application/pdf":
        return _extract_pdf_text(raw_bytes, final_url=final_url)
    if mime in {"text/html", "application/xhtml+xml"}:
        parser = _VisibleTextParser()
        parser.feed(raw_bytes.decode("utf-8", errors="replace"))
        title = parser.title.strip() or final_url
        text = "\n".join(part.strip() for part in parser.text_parts if part.strip())
        return title, text
    text = raw_bytes.decode("utf-8", errors="replace")
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return first_line or final_url, text


def _extract_pdf_text(raw_bytes: bytes, *, final_url: str) -> tuple[str, str]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(raw_bytes))
        parts: list[str] = []
        for page in reader.pages[:25]:
            page_text = page.extract_text() or ""
            if page_text.strip():
                parts.append(page_text)
        title = ""
        metadata = getattr(reader, "metadata", None)
        if metadata is not None:
            title = str(getattr(metadata, "title", "") or "").strip()
        return title or final_url, "\n".join(parts)
    except Exception:
        text = raw_bytes.decode("utf-8", errors="replace")
        return final_url, text


def _infer_source_type(
    url: str,
    *,
    title: str,
    text: str,
    source_type_hint: str,
) -> str:
    host = urllib.parse.urlparse(url).hostname or ""
    haystack = f"{host} {title} {text[:2000]}".lower()
    if host.endswith(".gov") or "ministry" in haystack or "government" in haystack:
        return "government"
    if host.endswith(".edu") or "doi" in haystack or "journal" in haystack:
        return "academic"
    if "regulation" in haystack or "law" in haystack or "directive" in haystack:
        return "law"
    if source_type_hint:
        return source_type_hint
    return "web"


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._capture_title = False
        self._title_parts: list[str] = []
        self.text_parts: list[str] = []

    @property
    def title(self) -> str:
        return " ".join(part.strip() for part in self._title_parts if part.strip())

    def handle_starttag(self, tag: str, attrs: Sequence[tuple[str, str | None]]) -> None:
        del attrs
        if tag.lower() in {"script", "style", "noscript", "template", "svg"}:
            self._skip_depth += 1
        elif tag.lower() == "title":
            self._capture_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "template", "svg"}:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag.lower() == "title":
            self._capture_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if self._capture_title:
            self._title_parts.append(data)
            return
        if data.strip():
            self.text_parts.append(data)


__all__ = [
    "fetch_and_find_in_page",
    "fetch_open_page",
    "find_in_page",
    "source_id_from_url",
]
