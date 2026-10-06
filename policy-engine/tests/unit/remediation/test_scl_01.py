"""Regression witnesses for Scholar provider selection and shared fetch adapters."""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.scholar import SourceSpec
from polisyos.scholar.discover.http_fetch import fetch_url
from polisyos.scholar.errors import ScholarAcquireError
from polisyos.scholar.search.cache import UrlFetchCache
from polisyos.scholar.search.fetcher import fetch_open_page
from polisyos.scholar.search.models import (
    QueryGraph,
    QueryNode,
    ResearchBrief,
    SearchBudgetControls,
    SearchConstraints,
    WebEvidenceBundle,
    WebSearchHit,
)
from polisyos.scholar.search.providers import ProviderFailoverPolicy
from polisyos.scholar.search.service import ScholarDeepSearchService


@contextmanager
def _redirecting_server() -> Iterator[tuple[str, list[str]]]:
    transcript: list[str] = []
    body = b"raw scholar response v1\n"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            transcript.append(self.path)
            if self.path == "/entry":
                self.send_response(302)
                self.send_header("Location", "/final-v1")
                self.end_headers()
                return
            if self.path == "/blocked-redirect":
                self.send_response(302)
                self.send_header(
                    "Location",
                    f"http://blocked.localhost:{server.server_address[1]}/final-v1",
                )
                self.end_headers()
                return
            if self.path == "/loop":
                self.send_response(302)
                self.send_header("Location", "/loop")
                self.end_headers()
                return
            if self.path == "/timeout":
                time.sleep(0.2)
            response_body = body
            if self.path == "/oversize":
                response_body = b"1234567890"
            if self.path == "/wrong-mime":
                response_body = b"{}"
            self.send_response(200)
            content_type = "application/json" if self.path == "/wrong-mime" else "text/plain"
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("ETag", '"scl01-v1"')
            self.send_header("X-PolicyOS-Test", "v1")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            try:
                self.wfile.write(response_body)
            except BrokenPipeError:
                return

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/entry", transcript
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class _ScriptedProvider:
    def __init__(self, name: str, response: list[WebSearchHit] | Exception) -> None:
        self.name = name
        self.response = response
        self.calls: list[tuple[str, SearchConstraints]] = []

    async def search(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float,
    ) -> list[WebSearchHit]:
        del max_results, timeout_s
        self.calls.append((query, constraints))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _hit(name: str, url: str, *, source_type: str = "government") -> WebSearchHit:
    return WebSearchHit(
        url=url,
        title=name,
        provider=name,
        query="employment policy",
        rank=1,
        source_type=source_type,
    )


@pytest.mark.asyncio
async def test_provider_selection_continues_after_empty_and_stops_at_first_useful_result() -> None:
    empty = _ScriptedProvider("empty", [])
    useful = _ScriptedProvider("useful", [_hit("v2", "https://allowed.example/report")])
    forbidden_later = _ScriptedProvider("later", RuntimeError("must not run"))
    policy = ProviderFailoverPolicy([empty, useful, forbidden_later])
    constraints = SearchConstraints(
        allowed_domains=["allowed.example"],
        source_types=["government"],
    )

    result = await policy.search_detailed(
        "employment policy",
        constraints=constraints,
        max_results=5,
        timeout_s=1,
    )

    assert [provider.name for provider in (empty, useful, forbidden_later) if provider.calls] == [
        "empty",
        "useful",
    ]
    assert [str(hit.url) for hit in result.hits] == ["https://allowed.example/report"]
    assert [(attempt.provider, attempt.outcome) for attempt in result.attempts] == [
        ("empty", "empty"),
        ("useful", "useful"),
    ]
    assert result.exhausted is False


@pytest.mark.asyncio
async def test_useful_first_provider_short_circuits_remaining_providers() -> None:
    useful = _ScriptedProvider("first", [_hit("report", "https://allowed.example/report")])
    uncalled = _ScriptedProvider("second", RuntimeError("must not run"))
    policy = ProviderFailoverPolicy([useful, uncalled])

    result = await policy.search_detailed(
        "employment policy",
        constraints=SearchConstraints(
            allowed_domains=["allowed.example"],
            source_types=["government"],
        ),
        max_results=5,
        timeout_s=1,
    )

    assert len(useful.calls) == 1
    assert not uncalled.calls
    assert [attempt.provider for attempt in result.attempts] == ["first"]
    assert result.stop_reason == "useful"
    assert result.exhausted is False


@pytest.mark.asyncio
async def test_provider_selection_records_unsuitable_error_and_empty_before_exhaustion() -> None:
    unsuitable = _ScriptedProvider(
        "unsuitable",
        [_hit("wrong domain", "https://blocked.example/report")],
    )
    errored = _ScriptedProvider("error", RuntimeError("provider unavailable"))
    empty = _ScriptedProvider("empty", [])
    policy = ProviderFailoverPolicy([unsuitable, errored, empty])
    constraints = SearchConstraints(
        allowed_domains=["allowed.example"],
        source_types=["government"],
    )

    result = await policy.search_detailed(
        "employment policy",
        constraints=constraints,
        max_results=5,
        timeout_s=1,
    )

    assert [attempt.outcome for attempt in result.attempts] == [
        "unsuitable",
        "error",
        "empty",
    ]
    assert [attempt.provider for attempt in result.attempts] == [
        "unsuitable",
        "error",
        "empty",
    ]
    assert [
        (attempt.returned_hit_count, attempt.accepted_hit_count)
        for attempt in result.attempts
    ] == [(1, 0), (0, 0), (0, 0)]
    assert result.attempts[1].error_type == "RuntimeError"
    assert result.hits == []
    assert result.exhausted is True
    assert result.stop_reason == "providers_exhausted"


@pytest.mark.asyncio
async def test_deep_search_consumes_next_permitted_provider_after_empty_result(tmp_path) -> None:
    with _redirecting_server() as (url, transcript):
        empty = _ScriptedProvider("empty", [])
        useful = _ScriptedProvider("useful", [_hit("report", url)])
        uncalled = _ScriptedProvider("uncalled", RuntimeError("must not run"))
        cas = FileSystemCAS(tmp_path / "cas")
        service = ScholarDeepSearchService(
            provider_policy=ProviderFailoverPolicy([empty, useful, uncalled]),
            cache=UrlFetchCache(index_path=tmp_path / "cache.json", cas=cas),
            cas=cas,
            fetch_timeout_s=3,
        )
        brief = ResearchBrief(question="employment policy")
        graph = QueryGraph(
            brief=brief,
            nodes=[QueryNode(node_id="q1", query="employment", perspective="overview")],
            root_node_ids=["q1"],
        )

        bundle = await service.deep_search(
            brief=brief,
            query_graph=graph,
            constraints=SearchConstraints(
                allowed_domains=["127.0.0.1"],
                source_types=["government"],
                allow_private_networks=True,
                allowed_content_types=["text/plain"],
            ),
            budgets=SearchBudgetControls(
                max_search_queries=1,
                max_fetch_pages=1,
                max_parallel_queries=1,
                max_parallel_fetches=1,
                max_depth=0,
                per_page_max_bytes=1024,
            ),
        )

    assert [attempt.outcome for attempt in bundle.query_traces[0].provider_attempts] == [
        "empty",
        "useful",
    ]
    assert bundle.query_traces[0].terminal_reason == "useful"
    assert not bundle.no_hit_frontier
    assert [provider.calls[0][1].allowed_domains for provider in (empty, useful)] == [
        ["127.0.0.1"],
        ["127.0.0.1"],
    ]
    assert not uncalled.calls
    assert len(bundle.sources) == 1
    assert bundle.sources[0].final_url.endswith("/final-v1")
    assert bundle.sources[0].artifact_id == "sha256:" + hashlib.sha256(
        b"raw scholar response v1\n"
    ).hexdigest()
    assert transcript == ["/entry", "/final-v1"]


@pytest.mark.asyncio
async def test_deep_search_persists_exhaustion_after_unsuitable_error_and_empty(tmp_path) -> None:
    providers = [
        _ScriptedProvider(
            "unsuitable",
            [_hit("blocked", "https://blocked.example/report")],
        ),
        _ScriptedProvider("error", RuntimeError("provider unavailable")),
        _ScriptedProvider("empty", []),
    ]
    brief = ResearchBrief(question="employment policy")
    graph = QueryGraph(
        brief=brief,
        nodes=[QueryNode(node_id="q1", query="employment", perspective="overview")],
        root_node_ids=["q1"],
    )
    service = ScholarDeepSearchService(provider_policy=ProviderFailoverPolicy(providers))

    bundle = await service.deep_search(
        brief=brief,
        query_graph=graph,
        constraints=SearchConstraints(allowed_domains=["allowed.example"]),
        budgets=SearchBudgetControls(
            max_search_queries=1,
            max_fetch_pages=1,
            max_parallel_queries=1,
            max_depth=0,
        ),
    )

    assert [attempt.outcome for attempt in bundle.query_traces[0].provider_attempts] == [
        "unsuitable",
        "error",
        "empty",
    ]
    assert bundle.query_traces[0].terminal_reason == "providers_exhausted"
    assert bundle.no_hit_frontier[0].reason == "providers_exhausted"
    assert bundle.query_graph.nodes[0].hit_count == 0


@pytest.mark.asyncio
async def test_deep_search_persists_attempt_trace_and_distinct_query_budget_stop(
    tmp_path,
) -> None:
    provider = _ScriptedProvider("empty", [])
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([provider]),
        cas=FileSystemCAS(tmp_path / "cas"),
    )
    brief = ResearchBrief(question="employment policy")
    graph = QueryGraph(
        brief=brief,
        nodes=[
            QueryNode(node_id="q1", query="one", perspective="overview"),
            QueryNode(node_id="q2", query="two", perspective="overview"),
        ],
        root_node_ids=["q1", "q2"],
    )

    bundle = await service.deep_search(
        brief=brief,
        query_graph=graph,
        constraints=SearchConstraints(),
        budgets=SearchBudgetControls(
            max_search_queries=1,
            max_fetch_pages=10,
            max_parallel_queries=1,
            max_depth=0,
        ),
    )
    ref = service.persist_bundle(bundle)
    manifest = service._cas.get_manifest(ref.artifact_id)
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.version == "1.1"
    persisted = WebEvidenceBundle.model_validate(
        from_canonical_bytes(
            service._cas.get_bytes(ref.artifact_id)
        )
    )

    assert len(provider.calls) == 1
    assert persisted.query_traces[0].provider_attempts[0].outcome == "empty"
    assert persisted.query_traces[0].terminal_reason == "providers_exhausted"
    assert persisted.no_hit_frontier[0].reason == "provider_returned_no_hits"
    assert [stop.reason for stop in persisted.budget_stops] == ["max_search_queries"]


@pytest.mark.asyncio
async def test_search_and_seed_adapters_preserve_the_same_raw_transport_record(tmp_path) -> None:
    constraints = SearchConstraints(
        allow_private_networks=True,
        allowed_content_types=["text/plain"],
    )
    with _redirecting_server() as (url, transcript):
        cas = FileSystemCAS(tmp_path / "cas")
        cache = UrlFetchCache(index_path=tmp_path / "cache.json", cas=cas)
        searched = await fetch_open_page(
            url,
            constraints=constraints,
            cache=cache,
            timeout_s=3,
            user_agent="scl01-test",
            max_bytes=1024,
        )
        seeded = fetch_url(
            SourceSpec(
                kind="url",
                canonical_url=url,
                url=url,
                license="CC-BY-4.0",
                mime_hint="text/plain",
            ),
            constraints=constraints,
            timeout_s=3,
            user_agent="scl01-test",
            max_bytes=1024,
        )
        cached = cache.get(url)

    expected_bytes = b"raw scholar response v1\n"
    expected_hash = hashlib.sha256(expected_bytes).hexdigest()
    assert searched.status == "ok"
    assert searched.final_url.endswith("/final-v1")
    assert searched.content_sha256 == expected_hash
    assert searched.byte_size == len(expected_bytes)
    assert searched.headers["X-PolicyOS-Test"] == "v1"
    assert searched.redirect_chain == [searched.final_url]
    assert searched.artifact_id == f"sha256:{expected_hash}"
    assert searched.license == "public-web"
    assert searched.fetch_profile["max_bytes"] == 1024
    assert cached is not None
    assert cached.artifact_id == searched.artifact_id
    assert cached.final_url == searched.final_url
    assert cached.headers == searched.headers
    assert cached.redirect_chain == searched.redirect_chain
    assert cached.byte_size == searched.byte_size
    assert cached.fetch_profile == searched.fetch_profile

    assert seeded.raw_bytes == expected_bytes
    assert seeded.final_url.endswith("/final-v1")
    assert seeded.headers["X-PolicyOS-Test"] == "v1"
    assert seeded.redirect_chain == [seeded.final_url]
    assert seeded.content_sha256 == expected_hash
    assert seeded.byte_size == len(expected_bytes)
    assert seeded.doc_source.license == "CC-BY-4.0"
    assert seeded.fetch_profile["max_bytes"] == 1024
    assert transcript == ["/entry", "/final-v1", "/entry", "/final-v1"]


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("initial_block", "blocked_private_network"),
        ("redirect_block", "blocked_domain"),
        ("redirect_loop", "redirect_error"),
        ("timeout", "timeout"),
        ("oversize", "max_bytes_exceeded"),
        ("wrong_mime", "blocked_content_type"),
    ],
)
@pytest.mark.parametrize("caller", ["search", "seed"])
@pytest.mark.asyncio
async def test_search_and_seed_adapters_preserve_typed_fetch_refusals(
    caller: str,
    case: str,
    reason: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _redirecting_server() as (base_url, transcript):
        path = {
            "initial_block": "/final-v1",
            "redirect_block": "/blocked-redirect",
            "redirect_loop": "/loop",
            "timeout": "/timeout",
            "oversize": "/oversize",
            "wrong_mime": "/wrong-mime",
        }[case]
        url = f"{base_url.rsplit('/', 1)[0]}{path}"
        constraints = SearchConstraints(
            allow_private_networks=case != "initial_block",
            blocked_domains=["blocked.localhost"] if case == "redirect_block" else [],
            allowed_content_types=["text/plain"],
        )
        max_bytes = 4 if case == "oversize" else 1024
        timeout_s = 0.05 if case == "timeout" else 1
        if case == "timeout":
            class _TimeoutOpener:
                def open(self, request: object, timeout: float) -> object:
                    del request
                    assert timeout == timeout_s
                    raise TimeoutError("fixture request timed out")

            monkeypatch.setattr(
                "polisyos.scholar.discover.transport.urllib.request.build_opener",
                lambda *handlers: _TimeoutOpener(),
            )

        if caller == "search":
            fetched = await fetch_open_page(
                url,
                constraints=constraints,
                cache=None,
                timeout_s=timeout_s,
                user_agent="scl01-test",
                max_bytes=max_bytes,
            )
            assert fetched.failure_reason == reason
        else:
            source = SourceSpec(
                kind="url",
                canonical_url=url,
                url=url,
                license="CC-BY-4.0",
                mime_hint="text/plain",
            )
            with pytest.raises(ScholarAcquireError) as caught:
                fetch_url(
                    source,
                    constraints=constraints,
                    timeout_s=timeout_s,
                    user_agent="scl01-test",
                    max_bytes=max_bytes,
                )
            assert caught.value.details["reason"] == reason
        if case == "redirect_block":
            assert "/blocked-redirect" in transcript
            assert "/final-v1" not in transcript
