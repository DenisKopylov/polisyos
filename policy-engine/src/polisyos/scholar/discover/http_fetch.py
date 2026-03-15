from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from polisyos.core.contracts.scholar import SourceSpec
from polisyos.fabric.docs import DocSourceSpec
from polisyos.scholar.errors import ScholarAcquireError, ScholarValidationError
from polisyos.scholar.types import AcquireResult


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
) -> AcquireResult:
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

    request = Request(request_url, headers={"User-Agent": user_agent})
    try:
        with urlopen(request, timeout=timeout_s) as response:
            limit = max_bytes + 1 if max_bytes is not None else -1
            raw_bytes = response.read(limit)
            if max_bytes is not None and len(raw_bytes) > max_bytes:
                raise ScholarAcquireError(
                    "URL payload exceeds max_bytes_per_doc",
                    source_identity=canonical_url,
                    details={"bytes": len(raw_bytes), "max_bytes": max_bytes},
                )
            content_type = response.headers.get("Content-Type")
    except HTTPError as exc:
        raise ScholarAcquireError(
            f"HTTP error while fetching URL: {exc.code}",
            source_identity=canonical_url,
            details={"status": exc.code, "url": request_url},
        ) from exc
    except URLError as exc:
        raise ScholarAcquireError(
            f"URL fetch failed: {exc}",
            source_identity=canonical_url,
            details={"url": request_url},
        ) from exc

    mime = _extract_mime(content_type, source.mime_hint)
    doc_source = _doc_source_from_source(source, canonical_url=canonical_url)
    return AcquireResult(
        source=source,
        source_identity=canonical_url,
        raw_bytes=raw_bytes,
        mime=mime,
        doc_source=doc_source,
    )


__all__ = ["fetch_url"]
