"""Contract models for the streaming resolve/extract stage."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResolveExtractStats:
    """Cumulative counters and latency samples for resolve/extract passes."""

    records: int = 0
    fulltext_resolved: int = 0
    abstract_only: int = 0
    eligible_fulltext: int = 0
    context_eligible: int = 0
    rejected: int = 0
    llm_requests: int = 0
    extracted: int = 0
    raw_claims: int = 0
    published_claims: int = 0
    extraction_errors: int = 0
    provider_length_stop: int = 0
    provider_429: int = 0
    provider_5xx: int = 0
    timeouts: int = 0
    json_parse_errors: int = 0
    empty_responses: int = 0
    low_fulltext_coverage_topics: int = 0
    papers_classified: int = 0
    track_b_routed: int = 0
    track_b_only_routed: int = 0
    track_b_rejected_hard: int = 0
    context_attributes_extracted: int = 0
    moderation_edges_extracted: int = 0
    numeric_rescue_requests: int = 0
    numeric_rescue_successes: int = 0
    numeric_rescue_failures: int = 0
    numeric_rescue_parameters_added: int = 0
    deterministic_numeric_rescue_successes: int = 0
    deterministic_numeric_rescue_parameters_added: int = 0
    total_tokens_prompt: int = 0
    total_tokens_completion: int = 0
    total_extraction_cost_usd: float = 0.0
    fetch_latency_ms: list[float] = field(default_factory=list)
    llm_latency_ms: list[float] = field(default_factory=list)
    limiter_wait_ms: list[float] = field(default_factory=list)
    rejection_reason_counts: Counter[str] = field(default_factory=Counter)
    failure_class_counts: Counter[str] = field(default_factory=Counter)


@dataclass
class WorkItem:
    """Selected OpenAlex work plus topic routing metadata for resolve/extract scheduling."""

    work: dict[str, Any]
    work_id: str
    topic_id: str
    topic_ids: list[str]
    topic_display_names: list[str]
    prefetch_priority: float
    selected_rank: int


@dataclass
class EligibleItem:
    """Full-text work payload annotated with source quality and LLM/context eligibility flags."""

    work_item: WorkItem
    text: str
    source_kind: str
    source_url: str
    text_quality: str
    post_priority: float
    llm_eligible: bool
    context_eligible: bool


@dataclass(frozen=True)
class EligibilityDecision:
    """Binary routing decision and rejection reasons for one resolve/extract candidate."""

    llm_eligible: bool
    context_eligible: bool
    rejection_reasons: list[str]


@dataclass
class ProviderResponse:
    """Normalized LLM provider response for one extraction call."""

    parsed: dict[str, Any]
    usage: dict[str, Any]
    http_status: int
    finish_reason: str
    latency_ms: float
    retry_count: int
    limiter_wait_ms: float
    backoff_sleep_ms: float
    parse_status: str
    error_class: str
    raw_content: str
    truncated_output: bool
    provider_key_index: int | None = None


__all__ = [
    "EligibilityDecision",
    "EligibleItem",
    "ProviderResponse",
    "ResolveExtractStats",
    "WorkItem",
]
