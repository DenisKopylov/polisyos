"""Tests for deep-search orchestration, job checkpoints, and agent tool wrappers."""

from __future__ import annotations

import asyncio
import copy
import json

import httpx
import pytest
from pydantic import ValidationError

import polisyos.scholar.search.jobs as jobs_module
from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts import BoundedLivenessConfig
from polisyos.scholar import build_scholar_academic_evidence_report_from_web_bundle
from polisyos.scholar.api import ScholarService
from polisyos.scholar.search.jobs import DeepResearchJobManager
from polisyos.scholar.search.models import (
    FetchResult,
    NoHitFrontierRecord,
    ProviderAttemptTrace,
    QueryGraph,
    QueryNode,
    ResearchBrief,
    ResearchJobCheckpoint,
    SearchBudgetControls,
    SearchConstraints,
    SearchQueryTrace,
    WebEvidenceBundle,
    WebSearchHit,
)
from polisyos.scholar.search.providers import (
    OpenAlexWorksProvider,
    ProviderFailoverPolicy,
)
from polisyos.scholar.search.service import ScholarDeepSearchService
from polisyos.scholar_requirement import ScholarSupportRequirementCompiler
from polisyos.scientist.agent.tools.scholar_search_tools import (
    build_scholar_search_tool_registry,
)


def _assert_expected_validation_error(
    error: ValidationError,
    *,
    expected_location_suffix: tuple[str | int, ...] | None = None,
    expected_error_type: str | None = None,
    expected_message: str | None = None,
) -> None:
    """Require one specific typed validation failure, not an earlier decode error."""
    errors = error.errors(include_url=False)
    assert errors
    assert (
        expected_location_suffix is not None
        or expected_error_type is not None
        or expected_message is not None
    )
    assert any(
        (
            expected_location_suffix is None
            or tuple(item["loc"][-len(expected_location_suffix) :]) == expected_location_suffix
        )
        and (expected_error_type is None or item["type"] == expected_error_type)
        and (expected_message is None or expected_message in item["msg"])
        for item in errors
    ), errors


def _assert_bundle_rejected(
    payload: object,
    *,
    expected_location_suffix: tuple[str | int, ...] | None = None,
    expected_error_type: str | None = None,
    expected_message: str | None = None,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        WebEvidenceBundle.model_validate(payload)
    _assert_expected_validation_error(
        exc_info.value,
        expected_location_suffix=expected_location_suffix,
        expected_error_type=expected_error_type,
        expected_message=expected_message,
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


class _CapturingProvider(_StaticProvider):
    def __init__(self) -> None:
        self.seen_constraints = []

    async def search(self, query, *, constraints, max_results, timeout_s):
        self.seen_constraints.append(constraints)
        return await super().search(
            query,
            constraints=constraints,
            max_results=max_results,
            timeout_s=timeout_s,
        )


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
async def test_deep_search_consumes_scholar_requirement_spec(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "polisyos.scholar.search.service.fetch_open_page",
        _fake_fetch_open_page,
    )
    spec = (
        ScholarSupportRequirementCompiler()
        .compile(
            {
                "run_id": "run.scholar.search",
                "authority_level": "production",
                "claims": [
                    {
                        "claim_id": "claim.1",
                        "claim_text": "Minimum wage increased earnings.",
                        "claim_type": "causal",
                        "claim_family": "causal",
                        "claim_use": "decision_support",
                    }
                ],
            }
        )
        .requirements[0]
    )
    provider = _CapturingProvider()
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([provider]),
        cas=FileSystemCAS(tmp_path / "cas"),
    )

    bundle = await service.deep_search(
        question="minimum wage impact on low-wage workers",
        requirement_specs=[spec],
        constraints=SearchConstraints(allowed_domains=["agency.gov", "journal.edu"]),
        budgets=SearchBudgetControls(
            max_search_queries=2,
            max_fetch_pages=2,
            max_parallel_fetches=2,
            max_depth=1,
        ),
    )

    assert provider.seen_constraints
    assert provider.seen_constraints[0].recency_days == spec.recency_days
    assert "academic" in provider.seen_constraints[0].source_types
    assert bundle.claim_supports[0].claim_id == "claim.1"
    assert bundle.claim_supports[0].metadata["requirement_id"] == spec.requirement_id


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


class _HangingService:
    async def deep_search(self, **kwargs):
        del kwargs
        await asyncio.Event().wait()


class _CancellationResistantService:
    def __init__(self, release: asyncio.Event) -> None:
        self._release = release

    async def deep_search(self, **kwargs):
        del kwargs
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await self._release.wait()


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
    assert completed_status.scholar_academic_evidence_artifact_id is not None
    assert completed_status.result_bundle is not None
    assert completed_status.result_bundle.claim_supports
    report_payload = json.loads(
        cas.get_bytes(completed_status.scholar_academic_evidence_artifact_id).decode("utf-8")
    )
    assert report_payload["schema_version"] == "policyos.scholar.academic_evidence.v1"
    assert report_payload["capability_reality_status"] == "implemented"


@pytest.mark.asyncio
async def test_deep_research_job_manager_escalates_when_producer_wait_exceeds_deadline(
    tmp_path,
):
    manager = DeepResearchJobManager(
        service=_HangingService(),
        cas=FileSystemCAS(tmp_path / "cas"),
        liveness_config=BoundedLivenessConfig(
            config_id="bounded-liveness.test.v1",
            owner="team-runtime-quality",
            version="2026-05-22",
            default_deadline_s=0.01,
            default_retry_ceiling=0,
            producer_deadline_overrides_s={"scholar.deep_research_job": 0.01},
            feature_flag="universal_pdc_bounded_liveness",
            rollback_path="restore previous governed config artifact",
            promotion_evidence_ref="artifact://bounded-liveness/evidence",
        ),
    )

    job_id = manager.submit(question="minimum wage")

    status = await manager.wait(job_id)

    assert status.status == "escalated"
    assert status.error == "bounded_liveness_deadline_exceeded:scholar.deep_research_job"
    assert manager.get_status(job_id).status == "escalated"


@pytest.mark.asyncio
async def test_deep_research_job_manager_wait_returns_even_when_producer_ignores_cancel(
    tmp_path,
):
    release = asyncio.Event()
    manager = DeepResearchJobManager(
        service=_CancellationResistantService(release),
        cas=FileSystemCAS(tmp_path / "cas"),
        liveness_config=BoundedLivenessConfig(
            config_id="bounded-liveness.test.v1",
            owner="team-runtime-quality",
            version="2026-05-22",
            default_deadline_s=0.01,
            default_retry_ceiling=0,
            producer_deadline_overrides_s={"scholar.deep_research_job": 0.01},
            feature_flag="universal_pdc_bounded_liveness",
            rollback_path="restore previous governed config artifact",
            promotion_evidence_ref="artifact://bounded-liveness/evidence",
        ),
    )
    job_id = manager.submit(question="minimum wage")

    try:
        status = await asyncio.wait_for(manager.wait(job_id), timeout=0.2)
    finally:
        release.set()

    assert status.status == "escalated"


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


@pytest.mark.asyncio
async def test_deep_search_persists_inaccessible_text_and_budget_stop_separately(
    monkeypatch,
    tmp_path,
):
    async def _blocked_fetch(
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
            title="",
            text="",
            content_type="text/html",
            status="blocked",
            error="blocked_domain",
            source_type=source_type_hint,
        )

    monkeypatch.setattr(
        "polisyos.scholar.search.service.fetch_open_page",
        _blocked_fetch,
    )
    cas = FileSystemCAS(tmp_path / "scholar-attempt-cas")
    brief = ResearchBrief(question="minimum wage evidence")
    graph = QueryGraph(
        brief=brief,
        nodes=[
            QueryNode(node_id="q0", query=brief.question, perspective="root"),
            QueryNode(
                node_id="q1",
                query="minimum wage subgroup",
                perspective="subgroup",
            ),
        ],
        root_node_ids=["q0", "q1"],
    )
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([_StaticProvider()]),
        cas=cas,
        search_timeout_s=5,
        fetch_timeout_s=5,
    )

    bundle = await service.deep_search(
        brief=brief,
        query_graph=graph,
        constraints=SearchConstraints(),
        budgets=SearchBudgetControls(
            max_search_queries=1,
            max_fetch_pages=1,
            max_parallel_queries=1,
            max_parallel_fetches=1,
            max_depth=0,
            max_wall_time_s=5,
        ),
    )
    ref = service.persist_bundle(bundle)
    persisted = json.loads(cas.get_bytes(ref))

    assert len(persisted["query_traces"]) == 1
    assert persisted["query_traces"][0]["provider_attempts"][0]["reason"] == ("not_established")
    assert len(persisted["sources"]) == 1
    assert persisted["sources"][0]["fetch_status"] == "blocked"
    assert persisted["sources"][0]["error"] == "blocked_domain"
    assert persisted["sources"][0]["provider"] == "static"
    assert persisted["sources"][0]["search_query"] == brief.question
    assert "stopped:max_search_queries" in persisted["uncertainty_notes"]
    assert "stopped:max_fetch_pages" not in persisted["uncertainty_notes"]


@pytest.mark.parametrize(
    "round_trip",
    [True, False],
    ids=["read-v1", "attempt-requires-v1_1"],
)
def test_web_evidence_bundle_attempt_schema_is_backward_explicit(round_trip):
    brief = ResearchBrief(question="legacy web evidence")
    graph = QueryGraph(brief=brief)
    trace = SearchQueryTrace(
        query_node_id="q0",
        query="legacy web evidence",
        perspective="root",
        provider="legacy",
        provider_attempts=[
            ProviderAttemptTrace(
                attempt_index=0,
                provider="legacy",
                outcome="returned_no_hits",
                reason="not_established",
            )
        ],
    )

    if round_trip:
        legacy_trace = SearchQueryTrace(
            query_node_id="q0",
            query="legacy web evidence",
            perspective="root",
            provider="legacy",
        )
        legacy = WebEvidenceBundle(
            schema_version="1.0",
            bundle_id="legacy",
            brief=brief,
            query_graph=graph,
            query_traces=[legacy_trace],
        )
        payload = legacy.model_dump(mode="json", exclude_none=True)
        assert "provider_attempts" not in payload["query_traces"][0]
        restored = WebEvidenceBundle.model_validate(payload)
        assert restored.schema_version == "1.0"
        assert restored.query_traces[0].provider_attempts is None
    else:
        with pytest.raises(ValueError, match="provider attempts require"):
            WebEvidenceBundle(
                schema_version="1.0",
                bundle_id="invalid-legacy",
                brief=brief,
                query_graph=graph,
                query_traces=[trace],
            )


@pytest.mark.asyncio
async def test_deep_search_persists_safe_provider_error_aggregate_and_rejects_tampering(
    monkeypatch,
    tmp_path,
):
    url_marker = "r4-private-url-marker"
    mailto_marker = "r4-private-mailto"
    payload_marker = "r4-private-response-payload"

    async def _raise_openalex_status(url, **kwargs):
        del kwargs
        request = httpx.Request("GET", url)
        response = httpx.Response(503, request=request, text=payload_marker)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as status_error:
            detailed = httpx.HTTPStatusError(
                f"{status_error} response_body={payload_marker}",
                request=request,
                response=response,
            )
            assert url_marker in str(detailed)
            assert mailto_marker in str(detailed)
            assert payload_marker in str(detailed)
            raise detailed from status_error
        raise AssertionError("HTTP 503 must raise HTTPStatusError")

    monkeypatch.setattr(
        "polisyos.scholar.search.providers._read_openalex_url_text",
        _raise_openalex_status,
    )
    cas = FileSystemCAS(tmp_path / "cas-provider-error-aggregate")
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy(
            [
                OpenAlexWorksProvider(
                    endpoint=f"https://api.openalex.test/{url_marker}",
                    mailto=f"{mailto_marker}@example.test",
                )
            ]
        ),
        cas=cas,
    )

    bundle = await service.deep_search(
        question="minimum wage effects",
        budgets=SearchBudgetControls(
            max_search_queries=1,
            max_fetch_pages=1,
            max_parallel_queries=1,
            max_parallel_fetches=1,
            max_depth=0,
            max_wall_time_s=5,
        ),
    )
    ref = service.persist_bundle(bundle)
    manifest = cas.get_manifest(ref)
    assert manifest.artifact_schema.version == "1.1"
    payload_bytes = cas.get_bytes(ref)
    payload_text = payload_bytes.decode("utf-8")
    assert all(marker not in payload_text for marker in (url_marker, mailto_marker, payload_marker))
    persisted = json.loads(payload_text)
    trace = persisted["query_traces"][0]
    attempt = trace["provider_attempts"][0]
    assert attempt["error"] == "provider_error"
    assert attempt["error_type"] == "http_status_error"
    assert trace["error"] == "provider_error"
    assert persisted["no_hit_frontier"][0]["error"] == "provider_error"

    typed_persisted = from_canonical_bytes(payload_bytes)
    validated_base = WebEvidenceBundle.model_validate(typed_persisted)
    assert validated_base.query_traces[0].provider_attempts[0].error == "provider_error"
    mutation_expectations = {
        "raw_attempt_error": {
            "expected_location_suffix": ("error",),
            "expected_error_type": "literal_error",
        },
        "raw_aggregate_error": {
            "expected_message": "query error must match the latest observed provider error"
        },
        "raw_frontier_error": {
            "expected_message": "schema 1.1 frontier errors must use a safe category"
        },
        "missing_error_type": {
            "expected_message": "error outcome requires a safe category and exception type"
        },
    }
    for mutation, expected_error in mutation_expectations.items():
        tampered = copy.deepcopy(typed_persisted)
        if mutation == "raw_attempt_error":
            tampered["query_traces"][0]["provider_attempts"][0]["error"] = url_marker
        elif mutation == "raw_aggregate_error":
            tampered["query_traces"][0]["error"] = url_marker
        elif mutation == "raw_frontier_error":
            tampered["no_hit_frontier"][0]["error"] = url_marker
        else:
            del tampered["query_traces"][0]["provider_attempts"][0]["error_type"]
        _assert_bundle_rejected(tampered, **expected_error)


@pytest.mark.asyncio
async def test_legacy_v1_bundle_resume_projects_errors_without_rewriting_old_cas(
    tmp_path,
):
    sentinel = "legacy-provider-error-private-sentinel"
    cas_root = tmp_path / "cas-legacy-bundle"
    cas = FileSystemCAS(cas_root)
    brief = ResearchBrief(question="legacy evidence query")
    graph = QueryGraph(
        brief=brief,
        nodes=[
            QueryNode(
                node_id="legacy.query.1",
                query=brief.question,
                perspective="root",
                status="failed",
                hit_count=0,
            )
        ],
        root_node_ids=["legacy.query.1"],
    )
    legacy_bundle = WebEvidenceBundle(
        schema_version="1.0",
        bundle_id="webkb.legacy-provider-error",
        brief=brief,
        query_graph=graph,
        query_traces=[
            SearchQueryTrace(
                query_node_id="legacy.query.1",
                query=brief.question,
                perspective="root",
                provider="legacy-provider",
                hit_count=0,
                error=f"legacy-provider: {sentinel}",
            )
        ],
        no_hit_frontier=[
            NoHitFrontierRecord(
                query_node_id="legacy.query.1",
                query=brief.question,
                perspective="root",
                provider="legacy-provider",
                reason="provider_error_no_hits",
                error=f"legacy-provider: {sentinel}",
            )
        ],
    )
    legacy_payload = legacy_bundle.model_dump(mode="json", exclude_none=True)
    legacy_report = build_scholar_academic_evidence_report_from_web_bundle(
        scholar_evidence_ref="sha256:" + "1" * 64,
        bundle=legacy_payload,
        corpus_snapshot_ref="corpus-snapshot:legacy-provider-error",
        lineage_ref="scholar-lineage:legacy-provider-error",
    )
    assert sentinel not in json.dumps(legacy_report, sort_keys=True)
    assert legacy_report["provider_traces"][0]["error"] == ("legacy_error_not_established")
    unversioned_payload = dict(legacy_payload)
    unversioned_payload.pop("schema_version")
    with pytest.raises(ValueError, match="unversioned provider errors"):
        build_scholar_academic_evidence_report_from_web_bundle(
            scholar_evidence_ref="sha256:" + "2" * 64,
            bundle=unversioned_payload,
            corpus_snapshot_ref="corpus-snapshot:unversioned-error",
            lineage_ref="scholar-lineage:unversioned-error",
        )
    legacy_ref = cas.put_json(
        legacy_payload,
        ArtifactWriteOptions(
            kind="scholar.web_evidence_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scholar.web_evidence_bundle",
                version="1.0",
            ),
            producer=ProducerInfo(
                component="polisyos.scholar.search.service",
                version="1.0.0",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    legacy_bytes = cas.get_bytes(legacy_ref)
    assert cas.get_manifest(legacy_ref).artifact_schema.version == "1.0"
    assert sentinel.encode() in legacy_bytes

    legacy_checkpoint = ResearchJobCheckpoint(
        job_id="research.legacy-provider-error",
        status="failed",
        brief=brief,
        query_graph=graph,
        bundle=legacy_bundle,
    )
    checkpoint_ref = cas.put_json(
        legacy_checkpoint.model_dump(mode="json", exclude_none=True),
        ArtifactWriteOptions(
            kind="scholar.web_research_checkpoint",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scholar.web_research_checkpoint",
                version="1.0",
            ),
            producer=ProducerInfo(
                component="polisyos.scholar.search.jobs",
                version="1.0.0",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    legacy_checkpoint_bytes = cas.get_bytes(checkpoint_ref)

    reopened_cas = FileSystemCAS(cas_root)
    assert reopened_cas.get_bytes(legacy_ref) == legacy_bytes
    assert reopened_cas.get_bytes(checkpoint_ref) == legacy_checkpoint_bytes
    reopened_checkpoint = ResearchJobCheckpoint.model_validate(
        from_canonical_bytes(legacy_checkpoint_bytes)
    )
    assert reopened_checkpoint.bundle.schema_version == "1.0"
    assert reopened_checkpoint.bundle.query_traces[0].provider_attempts is None
    assert sentinel in reopened_checkpoint.bundle.query_traces[0].error

    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([_StaticProvider()]),
        cas=reopened_cas,
    )
    manager = DeepResearchJobManager(
        service=service,
        cas=reopened_cas,
        status_root=tmp_path / "job-status",
    )
    job_id = await manager.resume(
        checkpoint_artifact_id=str(checkpoint_ref.artifact_id),
    )
    status = await manager.wait(job_id, deadline_s=10)

    assert status.status == "completed"
    assert status.result_bundle is not None
    assert status.result_bundle.schema_version == "1.1"
    assert status.result_bundle.query_traces[0].provider_attempts is None
    assert status.result_bundle.query_traces[0].error == "legacy_error_not_established"
    assert status.result_bundle.no_hit_frontier[0].error == "legacy_error_not_established"
    assert reopened_cas.get_bytes(legacy_ref) == legacy_bytes
    assert (
        sentinel.encode()
        not in (tmp_path / "job-status" / "scholar_web_jobs" / "status_index.json").read_bytes()
    )

    direct_legacy_ref = service.persist_bundle(legacy_bundle)
    direct_legacy_bytes = reopened_cas.get_bytes(direct_legacy_ref)
    assert reopened_cas.get_manifest(direct_legacy_ref).artifact_schema.version == "1.1"
    assert sentinel.encode() not in direct_legacy_bytes
    direct_legacy_bundle = WebEvidenceBundle.model_validate(
        from_canonical_bytes(direct_legacy_bytes)
    )
    assert direct_legacy_bundle.query_traces[0].provider_attempts is None
    assert direct_legacy_bundle.query_traces[0].error == "legacy_error_not_established"

    bundle_ref = service.persist_bundle(status.result_bundle)
    bundle_bytes = reopened_cas.get_bytes(bundle_ref)
    assert reopened_cas.get_manifest(bundle_ref).artifact_schema.version == "1.1"
    assert sentinel.encode() not in bundle_bytes
    typed_bundle_payload = from_canonical_bytes(bundle_bytes)
    fresh_bundle = WebEvidenceBundle.model_validate(typed_bundle_payload)
    assert fresh_bundle.schema_version == "1.1"
    assert fresh_bundle.query_traces[0].provider_attempts is None
    assert fresh_bundle.query_traces[0].error == "legacy_error_not_established"

    completed_checkpoint_bytes = reopened_cas.get_bytes(status.checkpoint_artifact_id)
    completed_checkpoint = ResearchJobCheckpoint.model_validate(
        from_canonical_bytes(completed_checkpoint_bytes)
    )
    assert completed_checkpoint.bundle.schema_version == "1.1"
    assert completed_checkpoint.bundle.query_traces[0].provider_attempts is None
    assert sentinel.encode() not in completed_checkpoint_bytes

    report_bytes = reopened_cas.get_bytes(status.scholar_academic_evidence_artifact_id)
    report_payload = json.loads(report_bytes)
    assert sentinel.encode() not in report_bytes
    assert report_payload["provider_traces"][0]["error"] == ("legacy_error_not_established")

    malformed_query = copy.deepcopy(typed_bundle_payload)
    malformed_query["query_traces"][0].pop("provider_attempts", None)
    malformed_query["query_traces"][0]["error"] = sentinel
    _assert_bundle_rejected(
        malformed_query,
        expected_message="schema 1.1 query errors must use a safe category",
    )
    with pytest.raises(ValidationError) as report_error:
        build_scholar_academic_evidence_report_from_web_bundle(
            scholar_evidence_ref="sha256:" + "3" * 64,
            bundle=malformed_query,
            corpus_snapshot_ref="corpus-snapshot:malformed-attempts",
            lineage_ref="scholar-lineage:malformed-attempts",
        )
    _assert_expected_validation_error(
        report_error.value,
        expected_message="schema 1.1 query errors must use a safe category",
    )

    malformed_frontier = copy.deepcopy(typed_bundle_payload)
    malformed_frontier["no_hit_frontier"][0]["error"] = sentinel
    _assert_bundle_rejected(
        malformed_frontier,
        expected_message="schema 1.1 frontier errors must use a safe category",
    )

    bypassed = fresh_bundle.model_copy(
        update={
            "query_traces": [
                fresh_bundle.query_traces[0].model_copy(
                    update={"error": sentinel, "provider_attempts": None}
                )
            ],
            "no_hit_frontier": [
                fresh_bundle.no_hit_frontier[0].model_copy(update={"error": sentinel})
            ],
        }
    )
    artifacts_before = {str(item) for item in reopened_cas.iter_artifact_ids()}
    with pytest.raises(ValidationError) as persist_error:
        service.persist_bundle(bypassed)
    _assert_expected_validation_error(
        persist_error.value,
        expected_message="schema 1.1 query errors must use a safe category",
    )
    artifacts_after = {str(item) for item in reopened_cas.iter_artifact_ids()}
    assert artifacts_after == artifacts_before
