"""Pydantic contracts for Scholar web search, page retrieval, and evidence bundles."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictStr,
    field_validator,
    model_validator,
)

from polisyos.core.artifacts import ArtifactRef  # Pydantic field type


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
    raw_artifact_ref: ArtifactRef | None = None
    byte_size: int | None = Field(default=None, ge=0)
    license: str = "public-web"
    fetch_profile: dict[str, Any] = Field(default_factory=dict)
    lineage_parent_artifact_id: str | None = None
    refresh_reason: str | None = None


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
    artifact_id: str | None = None
    raw_artifact_ref: ArtifactRef | None = None
    byte_size: int | None = Field(default=None, ge=0)
    license: str = "public-web"
    fetch_profile: dict[str, Any] = Field(default_factory=dict)
    final_url: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    redirect_chain: list[str] = Field(default_factory=list)
    lineage_parent_artifact_id: str | None = None
    refresh_reason: str | None = None
    publication_tier: str | None = None
    underlying_study_id: str | None = None
    dataset_ids: list[str] = Field(default_factory=list)
    author_names: list[str] = Field(default_factory=list)
    institution_names: list[str] = Field(default_factory=list)
    citation_network_refs: list[str] = Field(default_factory=list)
    replication_of_source_id: str | None = None
    review_status: str | None = None
    quality_score: float = 0.0
    anti_seo_score: float = 0.0
    duplicate_of_source_id: str | None = None
    paywalled: bool = False
    error: str | None = None

    @model_validator(mode="after")
    def _derive_raw_artifact_id(self) -> SourceMetadata:
        """Bind the content-addressed raw artifact when the fetch supplied a digest."""
        if self.raw_artifact_ref is not None:
            selected_id = str(self.raw_artifact_ref.artifact_id)
            if self.artifact_id is not None and self.artifact_id != selected_id:
                raise ValueError("artifact_id must match raw_artifact_ref")
            self.artifact_id = selected_id
        if self.artifact_id is None and self.content_sha256:
            digest = self.content_sha256.strip().lower()
            if digest.startswith("sha256:"):
                digest = digest[7:]
            if len(digest) == 64 and all(char in "0123456789abcdef" for char in digest):
                self.artifact_id = f"sha256:{digest}"
        return self


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


_ProviderTraceCount = Annotated[int, Field(ge=0, strict=True)]
_ProviderTraceReason = Annotated[StrictStr, Field(min_length=1)]
_ProviderTraceErrorType = Literal[
    "http_status_error",
    "timeout_error",
    "connection_error",
    "request_error",
    "provider_contract_error",
    "provider_exception",
]
_PERSISTED_PROVIDER_ERROR_CATEGORIES = frozenset({"provider_error", "legacy_error_not_established"})
_LEGACY_PROVIDER_ERROR_CATEGORY = "legacy_error_not_established"


class ProviderAttemptTrace(BaseModel):
    """Observed outcome for one provider in one ordered query attempt."""

    model_config = ConfigDict(extra="forbid")

    attempt_index: _ProviderTraceCount
    provider: StrictStr = Field(min_length=1)
    outcome: Literal[
        "error",
        "returned_hits",
        "returned_no_hits",
        "all_candidates_filtered",
    ]
    reason: Literal[
        "provider_error",
        "provider_returned_hits",
        "provider_returned_no_hits",
        "all_candidates_filtered",
        "normalization_rejected_candidates",
        "not_established",
    ]
    raw_result_count: _ProviderTraceCount | None = None
    pre_filter_candidate_count: _ProviderTraceCount | None = None
    eligible_candidate_count: _ProviderTraceCount | None = None
    returned_hit_count: _ProviderTraceCount = 0
    normalization_rejection_counts: dict[_ProviderTraceReason, _ProviderTraceCount] = Field(
        default_factory=dict
    )
    constraint_rejection_counts: dict[_ProviderTraceReason, _ProviderTraceCount] = Field(
        default_factory=dict
    )
    error: Literal["provider_error"] | None = None
    error_type: _ProviderTraceErrorType | None = None

    @model_validator(mode="after")
    def _validate_observed_outcome(self) -> ProviderAttemptTrace:
        """Reject count and status combinations that the producer cannot emit."""
        normalization_total = sum(self.normalization_rejection_counts.values())
        constraint_total = sum(self.constraint_rejection_counts.values())

        if self.raw_result_count is not None:
            if normalization_total > self.raw_result_count:
                raise ValueError("normalization rejection counts exceed raw results")
            if self.pre_filter_candidate_count is not None and (
                self.raw_result_count != self.pre_filter_candidate_count + normalization_total
            ):
                raise ValueError("raw results must reconcile with normalized candidates")

        if self.pre_filter_candidate_count is None:
            if self.eligible_candidate_count is not None or constraint_total:
                raise ValueError("constraint counts require observed candidates")
        elif constraint_total > self.pre_filter_candidate_count:
            raise ValueError("constraint rejection counts exceed normalized candidates")

        if self.eligible_candidate_count is not None:
            if self.pre_filter_candidate_count is None:
                raise ValueError("eligible count requires a pre-filter candidate count")
            if self.pre_filter_candidate_count - self.eligible_candidate_count != constraint_total:
                raise ValueError("eligible candidates must reconcile with constraint rejections")

        upper_bound = (
            self.eligible_candidate_count
            if self.eligible_candidate_count is not None
            else self.pre_filter_candidate_count
        )
        if upper_bound is not None and self.returned_hit_count > upper_bound:
            raise ValueError("returned hits exceed observed eligible candidates")

        if self.outcome == "error":
            if (
                self.reason != "provider_error"
                or self.error != "provider_error"
                or self.error_type is None
            ):
                raise ValueError("error outcome requires a safe category and exception type")
            if (
                self.returned_hit_count
                or self.raw_result_count is not None
                or self.pre_filter_candidate_count is not None
                or self.eligible_candidate_count is not None
                or normalization_total
                or constraint_total
            ):
                raise ValueError("provider errors cannot assert response counts")
            return self

        if self.error is not None or self.error_type is not None:
            raise ValueError("non-error outcome cannot carry provider error diagnostics")
        if self.outcome == "returned_hits":
            if self.returned_hit_count == 0:
                raise ValueError("returned_hits outcome requires at least one hit")
            if self.reason == "provider_returned_hits":
                if (
                    self.pre_filter_candidate_count is None
                    or self.eligible_candidate_count is None
                    or self.eligible_candidate_count == 0
                ):
                    raise ValueError("observed hit outcome requires eligible-candidate counts")
            elif self.reason == "not_established":
                if (
                    self.raw_result_count is not None
                    or self.pre_filter_candidate_count is not None
                    or self.eligible_candidate_count is not None
                    or normalization_total
                    or constraint_total
                ):
                    raise ValueError("unknown hit outcome cannot carry established counts")
            else:
                raise ValueError("returned hits have an incompatible reason")
            return self

        if self.returned_hit_count != 0:
            raise ValueError("no-hit outcomes cannot report returned hits")
        if self.outcome == "all_candidates_filtered":
            if (
                self.reason != "all_candidates_filtered"
                or self.pre_filter_candidate_count is None
                or self.pre_filter_candidate_count == 0
                or self.eligible_candidate_count != 0
                or constraint_total == 0
            ):
                raise ValueError("filtered outcome requires observed candidate rejections")
            return self

        if self.reason == "normalization_rejected_candidates":
            if (
                (self.raw_result_count is not None and self.raw_result_count == 0)
                or self.pre_filter_candidate_count != 0
                or self.eligible_candidate_count != 0
                or normalization_total == 0
            ):
                raise ValueError("normalization outcome requires rejected raw candidates")
        elif self.reason == "provider_returned_no_hits":
            if (
                self.raw_result_count != 0
                or self.pre_filter_candidate_count != 0
                or self.eligible_candidate_count != 0
                or normalization_total
                or constraint_total
            ):
                raise ValueError("provider-empty outcome requires an observed empty response")
        elif self.reason == "all_candidates_filtered":
            raise ValueError("filtered reason requires all_candidates_filtered outcome")
        elif self.reason == "not_established":
            if (
                self.raw_result_count == 0
                or (self.pre_filter_candidate_count or 0) > 0
                or (self.eligible_candidate_count or 0) > 0
                or normalization_total
                or constraint_total
            ):
                raise ValueError("unknown no-hit outcome cannot contradict observed counts")
        else:
            raise ValueError("no-hit outcome has an incompatible reason")
        return self


class SearchQueryTrace(BaseModel):
    """Execution trace for one provider query."""

    model_config = ConfigDict(extra="forbid")

    query_node_id: str
    query: str
    perspective: str
    provider: str
    hit_count: _ProviderTraceCount = 0
    searched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error: str | None = Field(default=None, min_length=1)
    provider_attempts: list[ProviderAttemptTrace] | None = None

    @model_validator(mode="after")
    def _validate_attempt_sequence(self) -> SearchQueryTrace:
        """Bind selected provider, hit count, and error to the observed attempts."""
        if self.provider_attempts is None:
            return self
        if not self.provider_attempts:
            raise ValueError("provider_attempts must contain at least one observed call")
        for expected_index, attempt in enumerate(self.provider_attempts):
            if attempt.attempt_index != expected_index:
                raise ValueError("provider attempt indexes must be ordered and contiguous")

        final_attempt = self.provider_attempts[-1]
        if self.provider != final_attempt.provider:
            raise ValueError("selected provider must match the final observed attempt")
        latest_error = next(
            (attempt.error for attempt in reversed(self.provider_attempts) if attempt.error),
            None,
        )
        if self.hit_count:
            if self.error is not None:
                raise ValueError("successful query trace cannot retain a provider error")
            if final_attempt.returned_hit_count != self.hit_count:
                raise ValueError("query hit count must match the selected provider attempt")
            if any(attempt.returned_hit_count for attempt in self.provider_attempts[:-1]):
                raise ValueError("provider failover stops after the first non-empty response")
        else:
            if any(attempt.returned_hit_count for attempt in self.provider_attempts):
                raise ValueError("no-hit query trace cannot contain returned hits")
            if self.error != latest_error:
                raise ValueError("query error must match the latest observed provider error")
        return self


class NoHitFrontierRecord(BaseModel):
    """Replayable record that a real provider query returned no candidate hits."""

    model_config = ConfigDict(extra="forbid")

    query_node_id: str
    query: str
    perspective: str
    provider: str
    reason: Literal["provider_returned_no_hits", "provider_error_no_hits"]
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

    schema_version: Literal["1.0", "1.1"] = "1.0"
    bundle_id: str
    brief: ResearchBrief
    query_graph: QueryGraph
    query_traces: list[SearchQueryTrace] = Field(default_factory=list)
    no_hit_frontier: list[NoHitFrontierRecord] = Field(default_factory=list)
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
        if self.schema_version == "1.0" and any(
            trace.provider_attempts is not None for trace in self.query_traces
        ):
            raise ValueError("provider attempts require WebEvidenceBundle schema 1.1")
        attempted_query_ids = {
            trace.query_node_id
            for trace in self.query_traces
            if trace.provider_attempts is not None
        }
        if self.schema_version == "1.1":
            if any(
                trace.error not in _PERSISTED_PROVIDER_ERROR_CATEGORIES | {None}
                for trace in self.query_traces
            ):
                raise ValueError("schema 1.1 query errors must use a safe category")
            if any(
                record.error not in _PERSISTED_PROVIDER_ERROR_CATEGORIES | {None}
                for record in self.no_hit_frontier
            ):
                raise ValueError("schema 1.1 frontier errors must use a safe category")
            for frontier_record in self.no_hit_frontier:
                if (
                    frontier_record.query_node_id in attempted_query_ids
                    and frontier_record.error not in {None, "provider_error"}
                ):
                    raise ValueError(
                        "provider-attempt no-hit errors must use the safe provider category"
                    )
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

    def _validated_schema_1_1_candidate(self) -> WebEvidenceBundle:
        """Validate a new 1.1 write, projecting only legacy 1.0 errors.

        Historical 1.0 traces do not establish structured provider attempts. Their
        old free-text errors are therefore replaced in the new projection by an
        explicit unknown category; the original artifact is never rewritten.
        """
        source = WebEvidenceBundle.model_validate(self.model_dump(mode="python"))
        payload = source.model_dump(mode="python")
        if source.schema_version == "1.0":
            for trace in payload["query_traces"]:
                if trace["error"] is not None:
                    trace["error"] = _LEGACY_PROVIDER_ERROR_CATEGORY
            for frontier_record in payload["no_hit_frontier"]:
                if frontier_record["error"] is not None:
                    frontier_record["error"] = _LEGACY_PROVIDER_ERROR_CATEGORY
            payload["schema_version"] = "1.1"
        return WebEvidenceBundle.model_validate(payload)


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
    requirement_specs: list[dict[str, Any]] = Field(default_factory=list)
    bundle: WebEvidenceBundle
    progress_events: list[ResearchProgressEvent] = Field(default_factory=list)
    error: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResearchJobStatus(BaseModel):
    """Current status of an in-memory or resumed deep-search job."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: Literal["pending", "running", "completed", "failed", "escalated"]
    checkpoint_artifact_id: str | None = None
    scholar_academic_evidence_artifact_id: str | None = None
    latest_event: ResearchProgressEvent | None = None
    result_bundle: WebEvidenceBundle | None = None
    error: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


__all__ = [
    "ClaimSupportLink",
    "FetchResult",
    "FetchSafetyEvent",
    "NoHitFrontierRecord",
    "ProviderAttemptTrace",
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
