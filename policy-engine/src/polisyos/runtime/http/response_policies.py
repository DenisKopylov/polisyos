"""HTTP response helpers for cacheability, versioning, and lightweight link relations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import format_datetime, parsedate_to_datetime
from typing import Any

from fastapi import Response

_IMMUTABLE_PRIVATE_CACHE_CONTROL = "private, max-age=31536000, immutable"


@dataclass(frozen=True)
class RuntimeApiVersioningPolicy:
    """Versioning and deprecation posture for runtime HTTP responses."""

    version: str = "1"
    compatibility_window: str = "12 months"
    migration_guide_url: str = "https://polisyos.dev/docs/reference/api/versioning"
    sunset: str | None = None
    deprecated: bool = False

    @classmethod
    def from_env(cls) -> RuntimeApiVersioningPolicy:
        return cls(
            version=os.getenv("POLISYOS_RUNTIME_API_VERSION", "1").strip() or "1",
            compatibility_window=(
                os.getenv("POLISYOS_RUNTIME_API_COMPATIBILITY_WINDOW", "12 months").strip()
                or "12 months"
            ),
            migration_guide_url=(
                os.getenv(
                    "POLISYOS_RUNTIME_API_MIGRATION_GUIDE_URL",
                    "https://polisyos.dev/docs/reference/api/versioning",
                ).strip()
                or "https://polisyos.dev/docs/reference/api/versioning"
            ),
            sunset=(os.getenv("POLISYOS_RUNTIME_API_SUNSET", "").strip() or None),
            deprecated=os.getenv("POLISYOS_RUNTIME_API_DEPRECATED", "").strip().lower()
            in {"1", "true", "yes", "on"},
        )


def format_http_date(value: datetime) -> str:
    """Format a timezone-aware datetime for HTTP cache headers."""
    return format_datetime(value.astimezone(UTC), usegmt=True)


def build_artifact_etag(*parts: str) -> str:
    """Build a stable weak ETag token from immutable artifact metadata."""
    token = "-".join(part.strip() for part in parts if part.strip())
    return f'W/"{token}"'


def set_versioning_headers(
    response: Response,
    *,
    policy: RuntimeApiVersioningPolicy | None = None,
    deprecated: bool | None = None,
) -> None:
    """Attach runtime API version/deprecation headers to a response."""
    resolved = policy or RuntimeApiVersioningPolicy.from_env()
    response.headers["X-API-Version"] = resolved.version
    response.headers["X-API-Compatibility-Window"] = resolved.compatibility_window
    _append_link_header(
        response,
        f'<{resolved.migration_guide_url}>; rel="describedby"',
    )
    if deprecated is True or (deprecated is None and resolved.deprecated):
        response.headers["Deprecation"] = "true"
        if resolved.sunset:
            response.headers["Sunset"] = resolved.sunset


def set_immutable_resource_headers(
    response: Response,
    *,
    etag: str,
    last_modified: datetime,
    cache_control: str = _IMMUTABLE_PRIVATE_CACHE_CONTROL,
) -> None:
    """Attach immutable-resource cache metadata to a response."""
    response.headers["ETag"] = etag
    response.headers["Last-Modified"] = format_http_date(last_modified)
    response.headers["Cache-Control"] = cache_control


def add_artifact_link_relations(response: Response, *, artifact_id: str) -> None:
    """Attach lightweight discovery links for artifact-related endpoints."""
    base = f"/api/v1/artifacts/{artifact_id}"
    _append_link_header(response, f'<{base}>; rel="self"')
    _append_link_header(response, f'<{base}/content>; rel="preview"')
    _append_link_header(response, f'<{base}/download>; rel="download"')
    _append_link_header(response, f'<{base}/schema>; rel="describedby"')
    _append_link_header(response, f'<{base}/lineage>; rel="related"')


def add_run_link_relations(response: Response, *, run_id: str) -> None:
    """Attach lightweight discovery links for run-related endpoints."""
    base = f"/api/v1/runs/{run_id}"
    _append_link_header(response, '</api/v1/runs>; rel="collection"')
    _append_link_header(response, f'<{base}>; rel="self"')
    _append_link_header(response, f'<{base}/timeline>; rel="related"')
    _append_link_header(response, f'<{base}/nodes>; rel="related"')
    _append_link_header(response, f'<{base}/lineage>; rel="related"')
    _append_link_header(response, f'<{base}/quantities>; rel="related"')
    _append_link_header(response, f'<{base}/fabric-decision-data>; rel="related"')
    _append_link_header(response, f'<{base}/agents>; rel="related"')
    _append_link_header(response, f'<{base}/evidence-context>; rel="describedby"')
    _append_link_header(response, f'<{base}/workflow>; rel="related"')


def build_not_modified_response(
    request_headers: Any,
    *,
    etag: str,
    last_modified: datetime,
) -> Response | None:
    """Return a 304 response when conditional request headers already match."""
    if_none_match = getattr(request_headers, "get", lambda *_args, **_kwargs: None)("if-none-match")
    if isinstance(if_none_match, str) and _etag_matches(if_none_match, etag):
        response = Response(status_code=304)
        set_immutable_resource_headers(response, etag=etag, last_modified=last_modified)
        return response

    if_modified_since = getattr(request_headers, "get", lambda *_args, **_kwargs: None)(
        "if-modified-since"
    )
    if isinstance(if_modified_since, str):
        try:
            parsed = parsedate_to_datetime(if_modified_since)
        except (TypeError, ValueError, IndexError):
            parsed = None
        if parsed is not None and parsed.astimezone(UTC) >= last_modified.astimezone(UTC):
            response = Response(status_code=304)
            set_immutable_resource_headers(response, etag=etag, last_modified=last_modified)
            return response
    return None


def _etag_matches(header_value: str, etag: str) -> bool:
    candidates = {item.strip() for item in header_value.split(",") if item.strip()}
    return "*" in candidates or etag in candidates


def _append_link_header(response: Response, value: str) -> None:
    existing = response.headers.get("Link")
    response.headers["Link"] = value if not existing else f"{existing}, {value}"


__all__ = [
    "RuntimeApiVersioningPolicy",
    "add_artifact_link_relations",
    "add_run_link_relations",
    "build_artifact_etag",
    "build_not_modified_response",
    "format_http_date",
    "set_immutable_resource_headers",
    "set_versioning_headers",
]
