"""Deep-search orchestration that produces citation-ready Scholar web evidence bundles."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, content_hash
from polisyos.scholar.search.cache import UrlFetchCache
from polisyos.scholar.search.fetcher import fetch_open_page, find_in_page, source_id_from_url
from polisyos.scholar.search.models import (
    ClaimSupportLink,
    FetchResult,
    NoHitFrontierRecord,
    QueryGraph,
    QueryNode,
    ResearchBrief,
    ResearchProgressEvent,
    SearchBudgetControls,
    SearchConstraints,
    SearchQueryTrace,
    SourceMetadata,
    SourceSnippet,
    WebEvidenceBundle,
    WebSearchHit,
)
from polisyos.scholar.search.planner import (
    apply_adaptive_query_reformulation,
    build_research_brief,
    plan_query_graph,
)
from polisyos.scholar.search.providers import (
    DuckDuckGoHtmlSearchProvider,
    ProviderFailoverPolicy,
    WikipediaOpenSearchProvider,
)
from polisyos.scholar.search.scoring import (
    build_source_metadata,
    compress_page_to_snippets,
    detect_conflict_score,
    detect_duplicate_source_id,
    lexical_support_score,
    score_search_hit,
    source_rank_key,
)
from polisyos.scholar_requirement import (
    ScholarSupportRequirementSpec,
    normalize_scholar_support_requirement_specs,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.contracts.scholar import ResearchIntent

ProgressCallback = Callable[[ResearchProgressEvent, WebEvidenceBundle], Awaitable[None] | None]
NoHitRecorder = Callable[[SearchQueryTrace, NoHitFrontierRecord], None]


class ScholarDeepSearchService:
    """Plan, search, fetch, compress, score, and persist citation-ready web evidence."""

    def __init__(
        self,
        *,
        provider_policy: ProviderFailoverPolicy | None = None,
        cache: UrlFetchCache | None = None,
        cas: ArtifactStore | None = None,
        cache_index_root: Path | None = None,
        cache_ttl_seconds: int = 86_400,
        search_timeout_s: float = 10.0,
        fetch_timeout_s: float = 10.0,
        user_agent: str = "polisyos-scholar-search/1.0",
        no_hit_recorder: NoHitRecorder | None = None,
    ) -> None:
        self._provider_policy = provider_policy or ProviderFailoverPolicy(
            [DuckDuckGoHtmlSearchProvider(), WikipediaOpenSearchProvider()],
        )
        self._cas = cas
        if cache is not None:
            self._cache = cache
        elif cas is not None:
            self._cache = UrlFetchCache(
                index_path=_resolve_cache_index_path(cas, cache_index_root),
                cas=cas,
                ttl_seconds=cache_ttl_seconds,
            )
        else:
            self._cache = UrlFetchCache(ttl_seconds=cache_ttl_seconds)
        self._search_timeout_s = max(float(search_timeout_s), 1.0)
        self._fetch_timeout_s = max(float(fetch_timeout_s), 1.0)
        self._user_agent = user_agent
        self._no_hit_recorder = no_hit_recorder

    async def scholar_web_search(
        self,
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
        """Run one web search request with domain/source/recency controls."""
        constraints = SearchConstraints(
            allowed_domains=allowed_domains or [],
            blocked_domains=blocked_domains or [],
            source_types=source_types or [],
            recency_days=recency_days,
            locale=locale,
            user_location=user_location,
        )
        provider_name, hits, error = await self._provider_policy.search(
            query,
            constraints=constraints,
            max_results=max_results,
            timeout_s=self._search_timeout_s,
        )
        scored = [hit.model_copy(update={"score": score_search_hit(hit)}) for hit in hits]
        return {
            "provider": provider_name,
            "query": query,
            "error": error,
            "results": [hit.model_dump(mode="json") for hit in scored],
        }

    async def scholar_fetch_open(
        self,
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
    ) -> dict[str, Any]:
        """Fetch one web page with safety and cache guards."""
        fetched = await fetch_open_page(
            url,
            constraints=SearchConstraints(
                allowed_domains=allowed_domains or [],
                blocked_domains=blocked_domains or [],
                source_types=source_types or [],
                recency_days=recency_days,
                locale=locale,
                user_location=user_location,
                allow_private_networks=allow_private_networks,
            ),
            cache=self._cache,
            timeout_s=self._fetch_timeout_s,
            user_agent=self._user_agent,
            max_bytes=max_bytes,
            source_type_hint=(source_types or ["web"])[0],
        )
        return cast("dict[str, Any]", fetched.model_dump(mode="json", exclude_none=True))

    async def scholar_find_in_page(
        self,
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
    ) -> dict[str, Any]:
        """Fetch one page and return stable text spans around a search pattern."""
        fetched = await fetch_open_page(
            url,
            constraints=SearchConstraints(
                allowed_domains=allowed_domains or [],
                blocked_domains=blocked_domains or [],
                source_types=source_types or [],
                recency_days=recency_days,
                locale=locale,
                user_location=user_location,
                allow_private_networks=allow_private_networks,
            ),
            cache=self._cache,
            timeout_s=self._fetch_timeout_s,
            user_agent=self._user_agent,
            max_bytes=max_bytes,
            source_type_hint=(source_types or ["web"])[0],
        )
        snippets = []
        if fetched.status not in {"error", "blocked"}:
            snippets = find_in_page(
                fetched,
                pattern=pattern,
                max_snippets=max_snippets,
                window_chars=window_chars,
            )
        return {
            "page": fetched.model_dump(mode="json", exclude_none=True),
            "snippets": [snippet.model_dump(mode="json") for snippet in snippets],
        }

    async def deep_search(
        self,
        *,
        question: str | None = None,
        intent: ResearchIntent | None = None,
        brief: ResearchBrief | None = None,
        query_graph: QueryGraph | None = None,
        claim_texts: Sequence[str] | None = None,
        requirement_specs: Sequence[ScholarSupportRequirementSpec | Mapping[str, Any]]
        | None = None,
        constraints: SearchConstraints | None = None,
        budgets: SearchBudgetControls | None = None,
        progress_callback: ProgressCallback | None = None,
        resume_bundle: WebEvidenceBundle | None = None,
    ) -> WebEvidenceBundle:
        """Run one resumable deep-search job and return a citation-ready bundle."""
        search_budgets = budgets or SearchBudgetControls()
        scholar_requirements = normalize_scholar_support_requirement_specs(requirement_specs)
        active_claim_texts = (
            list(claim_texts)
            if claim_texts is not None
            else [requirement.claim_text for requirement in scholar_requirements]
        )
        active_brief = brief or build_research_brief(
            question=question,
            intent=intent,
            locale=constraints.locale
            if constraints is not None
            else (brief.locale if brief else "en-US"),
        )
        active_constraints = _resolve_constraints(
            active_brief,
            constraints,
            requirement_specs=scholar_requirements,
        )
        graph = query_graph or plan_query_graph(
            active_brief,
            max_depth=search_budgets.max_depth,
        )

        bundle = (
            resume_bundle.model_copy(deep=True)
            if resume_bundle is not None
            else WebEvidenceBundle(
                bundle_id=_bundle_id(active_brief, graph),
                brief=active_brief,
                query_graph=graph,
            )
        )
        if not bundle.query_graph.nodes:
            bundle.query_graph = graph
        if bundle.brief != active_brief:
            bundle.brief = active_brief

        start_time = time.monotonic()
        seen_urls = {str(source.url) for source in bundle.sources}
        seen_by_hash = {
            source.content_sha256: source.source_id
            for source in bundle.sources
            if source.content_sha256
        }
        source_by_id = {source.source_id: source for source in bundle.sources}
        snippet_by_id = {snippet.snippet_id: snippet for snippet in bundle.snippets}
        fetch_semaphore = asyncio.Semaphore(search_budgets.max_parallel_fetches)
        searched_queries = len(bundle.query_traces)

        await _emit_progress(
            progress_callback,
            ResearchProgressEvent(
                job_id=bundle.bundle_id,
                phase="planning",
                message="query graph initialized",
                progress=0.02,
            ),
            bundle,
        )

        queue = [node.node_id for node in bundle.query_graph.nodes if node.status == "pending"]
        while queue:
            if searched_queries >= search_budgets.max_search_queries:
                bundle.uncertainty_notes.append("stopped:max_search_queries")
                break
            if len(source_by_id) >= search_budgets.max_fetch_pages:
                bundle.uncertainty_notes.append("stopped:max_fetch_pages")
                break
            if time.monotonic() - start_time > search_budgets.max_wall_time_s:
                bundle.partial = True
                bundle.uncertainty_notes.append("stopped:max_wall_time_s")
                break

            remaining_query_budget = search_budgets.max_search_queries - searched_queries
            batch_size = min(
                max(1, search_budgets.max_parallel_queries),
                max(1, remaining_query_budget),
                len(queue),
            )
            batch_nodes: list[QueryNode] = []
            while queue and len(batch_nodes) < batch_size:
                node = bundle.query_graph.node_by_id(queue.pop(0))
                if node.status in {"pending", "expanded"}:
                    batch_nodes.append(node)
            if not batch_nodes:
                continue

            search_results = await asyncio.gather(
                *[
                    self._provider_policy.search(
                        node.query,
                        constraints=active_constraints,
                        max_results=max(5, min(search_budgets.max_fetch_pages, 20)),
                        timeout_s=self._search_timeout_s,
                    )
                    for node in batch_nodes
                ]
            )

            fetch_specs: list[tuple[WebSearchHit, QueryNode]] = []
            batch_seen_urls: set[str] = set()
            for node, (provider_name, hits, error) in zip(
                batch_nodes, search_results, strict=False
            ):
                node.provider = provider_name
                node.hit_count = len(hits)
                node.status = "failed" if error and not hits else "searched"
                query_trace = SearchQueryTrace(
                    query_node_id=node.node_id,
                    query=node.query,
                    perspective=node.perspective,
                    provider=provider_name,
                    hit_count=len(hits),
                    error=error,
                )
                bundle.query_traces.append(query_trace)
                if not hits:
                    frontier = NoHitFrontierRecord(
                        query_node_id=node.node_id,
                        query=node.query,
                        perspective=node.perspective,
                        provider=provider_name,
                        reason=(
                            "provider_error_no_hits"
                            if error
                            else "provider_returned_no_hits"
                        ),
                        searched_at=query_trace.searched_at,
                        error=error,
                    )
                    bundle.no_hit_frontier.append(frontier)
                    if self._no_hit_recorder is not None:
                        self._no_hit_recorder(query_trace, frontier)
                searched_queries += 1

                candidates = [
                    hit.model_copy(update={"score": score_search_hit(hit)})
                    for hit in hits
                    if str(hit.url) not in seen_urls and str(hit.url) not in batch_seen_urls
                ]
                candidates.sort(key=lambda hit: (-hit.score, hit.rank))
                remaining_fetch_budget = (
                    search_budgets.max_fetch_pages - len(source_by_id) - len(fetch_specs)
                )
                candidates = candidates[: max(0, remaining_fetch_budget)]
                for hit in candidates:
                    batch_seen_urls.add(str(hit.url))
                    fetch_specs.append((hit, node))

            fetch_tasks = [
                _fetch_hit(
                    hit,
                    node=node,
                    service=self,
                    constraints=active_constraints,
                    budgets=search_budgets,
                    semaphore=fetch_semaphore,
                )
                for hit, node in fetch_specs
            ]
            for hit, fetch_result, snippets in await asyncio.gather(*fetch_tasks):
                seen_urls.add(str(hit.url))
                source_id = source_id_from_url(
                    fetch_result.final_url,
                    fetch_result.content_sha256,
                )
                duplicate_of = detect_duplicate_source_id(
                    seen_by_hash=seen_by_hash,
                    fetch=fetch_result,
                )
                if fetch_result.content_sha256 and duplicate_of is None:
                    seen_by_hash[fetch_result.content_sha256] = source_id
                source_metadata = build_source_metadata(
                    source_id=source_id,
                    hit=hit,
                    fetch=fetch_result,
                    duplicate_of_source_id=duplicate_of,
                )
                source_by_id[source_id] = source_metadata
                for snippet in snippets:
                    snippet_by_id[snippet.snippet_id] = snippet

            bundle.sources = sorted(source_by_id.values(), key=source_rank_key)
            bundle.snippets = sorted(
                snippet_by_id.values(),
                key=lambda snippet: (
                    -snippet.relevance_score,
                    snippet.source_id,
                    snippet.snippet_id,
                ),
            )

            for node in batch_nodes:
                if (
                    node.hit_count < 2
                    and node.depth < search_budgets.max_depth
                    and searched_queries < search_budgets.max_search_queries
                ):
                    children = apply_adaptive_query_reformulation(
                        bundle.query_graph,
                        node_id=node.node_id,
                        min_hit_count=2,
                        max_children=2,
                    )
                    queue.extend(child.node_id for child in children)

                done_queries = sum(
                    1 for item in bundle.query_graph.nodes if item.status in {"searched", "failed"}
                )
                progress = min(
                    0.98,
                    0.05 + done_queries / max(len(bundle.query_graph.nodes), 1) * 0.9,
                )
                await _emit_progress(
                    progress_callback,
                    ResearchProgressEvent(
                        job_id=bundle.bundle_id,
                        phase="search",
                        message=f"searched {node.query}",
                        progress=progress,
                    ),
                    bundle,
                )

        bundle.claim_supports = _build_claim_supports(
            claim_texts=active_claim_texts or [active_brief.question],
            snippets=bundle.snippets,
            requirement_specs=scholar_requirements,
        )
        bundle.uncertainty_notes = sorted(dict.fromkeys(bundle.uncertainty_notes))
        bundle.partial = bundle.partial or any(
            node.status == "pending" for node in bundle.query_graph.nodes
        )
        bundle.bundle_id = _bundle_id(
            bundle.brief, bundle.query_graph, bundle.sources, bundle.snippets
        )

        await _emit_progress(
            progress_callback,
            ResearchProgressEvent(
                job_id=bundle.bundle_id,
                phase="finalize",
                message="evidence bundle ready",
                progress=1.0,
            ),
            bundle,
        )
        return bundle

    def persist_bundle(self, bundle: WebEvidenceBundle) -> ArtifactRef:
        """Persist a `WebEvidenceBundle` into CAS."""
        if self._cas is None:
            raise ValueError("persist_bundle requires a CAS-backed ScholarDeepSearchService")
        return self._cas.put_json(
            bundle.model_dump(mode="json", exclude_none=True),
            ArtifactWriteOptions(
                kind="scholar.web_evidence_bundle",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.scholar.web_evidence_bundle", version="1.0"),
                producer=ProducerInfo(component="polisyos.scholar.search.service", version="1.0.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )

    async def fetch_and_rank_hit(
        self,
        hit: WebSearchHit,
        *,
        node: QueryNode,
        constraints: SearchConstraints,
        budgets: SearchBudgetControls,
    ) -> tuple[WebSearchHit, FetchResult, list[SourceSnippet]]:
        """Fetch one search hit and compress the page text into snippets."""
        fetch_result = await fetch_open_page(
            str(hit.url),
            constraints=constraints,
            cache=self._cache,
            timeout_s=self._fetch_timeout_s,
            user_agent=self._user_agent,
            max_bytes=budgets.per_page_max_bytes,
            source_type_hint=hit.source_type,
        )
        snippets = []
        if fetch_result.status not in {"error", "blocked"}:
            snippets = compress_page_to_snippets(
                source_id=source_id_from_url(
                    fetch_result.final_url,
                    fetch_result.content_sha256,
                ),
                url=str(hit.url),
                text=fetch_result.text,
                query_node_id=node.node_id,
                perspective=node.perspective,
                query_terms=_query_terms(node.query),
                max_snippets=3,
                window_chars=480,
            )
        return hit, fetch_result, snippets


def _resolve_cache_index_path(
    store: ArtifactStore,
    cache_index_root: Path | None,
) -> Path:
    if cache_index_root is not None:
        base_root = cache_index_root
    else:
        root_value = getattr(store, "root", None)
        if isinstance(root_value, Path):
            base_root = root_value
        elif isinstance(root_value, str):
            base_root = Path(root_value)
        else:
            base_root = Path.cwd() / ".polisyos" / "scholar_cache"
    return base_root / "scholar_web_cache" / "index.json"


def _query_terms(query: str) -> list[str]:
    terms = [
        token.lower()
        for token in re_split_words(query)
        if len(token) >= 3 and not token.lower().startswith("site:")
    ]
    return terms or [query]


def re_split_words(text: str) -> list[str]:
    import re

    return re.findall(r"[\w'.:-]+", text)


async def _fetch_hit(
    hit: WebSearchHit,
    *,
    node: QueryNode,
    service: ScholarDeepSearchService,
    constraints: SearchConstraints,
    budgets: SearchBudgetControls,
    semaphore: asyncio.Semaphore,
) -> tuple[WebSearchHit, FetchResult, list[SourceSnippet]]:
    async with semaphore:
        return await service.fetch_and_rank_hit(
            hit,
            node=node,
            constraints=constraints,
            budgets=budgets,
        )


def _build_claim_supports(
    *,
    claim_texts: Sequence[str],
    snippets: Sequence[SourceSnippet],
    requirement_specs: Sequence[ScholarSupportRequirementSpec] | None = None,
) -> list[ClaimSupportLink]:
    supports: list[ClaimSupportLink] = []
    requirements = list(requirement_specs or ())
    claim_rows: list[tuple[str, str, ScholarSupportRequirementSpec | None]] = []
    if requirements:
        claim_rows.extend(
            (requirement.claim_id, requirement.claim_text, requirement)
            for requirement in requirements
        )
    else:
        claim_rows.extend(
            (f"claim.{index + 1}", claim_text, None)
            for index, claim_text in enumerate(claim_texts)
        )
    for _index, (claim_id, claim_text, requirement) in enumerate(claim_rows):
        ranked = sorted(
            ((lexical_support_score(claim_text, snippet.text), snippet) for snippet in snippets),
            key=lambda item: (-item[0], item[1].source_id, item[1].snippet_id),
        )
        selected = [(score, snippet) for score, snippet in ranked if score > 0][:8]
        snippet_ids = [snippet.snippet_id for _, snippet in selected]
        source_ids = sorted(dict.fromkeys(snippet.source_id for _, snippet in selected))
        support_score = sum(score for score, _ in selected) / max(len(selected), 1)
        conflict_score, uncertainty_note = detect_conflict_score(
            claim_text,
            [snippet.text for _, snippet in selected],
        )
        support_status = _claim_support_status(
            support_score=support_score,
            conflict_score=conflict_score,
            snippet_count=len(snippet_ids),
        )
        supports.append(
            ClaimSupportLink(
                claim_id=claim_id,
                claim_text=claim_text,
                snippet_ids=snippet_ids,
                source_ids=source_ids,
                support_score=round(support_score, 6),
                conflict_score=round(conflict_score, 6),
                uncertainty_note=uncertainty_note,
                metadata={
                    "claim_id_namespace": "legacy_local",
                    "support_status": support_status,
                    **_requirement_support_metadata(requirement),
                },
            )
        )
    return supports


def _claim_support_status(
    *,
    support_score: float,
    conflict_score: float,
    snippet_count: int,
) -> str:
    if snippet_count <= 0 or support_score <= 0:
        return "unsupported"
    if conflict_score >= 0.5:
        return "contested"
    if support_score >= 0.12:
        return "supported"
    return "weakly_supported"


def _resolve_constraints(
    brief: ResearchBrief,
    constraints: SearchConstraints | None,
    *,
    requirement_specs: Sequence[ScholarSupportRequirementSpec] | None = None,
) -> SearchConstraints:
    """Merge planner-derived defaults with explicit runtime constraints."""
    requirements = list(requirement_specs or ())
    if constraints is None:
        resolved = SearchConstraints(
            allowed_domains=brief.preferred_domains,
            source_types=brief.required_source_types,
            locale=brief.locale,
        )
    else:
        resolved = constraints.model_copy(
            update={
                "allowed_domains": constraints.allowed_domains or brief.preferred_domains,
                "source_types": constraints.source_types or brief.required_source_types,
                "locale": constraints.locale or brief.locale,
            }
        )
    if not requirements:
        return resolved
    recency_days = min(requirement.recency_days for requirement in requirements)
    source_types = sorted(
        dict.fromkeys(
            [
                *resolved.source_types,
                *(
                    _source_type_for_publication_tier(requirement.required_publication_tier)
                    for requirement in requirements
                ),
            ]
        )
    )
    return resolved.model_copy(
        update={
            "recency_days": resolved.recency_days or recency_days,
            "source_types": source_types,
        }
    )


def _requirement_support_metadata(
    requirement: ScholarSupportRequirementSpec | None,
) -> dict[str, Any]:
    if requirement is None:
        return {}
    return {
        "requirement_id": requirement.requirement_id,
        "claim_use_requested": requirement.participation_claim_use_requested,
        "claim_use_allowed": requirement.participation_claim_use_allowed,
        "authority_level": requirement.authority_level,
        "population_scope": requirement.population_scope,
        "required_publication_tier": requirement.required_publication_tier,
        "required_recency_days": requirement.recency_days,
        "required_replication_count": requirement.required_replication_count,
        "required_independence_breadth": requirement.required_independence_breadth,
        "required_citation_network_depth": requirement.required_citation_network_depth,
    }


def _source_type_for_publication_tier(tier: str) -> str:
    if tier in {"peer_reviewed", "systematic_review", "working_paper"}:
        return "academic"
    if tier == "government_report":
        return "government"
    return "grey_literature"


async def _emit_progress(
    progress_callback: ProgressCallback | None,
    event: ResearchProgressEvent,
    bundle: WebEvidenceBundle,
) -> None:
    if progress_callback is None:
        return
    outcome = progress_callback(event, bundle)
    if asyncio.iscoroutine(outcome):
        await outcome


def _bundle_id(
    brief: ResearchBrief,
    query_graph: QueryGraph,
    sources: Sequence[SourceMetadata] | None = None,
    snippets: Sequence[SourceSnippet] | None = None,
) -> str:
    payload = {
        "brief": brief.model_dump(mode="json", exclude_none=True),
        "query_graph": query_graph.model_dump(mode="json", exclude_none=True),
        "sources": [
            source.model_dump(mode="json", exclude_none=True) for source in (sources or [])
        ],
        "snippets": [
            snippet.model_dump(mode="json", exclude_none=True) for snippet in (snippets or [])
        ],
    }
    digest = content_hash(repr(payload).encode("utf-8"))
    return f"webkb.{digest[:24]}"


__all__ = [
    "ScholarDeepSearchService",
]
