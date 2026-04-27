"""Pydantic contracts for Scholar web search, page retrieval, and evidence bundles."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class SearchBudgetControls(BaseModel):
    """Hard limits for one deep-search run."""

    model_config = ConfigDict(extra="forbid")

    max_search_queries: int = Field(default=12, ge=1, le=256)
    max_fetch_pages: int = Field(default=24, ge=1, le=1024)
    max_parallel_queries: int = Field(default=3, ge=1, le=64)
    max_parallel_fetches: int = Field(default=8, ge=1, le=128)
    max_depth: int = Field(default=2, ge=0, le=8)
    max_wall_time_s: float = Field(default=60.0, ge=1.0, le=3600.0)
    per_page_max_bytes: int = Field(default=2_000_000, ge=1024, le=50_000_000)


class SearchConstraints(BaseModel):
    """Provider/runtime constraints applied to search and fetch operations."""

    model_config = ConfigDict(extra="forbid")

    allowed_domains: list[str] = Field(default_factory=list)
    blocked_domains: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)
    recency_days: int | None = Field(default=None, ge=1, le=3650)
    locale: str = "en-US"
    user_location: str | None = None
    allow_private_networks: bool = False
    allowed_content_types: list[str] = Field(
        default_factory=lambda: ["text/html", "text/plain", "application/pdf"],
    )

    @field_validator("allowed_domains", "blocked_domains", "source_types")
    @classmethod
    def _normalize_text_list(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            text = value.strip().lower()
            if text:
                cleaned.append(text)
        return sorted(dict.fromkeys(cleaned))


class ResearchBrief(BaseModel):
    """Normalized research task used to derive a query graph."""

    model_config = ConfigDict(extra="forbid")

    question: str
    domain: str = ""
    jurisdictions: list[str] = Field(default_factory=list)
    time_window_start: str | None = None
    time_window_end: str | None = None
    locale: str = "en-US"
    perspectives: list[str] = Field(default_factory=list)
    required_source_types: list[str] = Field(default_factory=list)
    preferred_domains: list[str] = Field(default_factory=list)
    seed_terms: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class QueryNode(BaseModel):
    """One query expansion node in the deep-research DAG."""

    model_config = ConfigDict(extra="forbid")

    node_id: str
    query: str
    perspective: str
    depth: int = Field(default=0, ge=0)
    parent_id: str | None = None
    rationale: str = ""
    provider: str | None = None
    status: Literal["pending", "searched", "expanded", "failed"] = "pending"
    hit_count: int = Field(default=0, ge=0)
    reformulations: list[str] = Field(default_factory=list)


class QueryGraph(BaseModel):
    """Search query DAG generated from a ``ResearchBrief``."""

    model_config = ConfigDict(extra="forbid")

    brief: ResearchBrief
    nodes: list[QueryNode] = Field(default_factory=list)
    root_node_ids: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def node_by_id(self, node_id: str) -> QueryNode:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(node_id)


class WebSearchHit(BaseModel):
    """One search engine result before page fetching."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    title: str = ""
    snippet: str = ""
    provider: str
    query: str
    rank: int = Field(default=0, ge=0)
    source_type: str = "web"
    published_at: datetime | None = None
    score: float = 0.0


class FetchResult(BaseModel):
    """Extracted page payload plus retrieval metadata."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    final_url: str
    title: str = ""
    text: str = ""
    content_type: str = "application/octet-stream"
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: Literal["ok", "cached", "blocked", "error"] = "ok"
    content_sha256: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    redirect_chain: list[str] = Field(default_factory=list)
    paywalled: bool = False
    error: str | None = None
    source_type: str = "web"
    artifact_id: str | None = None


class SourceMetadata(BaseModel):
    """Normalized evidence source metadata for citation and ranking."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    url: HttpUrl
    title: str = ""
    domain: str
    source_type: str = "web"
    provider: str = ""
    search_query: str = ""
    search_rank: int = 0
    fetched_at: datetime | None = None
    published_at: datetime | None = None
    page_age_days: int | None = None
    fetch_status: str = "ok"
    content_type: str = "application/octet-stream"
    content_sha256: str | None = None
    quality_score: float = 0.0
    anti_seo_score: float = 0.0
    duplicate_of_source_id: str | None = None
    paywalled: bool = False
    error: str | None = None


class SourceSnippet(BaseModel):
    """Citation-ready source span extracted from a fetched page."""

    model_config = ConfigDict(extra="forbid")

    snippet_id: str
    source_id: str
    url: HttpUrl
    query_node_id: str
    perspective: str
    text: str
    start_char: int = Field(default=0, ge=0)
    end_char: int = Field(default=0, ge=0)
    relevance_score: float = 0.0


class SearchQueryTrace(BaseModel):
    """Execution trace for one provider query."""

    model_config = ConfigDict(extra="forbid")

    query_node_id: str
    query: str
    perspective: str
    provider: str
    hit_count: int = Field(default=0, ge=0)
    searched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None


class ClaimSupportLink(BaseModel):
    """Link one claim to ranked evidence snippets and source URLs."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_text: str
    snippet_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    support_score: float = 0.0
    conflict_score: float = 0.0
    uncertainty_note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_snippet_level_support(self) -> ClaimSupportLink:
        status = str(self.metadata.get("support_status", "")).strip().lower()
        if self.source_ids and not self.snippet_ids and status != "unsupported":
            raise ValueError(
                "ClaimSupportLink with source_ids must include snippet_ids or be marked unsupported"
            )
        if self.support_score > 0 and not self.snippet_ids and status != "unsupported":
            raise ValueError(
                "ClaimSupportLink with positive support_score must include snippet_ids"
            )
        return self


class FetchSafetyEvent(BaseModel):
    """Machine-readable safety event emitted by safe fetch/extract stages."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    url: str
    event_type: Literal[
        "blocked_private_network",
        "blocked_domain",
        "blocked_content_type",
        "max_bytes_exceeded",
        "prompt_injection_suspected",
        "malformed_url",
        "robots_or_policy_block",
    ]
    severity: Literal["info", "warning", "block"]
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceQualitySignal(BaseModel):
    """Deterministic heuristic source-quality signal for one source."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    authority_score: float = Field(ge=0.0, le=1.0)
    freshness_score: float = Field(ge=0.0, le=1.0)
    primary_source_score: float = Field(ge=0.0, le=1.0)
    anti_seo_score: float = Field(ge=0.0, le=1.0)
    duplicate_score: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class WebEvidenceBundle(BaseModel):
    """Final deep-search artifact with query traces, source metadata, snippets, and claim links."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    bundle_id: str
    brief: ResearchBrief
    query_graph: QueryGraph
    query_traces: list[SearchQueryTrace] = Field(default_factory=list)
    sources: list[SourceMetadata] = Field(default_factory=list)
    snippets: list[SourceSnippet] = Field(default_factory=list)
    claim_supports: list[ClaimSupportLink] = Field(default_factory=list)
    fetch_safety_events: list[FetchSafetyEvent] = Field(default_factory=list)
    source_quality_signals: list[SourceQualitySignal] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    partial: bool = False
    checkpoint_artifact_id: str | None = None

    @model_validator(mode="after")
    def _validate_evidence_links(self) -> WebEvidenceBundle:
        source_ids = {source.source_id for source in self.sources}
        snippet_ids = {snippet.snippet_id for snippet in self.snippets}
        duplicate_sources = len(source_ids) != len(self.sources)
        duplicate_snippets = len(snippet_ids) != len(self.snippets)
        if duplicate_sources:
            raise ValueError("WebEvidenceBundle source_id values must be unique")
        if duplicate_snippets:
            raise ValueError("WebEvidenceBundle snippet_id values must be unique")
        for snippet in self.snippets:
            if source_ids and snippet.source_id not in source_ids:
                raise ValueError(f"snippet references missing source_id: {snippet.source_id}")
            if snippet.end_char and snippet.end_char < snippet.start_char:
                raise ValueError(f"snippet has invalid span: {snippet.snippet_id}")
        for support in self.claim_supports:
            missing_snippets = [item for item in support.snippet_ids if item not in snippet_ids]
            if missing_snippets:
                raise ValueError(
                    f"claim support references missing snippet_id: {missing_snippets[0]}"
                )
            missing_sources = [
                item for item in support.source_ids if source_ids and item not in source_ids
            ]
            if missing_sources:
                raise ValueError(
                    f"claim support references missing source_id: {missing_sources[0]}"
                )
        for signal in self.source_quality_signals:
            if source_ids and signal.source_id not in source_ids:
                raise ValueError(f"quality signal references missing source_id: {signal.source_id}")
        return self


class ResearchProgressEvent(BaseModel):
    """One resumable research progress event."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    phase: str
    message: str
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    checkpoint_artifact_id: str | None = None


class ResearchJobCheckpoint(BaseModel):
    """Persisted resumable state for background deep-search jobs."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    brief: ResearchBrief
    query_graph: QueryGraph
    constraints: SearchConstraints | None = None
    budgets: SearchBudgetControls | None = None
    bundle: WebEvidenceBundle
    progress_events: list[ResearchProgressEvent] = Field(default_factory=list)
    error: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResearchJobStatus(BaseModel):
    """Current status of an in-memory or resumed deep-search job."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    checkpoint_artifact_id: str | None = None
    latest_event: ResearchProgressEvent | None = None
    result_bundle: WebEvidenceBundle | None = None
    error: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


__all__ = [
    "ClaimSupportLink",
    "FetchResult",
    "FetchSafetyEvent",
    "QueryGraph",
    "QueryNode",
    "ResearchBrief",
    "ResearchJobCheckpoint",
    "ResearchJobStatus",
    "ResearchProgressEvent",
    "SearchBudgetControls",
    "SearchConstraints",
    "SearchQueryTrace",
    "SourceMetadata",
    "SourceQualitySignal",
    "SourceSnippet",
    "WebEvidenceBundle",
    "WebSearchHit",
]
