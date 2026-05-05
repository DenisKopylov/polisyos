"""Tests for Scholar API web-search bootstrap when seed sources are omitted."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.scholar import KnowledgeBundleRef, ResearchIntent
from polisyos.scholar.api import enrich_topic
from polisyos.scholar.search.models import (
    FetchResult,
    SearchBudgetControls,
    SourceMetadata,
    WebSearchHit,
)
from polisyos.scholar.search.providers import ProviderFailoverPolicy
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
    del constraints, cache, timeout_s, user_agent, max_bytes
    return FetchResult(
        url=url,
        final_url=url,
        title="Minimum wage report",
        text="Minimum wage increased earnings for low-wage workers.",
        content_type="text/html",
        status="ok",
        content_sha256="hash-agency",
        source_type=source_type_hint,
    )


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
    assert captured["intent"].seed_sources[0].canonical_url == "https://agency.gov/minimum-wage"
    assert captured["web_evidence_bundle"].bundle_id.startswith("webkb.")
    assert captured["web_evidence_artifact_id"].startswith("sha256:")


def test_enrich_topic_uses_shared_async_bridge(monkeypatch, tmp_path):
    captured = {"used_run_coro_sync": False}

    async def _fake_deep_search(**_kwargs):
        return SimpleNamespace(
            bundle_id="webkb.fixture",
            sources=[
                SourceMetadata(
                    source_id="src-1",
                    url="https://agency.gov/minimum-wage",
                    title="Minimum wage report",
                    domain="agency.gov",
                    content_type="text/html",
                    fetch_status="ok",
                    content_sha256="hash-agency",
                    source_type="government",
                )
            ],
        )

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

    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([_StaticProvider()]),
        cas=FileSystemCAS(tmp_path / "cas"),
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
        cas=FileSystemCAS(tmp_path / "cas-shared"),
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
