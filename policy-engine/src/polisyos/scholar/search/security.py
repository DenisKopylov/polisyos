"""Fetch and page-extraction safety guards for Scholar web search."""

from __future__ import annotations

import ipaddress
import re
import socket
import urllib.parse
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


def validate_fetch_url(url: str, constraints: SearchConstraints) -> None:
    """Reject non-http, blocked-domain, and private-network URLs."""
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").strip().lower()
    if scheme not in {"http", "https"} or not host:
        raise ValueError(f"unsupported fetch URL: {url!r}")

    if constraints.allowed_domains and not any(
        _domain_matches(host, allowed) for allowed in constraints.allowed_domains
    ):
        raise ValueError(f"domain not allowed: {host}")
    if constraints.blocked_domains and any(
        _domain_matches(host, blocked) for blocked in constraints.blocked_domains
    ):
        raise ValueError(f"domain blocked: {host}")

    if constraints.allow_private_networks:
        return

    if host in _LOCAL_HOSTS or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError(f"private network address blocked: {host}")

    try:
        ip_obj = ipaddress.ip_address(host)
    except ValueError:
        infos = socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP)
        for info in infos:
            address = info[4][0]
            _ensure_public_address(address)
    else:
        _ensure_public_address(str(ip_obj))


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
