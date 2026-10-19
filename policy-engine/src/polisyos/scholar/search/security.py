"""Fetch and page-extraction safety guards for Scholar web search."""

from __future__ import annotations

import ipaddress
import re
import socket
import urllib.parse
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.scholar.search.models import SearchConstraints


_LOCAL_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
}

_PAYWALL_MARKERS = [
    "subscribe to continue",
    "already a subscriber",
    "sign in to continue",
    "create an account to read",
    "this article is for subscribers",
    "enable javascript and disable ad blocker",
]

_PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?prior\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"developer\s*:\s*", re.IGNORECASE),
]


@dataclass(frozen=True, slots=True)
class _ResolvedSocketAddress:
    """One resolver-returned numeric address suitable for a TCP connection."""

    address: str
    family: int
    socket_type: int
    protocol: int
    sockaddr: tuple[str, int] | tuple[str, int, int, int]


@dataclass(frozen=True, slots=True)
class _ResolvedFetchTarget:
    """A URL validated against constraints and bound to approved TCP addresses."""

    request_url: str = field(repr=False)
    scheme: str
    hostname: str
    port: int
    addresses: tuple[_ResolvedSocketAddress, ...]
    constraints_signature: tuple[tuple[str, ...], tuple[str, ...], bool] = field(repr=False)


def sanitize_untrusted_text(text: str, *, max_chars: int = 400_000) -> str:
    """Normalize text and neutralize common prompt-injection control strings."""

    cleaned = "".join(ch if ch == "\n" or ch == "\t" or ord(ch) >= 32 else " " for ch in text)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    for pattern in _PROMPT_INJECTION_PATTERNS:
        cleaned = pattern.sub("[[removed-untrusted-instruction]]", cleaned)
    cleaned = cleaned.strip()
    if len(cleaned) > max_chars:
        return cleaned[:max_chars]
    return cleaned


def _resolve_fetch_target(url: str, constraints: SearchConstraints) -> _ResolvedFetchTarget:
    """Validate a fetch URL and retain every approved numeric TCP destination.

    The returned target is an internal handoff to the shared transport. It binds the
    checked URL and policy inputs to the exact resolver answers that the transport
    must use for its socket connection.
    """
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").strip().lower()
    if scheme not in {"http", "https"} or not host:
        raise ValueError(f"unsupported fetch URL: {url!r}")
    try:
        explicit_port = parsed.port
    except ValueError as exc:
        raise ValueError(f"unsupported fetch URL port: {url!r}") from exc
    port = explicit_port if explicit_port is not None else (443 if scheme == "https" else 80)

    if constraints.allowed_domains and not any(
        _domain_matches(host, allowed) for allowed in constraints.allowed_domains
    ):
        raise ValueError(f"domain not allowed: {host}")
    if constraints.blocked_domains and any(
        _domain_matches(host, blocked) for blocked in constraints.blocked_domains
    ):
        raise ValueError(f"domain blocked: {host}")

    if not constraints.allow_private_networks and (
        host in _LOCAL_HOSTS or host.endswith(".localhost") or host.endswith(".local")
    ):
        raise ValueError(f"private network address blocked: {host}")

    try:
        infos = socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except OSError as exc:
        raise ValueError(f"fetch hostname could not be resolved: {host}") from exc

    addresses: list[_ResolvedSocketAddress] = []
    seen: set[tuple[int, str, tuple[str, int] | tuple[str, int, int, int]]] = set()
    for family, socket_type, protocol, _canonical_name, sockaddr_value in infos:
        if family not in {socket.AF_INET, socket.AF_INET6} or socket_type != socket.SOCK_STREAM:
            continue
        if not isinstance(sockaddr_value, tuple) or not sockaddr_value:
            raise ValueError(f"resolver returned a malformed address for {host}")
        if not isinstance(sockaddr_value[0], str):
            raise ValueError(f"resolver returned a non-numeric address for {host}")
        try:
            ip_obj = ipaddress.ip_address(sockaddr_value[0])
        except ValueError as exc:
            raise ValueError(f"resolver returned a non-numeric address for {host}") from exc
        expected_version = 4 if family == socket.AF_INET else 6
        if ip_obj.version != expected_version:
            raise ValueError(f"resolver returned an address-family mismatch for {host}")
        if family == socket.AF_INET:
            if len(sockaddr_value) != 2 or sockaddr_value[1] != port:
                raise ValueError(f"resolver returned a mismatched port for {host}")
            sockaddr: tuple[str, int] | tuple[str, int, int, int] = (str(ip_obj), port)
        else:
            if (
                len(sockaddr_value) != 4
                or sockaddr_value[1] != port
                or not isinstance(sockaddr_value[2], int)
                or not isinstance(sockaddr_value[3], int)
            ):
                raise ValueError(f"resolver returned a malformed IPv6 address for {host}")
            sockaddr = (str(ip_obj), port, sockaddr_value[2], sockaddr_value[3])
        if not constraints.allow_private_networks:
            _ensure_public_address(str(ip_obj))
        identity = (family, str(ip_obj), sockaddr)
        if identity in seen:
            continue
        seen.add(identity)
        addresses.append(
            _ResolvedSocketAddress(
                address=str(ip_obj),
                family=family,
                socket_type=socket_type,
                protocol=protocol,
                sockaddr=sockaddr,
            )
        )

    if not addresses:
        raise ValueError(f"fetch hostname returned no TCP addresses: {host}")

    return _ResolvedFetchTarget(
        request_url=url,
        scheme=scheme,
        hostname=host,
        port=port,
        addresses=tuple(addresses),
        constraints_signature=(
            tuple(constraints.allowed_domains),
            tuple(constraints.blocked_domains),
            constraints.allow_private_networks,
        ),
    )


def validate_fetch_url(url: str, constraints: SearchConstraints) -> None:
    """Reject unsupported, disallowed, or private-network fetch URLs."""
    _resolve_fetch_target(url, constraints)


def validate_content_type(content_type: str, constraints: SearchConstraints) -> str:
    """Normalize and enforce an allowlist of supported response MIME types."""
    mime = (content_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    if not mime:
        mime = "application/octet-stream"
    if constraints.allowed_content_types and mime not in {
        value.strip().lower() for value in constraints.allowed_content_types if value.strip()
    }:
        raise ValueError(f"content type blocked: {mime}")
    return mime


def detect_paywall(text: str) -> bool:
    """Return ``True`` for common paywall/interstitial markers."""
    lowered = text.lower()
    return any(marker in lowered for marker in _PAYWALL_MARKERS)


def _ensure_public_address(address: str) -> None:
    ip_obj = ipaddress.ip_address(address)
    if (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
        or not ip_obj.is_global
    ):
        raise ValueError(f"private network address blocked: {address}")


def _domain_matches(domain: str, pattern: str) -> bool:
    domain = domain.lower().strip(".")
    pattern = pattern.lower().strip(".")
    return domain == pattern or domain.endswith(f".{pattern}")


__all__ = [
    "detect_paywall",
    "sanitize_untrusted_text",
    "validate_content_type",
    "validate_fetch_url",
]
