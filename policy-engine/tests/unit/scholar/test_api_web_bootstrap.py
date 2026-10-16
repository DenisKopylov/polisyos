"""Tests for Scholar API web-search bootstrap when seed sources are omitted."""

from __future__ import annotations

import asyncio
import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import (
    artifact_manifest_profile_sha256,
    load_core_json_artifact,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import content_hash, from_canonical_bytes
from polisyos.core.contracts.scholar import KnowledgeBundleRef, ResearchIntent
from polisyos.fabric.claims.persist import load_doc_meta
from polisyos.ir.world.ids import doc_version_id_from_raw_artifact
from polisyos.scholar.api import _source_spec_from_snapshot, enrich_topic
from polisyos.scholar.errors import ScholarAcquireError
from polisyos.scholar.search.cache import UrlFetchCache
from polisyos.scholar.search.fetcher import source_id_from_url
from polisyos.scholar.search.models import (
    FetchResult,
    QueryGraph,
    ResearchBrief,
    SearchBudgetControls,
    SearchConstraints,
    SourceSnippet,
    WebEvidenceBundle,
    WebSearchHit,
)
from polisyos.scholar.search.providers import (
    DuckDuckGoHtmlSearchProvider,
    OpenAlexWorksProvider,
    ProviderFailoverPolicy,
)
from polisyos.scholar.search.scoring import build_source_metadata
from polisyos.scholar.search.security import sanitize_untrusted_text
from polisyos.scholar.search.service import ScholarDeepSearchService
from polisyos.scholar.types import (
    EnrichmentReportV1,
    EnrichResultV1,
    KnowledgeBundlePayloadV1,
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
                title="Minimum wage report",
                snippet="Wage policy evidence",
                provider=self.name,
                query=query,
                rank=1,
                source_type="government",
            )
        ][:max_results]


class _EmptyProvider:
    name = "empty"

    def __init__(self, calls):
        self._calls = calls

    async def search(self, query, *, constraints, max_results, timeout_s):
        del query, constraints, max_results, timeout_s
        self._calls.append(self.name)
        return []


class _RecordingStaticProvider(_StaticProvider):
    def __init__(self, calls):
        self._calls = calls

    async def search(self, query, *, constraints, max_results, timeout_s):
        self._calls.append(self.name)
        return await super().search(
            query,
            constraints=constraints,
            max_results=max_results,
            timeout_s=timeout_s,
        )


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


@pytest.mark.parametrize(
    ("provider_order", "expected_provider_calls"),
    [
        (("empty", "static"), ["empty", "static"]),
        (("static", "empty"), ["static"]),
    ],
    ids=["empty-falls-through", "useful-first-short-circuits"],
)
def test_enrich_topic_bootstraps_seed_sources_from_web(
    monkeypatch,
    tmp_path,
    provider_order,
    expected_provider_calls,
):
    captured = {}
    provider_calls = []
    providers = {
        "empty": _EmptyProvider(provider_calls),
        "static": _RecordingStaticProvider(provider_calls),
    }

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
            provider_policy=ProviderFailoverPolicy([providers[name] for name in provider_order]),
            cas=cas,
        ),
        web_search_budgets=SearchBudgetControls(
            max_search_queries=1,
            max_fetch_pages=1,
            max_parallel_fetches=1,
            max_depth=0,
        ),
    )

    assert result.bundle_id == "bundle.web-bootstrap"
    assert provider_calls == expected_provider_calls
    assert len(captured["web_evidence_bundle"].query_traces) == 1
    trace = captured["web_evidence_bundle"].query_traces[0]
    assert trace.provider == "static"
    assert [attempt.provider for attempt in trace.provider_attempts] == expected_provider_calls
    assert [attempt.reason for attempt in trace.provider_attempts] == [
        "not_established" for _ in expected_provider_calls
    ]
    assert [attempt.outcome for attempt in trace.provider_attempts] == [
        "returned_no_hits" if name == "empty" else "returned_hits"
        for name in expected_provider_calls
    ]
    assert captured["intent"].seed_sources
    assert captured["intent"].seed_sources[0].props["canonical_url"] == (
        "https://agency.gov/minimum-wage"
    )
    assert captured["intent"].seed_sources[0].raw_artifact_ref is not None
    assert captured["web_evidence_bundle"].bundle_id.startswith("webkb.")
    assert captured["web_evidence_artifact_id"].startswith("sha256:")
    payload_bytes = cas.get_bytes(ArtifactID.model_validate(captured["web_evidence_artifact_id"]))
    persisted = json.loads(payload_bytes)
    typed_persisted = from_canonical_bytes(payload_bytes)
    assert persisted["schema_version"] == "1.1"
    assert [
        attempt["provider"] for attempt in persisted["query_traces"][0]["provider_attempts"]
    ] == expected_provider_calls
    assert [
        attempt["outcome"] for attempt in persisted["query_traces"][0]["provider_attempts"]
    ] == [
        "returned_no_hits" if name == "empty" else "returned_hits"
        for name in expected_provider_calls
    ]

    restored = WebEvidenceBundle.model_validate(typed_persisted)
    assert restored.query_traces[0].provider_attempts == trace.provider_attempts
    assert restored.query_traces[0].provider == trace.provider
    assert restored.query_traces[0].hit_count == trace.hit_count

    malformed_payloads = []
    malformed = copy.deepcopy(typed_persisted)
    malformed["query_traces"][0]["provider_attempts"][0]["returned_hit_count"] = True
    malformed_payloads.append(
        (
            malformed,
            {
                "expected_location_suffix": ("returned_hit_count",),
                "expected_error_type": "int_type",
            },
        )
    )

    malformed = copy.deepcopy(typed_persisted)
    malformed["query_traces"][0]["provider_attempts"][0]["constraint_rejection_counts"] = {
        "forged": -1
    }
    malformed_payloads.append(
        (
            malformed,
            {
                "expected_location_suffix": ("constraint_rejection_counts", "forged"),
                "expected_error_type": "greater_than_equal",
            },
        )
    )

    malformed = copy.deepcopy(typed_persisted)
    malformed["query_traces"][0]["provider_attempts"][0]["normalization_rejection_counts"] = {
        "forged": True
    }
    malformed_payloads.append(
        (
            malformed,
            {
                "expected_location_suffix": (
                    "normalization_rejection_counts",
                    "forged",
                ),
                "expected_error_type": "int_type",
            },
        )
    )

    malformed = copy.deepcopy(typed_persisted)
    malformed["query_traces"][0]["provider_attempts"][0]["outcome"] = "error"
    malformed_payloads.append(
        (
            malformed,
            {"expected_message": "error outcome requires a safe category and exception type"},
        )
    )

    if expected_provider_calls[0] == "empty":
        malformed = copy.deepcopy(typed_persisted)
        malformed["query_traces"][0]["provider_attempts"][0]["outcome"] = "returned_hits"
        malformed_payloads.append(
            (
                malformed,
                {"expected_message": "returned_hits outcome requires at least one hit"},
            )
        )

    malformed = copy.deepcopy(typed_persisted)
    malformed["query_traces"][0]["provider_attempts"][0]["attempt_index"] = 1
    malformed_payloads.append(
        (
            malformed,
            {"expected_message": "provider attempt indexes must be ordered and contiguous"},
        )
    )

    if len(expected_provider_calls) > 1:
        malformed = copy.deepcopy(typed_persisted)
        malformed["query_traces"][0]["provider_attempts"][1]["attempt_index"] = 0
        malformed_payloads.append(
            (
                malformed,
                {"expected_message": "provider attempt indexes must be ordered and contiguous"},
            )
        )

    malformed = copy.deepcopy(typed_persisted)
    malformed["query_traces"][0]["provider"] = "unobserved-provider"
    malformed_payloads.append(
        (
            malformed,
            {"expected_message": "selected provider must match the final observed attempt"},
        )
    )

    malformed = copy.deepcopy(typed_persisted)
    malformed["query_traces"][0]["error"] = "unobserved error"
    malformed_payloads.append(
        (
            malformed,
            {"expected_message": "successful query trace cannot retain a provider error"},
        )
    )

    for malformed_payload, expected_error in malformed_payloads:
        _assert_bundle_rejected(malformed_payload, **expected_error)


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


def test_enrich_topic_persists_value_free_provider_attempt_trace(
    monkeypatch,
    tmp_path,
):
    captured = {}
    url_marker = "r4-private-url-marker"
    mailto_marker = "r4-private-mailto"
    payload_marker = "r4-private-response-payload"

    async def _raise_openalex_status(url, **kwargs):
        del kwargs
        request = httpx.Request("GET", url)
        response = httpx.Response(429, request=request, text=payload_marker)
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
        raise AssertionError("HTTP 429 must raise HTTPStatusError")

    async def _fake_ddg_html(url, *, headers, timeout_s):
        del url, headers, timeout_s
        return (
            '<a class="result__a" href="https://agency.gov/minimum-wage">'
            "Minimum wage report</a>"
            '<a class="result__snippet">Wage policy evidence</a>'
        )

    def _capture_enrichment(**kwargs):
        captured.update(kwargs)
        return EnrichResultV1(
            knowledge_bundle_ref=KnowledgeBundleRef(
                artifact_id=ArtifactID.model_validate("sha256:" + "0" * 64)
            ),
            bundle_id="bundle.provider-attempt-privacy",
            report=EnrichmentReportV1(
                bundle_artifact_id="sha256:" + "0" * 64,
                bundle_id="bundle.provider-attempt-privacy",
            ),
        )

    monkeypatch.setattr(
        "polisyos.scholar.search.providers._read_openalex_url_text",
        _raise_openalex_status,
    )
    monkeypatch.setattr(
        "polisyos.scholar.search.providers._read_url_text",
        _fake_ddg_html,
    )
    monkeypatch.setattr(
        "polisyos.scholar.search.service.fetch_open_page",
        _fake_fetch_open_page,
    )
    monkeypatch.setattr("polisyos.scholar.api._enrich_topic", _capture_enrichment)

    cas = FileSystemCAS(tmp_path / "cas-provider-attempt-privacy")
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy(
            [
                OpenAlexWorksProvider(
                    endpoint=f"https://api.openalex.test/{url_marker}",
                    mailto=f"{mailto_marker}@example.test",
                ),
                DuckDuckGoHtmlSearchProvider(endpoint="https://ddg.test/html/"),
            ]
        ),
        cas=cas,
    )
    result = enrich_topic(
        cas=cas,
        fact_log_root=tmp_path / "facts-provider-attempt-privacy",
        intent=ResearchIntent(domain="labor", topic="minimum wage effects"),
        web_search_service=service,
        web_search_budgets=SearchBudgetControls(
            max_search_queries=1,
            max_fetch_pages=1,
            max_parallel_queries=1,
            max_parallel_fetches=1,
            max_depth=0,
        ),
    )

    assert result.bundle_id == "bundle.provider-attempt-privacy"
    assert captured["web_evidence_bundle"].schema_version == "1.1"
    artifact_id = ArtifactID.model_validate(captured["web_evidence_artifact_id"])
    manifest = cas.get_manifest(artifact_id)
    assert manifest.artifact_schema.version == "1.1"
    payload_bytes = cas.get_bytes(artifact_id)
    payload_text = payload_bytes.decode("utf-8")
    assert all(marker not in payload_text for marker in (url_marker, mailto_marker, payload_marker))
    persisted = json.loads(payload_text)
    trace = next(
        item
        for item in persisted["query_traces"]
        if any(attempt["provider"] == "openalex" for attempt in item["provider_attempts"])
    )
    attempt = trace["provider_attempts"][0]
    assert attempt["provider"] == "openalex"
    assert attempt["error"] == "provider_error"
    assert attempt["error_type"] == "http_status_error"
    assert trace["provider"] == "duckduckgo_html"
    assert trace.get("error") is None


def test_actual_snapshot_bytes_feed_unpatched_enrichment_and_fresh_bundle_reader(
    tmp_path,
):
    v1 = (
        b"Controlled LA-025 fixture report.\n"
        b"Search snapshot version v1.\n"
        b"claim: wage_index(region_a) = 120 [index]\n"
    )
    v2 = (
        b"Controlled LA-025 fixture report.\n"
        b"Same URL expired-cache version v2.\n"
        b"claim: wage_index(region_a) = 999 [index]\n"
    )

    class _VersionedHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.server.request_count += 1
            body = v1 if self.server.request_count == 1 else v2
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), _VersionedHandler)
    server.request_count = 0
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/same-report"

    class _LocalOneHitProvider:
        name = "controlled-la025-local-fixture"

        async def search(self, query, *, constraints, max_results, timeout_s):
            del constraints, timeout_s
            return [
                WebSearchHit(
                    url=url,
                    title="Controlled fixture",
                    snippet="wage index evidence",
                    provider=self.name,
                    query=query,
                    rank=1,
                    source_type="government",
                )
            ][:max_results]

    def _rows_for_kind(store, kind):
        rows = []
        for artifact_id in store.iter_artifact_ids():
            manifest = store.get_manifest(artifact_id)
            if manifest.kind == kind:
                rows.append((artifact_id, manifest))
        return rows

    try:
        tenant = "la025-actual-route-fixture"
        cas_root = tmp_path / "cas"
        cas = FileSystemCAS(cas_root, tenant_id=tenant)
        cache_index = tmp_path / "cache" / "index.json"
        cache_index.parent.mkdir(parents=True)
        cache = UrlFetchCache(index_path=cache_index, cas=cas, ttl_seconds=86_400)
        provider = _LocalOneHitProvider()
        service = ScholarDeepSearchService(
            provider_policy=ProviderFailoverPolicy([provider]),
            cas=cas,
            cache=cache,
        )
        intent = ResearchIntent(domain="labor", topic="wage index controlled lineage")
        constraints = SearchConstraints(
            allowed_domains=["127.0.0.1"],
            allow_private_networks=True,
        )
        budgets = SearchBudgetControls(
            max_search_queries=1,
            max_fetch_pages=1,
            max_parallel_queries=1,
            max_parallel_fetches=1,
            max_depth=0,
            max_wall_time_s=10,
            per_page_max_bytes=4096,
        )

        # This is the real public API and the real unpatched search/fetch/intake/enrich route.
        result = enrich_topic(
            cas=cas,
            fact_log_root=tmp_path / "facts",
            intent=intent,
            web_search_service=service,
            web_search_constraints=constraints,
            web_search_budgets=budgets,
        )
        assert server.request_count == 1

        fresh = FileSystemCAS(cas_root, tenant_id=tenant)
        web_rows = _rows_for_kind(fresh, "scholar.web_evidence_bundle")
        assert len(web_rows) == 1
        web_artifact_id, web_manifest = web_rows[0]
        web_bundle = WebEvidenceBundle.model_validate(
            from_canonical_bytes(fresh.get_bytes(web_artifact_id))
        )
        assert web_manifest.kind == "scholar.web_evidence_bundle"
        assert len(web_bundle.sources) == 1
        source = web_bundle.sources[0]
        selected_ref = source.raw_artifact_ref
        assert selected_ref is not None
        assert selected_ref.kind == "scholar.web_fetch_payload"
        assert selected_ref.media_type == "text/plain"
        assert source.content_sha256 == content_hash(v1)
        assert fresh.get_bytes(selected_ref) == v1

        knowledge_ref = result.knowledge_bundle_ref
        knowledge_manifest = fresh.get_manifest(knowledge_ref)
        knowledge_bytes = fresh.get_bytes(knowledge_ref)
        knowledge_payload = load_core_json_artifact(fresh, knowledge_ref)
        assert isinstance(knowledge_payload, dict)
        knowledge = KnowledgeBundlePayloadV1.model_validate(knowledge_payload)
        assert knowledge_manifest.kind == "scholar.knowledge_bundle"
        assert knowledge_manifest.media_type == "application/json"
        assert knowledge_manifest.artifact_schema.name == (
            "polisyos.scholar.KnowledgeBundlePayloadV1"
        )
        assert knowledge_manifest.canon is not None
        assert knowledge_manifest.canon.forbid_floats is False
        assert knowledge_ref.manifest_profile_sha256 is not None
        assert artifact_manifest_profile_sha256(knowledge_manifest) == (
            knowledge_ref.manifest_profile_sha256
        )
        assert knowledge.doc_meta_artifact_ids
        assert knowledge.web_evidence["sources"][0]["content_sha256"] == content_hash(v1)
        assert knowledge.web_evidence["sources"][0]["raw_artifact_ref"] == (
            selected_ref.model_dump(mode="json", exclude_none=True)
        )
        assert isinstance(knowledge.web_evidence["sources"][0]["quality_score"], float)
        assert isinstance(knowledge.web_evidence["snippets"][0]["relevance_score"], float)

        matching_doc_metas = []
        for artifact_id in knowledge.doc_meta_artifact_ids:
            meta = load_doc_meta(fresh, str(artifact_id))
            if meta.canonical_url != url:
                continue
            raw = fresh.get_bytes(ArtifactID.model_validate(meta.raw_ref))
            matching_doc_metas.append(meta)
            assert raw == v1
            assert meta.doc_version_id == doc_version_id_from_raw_artifact(
                raw_artifact_id=meta.raw_ref
            )
        assert matching_doc_metas
        assert all(meta.license == "public-web" for meta in matching_doc_metas)

        cached_bundle = asyncio.run(
            service.deep_search(
                intent=intent,
                claim_texts=[intent.topic],
                constraints=constraints,
                budgets=budgets,
            )
        )
        cached_source = cached_bundle.sources[0]
        assert cached_source.fetch_status == "cached"
        assert cached_source.source_id == source.source_id
        assert cached_source.raw_artifact_ref == selected_ref
        assert server.request_count == 1

        expired_cache = UrlFetchCache(
            index_path=cache_index,
            cas=cas,
            ttl_seconds=0,
        )
        refresh_service = ScholarDeepSearchService(
            provider_policy=ProviderFailoverPolicy([_LocalOneHitProvider()]),
            cas=cas,
            cache=expired_cache,
        )
        refreshed_bundle = asyncio.run(
            refresh_service.deep_search(
                intent=intent,
                claim_texts=[intent.topic],
                constraints=constraints,
                budgets=budgets,
            )
        )
        refreshed = refreshed_bundle.sources[0]
        assert server.request_count == 2
        assert str(refreshed.url) == url
        assert refreshed.raw_artifact_ref is not None
        assert fresh.get_bytes(refreshed.raw_artifact_ref) == v2
        assert refreshed.content_sha256 == content_hash(v2)
        assert refreshed.source_id != source.source_id
        assert refreshed.lineage_parent_artifact_id == str(selected_ref.artifact_id)
        assert refreshed.refresh_reason == "cache-refresh"

        malformed_wire = web_bundle.model_dump(mode="python")
        malformed_wire["sources"][0]["raw_artifact_ref"]["manifest_profile_sha256"] = (
            "not-a-manifest-profile"
        )
        with pytest.raises(ValidationError):
            WebEvidenceBundle.model_validate(malformed_wire)

        wrong_profile_ref = selected_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + ("f" * 64)}
        )
        wrong_profile_source = source.model_copy(update={"raw_artifact_ref": wrong_profile_ref})
        with pytest.raises(ScholarAcquireError, match="raw snapshot is unavailable"):
            _source_spec_from_snapshot(
                wrong_profile_source,
                cas=fresh,
                cache=service._cache,
            )

        missing_hex = "e" * 64
        missing_ref = selected_ref.model_copy(
            update={"artifact_id": ArtifactID.model_validate("sha256:" + missing_hex)}
        )
        missing_source = source.model_copy(
            update={
                "raw_artifact_ref": missing_ref,
                "content_sha256": missing_hex,
            }
        )
        with pytest.raises(ScholarAcquireError, match="raw snapshot is unavailable"):
            _source_spec_from_snapshot(missing_source, cas=fresh, cache=service._cache)

        no_snapshot = source.model_copy(
            update={
                "raw_artifact_ref": None,
                "artifact_id": None,
                "content_sha256": None,
            }
        )
        with pytest.raises(ScholarAcquireError, match="no reusable raw snapshot"):
            _source_spec_from_snapshot(no_snapshot, cas=fresh, cache=None)

        assert fresh.get_bytes(selected_ref) == v1
        assert server.request_count == 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
