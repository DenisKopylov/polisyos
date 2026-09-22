"""Shared redirect-aware raw HTTP transport for Scholar adapters."""

from __future__ import annotations

import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.scholar.search.models import SearchConstraints


class RawFetchSizeError(ValueError):
    """Raised when a raw response exceeds the caller's byte budget."""

    def __init__(self, *, observed_bytes: int, max_bytes: int) -> None:
        super().__init__(f"raw payload exceeds max_bytes={max_bytes}")
        self.observed_bytes = observed_bytes
        self.max_bytes = max_bytes


@dataclass(frozen=True, slots=True)
class RawFetchResult:
    """Raw response bytes and the metadata needed by typed result adapters."""

    raw_bytes: bytes
    final_url: str
    content_type: str
    headers: dict[str, str]
    redirect_chain: list[str]


def fetch_raw(
    url: str,
    *,
    constraints: SearchConstraints,
    timeout_s: float,
    user_agent: str,
    max_bytes: int | None,
) -> RawFetchResult:
    """Fetch one URL while preserving redirect and response metadata for adapters."""
    from polisyos.scholar.search.security import validate_fetch_url

    validate_fetch_url(url, constraints)
    redirect_chain: list[str] = []
    opener = urllib.request.build_opener(
        _ValidatingRedirectHandler(
            constraints=constraints,
            redirect_chain=redirect_chain,
            validate_url=validate_fetch_url,
        )
    )
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with opener.open(request, timeout=timeout_s) as response:
        limit = max_bytes + 1 if max_bytes is not None else -1
        raw_bytes = response.read(limit)
        if max_bytes is not None and len(raw_bytes) > max_bytes:
            raise RawFetchSizeError(
                observed_bytes=len(raw_bytes),
                max_bytes=max_bytes,
            )
        final_url = getattr(response, "url", url) or url
        validate_fetch_url(final_url, constraints)
        headers = {str(key): str(value) for key, value in response.headers.items()}
        content_type = response.headers.get("Content-Type") or "application/octet-stream"
        return RawFetchResult(
            raw_bytes=raw_bytes,
            final_url=final_url,
            content_type=content_type,
            headers=headers,
            redirect_chain=list(redirect_chain),
        )


class _ValidatingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(
        self,
        *,
        constraints: SearchConstraints,
        redirect_chain: list[str],
        validate_url: Callable[[str, SearchConstraints], None],
    ) -> None:
        super().__init__()
        self._constraints = constraints
        self._redirect_chain = redirect_chain
        self._validate_url = validate_url

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: Mapping[str, str],
        newurl: str,
    ) -> urllib.request.Request | None:  # type: ignore[override]
        self._validate_url(newurl, self._constraints)
        self._redirect_chain.append(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


__all__ = ["RawFetchResult", "RawFetchSizeError", "fetch_raw"]
