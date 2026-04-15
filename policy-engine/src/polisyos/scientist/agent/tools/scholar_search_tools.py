"""Register Scholar web-search functions as LLM-callable tools."""

from __future__ import annotations

from polisyos.scholar.search.service import ScholarDeepSearchService

from .registry import ToolRegistry
from .schema import ToolDefinition


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
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 10},
                    "allowed_domains": {"type": "array", "items": {"type": "string"}},
                    "blocked_domains": {"type": "array", "items": {"type": "string"}},
                    "source_types": {"type": "array", "items": {"type": "string"}},
                    "recency_days": {"type": ["integer", "null"]},
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
        service.scholar_web_search,
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
                    "url": {"type": "string"},
                    "allowed_domains": {"type": "array", "items": {"type": "string"}},
                    "blocked_domains": {"type": "array", "items": {"type": "string"}},
                    "source_types": {"type": "array", "items": {"type": "string"}},
                    "recency_days": {"type": ["integer", "null"]},
                    "locale": {"type": "string", "default": "en-US"},
                    "user_location": {"type": ["string", "null"]},
                    "allow_private_networks": {"type": "boolean", "default": False},
                    "max_bytes": {"type": "integer", "default": 2000000},
                },
                "required": ["url"],
                "additionalProperties": False,
            },
            domain="academic",
            timeout_s=30.0,
            response_verbosity="detailed",
            response_max_chars=60_000,
        ),
        service.scholar_fetch_open,
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
                    "url": {"type": "string"},
                    "pattern": {"type": "string"},
                    "allowed_domains": {"type": "array", "items": {"type": "string"}},
                    "blocked_domains": {"type": "array", "items": {"type": "string"}},
                    "source_types": {"type": "array", "items": {"type": "string"}},
                    "recency_days": {"type": ["integer", "null"]},
                    "locale": {"type": "string", "default": "en-US"},
                    "user_location": {"type": ["string", "null"]},
                    "allow_private_networks": {"type": "boolean", "default": False},
                    "max_bytes": {"type": "integer", "default": 2000000},
                    "max_snippets": {"type": "integer", "default": 5},
                    "window_chars": {"type": "integer", "default": 400},
                },
                "required": ["url", "pattern"],
                "additionalProperties": False,
            },
            domain="academic",
            timeout_s=30.0,
            response_verbosity="concise",
            response_max_chars=24_000,
        ),
        service.scholar_find_in_page,
    )
    return registry


__all__ = ["build_scholar_search_tool_registry"]
