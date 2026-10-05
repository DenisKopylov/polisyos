"""Tests for Scholar API web-search bootstrap when seed sources are omitted."""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import content_hash
from polisyos.core.contracts.scholar import KnowledgeBundleRef, ResearchIntent
from polisyos.scholar.api import _source_spec_from_snapshot, enrich_topic
from polisyos.scholar.errors import ScholarAcquireError, ScholarDiscoverError
from polisyos.scholar.orchestrator.enrich import _acquire_bytes
from polisyos.scholar.search.models import (
    FetchResult,
    SearchBudgetControls,
    SearchConstraints,
    SourceMetadata,
    WebSearchHit,
)
from polisyos.scholar.search.providers import ProviderFailoverPolicy
from polisyos.scholar.search.service import ScholarDeepSearchService
from polisyos.scholar.types import EnrichmentReportV1, EnrichResultV1


class _StaticProvider:
    name = "static"

    def __init__(self, url: str = "https://agency.gov/minimum-wage") -> None:
        self._url = url

    async def search(self, query, *, constraints, max_results, timeout_s):
        del constraints, timeout_s
        return [
            WebSearchHit(
                url=self._url,
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
    del timeout_s, user_agent, max_bytes
    raw_bytes = b"<html><title>Minimum wage report</title><body>snapshot payload</body></html>"
    result = FetchResult(
        url=url,
        final_url=url,
        title="Minimum wage report",
        text="Minimum wage increased earnings for low-wage workers.",
        content_type="text/html",
        status="ok",
        content_sha256=content_hash(raw_bytes),
        fetch_profile={
            "request_url": str(url),
            "timeout_s": 10.0,
            "max_bytes": 2_000_000,
            "allowed_domains": list(constraints.allowed_domains),
        },
        source_type=source_type_hint,
    )
    cache.put(result, raw_bytes=raw_bytes)
    return result


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
    seed_source = captured["intent"].seed_sources[0]
    assert seed_source.kind == "bytes"
    assert seed_source.props["canonical_url"] == "https://agency.gov/minimum-wage"
    assert captured["web_evidence_bundle"].bundle_id.startswith("webkb.")
    assert captured["web_evidence_artifact_id"].startswith("sha256:")


def test_enrich_topic_uses_shared_async_bridge(monkeypatch, tmp_path):
    captured = {"used_run_coro_sync": False}
    raw_bytes = b"<html><body>shared bridge snapshot</body></html>"
    cas = FileSystemCAS(tmp_path / "cas-shared")
    raw_ref = cas.put_bytes(raw_bytes, _snapshot_write_options()).artifact_id
    raw_digest = content_hash(raw_bytes)

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
                    content_sha256=raw_digest,
                    artifact_id=str(raw_ref),
                    byte_size=len(raw_bytes),
                    fetch_profile={
                        "request_url": "https://agency.gov/minimum-wage",
                        "timeout_s": 10.0,
                        "max_bytes": 2_000_000,
                    },
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


def test_search_snapshot_bytes_are_reused_and_request_binding_is_enforced(monkeypatch, tmp_path):
    requested_paths: list[str] = []
    request_lock = threading.Lock()
    versions = [
        b"<html><title>snapshot v1</title><body>minimum wage snapshot v1</body></html>",
        b"<html><title>snapshot v2</title><body>minimum wage snapshot v2</body></html>",
    ]

    class _VersionedHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            with request_lock:
                version_index = len(requested_paths)
                requested_paths.append(self.path)
            body = versions[min(version_index, len(versions) - 1)]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), _VersionedHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = f"http://127.0.0.1:{server.server_port}/snapshot"
    cas = FileSystemCAS(tmp_path / "cas-snapshot")
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([_StaticProvider(url)]),
        cas=cas,
        fetch_timeout_s=2,
    )
    captured = {}

    def _consume_snapshot(**kwargs):
        source = kwargs["intent"].seed_sources[0]
        acquired = _acquire_bytes(source, max_bytes=100_000)
        captured["source"] = source
        captured["raw_bytes"] = acquired.raw_bytes
        captured["web_bundle"] = kwargs["web_evidence_bundle"]
        captured["web_bundle_artifact_id"] = kwargs["web_evidence_artifact_id"]
        return EnrichResultV1(
            knowledge_bundle_ref=KnowledgeBundleRef(
                artifact_id=ArtifactID.model_validate("sha256:" + "3" * 64)
            ),
            bundle_id="bundle.snapshot-reuse",
            report=EnrichmentReportV1(
                bundle_artifact_id="sha256:" + "3" * 64,
                bundle_id="bundle.snapshot-reuse",
            ),
        )

    monkeypatch.setattr("polisyos.scholar.api._enrich_topic", _consume_snapshot)
    try:
        result = enrich_topic(
            cas=cas,
            fact_log_root=tmp_path / "facts-snapshot",
            intent=ResearchIntent(domain="labor", topic="minimum wage snapshot"),
            web_search_service=service,
            web_search_constraints=SearchConstraints(
                allowed_domains=["127.0.0.1"],
                source_types=["web"],
                allow_private_networks=True,
            ),
            web_search_budgets=SearchBudgetControls(
                max_search_queries=1,
                max_fetch_pages=1,
                max_parallel_fetches=1,
                max_depth=0,
                max_wall_time_s=10,
            ),
        )

        source = captured["web_bundle"].sources[0]
        artifact_id = ArtifactID.model_validate(source.artifact_id)
        persisted_bundle = json.loads(
            cas.get_bytes(ArtifactID.model_validate(captured["web_bundle_artifact_id"]))
        )
        assert requested_paths == ["/snapshot"]
        assert cas.get_bytes(artifact_id) == versions[0]
        assert persisted_bundle["sources"][0]["artifact_id"] == source.artifact_id
        assert persisted_bundle["sources"][0]["fetch_profile"]["request_url"] == url
        assert captured["raw_bytes"] == versions[0]
        assert captured["source"].kind == "bytes"
        assert source.byte_size == len(versions[0])
        assert source.fetch_profile["request_url"] == url
        assert result.bundle_id == "bundle.snapshot-reuse"

        with pytest.raises(ScholarAcquireError) as mutated:
            _source_spec_from_snapshot(
                source,
                cas=_MutatingCAS(cas, artifact_id, versions[0] + b"changed"),
                cache=service._cache,
            )
        assert mutated.value.details["expected_sha256"] == source.content_sha256

        sibling_ref = cas.put_bytes(
            b"sibling artifact",
            _snapshot_write_options(),
        ).artifact_id
        with pytest.raises(ScholarAcquireError) as sibling:
            _source_spec_from_snapshot(
                source.model_copy(update={"artifact_id": str(sibling_ref)}),
                cas=cas,
                cache=service._cache,
            )
        assert sibling.value.details["reason"] == "artifact_ref_mismatch"

        wrong_request_source = source.model_copy(
            update={
                "fetch_profile": {
                    **source.fetch_profile,
                    "request_url": "http://127.0.0.1:9/wrong-request",
                }
            }
        )
        with pytest.raises(ScholarAcquireError) as wrong_request:
            _source_spec_from_snapshot(
                wrong_request_source,
                cas=cas,
                cache=service._cache,
            )
        assert wrong_request.value.details["reason"] == "request_binding_mismatch"
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)


class _MutatingCAS:
    def __init__(self, cas, artifact_id, replacement: bytes) -> None:
        self._cas = cas
        self._artifact_id = str(artifact_id)
        self._replacement = replacement

    def get_bytes(self, artifact_id):
        if str(artifact_id) == self._artifact_id:
            return self._replacement
        return self._cas.get_bytes(artifact_id)


def _snapshot_write_options():
    from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions

    return ArtifactWriteOptions(
        kind="scholar.web_fetch_payload",
        media_type="text/plain",
        schema=SchemaInfo(name="polisyos.scholar.web_fetch_payload", version="1.0"),
        producer=ProducerInfo(component="tests.scholar.snapshot", version="1.0.0"),
    )


def test_empty_provider_responses_and_failures_survive_search_bundle_and_api_error(tmp_path):
    class _Empty:
        name = "empty"

        async def search(self, query, *, constraints, max_results, timeout_s):
            del query, constraints, max_results, timeout_s
            return []

    class _Failure:
        name = "failed"

        async def search(self, query, *, constraints, max_results, timeout_s):
            del query, constraints, max_results, timeout_s
            raise RuntimeError("fixture provider failure")

    cas = FileSystemCAS(tmp_path / "cas-empty-search")
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([_Empty(), _Failure()]),
        cas=cas,
    )

    with pytest.raises(ScholarDiscoverError) as discover_error:
        enrich_topic(
            cas=cas,
            fact_log_root=tmp_path / "facts-empty-search",
            intent=ResearchIntent(domain="labor", topic="minimum wage snapshot"),
            web_search_service=service,
            web_search_budgets=SearchBudgetControls(
                max_search_queries=1,
                max_fetch_pages=1,
                max_depth=0,
            ),
        )

    details = discover_error.value.details
    assert details["reason"] == "search_returned_no_sources"
    attempts = details["provider_attempts"]
    assert [
        (attempt["provider"], attempt["outcome"], attempt["hit_count"], attempt["error"])
        for attempt in attempts
    ] == [
        ("empty", "no_hits", 0, None),
        ("failed", "error", 0, "fixture provider failure"),
    ]
    assert attempts[0]["query_node_id"] == attempts[1]["query_node_id"]
    assert details["web_evidence_artifact_id"].startswith("sha256:")
    persisted_bundle = json.loads(
        cas.get_bytes(ArtifactID.model_validate(details["web_evidence_artifact_id"]))
    )
    assert [
        (attempt["provider"], attempt["outcome"], attempt.get("error"))
        for attempt in persisted_bundle["query_traces"][0]["provider_attempts"]
    ] == [
        ("empty", "no_hits", None),
        ("failed", "error", "fixture provider failure"),
    ]
