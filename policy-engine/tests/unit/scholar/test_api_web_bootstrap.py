"""Tests for Scholar API web-search bootstrap when seed sources are omitted."""

from __future__ import annotations

import asyncio

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import content_hash
from polisyos.core.contracts.scholar import KnowledgeBundleRef, ResearchIntent
from polisyos.scholar.api import enrich_topic
from polisyos.scholar.errors import ScholarAcquireError
from polisyos.scholar.search.cache import UrlFetchCache
from polisyos.scholar.search.fetcher import source_id_from_url
from polisyos.scholar.search.models import (
    FetchResult,
    QueryGraph,
    ResearchBrief,
    SearchBudgetControls,
    SourceSnippet,
    WebEvidenceBundle,
    WebSearchHit,
)
from polisyos.scholar.search.providers import ProviderFailoverPolicy
from polisyos.scholar.search.scoring import build_source_metadata
from polisyos.scholar.search.security import sanitize_untrusted_text
from polisyos.scholar.search.service import ScholarDeepSearchService
from polisyos.scholar.types import EnrichmentReportV1, EnrichResultV1


class _StaticProvider:
    name = "static"

    async def search(self, query, *, constraints, max_results, timeout_s):
        del constraints, timeout_s
        return [
            WebSearchHit(
                url="https://agency.gov/minimum-wage",
                title="Minimum wage report",
                snippet="Wage policy evidence",
                provider=self.name,
                query=query,
                rank=1,
                source_type="government",
            )
        ][:max_results]


def _bundle_from_cache(cache: UrlFetchCache) -> WebEvidenceBundle:
    url = "https://agency.gov/minimum-wage"
    text = "Minimum wage increased earnings for low-wage workers."
    raw_bytes = f"<html><body>{text}</body></html>".encode()
    fetched = FetchResult(
        url=url,
        final_url=url,
        title="Minimum wage report",
        text=sanitize_untrusted_text(text),
        content_type="text/html",
        status="ok",
        content_sha256=content_hash(raw_bytes),
        byte_size=len(raw_bytes),
        source_type="government",
    )
    fetched = cache.put(fetched, raw_bytes=raw_bytes).to_fetch_result()
    source_id = source_id_from_url(url, fetched.content_sha256)
    brief = ResearchBrief(question="minimum wage effects")
    source = build_source_metadata(
        source_id=source_id,
        hit=WebSearchHit(
            url=url,
            title="Minimum wage report",
            provider="static",
            query="minimum wage effects",
            rank=1,
            source_type="government",
        ),
        fetch=fetched,
    )
    return WebEvidenceBundle(
        bundle_id="webkb.fixture",
        brief=brief,
        query_graph=QueryGraph(brief=brief),
        sources=[source],
        snippets=[
            SourceSnippet(
                snippet_id="snip.minimum-wage",
                source_id=source_id,
                url=url,
                query_node_id="q1",
                perspective="overview",
                text=text,
                start_char=0,
                end_char=len(text),
            )
        ],
    )


async def _fake_fetch_open_page(
    url,
    *,
    constraints,
    cache,
    timeout_s,
    user_agent,
    max_bytes,
    source_type_hint,
):
    del constraints, timeout_s, user_agent, max_bytes
    raw_bytes = b"<html><body>Minimum wage increased earnings for low-wage workers.</body></html>"
    text = "Minimum wage increased earnings for low-wage workers."
    result = FetchResult(
        url=url,
        final_url=url,
        title="Minimum wage report",
        text=sanitize_untrusted_text(text),
        content_type="text/html",
        status="ok",
        content_sha256=content_hash(raw_bytes),
        byte_size=len(raw_bytes),
        source_type=source_type_hint,
    )
    return cache.put(result, raw_bytes=raw_bytes).to_fetch_result()


def test_enrich_topic_bootstraps_seed_sources_from_web(monkeypatch, tmp_path):
    captured = {}

    def _fake_enrich_topic(**kwargs):
        captured.update(kwargs)
        return EnrichResultV1(
            knowledge_bundle_ref=KnowledgeBundleRef(
                artifact_id=ArtifactID.model_validate("sha256:" + "0" * 64)
            ),
            bundle_id="bundle.web-bootstrap",
            report=EnrichmentReportV1(
                bundle_artifact_id="sha256:" + "0" * 64,
                bundle_id="bundle.web-bootstrap",
            ),
        )

    monkeypatch.setattr("polisyos.scholar.api._enrich_topic", _fake_enrich_topic)
    monkeypatch.setattr(
        "polisyos.scholar.search.service.fetch_open_page",
        _fake_fetch_open_page,
    )

    cas = FileSystemCAS(tmp_path / "cas")
    result = enrich_topic(
        cas=cas,
        fact_log_root=tmp_path / "facts",
        intent=ResearchIntent(domain="labor", topic="minimum wage effects"),
        web_search_service=ScholarDeepSearchService(
            provider_policy=ProviderFailoverPolicy([_StaticProvider()]),
            cas=cas,
        ),
        web_search_budgets=SearchBudgetControls(
            max_search_queries=2,
            max_fetch_pages=2,
            max_parallel_fetches=2,
            max_depth=1,
        ),
    )

    assert result.bundle_id == "bundle.web-bootstrap"
    assert captured["intent"].seed_sources
    assert captured["intent"].seed_sources[0].props["canonical_url"] == (
        "https://agency.gov/minimum-wage"
    )
    assert captured["intent"].seed_sources[0].raw_artifact_ref is not None
    assert captured["web_evidence_bundle"].bundle_id.startswith("webkb.")
    assert captured["web_evidence_artifact_id"].startswith("sha256:")


def test_enrich_topic_uses_shared_async_bridge(monkeypatch, tmp_path):
    captured = {"used_run_coro_sync": False}

    async def _fake_deep_search(**_kwargs):
        return _bundle_from_cache(service._cache)

    def _fake_run_coro_sync(coro):
        captured["used_run_coro_sync"] = True
        return asyncio.run(coro)

    def _fake_enrich_topic(**kwargs):
        return EnrichResultV1(
            knowledge_bundle_ref=KnowledgeBundleRef(
                artifact_id=ArtifactID.model_validate("sha256:" + "1" * 64)
            ),
            bundle_id="bundle.shared-bridge",
            report=EnrichmentReportV1(
                bundle_artifact_id="sha256:" + "1" * 64,
                bundle_id="bundle.shared-bridge",
            ),
        )

    monkeypatch.setattr("polisyos.scholar.api.run_coro_sync", _fake_run_coro_sync)
    monkeypatch.setattr("polisyos.scholar.api._enrich_topic", _fake_enrich_topic)

    cas = FileSystemCAS(tmp_path / "cas-shared")
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([_StaticProvider()]),
        cas=cas,
    )
    monkeypatch.setattr(service, "deep_search", _fake_deep_search)
    monkeypatch.setattr(
        service,
        "persist_bundle",
        lambda _bundle: KnowledgeBundleRef(
            artifact_id=ArtifactID.model_validate("sha256:" + "2" * 64)
        ),
    )

    result = enrich_topic(
        cas=cas,
        fact_log_root=tmp_path / "facts",
        intent=ResearchIntent(domain="labor", topic="minimum wage effects"),
        web_search_service=service,
        web_search_budgets=SearchBudgetControls(
            max_search_queries=2,
            max_fetch_pages=2,
            max_parallel_fetches=2,
            max_depth=1,
        ),
    )

    assert captured["used_run_coro_sync"] is True
    assert result.bundle_id == "bundle.shared-bridge"


def test_enrich_topic_rejects_mismatched_source_text_before_persisting(
    monkeypatch,
    tmp_path,
):
    cas = FileSystemCAS(tmp_path / "cas")
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([_StaticProvider()]),
        cas=cas,
    )
    downstream = {"bundle_persisted": False, "enrichment_started": False}

    async def _tampered_search(**_kwargs):
        bundle = _bundle_from_cache(service._cache)
        snippet = bundle.snippets[0].model_copy(update={"text": "invented quote"})
        return bundle.model_copy(update={"snippets": [snippet]})

    def _persist(_bundle):
        downstream["bundle_persisted"] = True
        raise AssertionError("invalid bundle must be rejected before persistence")

    def _enrich(**_kwargs):
        downstream["enrichment_started"] = True
        raise AssertionError("invalid bundle must be rejected before enrichment")

    monkeypatch.setattr(service, "deep_search", _tampered_search)
    monkeypatch.setattr(service, "persist_bundle", _persist)
    monkeypatch.setattr("polisyos.scholar.api._enrich_topic", _enrich)

    with pytest.raises(ScholarAcquireError, match="failed source-content verification"):
        enrich_topic(
            cas=cas,
            fact_log_root=tmp_path / "facts",
            intent=ResearchIntent(domain="labor", topic="minimum wage effects"),
            web_search_service=service,
        )

    assert downstream == {"bundle_persisted": False, "enrichment_started": False}
