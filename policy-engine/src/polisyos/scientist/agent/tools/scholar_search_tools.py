"""Register Scholar web-search functions as LLM-callable tools."""

from __future__ import annotations

import hashlib
import inspect
from typing import Any

from polisyos.scholar.search.models import FetchSafetyEvent, SearchConstraints
from polisyos.scholar.search.service import ScholarDeepSearchService
from polisyos.scientist.evidence.safe_fetch import (
    build_blocked_fetch_result,
    cap_tool_int,
    detect_prompt_injection,
    evaluate_fetch_request,
    sanitize_untrusted_page_text,
)

from .registry import ToolRegistry
from .schema import ToolDefinition

MAX_SEARCH_RESULTS = 50
MAX_FETCH_BYTES = 5_000_000
MAX_EXTRACTED_CHARS = 120_000
MAX_SNIPPETS = 20
MAX_WINDOW_CHARS = 2_000


def build_scholar_search_tool_registry(
    service: ScholarDeepSearchService,
) -> ToolRegistry:
    """Create a `ToolRegistry` exposing first-class Scholar search tools."""
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="scholar_web_search",
            description=(
                "Search the public web for policy evidence with domain, recency, "
                "source-type, and locale controls."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 600},
                    "max_results": {
                        "type": "integer",
                        "default": 10,
                        "minimum": 1,
                        "maximum": MAX_SEARCH_RESULTS,
                    },
                    "allowed_domains": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 255},
                        "maxItems": 50,
                    },
                    "blocked_domains": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 255},
                        "maxItems": 200,
                    },
                    "source_types": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 64},
                        "maxItems": 20,
                    },
                    "recency_days": {"type": ["integer", "null"], "minimum": 1, "maximum": 3650},
                    "locale": {"type": "string", "default": "en-US"},
                    "user_location": {"type": ["string", "null"]},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            domain="academic",
            timeout_s=30.0,
            response_verbosity="concise",
            response_max_chars=24_000,
        ),
        _safe_web_search_handler(service),
    )
    registry.register(
        ToolDefinition(
            name="scholar_fetch_open",
            description=(
                "Fetch and extract one web page safely with cache-first retrieval, "
                "private-network guards, and content-type limits."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "minLength": 1, "maxLength": 2048},
                    "allowed_domains": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 255},
                        "maxItems": 50,
                    },
                    "blocked_domains": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 255},
                        "maxItems": 200,
                    },
                    "source_types": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 64},
                        "maxItems": 20,
                    },
                    "recency_days": {"type": ["integer", "null"], "minimum": 1, "maximum": 3650},
                    "locale": {"type": "string", "default": "en-US"},
                    "user_location": {"type": ["string", "null"]},
                    "allow_private_networks": {"type": "boolean", "default": False},
                    "max_bytes": {
                        "type": "integer",
                        "default": 2000000,
                        "minimum": 1024,
                        "maximum": MAX_FETCH_BYTES,
                    },
                    "max_extracted_chars": {
                        "type": "integer",
                        "default": MAX_EXTRACTED_CHARS,
                        "minimum": 1024,
                        "maximum": MAX_EXTRACTED_CHARS,
                    },
                },
                "required": ["url"],
                "additionalProperties": False,
            },
            domain="academic",
            timeout_s=30.0,
            response_verbosity="detailed",
            response_max_chars=60_000,
        ),
        _safe_fetch_open_handler(service),
    )
    registry.register(
        ToolDefinition(
            name="scholar_find_in_page",
            description=(
                "Find a pattern in a fetched page and return citation-ready source spans."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "minLength": 1, "maxLength": 2048},
                    "pattern": {"type": "string", "minLength": 1, "maxLength": 600},
                    "allowed_domains": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 255},
                        "maxItems": 50,
                    },
                    "blocked_domains": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 255},
                        "maxItems": 200,
                    },
                    "source_types": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 64},
                        "maxItems": 20,
                    },
                    "recency_days": {"type": ["integer", "null"], "minimum": 1, "maximum": 3650},
                    "locale": {"type": "string", "default": "en-US"},
                    "user_location": {"type": ["string", "null"]},
                    "allow_private_networks": {"type": "boolean", "default": False},
                    "max_bytes": {
                        "type": "integer",
                        "default": 2000000,
                        "minimum": 1024,
                        "maximum": MAX_FETCH_BYTES,
                    },
                    "max_snippets": {
                        "type": "integer",
                        "default": 5,
                        "minimum": 1,
                        "maximum": MAX_SNIPPETS,
                    },
                    "window_chars": {
                        "type": "integer",
                        "default": 400,
                        "minimum": 80,
                        "maximum": MAX_WINDOW_CHARS,
                    },
                    "max_extracted_chars": {
                        "type": "integer",
                        "default": MAX_EXTRACTED_CHARS,
                        "minimum": 1024,
                        "maximum": MAX_EXTRACTED_CHARS,
                    },
                },
                "required": ["url", "pattern"],
                "additionalProperties": False,
            },
            domain="academic",
            timeout_s=30.0,
            response_verbosity="concise",
            response_max_chars=24_000,
        ),
        _safe_find_in_page_handler(service),
    )
    return registry


def _safe_web_search_handler(service: ScholarDeepSearchService):
    async def _handler(
        *,
        query: str,
        max_results: int = 10,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
        source_types: list[str] | None = None,
        recency_days: int | None = None,
        locale: str = "en-US",
        user_location: str | None = None,
    ) -> dict[str, Any]:
        return await _call_service(
            service.scholar_web_search,
            query=query.strip(),
            max_results=cap_tool_int(
                max_results,
                default=10,
                minimum=1,
                maximum=MAX_SEARCH_RESULTS,
            ),
            allowed_domains=allowed_domains or [],
            blocked_domains=blocked_domains or [],
            source_types=source_types or [],
            recency_days=recency_days,
            locale=locale,
            user_location=user_location,
        )

    return _handler


def _safe_fetch_open_handler(service: ScholarDeepSearchService):
    async def _handler(
        *,
        url: str,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
        source_types: list[str] | None = None,
        recency_days: int | None = None,
        locale: str = "en-US",
        user_location: str | None = None,
        allow_private_networks: bool = False,
        max_bytes: int = 2_000_000,
        max_extracted_chars: int = MAX_EXTRACTED_CHARS,
    ) -> dict[str, Any]:
        constraints = _constraints(
            allowed_domains=allowed_domains,
            blocked_domains=blocked_domains,
            source_types=source_types,
            recency_days=recency_days,
            locale=locale,
            user_location=user_location,
            allow_private_networks=allow_private_networks,
        )
        resolved_max_bytes = cap_tool_int(
            max_bytes,
            default=2_000_000,
            minimum=1024,
            maximum=MAX_FETCH_BYTES,
        )
        events = evaluate_fetch_request(
            url,
            constraints=constraints,
            max_bytes=resolved_max_bytes,
        )
        if _has_block(events):
            blocked = build_blocked_fetch_result(
                url,
                error="; ".join(event.message for event in events if event.severity == "block"),
                source_type=(source_types or ["web"])[0],
            )
            return _with_events(
                blocked.model_dump(mode="json", exclude_none=True),
                events,
            )
        payload = await _call_service(
            service.scholar_fetch_open,
            url=url,
            allowed_domains=allowed_domains or [],
            blocked_domains=blocked_domains or [],
            source_types=source_types or [],
            recency_days=recency_days,
            locale=locale,
            user_location=user_location,
            allow_private_networks=allow_private_networks,
            max_bytes=resolved_max_bytes,
        )
        return _cap_untrusted_payload(
            payload,
            events=[
                *events,
                *_events_from_fetch_payload(
                    payload,
                    constraints=constraints,
                    url=url,
                ),
            ],
            url=url,
            max_extracted_chars=max_extracted_chars,
        )

    return _handler


def _safe_find_in_page_handler(service: ScholarDeepSearchService):
    async def _handler(
        *,
        url: str,
        pattern: str,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
        source_types: list[str] | None = None,
        recency_days: int | None = None,
        locale: str = "en-US",
        user_location: str | None = None,
        allow_private_networks: bool = False,
        max_bytes: int = 2_000_000,
        max_snippets: int = 5,
        window_chars: int = 400,
        max_extracted_chars: int = MAX_EXTRACTED_CHARS,
    ) -> dict[str, Any]:
        constraints = _constraints(
            allowed_domains=allowed_domains,
            blocked_domains=blocked_domains,
            source_types=source_types,
            recency_days=recency_days,
            locale=locale,
            user_location=user_location,
            allow_private_networks=allow_private_networks,
        )
        resolved_max_bytes = cap_tool_int(
            max_bytes,
            default=2_000_000,
            minimum=1024,
            maximum=MAX_FETCH_BYTES,
        )
        events = evaluate_fetch_request(
            url,
            constraints=constraints,
            max_bytes=resolved_max_bytes,
        )
        if _has_block(events):
            blocked = build_blocked_fetch_result(
                url,
                error="; ".join(event.message for event in events if event.severity == "block"),
                source_type=(source_types or ["web"])[0],
            )
            return {
                "page": blocked.model_dump(mode="json", exclude_none=True),
                "snippets": [],
                "fetch_safety_events": _events_json(events),
            }
        payload = await _call_service(
            service.scholar_find_in_page,
            url=url,
            pattern=pattern,
            allowed_domains=allowed_domains or [],
            blocked_domains=blocked_domains or [],
            source_types=source_types or [],
            recency_days=recency_days,
            locale=locale,
            user_location=user_location,
            allow_private_networks=allow_private_networks,
            max_bytes=resolved_max_bytes,
            max_snippets=cap_tool_int(
                max_snippets,
                default=5,
                minimum=1,
                maximum=MAX_SNIPPETS,
            ),
            window_chars=cap_tool_int(
                window_chars,
                default=400,
                minimum=80,
                maximum=MAX_WINDOW_CHARS,
            ),
        )
        return _cap_untrusted_payload(
            payload,
            events=[
                *events,
                *_events_from_fetch_payload(
                    payload.get("page") if isinstance(payload.get("page"), dict) else payload,
                    constraints=constraints,
                    url=url,
                ),
            ],
            url=url,
            max_extracted_chars=max_extracted_chars,
        )

    return _handler


async def _call_service(method: Any, **kwargs: Any) -> dict[str, Any]:
    signature = inspect.signature(method)
    accepted = {
        key: value
        for key, value in kwargs.items()
        if key in signature.parameters
    }
    result = method(**accepted)
    if inspect.isawaitable(result):
        result = await result
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json", exclude_none=True)
    return dict(result)


def _constraints(
    *,
    allowed_domains: list[str] | None,
    blocked_domains: list[str] | None,
    source_types: list[str] | None,
    recency_days: int | None,
    locale: str,
    user_location: str | None,
    allow_private_networks: bool,
) -> SearchConstraints:
    return SearchConstraints(
        allowed_domains=allowed_domains or [],
        blocked_domains=blocked_domains or [],
        source_types=source_types or [],
        recency_days=recency_days,
        locale=locale,
        user_location=user_location,
        allow_private_networks=allow_private_networks,
    )


def _cap_untrusted_payload(
    payload: dict[str, Any],
    *,
    events: list[FetchSafetyEvent],
    url: str,
    max_extracted_chars: int,
) -> dict[str, Any]:
    capped = cap_tool_int(
        max_extracted_chars,
        default=MAX_EXTRACTED_CHARS,
        minimum=1024,
        maximum=MAX_EXTRACTED_CHARS,
    )
    active_events = list(events)
    for key in ("text", "snippet"):
        value = payload.get(key)
        if isinstance(value, str):
            active_events.extend(detect_prompt_injection(value, url=url))
            payload[key] = sanitize_untrusted_page_text(value, max_chars=capped)
    page = payload.get("page")
    if isinstance(page, dict) and isinstance(page.get("text"), str):
        text = str(page["text"])
        active_events.extend(detect_prompt_injection(text, url=url))
        page["text"] = sanitize_untrusted_page_text(text, max_chars=capped)
    snippets = payload.get("snippets")
    if isinstance(snippets, list):
        for snippet in snippets:
            if isinstance(snippet, dict) and isinstance(snippet.get("text"), str):
                text = str(snippet["text"])
                active_events.extend(detect_prompt_injection(text, url=url))
                snippet["text"] = sanitize_untrusted_page_text(text, max_chars=capped)
    payload["untrusted_evidence_text"] = True
    return _with_events(payload, active_events)


def _events_from_fetch_payload(
    payload: Any,
    *,
    constraints: SearchConstraints,
    url: str,
) -> list[FetchSafetyEvent]:
    if not isinstance(payload, dict):
        return []
    events: list[FetchSafetyEvent] = []
    content_type = payload.get("content_type")
    if isinstance(content_type, str) and content_type:
        _mime, content_type_events = _evaluate_payload_content_type(
            content_type,
            constraints=constraints,
            url=url,
        )
        events.extend(content_type_events)
    error = str(payload.get("error") or "")
    lowered_error = error.lower()
    if "max_bytes" in lowered_error or "exceeds max_bytes" in lowered_error:
        events.append(
            _tool_safety_event(
                url=url,
                event_type="max_bytes_exceeded",
                severity="block",
                message=error,
            )
        )
    if "content type blocked" in lowered_error and not any(
        event.event_type == "blocked_content_type" for event in events
    ):
        events.append(
            _tool_safety_event(
                url=url,
                event_type="blocked_content_type",
                severity="block",
                message=error,
            )
        )
    return events


def _evaluate_payload_content_type(
    content_type: str,
    *,
    constraints: SearchConstraints,
    url: str,
) -> tuple[str, list[FetchSafetyEvent]]:
    from polisyos.scientist.evidence.safe_fetch import evaluate_content_type

    return evaluate_content_type(content_type, url=url, constraints=constraints)


def _tool_safety_event(
    *,
    url: str,
    event_type: str,
    severity: str,
    message: str,
) -> FetchSafetyEvent:
    payload = f"{event_type}|{url}|{message}".encode()
    return FetchSafetyEvent(
        event_id=f"fetch_safety.{hashlib.sha256(payload).hexdigest()[:16]}",
        url=url,
        event_type=event_type,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        message=message,
    )


def _with_events(payload: dict[str, Any], events: list[FetchSafetyEvent]) -> dict[str, Any]:
    payload["fetch_safety_events"] = _events_json(events)
    return payload


def _events_json(events: list[FetchSafetyEvent]) -> list[dict[str, Any]]:
    deduped: dict[str, FetchSafetyEvent] = {event.event_id: event for event in events}
    return [event.model_dump(mode="json", exclude_none=True) for event in deduped.values()]


def _has_block(events: list[FetchSafetyEvent]) -> bool:
    return any(event.severity == "block" for event in events)


__all__ = [
    "MAX_EXTRACTED_CHARS",
    "MAX_FETCH_BYTES",
    "MAX_SEARCH_RESULTS",
    "MAX_SNIPPETS",
    "MAX_WINDOW_CHARS",
    "build_scholar_search_tool_registry",
]
