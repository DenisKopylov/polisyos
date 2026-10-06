"""Fetches URL-backed Scholar seed sources into the normalized acquire payload shape."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError

from polisyos.fabric.docs import DocSourceSpec
from polisyos.scholar.discover.transport import (
    RawFetchSizeError,
    build_fetch_profile,
    fetch_failure_reason,
    fetch_raw,
)
from polisyos.scholar.errors import ScholarAcquireError, ScholarValidationError
from polisyos.scholar.search.models import SearchConstraints
from polisyos.scholar.search.security import validate_content_type, validate_fetch_url
from polisyos.scholar.types import AcquireResult

if TYPE_CHECKING:
    from polisyos.core.contracts.scholar import SourceSpec


def _doc_source_from_source(source: SourceSpec, *, canonical_url: str) -> DocSourceSpec:
    props = source.props
    return DocSourceSpec(
        canonical_url=canonical_url,
        official_id=None,
        source_locator=None,
        license=source.license,
        jurisdiction=props.get("jurisdiction"),
        language=props.get("language"),
        source_type=props.get("source_type"),
        title=props.get("title"),
        publisher=props.get("publisher"),
    )


def _extract_mime(content_type: str | None, fallback: str | None) -> str:
    if content_type:
        return content_type.split(";", 1)[0].strip() or "application/octet-stream"
    if fallback:
        return fallback.strip()
    return "application/octet-stream"


def fetch_url(
    source: SourceSpec,
    *,
    timeout_s: float,
    user_agent: str,
    max_bytes: int | None,
    constraints: SearchConstraints | None = None,
) -> AcquireResult:
    """Download a URL seed source, enforce byte limits, and return an ``AcquireResult``."""
    if source.kind != "url":
        raise ScholarValidationError(
            "fetch_url expects kind=url",
            stage="acquire",
            source_identity=source.canonical_url,
        )

    request_url = source.url or source.canonical_url
    canonical_url = source.canonical_url or source.url
    if not request_url or not canonical_url:
        raise ScholarValidationError(
            "url source requires canonical_url/url",
            stage="acquire",
            source_identity=source.canonical_url,
        )

    active_constraints = constraints or SearchConstraints()
    profile = build_fetch_profile(
        constraints=active_constraints,
        timeout_s=timeout_s,
        user_agent=user_agent,
        max_bytes=max_bytes,
    )
    try:
        validate_fetch_url(request_url, active_constraints)
    except ValueError as exc:
        raise ScholarAcquireError(
            f"blocked URL fetch: {exc}",
            source_identity=canonical_url,
            details={"url": request_url, "reason": fetch_failure_reason(exc)},
        ) from exc

    try:
        raw = fetch_raw(
            request_url,
            constraints=active_constraints,
            timeout_s=timeout_s,
            user_agent=user_agent,
            max_bytes=max_bytes,
        )
        raw_bytes = raw.raw_bytes
        content_type = raw.content_type
    except RawFetchSizeError as exc:
        raise ScholarAcquireError(
            "URL payload exceeds max_bytes_per_doc",
            source_identity=canonical_url,
            details={
                "bytes": exc.observed_bytes,
                "max_bytes": exc.max_bytes,
                "reason": fetch_failure_reason(exc),
            },
        ) from exc
    except HTTPError as exc:
        raise ScholarAcquireError(
            f"HTTP error while fetching URL: {exc.code}",
            source_identity=canonical_url,
            details={
                "status": exc.code,
                "url": request_url,
                "reason": fetch_failure_reason(exc),
            },
        ) from exc
    except URLError as exc:
        raise ScholarAcquireError(
            f"URL fetch failed: {exc}",
            source_identity=canonical_url,
            details={"url": request_url, "reason": fetch_failure_reason(exc)},
        ) from exc
    except TimeoutError as exc:
        raise ScholarAcquireError(
            f"URL fetch timed out: {exc}",
            source_identity=canonical_url,
            details={"url": request_url, "reason": "timeout"},
        ) from exc
    except ValueError as exc:
        raise ScholarAcquireError(
            f"blocked URL fetch: {exc}",
            source_identity=canonical_url,
            details={"url": request_url, "reason": fetch_failure_reason(exc)},
        ) from exc

    try:
        mime = validate_content_type(
            _extract_mime(content_type, source.mime_hint),
            constraints or SearchConstraints(),
        )
    except ValueError as exc:
        raise ScholarAcquireError(
            f"blocked content type: {exc}",
            source_identity=canonical_url,
            details={
                "url": request_url,
                "content_type": content_type,
                "reason": "blocked_content_type",
            },
        ) from exc
    doc_source = _doc_source_from_source(source, canonical_url=canonical_url)
    return AcquireResult(
        source=source,
        source_identity=canonical_url,
        raw_bytes=raw_bytes,
        mime=mime,
        doc_source=doc_source,
        final_url=raw.final_url,
        headers=dict(raw.headers),
        redirect_chain=list(raw.redirect_chain),
        content_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        byte_size=len(raw_bytes),
        fetch_profile=profile,
    )


__all__ = ["fetch_url"]
