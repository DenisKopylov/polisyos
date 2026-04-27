"""Safe fetch/open/find guards for Scientist deep-research evidence."""

from __future__ import annotations

import hashlib
import re
import urllib.parse
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from polisyos.scholar.search.models import FetchResult, FetchSafetyEvent, SearchConstraints
from polisyos.scholar.search.security import (
    sanitize_untrusted_text,
    validate_content_type,
    validate_fetch_url,
)

PROMPT_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?prior\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"developer\s*:\s*", re.IGNORECASE),
    re.compile(r"reveal\s+(the\s+)?(system|developer)\s+(prompt|message)", re.IGNORECASE),
    re.compile(r"exfiltrat(?:e|ion)", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
)

_SCRIPT_STYLE_BLOCK_RE = re.compile(
    r"<(script|style|noscript|template|svg)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True, slots=True)
class SafeFetchPolicy:
    """Runtime caps and policy for one fetch/open/find call."""

    constraints: SearchConstraints
    max_bytes: int = 2_000_000
    max_extracted_chars: int = 400_000
    fail_closed: bool = True


def cap_tool_int(value: int | None, *, default: int, minimum: int, maximum: int) -> int:
    """Clamp integer tool arguments before they can affect fetch/search limits."""

    try:
        resolved = int(default if value is None else value)
    except (TypeError, ValueError):
        resolved = default
    return max(minimum, min(maximum, resolved))


def evaluate_fetch_request(
    url: str,
    *,
    constraints: SearchConstraints,
    max_bytes: int = 2_000_000,
) -> list[FetchSafetyEvent]:
    """Return safety events for a URL before a live fetch is attempted."""

    events: list[FetchSafetyEvent] = []
    if max_bytes < 1024:
        events.append(
            _event(
                url=url,
                event_type="max_bytes_exceeded",
                severity="block",
                message="max_bytes is below the supported safe-fetch minimum",
                metadata={"max_bytes": max_bytes},
            )
        )
    try:
        validate_fetch_url(url, constraints)
    except Exception as exc:
        if _is_dns_resolution_error(str(exc)):
            events.append(
                _event(
                    url=url,
                    event_type="robots_or_policy_block",
                    severity="warning",
                    message=f"DNS resolution was unavailable during preflight: {exc}",
                )
            )
            return events
        event_type = _classify_fetch_error(str(exc))
        events.append(
            _event(
                url=url,
                event_type=event_type,
                severity="block",
                message=str(exc),
            )
        )
    return events


def _is_dns_resolution_error(message: str) -> bool:
    lowered = message.lower()
    return any(
        token in lowered
        for token in (
            "name or service not known",
            "nodename nor servname",
            "temporary failure in name resolution",
            "failed to resolve",
            "no address associated",
        )
    )


def evaluate_content_type(
    content_type: str,
    *,
    url: str,
    constraints: SearchConstraints,
) -> tuple[str, list[FetchSafetyEvent]]:
    """Normalize and validate a response MIME type without trusting page content."""

    try:
        return validate_content_type(content_type, constraints), []
    except Exception as exc:
        mime = (content_type or "application/octet-stream").split(";", 1)[0].strip().lower()
        return mime or "application/octet-stream", [
            _event(
                url=url,
                event_type="blocked_content_type",
                severity="block",
                message=str(exc),
                metadata={"content_type": content_type},
            )
        ]


def sanitize_untrusted_page_text(text: str, *, max_chars: int = 400_000) -> str:
    """Strip obvious non-visible HTML and neutralize instruction-like page text."""

    without_blocks = _SCRIPT_STYLE_BLOCK_RE.sub(" ", text)
    without_tags = _HTML_TAG_RE.sub(" ", without_blocks)
    return neutralize_instruction_markers(
        sanitize_untrusted_text(without_tags, max_chars=max_chars),
    )


def detect_prompt_injection(
    text: str,
    *,
    url: str = "",
) -> list[FetchSafetyEvent]:
    """Emit warnings for instruction-like text while keeping the text untrusted."""

    if not text:
        return []
    lowered = text.lower()
    marker_present = "[[removed-untrusted-instruction]]" in lowered
    pattern_present = any(pattern.search(text) for pattern in PROMPT_INJECTION_PATTERNS)
    if not marker_present and not pattern_present:
        return []
    return [
        _event(
            url=url,
            event_type="prompt_injection_suspected",
            severity="warning",
            message=(
                "Retrieved page text contains instruction-like phrases; "
                "store only as untrusted evidence text."
            ),
            metadata={"self_certifies_safe": False},
        )
    ]


def neutralize_instruction_markers(text: str) -> str:
    """Replace common instruction-control markers inside untrusted evidence text."""

    cleaned = text
    for pattern in PROMPT_INJECTION_PATTERNS:
        cleaned = pattern.sub("[[removed-untrusted-instruction]]", cleaned)
    return cleaned


def build_blocked_fetch_result(
    url: str,
    *,
    error: str,
    source_type: str = "web",
) -> FetchResult:
    """Build a FetchResult for a blocked URL without opening the network."""

    return FetchResult(
        url=url,
        final_url=url,
        text="",
        status="blocked",
        error=error,
        source_type=source_type,
        fetched_at=datetime.now(UTC),
    )


def _classify_fetch_error(message: str) -> Literal[
    "blocked_private_network",
    "blocked_domain",
    "blocked_content_type",
    "max_bytes_exceeded",
    "prompt_injection_suspected",
    "malformed_url",
    "robots_or_policy_block",
]:
    lowered = message.lower()
    if "private network" in lowered or "localhost" in lowered:
        return "blocked_private_network"
    if "domain blocked" in lowered or "domain not allowed" in lowered:
        return "blocked_domain"
    if "content type blocked" in lowered:
        return "blocked_content_type"
    if "max_bytes" in lowered or "exceeds" in lowered:
        return "max_bytes_exceeded"
    parsed = urllib.parse.urlparse(message)
    if "unsupported fetch url" in lowered or parsed.scheme not in {"http", "https", ""}:
        return "malformed_url"
    return "robots_or_policy_block"


def _event(
    *,
    url: str,
    event_type: Literal[
        "blocked_private_network",
        "blocked_domain",
        "blocked_content_type",
        "max_bytes_exceeded",
        "prompt_injection_suspected",
        "malformed_url",
        "robots_or_policy_block",
    ],
    severity: Literal["info", "warning", "block"],
    message: str,
    metadata: dict[str, object] | None = None,
) -> FetchSafetyEvent:
    payload = f"{event_type}|{url}|{message}".encode()
    return FetchSafetyEvent(
        event_id=f"fetch_safety.{hashlib.sha256(payload).hexdigest()[:16]}",
        url=url,
        event_type=event_type,
        severity=severity,
        message=message,
        metadata=metadata or {},
    )


__all__ = [
    "PROMPT_INJECTION_PATTERNS",
    "SafeFetchPolicy",
    "build_blocked_fetch_result",
    "cap_tool_int",
    "detect_prompt_injection",
    "evaluate_content_type",
    "evaluate_fetch_request",
    "neutralize_instruction_markers",
    "sanitize_untrusted_page_text",
]
