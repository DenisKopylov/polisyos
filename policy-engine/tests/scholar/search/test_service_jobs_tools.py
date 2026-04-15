"""Tests for deep-search orchestration, job checkpoints, and agent tool wrappers."""

from __future__ import annotations

import pytest

import polisyos.scholar.search.jobs as jobs_module
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scholar.api import ScholarService
from polisyos.scholar.search.jobs import DeepResearchJobManager
from polisyos.scholar.search.models import (
    FetchResult,
    SearchBudgetControls,
    SearchConstraints,
    WebSearchHit,
)
from polisyos.scholar.search.providers import ProviderFailoverPolicy
from polisyos.scholar.search.service import ScholarDeepSearchService
from polisyos.scientist.agent.tools.scholar_search_tools import (
    build_scholar_search_tool_registry,
)


class _StaticProvider:
    name = "static"

    async def search(self, query, *, constraints, max_results, timeout_s):
        del constraints, timeout_s
        return [
            WebSearchHit(
                url="https://agency.gov/minimum-wage",
                title="Minimum wage evidence",
                snippet="Minimum wage increased earnings.",
                provider=self.name,
                query=query,
                rank=1,
                source_type="government",
            ),
            WebSearchHit(
                url="https://journal.edu/minimum-wage-study",
                title="Study on youth employment",
                snippet="Youth employment did not decrease.",
                provider=self.name,
                query=query,
                rank=2,
                source_type="academic",
            ),
        ][:max_results]


class _ArtifactStoreProxy:
    def __init__(self, delegate: FileSystemCAS) -> None:
        self._delegate = delegate

    def has(self, artifact_id):
        return self._delegate.has(artifact_id)

    def get_bytes(self, artifact_id):
        return self._delegate.get_bytes(artifact_id)

    def get_manifest(self, artifact_id):
        return self._delegate.get_manifest(artifact_id)

    def put_bytes(self, data, opts):
        return self._delegate.put_bytes(data, opts)

    def put_json(self, obj, opts, canon_spec=None):
        return self._delegate.put_json(obj, opts, canon_spec=canon_spec)

    def verify(self, artifact_id):
        return self._delegate.verify(artifact_id)

    def iter_artifact_ids(self):
        return self._delegate.iter_artifact_ids()


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
    if "agency.gov" in url:
        return FetchResult(
            url=url,
            final_url=url,
            title="Agency minimum wage report",
            text="The minimum wage policy increased earnings for low-wage workers.",
            content_type="text/html",
            status="ok",
            content_sha256="hash-agency",
            source_type=source_type_hint,
        )
    return FetchResult(
        url=url,
        final_url=url,
        title="Academic youth employment study",
        text="The study found youth employment did not decrease after the reform.",
        content_type="text/html",
        status="ok",
        content_sha256="hash-study",
        source_type=source_type_hint,
    )


@pytest.mark.asyncio
async def test_deep_search_builds_citation_ready_bundle(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "polisyos.scholar.search.service.fetch_open_page",
        _fake_fetch_open_page,
    )
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([_StaticProvider()]),
        cas=FileSystemCAS(tmp_path / "cas"),
    )

    bundle = await service.deep_search(
        question="minimum wage impact on low-wage workers",
        claim_texts=["minimum wage increased earnings for low-wage workers"],
        constraints=SearchConstraints(allowed_domains=["agency.gov", "journal.edu"]),
        budgets=SearchBudgetControls(
            max_search_queries=4,
            max_fetch_pages=4,
            max_parallel_fetches=2,
            max_depth=1,
            max_wall_time_s=30,
            per_page_max_bytes=100_000,
        ),
    )
    ref = service.persist_bundle(bundle)

    assert bundle.bundle_id.startswith("webkb.")
    assert len(bundle.query_traces) >= 1
    assert len(bundle.sources) >= 2
    assert len(bundle.snippets) >= 2
    assert bundle.claim_supports
    assert bundle.claim_supports[0].snippet_ids
    assert any(source.domain in {"agency.gov", "journal.edu"} for source in bundle.sources)
    assert str(ref.artifact_id).startswith("sha256:")


@pytest.mark.asyncio
async def test_scholar_search_tool_registry_executes_tools(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "polisyos.scholar.search.service.fetch_open_page",
        _fake_fetch_open_page,
    )
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([_StaticProvider()]),
        cas=FileSystemCAS(tmp_path / "cas"),
    )
    registry = build_scholar_search_tool_registry(service)

    search_result = await registry.aexecute(
        "scholar_web_search",
        {
            "query": "minimum wage",
            "allowed_domains": ["agency.gov", "journal.edu"],
            "max_results": 5,
        },
    )
    find_result = await registry.aexecute(
        "scholar_find_in_page",
        {
            "url": "https://agency.gov/minimum-wage",
            "pattern": "earnings workers",
            "allowed_domains": ["agency.gov"],
        },
    )

    assert search_result.error is None
    assert search_result.result["results"][0]["title"] == "Minimum wage evidence"
    assert find_result.error is None
    assert find_result.result["snippets"]


class _FlakyService:
    def __init__(self, delegate: ScholarDeepSearchService):
        self._delegate = delegate
        self._calls = 0

    async def deep_search(self, **kwargs):
        self._calls += 1
        if self._calls == 1:
            async def _callback(event, bundle):
                callback = kwargs.get("progress_callback")
                if callback is not None:
                    outcome = callback(event, bundle)
                    if hasattr(outcome, "__await__"):
                        await outcome

            # Emit one checkpoint through the delegate callback, then fail.
            kwargs = dict(kwargs)
            kwargs["progress_callback"] = _callback
            bundle = await self._delegate.deep_search(**kwargs)
            del bundle
            raise RuntimeError("transient provider failure")
        return await self._delegate.deep_search(**kwargs)


@pytest.mark.asyncio
async def test_deep_research_job_manager_checkpoints_and_resumes(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "polisyos.scholar.search.service.fetch_open_page",
        _fake_fetch_open_page,
    )
    cas = FileSystemCAS(tmp_path / "cas")
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([_StaticProvider()]),
        cas=cas,
    )
    manager = DeepResearchJobManager(
        service=_FlakyService(service),
        cas=cas,
    )

    job_id = manager.submit(
        question="minimum wage",
        claim_texts=["minimum wage increased earnings"],
        constraints=SearchConstraints(allowed_domains=["agency.gov", "journal.edu"]),
        budgets=SearchBudgetControls(
            max_search_queries=2,
            max_fetch_pages=2,
            max_parallel_fetches=2,
            max_depth=1,
        ),
    )

    failed_status = await manager.wait(job_id)
    assert failed_status.status == "failed"
    assert failed_status.checkpoint_artifact_id is not None
    assert failed_status.result_bundle is not None

    resumed_job_id = await manager.resume(
        checkpoint_artifact_id=failed_status.checkpoint_artifact_id,
    )
    completed_status = await manager.wait(resumed_job_id)

    assert completed_status.status == "completed"
    assert completed_status.result_bundle is not None
    assert completed_status.result_bundle.claim_supports


@pytest.mark.asyncio
async def test_deep_research_job_manager_accepts_protocol_store_without_root(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        "polisyos.scholar.search.service.fetch_open_page",
        _fake_fetch_open_page,
    )
    backing_cas = FileSystemCAS(tmp_path / "cas")
    store = _ArtifactStoreProxy(backing_cas)
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([_StaticProvider()]),
        cas=store,
        cache_index_root=tmp_path / "cache",
    )
    manager = DeepResearchJobManager(
        service=service,
        cas=store,
        status_root=tmp_path / "jobs",
    )

    job_id = manager.submit(
        question="minimum wage",
        claim_texts=["minimum wage increased earnings"],
        constraints=SearchConstraints(allowed_domains=["agency.gov", "journal.edu"]),
        budgets=SearchBudgetControls(
            max_search_queries=2,
            max_fetch_pages=2,
            max_parallel_fetches=2,
            max_depth=1,
        ),
    )

    status = await manager.wait(job_id)

    assert status.status == "completed"
    assert status.result_bundle is not None
    assert (tmp_path / "jobs" / "scholar_web_jobs" / "status_index.json").exists()


@pytest.mark.asyncio
async def test_deep_research_job_manager_uses_async_artifact_store_for_checkpoint_io(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        "polisyos.scholar.search.service.fetch_open_page",
        _fake_fetch_open_page,
    )
    cas = FileSystemCAS(tmp_path / "cas_async")
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([_StaticProvider()]),
        cas=cas,
    )
    manager = DeepResearchJobManager(
        service=_FlakyService(service),
        cas=cas,
    )
    counts = {"put_json": 0, "get_bytes": 0}
    original_put_json = jobs_module.AsyncArtifactStoreAdapter.put_json
    original_get_bytes = jobs_module.AsyncArtifactStoreAdapter.get_bytes

    async def _count_put_json(self, *args, **kwargs):
        counts["put_json"] += 1
        return await original_put_json(self, *args, **kwargs)

    async def _count_get_bytes(self, *args, **kwargs):
        counts["get_bytes"] += 1
        return await original_get_bytes(self, *args, **kwargs)

    monkeypatch.setattr(
        jobs_module.AsyncArtifactStoreAdapter,
        "put_json",
        _count_put_json,
    )
    monkeypatch.setattr(
        jobs_module.AsyncArtifactStoreAdapter,
        "get_bytes",
        _count_get_bytes,
    )

    job_id = manager.submit(
        question="minimum wage",
        claim_texts=["minimum wage increased earnings"],
        constraints=SearchConstraints(allowed_domains=["agency.gov", "journal.edu"]),
        budgets=SearchBudgetControls(
            max_search_queries=2,
            max_fetch_pages=2,
            max_parallel_fetches=2,
            max_depth=1,
        ),
    )
    failed_status = await manager.wait(job_id)
    assert failed_status.checkpoint_artifact_id is not None

    resumed_job_id = await manager.resume(
        checkpoint_artifact_id=failed_status.checkpoint_artifact_id,
    )
    completed_status = await manager.wait(resumed_job_id)

    assert completed_status.status == "completed"
    assert counts["put_json"] >= 2
    assert counts["get_bytes"] >= 1


@pytest.mark.asyncio
async def test_scholar_service_exposes_resumable_job_api(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "polisyos.scholar.search.service.fetch_open_page",
        _fake_fetch_open_page,
    )
    cas = FileSystemCAS(tmp_path / "cas")
    service = ScholarService(
        fact_log_root=tmp_path / "facts",
        web_search_service=ScholarDeepSearchService(
            provider_policy=ProviderFailoverPolicy([_StaticProvider()]),
            cas=cas,
        ),
    )

    job_id = service.submit(
        cas,
        question="minimum wage",
        claim_texts=["minimum wage increased earnings"],
        constraints=SearchConstraints(allowed_domains=["agency.gov", "journal.edu"]),
        budgets=SearchBudgetControls(
            max_search_queries=2,
            max_fetch_pages=2,
            max_parallel_fetches=2,
            max_depth=1,
        ),
    )
    status = await service.wait(cas, job_id)

    assert status.status == "completed"
    assert service.get_status(cas, job_id).status == "completed"
    assert service.get_snapshot(cas, job_id) is not None
