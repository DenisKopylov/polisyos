"""Scholar web-search and deep-research package."""

from __future__ import annotations

from .cache import CachedPageRecord, UrlFetchCache
from .fetcher import fetch_and_find_in_page, fetch_open_page, find_in_page, source_id_from_url
from .jobs import DeepResearchJobManager
from .models import (
    ClaimSupportLink,
    FetchResult,
    FetchSafetyEvent,
    QueryGraph,
    QueryNode,
    ResearchBrief,
    ResearchJobCheckpoint,
    ResearchJobStatus,
    ResearchProgressEvent,
    SearchBudgetControls,
    SearchConstraints,
    SearchQueryTrace,
    SourceMetadata,
    SourceQualitySignal,
    SourceSnippet,
    WebEvidenceBundle,
    WebSearchHit,
)
from .planner import (
    apply_adaptive_query_reformulation,
    build_research_brief,
    plan_query_graph,
)
from .providers import (
    BraveSearchProvider,
    DuckDuckGoHtmlSearchProvider,
    ProviderFailoverPolicy,
    WebSearchProvider,
    WikipediaOpenSearchProvider,
)
from .scoring import (
    anti_seo_score,
    build_source_metadata,
    compress_page_to_snippets,
    detect_conflict_score,
    detect_duplicate_source_id,
    lexical_support_score,
    score_search_hit,
    source_rank_key,
)
from .security import (
    detect_paywall,
    sanitize_untrusted_text,
    validate_content_type,
    validate_fetch_url,
)
from .service import ScholarDeepSearchService

__all__ = [
    "BraveSearchProvider",
    "CachedPageRecord",
    "ClaimSupportLink",
    "DeepResearchJobManager",
    "DuckDuckGoHtmlSearchProvider",
    "FetchResult",
    "FetchSafetyEvent",
    "ProviderFailoverPolicy",
    "QueryGraph",
    "QueryNode",
    "ResearchBrief",
    "ResearchJobCheckpoint",
    "ResearchJobStatus",
    "ResearchProgressEvent",
    "ScholarDeepSearchService",
    "SearchBudgetControls",
    "SearchConstraints",
    "SearchQueryTrace",
    "SourceMetadata",
    "SourceQualitySignal",
    "SourceSnippet",
    "UrlFetchCache",
    "WebEvidenceBundle",
    "WebSearchHit",
    "WebSearchProvider",
    "WikipediaOpenSearchProvider",
    "anti_seo_score",
    "apply_adaptive_query_reformulation",
    "build_research_brief",
    "build_source_metadata",
    "compress_page_to_snippets",
    "detect_conflict_score",
    "detect_duplicate_source_id",
    "detect_paywall",
    "fetch_and_find_in_page",
    "fetch_open_page",
    "find_in_page",
    "lexical_support_score",
    "plan_query_graph",
    "sanitize_untrusted_text",
    "score_search_hit",
    "source_id_from_url",
    "source_rank_key",
    "validate_content_type",
    "validate_fetch_url",
]
