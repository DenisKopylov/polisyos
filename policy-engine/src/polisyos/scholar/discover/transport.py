"""Shared redirect-aware raw HTTP transport for Scholar adapters."""

from __future__ import annotations

import socket
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from polisyos.scholar.search.models import FetchFailureReason, SearchConstraints


class RawFetchSizeError(ValueError):
    """Raised when a raw response exceeds the caller's byte budget."""

    def __init__(self, *, observed_bytes: int, max_bytes: int) -> None:
        super().__init__(f"raw payload exceeds max_bytes={max_bytes}")
        self.observed_bytes = observed_bytes
        self.max_bytes = max_bytes


class RawFetchPolicyError(ValueError):
    """Preserve the network-policy refusal category at the shared transport boundary."""

    def __init__(self, reason: FetchFailureReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def fetch_failure_reason(exc: BaseException) -> FetchFailureReason:
    """Classify existing transport and admission refusals without changing their policy."""
    if isinstance(exc, RawFetchPolicyError):
        return exc.reason
    if isinstance(exc, RawFetchSizeError):
        return "max_bytes_exceeded"
    if isinstance(exc, HTTPError):
        return "redirect_error" if 300 <= exc.code < 400 else "http_error"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(exc, URLError):
        if isinstance(exc.reason, (TimeoutError, socket.timeout)) or "timed out" in str(
            exc.reason
        ).lower():
            return "timeout"
        return "transport_error"
    message = str(exc).lower()
    if "content type" in message or "mime" in message:
        return "blocked_content_type"
    if "private network" in message:
        return "blocked_private_network"
    if "domain blocked" in message or "domain not allowed" in message:
        return "blocked_domain"
    return "transport_error"


def _validate_url(url: str, constraints: SearchConstraints) -> None:
    from polisyos.scholar.search.security import validate_fetch_url

    try:
        validate_fetch_url(url, constraints)
    except ValueError as exc:
        raise RawFetchPolicyError(fetch_failure_reason(exc), str(exc)) from exc


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
    _validate_url(url, constraints)
    redirect_chain: list[str] = []
    opener = urllib.request.build_opener(
        _ValidatingRedirectHandler(
            constraints=constraints,
            redirect_chain=redirect_chain,
            validate_url=_validate_url,
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
        _validate_url(final_url, constraints)
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


def build_fetch_profile(
    *,
    constraints: SearchConstraints,
    timeout_s: float,
    user_agent: str,
    max_bytes: int | None,
) -> dict[str, object]:
    """Return the non-secret, deterministic profile used for one raw transport request."""
    return {
        "transport": "scholar.discover.transport.fetch_raw",
        "timeout_s": format(timeout_s, ".6g"),
        "user_agent": user_agent,
        "max_bytes": max_bytes,
        "allowed_domains": list(constraints.allowed_domains),
        "blocked_domains": list(constraints.blocked_domains),
        "source_types": list(constraints.source_types),
        "allowed_content_types": list(constraints.allowed_content_types),
        "allow_private_networks": constraints.allow_private_networks,
    }


__all__ = [
    "RawFetchPolicyError",
    "RawFetchResult",
    "RawFetchSizeError",
    "build_fetch_profile",
    "fetch_failure_reason",
    "fetch_raw",
]
