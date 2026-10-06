"""Cache-first page fetching, safe extraction, and in-page snippet lookup."""

from __future__ import annotations

import hashlib
import re
import urllib.parse
from html.parser import HTMLParser
from io import BytesIO
from typing import TYPE_CHECKING

from polisyos.common.async_tools import run_blocking_async
from polisyos.core.canon import content_hash
from polisyos.scholar.discover.transport import (
    RawFetchPolicyError,
    RawFetchSizeError,
    admit_raw_payload,
    build_fetch_profile,
    fetch_failure_reason,
    fetch_raw,
)
from polisyos.scholar.search.models import FetchResult, SearchConstraints, SourceSnippet
from polisyos.scholar.search.scoring import compress_page_to_snippets
from polisyos.scholar.search.security import (
    detect_paywall,
    sanitize_untrusted_text,
    validate_fetch_url,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.scholar.search.cache import UrlFetchCache


def _header_value(headers: dict[str, str], name: str) -> str | None:
    """Return one HTTP header value without assuming server header casing."""
    normalized_name = name.casefold()
    return next(
        (value for key, value in headers.items() if key.casefold() == normalized_name),
        None,
    )


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
    profile = build_fetch_profile(
        constraints=constraints,
        timeout_s=timeout_s,
        user_agent=user_agent,
        max_bytes=max_bytes,
    )
    try:
        validate_fetch_url(url, constraints)
    except Exception as exc:
        reason = fetch_failure_reason(exc)
        return FetchResult(
            url=url,
            final_url=url,
            status="error",
            failure_reason=reason,
            error=str(exc),
            source_type=source_type_hint,
            fetch_profile=profile,
        )
    cached = cache.get(url) if cache is not None else None
    if cached is not None:
        cached_result = cached.to_fetch_result()
        raw_bytes: bytes | None = None
        try:
            try:
                raw_bytes = cache.get_raw_bytes(cached)
            except Exception as exc:
                raise RawFetchPolicyError(
                    "cached_snapshot_unavailable",
                    f"cached raw CAS snapshot could not be resolved: {exc}",
                ) from exc
            mime = admit_raw_payload(
                final_url=cached.final_url,
                content_type=cached.content_type,
                raw_bytes=raw_bytes,
                constraints=constraints,
                max_bytes=max_bytes,
            )
            digest = hashlib.sha256(raw_bytes).hexdigest()
            if (
                _normalize_digest(cached.content_sha256) != digest
                or cached.artifact_id != f"sha256:{digest}"
                or (cached.byte_size is not None and cached.byte_size != len(raw_bytes))
            ):
                raise RawFetchPolicyError(
                    "cached_snapshot_mismatch",
                    "cached raw bytes do not match the stored digest, artifact, or byte size",
                )
            title, text = _extract_title_and_text(raw_bytes, mime=mime, final_url=cached.final_url)
            text = sanitize_untrusted_text(text)
            paywalled = detect_paywall(text)
            error = "paywall detected" if paywalled else None
            failure_reason = "paywall" if paywalled else None
            if not paywalled and not text.strip():
                error = "no accessible text in fetched response"
                failure_reason = "inaccessible_text"
            return cached_result.model_copy(
                update={
                    "title": title,
                    "text": text,
                    "content_type": mime,
                    "status": "blocked" if paywalled else "cached",
                    "failure_reason": failure_reason,
                    "content_sha256": digest,
                    "byte_size": len(raw_bytes),
                    "paywalled": paywalled,
                    "error": error,
                    "source_type": _infer_source_type(
                        cached.final_url,
                        title=title,
                        text=text,
                        source_type_hint=source_type_hint,
                    ),
                }
            )
        except Exception as exc:
            return cached_result.model_copy(
                update={
                    "status": "error",
                    "failure_reason": fetch_failure_reason(exc),
                    "error": str(exc),
                    "byte_size": (
                        exc.observed_bytes
                        if isinstance(exc, RawFetchSizeError)
                        else len(raw_bytes)
                        if raw_bytes is not None
                        else cached.byte_size
                    ),
                }
            )

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
            timeout_s,
            user_agent,
            max_bytes,
            timeout_seconds=timeout_s,
        )
        mime = content_type
        title, text = _extract_title_and_text(raw_bytes, mime=mime, final_url=final_url)
        text = sanitize_untrusted_text(text)
        paywalled = detect_paywall(text)
        status = "blocked" if paywalled else "ok"
        error = "paywall detected" if paywalled else None
        failure_reason = "paywall" if paywalled else None
        if not paywalled and not text.strip():
            error = "no accessible text in fetched response"
            failure_reason = "inaccessible_text"
        result = FetchResult(
            url=url,
            final_url=final_url,
            title=title,
            text=text,
            content_type=mime,
            status=status,
            failure_reason=failure_reason,
            content_sha256=content_hash(raw_bytes),
            headers=response_headers,
            etag=_header_value(response_headers, "ETag"),
            last_modified=_header_value(response_headers, "Last-Modified"),
            redirect_chain=redirect_chain,
            byte_size=len(raw_bytes),
            paywalled=paywalled,
            error=error,
            fetch_profile=profile,
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
        failure_reason = fetch_failure_reason(exc)
        result = FetchResult(
            url=url,
            final_url=url,
            text="",
            status="error",
            failure_reason=failure_reason,
            error=(
                f"page exceeds max_bytes={exc.max_bytes}"
                if isinstance(exc, RawFetchSizeError)
                else str(exc)
            ),
            source_type=source_type_hint,
            fetch_profile=profile,
        )
        return result


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
    timeout_s: float,
    user_agent: str,
    max_bytes: int,
) -> tuple[bytes, str, str, dict[str, str], list[str]]:
    raw = fetch_raw(
        url,
        constraints=constraints,
        timeout_s=timeout_s,
        user_agent=user_agent,
        max_bytes=max_bytes,
    )
    return (
        raw.raw_bytes,
        raw.final_url,
        raw.mime_type,
        raw.headers,
        raw.redirect_chain,
    )


def _normalize_digest(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized[7:] if normalized.startswith("sha256:") else normalized


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
