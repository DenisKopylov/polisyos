"""Test-first witnesses for SCL-03 raw-snapshot handoff into Scholar enrich."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.scholar import KnowledgeBundleRef, ResearchIntent, SourceSpec
from polisyos.scholar.api import enrich_topic
from polisyos.scholar.discover.http_fetch import fetch_url
from polisyos.scholar.errors import ScholarAcquireError
from polisyos.scholar.search.cache import UrlFetchCache
from polisyos.scholar.search.models import FetchResult, SearchConstraints, SourceMetadata
from polisyos.scholar.types import EnrichResultV1, EnrichmentReportV1


SOURCE_URL = "https://agency.gov/reports/employment"
FINAL_URL = "https://agency.gov/reports/employment-2026"
SNAPSHOT_V1 = b"policy v1: employment increased\n"
SNAPSHOT_V2 = b"policy v2: employment decreased\n"
SNAPSHOT_V1_SHA256 = "5268fce59c15375a7f1156ff7e08d165abee5f829bddf67eda1649dcc1d06029"
SNAPSHOT_V2_SHA256 = "e8698a4c29c7f109b79edcf11d3b4ed9fe2529e557c49d627f163555ba83f989"
FETCH_PROFILE = {
    "transport": "scl-01",
    "timeout_s": "5",
    "max_bytes": "4096",
    "allowed_content_types": "text/plain",
    "allow_private_networks": "false",
}


class _FixtureSearchService:
    """Return a local evidence bundle without invoking a provider or the network."""

    def __init__(self, bundle: SimpleNamespace) -> None:
        self._bundle = bundle
        self.deep_search_calls = 0

    async def deep_search(self, **_kwargs: object) -> SimpleNamespace:
        self.deep_search_calls += 1
        return self._bundle

    def persist_bundle(self, _bundle: object) -> KnowledgeBundleRef:
        return KnowledgeBundleRef(
            artifact_id=ArtifactID.model_validate("sha256:" + "a" * 64),
        )


class _FakeResponse:
    def __init__(self, body: bytes, *, content_type: str = "text/plain") -> None:
        self._body = body
        self.url = SOURCE_URL
        self.headers = {"Content-Type": content_type, "ETag": "fixture-v1"}

    def read(self, limit: int) -> bytes:
        return self._body[:limit]

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False


class _FakeOpener:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def open(self, request: object, timeout: float) -> _FakeResponse:
        assert getattr(request, "full_url") == SOURCE_URL
        assert timeout == 2
        return _FakeResponse(self._body)


def _source(
    *,
    payload: bytes,
    artifact_id: str | None,
    content_sha256: str | None = None,
    lineage_parent_artifact_id: str | None = None,
    refresh_reason: str | None = None,
    fetch_status: str = "cached",
) -> SimpleNamespace:
    """Build a search source with the complete raw binding expected by LA-025."""
    fields: dict[str, object] = {
        "source_id": "src.employment.v1",
        "url": SOURCE_URL,
        "final_url": FINAL_URL,
        "title": "Employment policy report",
        "domain": "agency.gov",
        "source_type": "government",
        "provider": "fixture",
        "search_query": "employment policy",
        "search_rank": 1,
        "fetched_at": datetime.now(UTC),
        "fetch_status": fetch_status,
        "content_type": "text/plain",
        "content_sha256": content_sha256
        if content_sha256 is not None
        else hashlib.sha256(payload).hexdigest(),
        "artifact_id": artifact_id,
        "license": "CC-BY-4.0",
        "byte_size": len(payload),
        "fetch_profile": dict(FETCH_PROFILE),
        "etag": "fixture-v1",
        "last_modified": "Wed, 01 Jan 2026 00:00:00 GMT",
        "redirect_chain": [SOURCE_URL, FINAL_URL],
        "paywalled": False,
        "error": None,
        "duplicate_of_source_id": None,
        "text": payload.decode("utf-8"),
    }
    if lineage_parent_artifact_id is not None:
        fields["lineage_parent_artifact_id"] = lineage_parent_artifact_id
    if refresh_reason is not None:
        fields["refresh_reason"] = refresh_reason
    return SimpleNamespace(**fields)


def _bundle(source: SimpleNamespace) -> SimpleNamespace:
    fragment = SimpleNamespace(
        snippet_id="snip.src.employment.v1.1",
        source_id=source.source_id,
        url=SOURCE_URL,
        text="employment increased",
        start_char=11,
        end_char=30,
    )
    return SimpleNamespace(
        bundle_id="webkb.scl03.fixture",
        sources=[source],
        snippets=[fragment],
    )


def _fake_result() -> EnrichResultV1:
    return EnrichResultV1(
        knowledge_bundle_ref=KnowledgeBundleRef(
            artifact_id=ArtifactID.model_validate("sha256:" + "b" * 64),
        ),
        bundle_id="bundle.scl03.fixture",
        report=EnrichmentReportV1(
            bundle_artifact_id="sha256:" + "b" * 64,
            bundle_id="bundle.scl03.fixture",
        ),
    )


def _write_snapshot(*, cas: FileSystemCAS, index_path: Path, payload: bytes) -> str:
    cache = UrlFetchCache(index_path=index_path, cas=cas, ttl_seconds=3600)
    result = FetchResult(
        url=SOURCE_URL,
        final_url=FINAL_URL,
        title="Employment policy report",
        text=payload.decode("utf-8"),
        content_type="text/plain",
        fetched_at=datetime.now(UTC),
        status="ok",
        content_sha256=hashlib.sha256(payload).hexdigest(),
        etag="fixture-v1",
        last_modified="Wed, 01 Jan 2026 00:00:00 GMT",
        redirect_chain=[SOURCE_URL, FINAL_URL],
        source_type="government",
    )
    record = cache.put(result, raw_bytes=payload)
    assert record.artifact_id is not None
    return record.artifact_id


def _bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    *,
    cas: FileSystemCAS,
    source: SimpleNamespace,
) -> tuple[SimpleNamespace, dict[str, object]]:
    captured: dict[str, object] = {}

    def _capture_enrich(**kwargs: object) -> EnrichResultV1:
        captured.update(kwargs)
        return _fake_result()

    monkeypatch.setattr("polisyos.scholar.api._enrich_topic", _capture_enrich)
    service = _FixtureSearchService(_bundle(source))
    enrich_topic(
        cas=cas,
        fact_log_root=cas.root / "facts",
        intent=ResearchIntent(domain="labor", topic="employment policy"),
        web_search_service=service,
    )
    hydrated_intent = captured["intent"]
    assert isinstance(hydrated_intent, ResearchIntent)
    assert len(hydrated_intent.seed_sources) == 1
    return hydrated_intent.seed_sources[0], captured


def _assert_gap_without_url_fallback(
    monkeypatch: pytest.MonkeyPatch,
    *,
    cas: FileSystemCAS,
    source: SimpleNamespace,
) -> None:
    called = False

    def _unexpected_enrich(**_kwargs: object) -> EnrichResultV1:
        nonlocal called
        called = True
        raise AssertionError("raw snapshot gap must not fall back to a second URL fetch")

    monkeypatch.setattr("polisyos.scholar.api._enrich_topic", _unexpected_enrich)
    service = _FixtureSearchService(_bundle(source))
    with pytest.raises(Exception) as caught:
        enrich_topic(
            cas=cas,
            fact_log_root=cas.root / "facts",
            intent=ResearchIntent(domain="labor", topic="employment policy"),
            web_search_service=service,
        )

    assert called is False
    assert not isinstance(caught.value, AssertionError)
    message = str(caught.value).lower()
    assert any(
        token in message
        for token in (
            "access",
            "artifact",
            "cas",
            "digest",
            "missing",
            "raw",
            "snapshot",
        )
    )


def test_source_metadata_carries_raw_binding_license_and_fetch_profile() -> None:
    source = SourceMetadata(
        source_id="src.employment.v1",
        url=SOURCE_URL,
        title="Employment policy report",
        domain="agency.gov",
        source_type="government",
        content_type="text/plain",
        content_sha256=SNAPSHOT_V1_SHA256,
        artifact_id="sha256:" + "c" * 64,
        license="CC-BY-4.0",
        fetch_profile=FETCH_PROFILE,
        lineage_parent_artifact_id=None,
    )

    assert source.artifact_id == "sha256:" + "c" * 64
    assert source.content_sha256 == SNAPSHOT_V1_SHA256
    assert source.license == "CC-BY-4.0"
    assert source.fetch_profile == FETCH_PROFILE


def test_web_bootstrap_hands_cached_snapshot_to_enrich_without_second_url_fetch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    raw_ref = _write_snapshot(cas=cas, index_path=tmp_path / "cache.json", payload=SNAPSHOT_V1)
    source = _source(payload=SNAPSHOT_V1, artifact_id=raw_ref)

    seed, captured = _bootstrap(monkeypatch, cas=cas, source=source)

    assert seed.kind == "bytes"
    assert seed.data == SNAPSHOT_V1
    assert seed.source_locator == raw_ref
    assert seed.url is None
    assert seed.mime_hint == "text/plain"
    assert seed.license == "CC-BY-4.0"
    assert seed.props["canonical_url"] == SOURCE_URL
    assert seed.props["final_url"] == FINAL_URL
    assert seed.props["content_sha256"] == SNAPSHOT_V1_SHA256
    assert seed.props["byte_size"] == str(len(SNAPSHOT_V1))
    assert seed.props["fetch_status"] == "cached"
    assert seed.props["fetch_profile"] == json.dumps(FETCH_PROFILE, sort_keys=True)

    # The downstream adapter receives the exact CAS bytes; it cannot reconstruct a document
    # from the search fragment or silently select the live URL branch.
    assert source.text.encode("utf-8") == SNAPSHOT_V1
    assert hashlib.sha256(seed.data).hexdigest() == source.content_sha256
    assert captured["web_evidence_bundle"].snippets[0].text.encode("utf-8") in seed.data


def test_explicit_refresh_hands_off_v2_with_new_lineage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    v1_ref = _write_snapshot(cas=cas, index_path=tmp_path / "cache.json", payload=SNAPSHOT_V1)
    v2_ref = _write_snapshot(cas=cas, index_path=tmp_path / "cache.json", payload=SNAPSHOT_V2)
    source = _source(
        payload=SNAPSHOT_V2,
        artifact_id=v2_ref,
        content_sha256=SNAPSHOT_V2_SHA256,
        lineage_parent_artifact_id=v1_ref,
        refresh_reason="explicit",
        fetch_status="ok",
    )

    seed, _captured = _bootstrap(monkeypatch, cas=cas, source=source)

    assert seed.kind == "bytes"
    assert seed.data == SNAPSHOT_V2
    assert seed.source_locator == v2_ref
    assert seed.source_locator != v1_ref
    assert seed.props["content_sha256"] == SNAPSHOT_V2_SHA256
    assert seed.props["lineage_parent_artifact_id"] == v1_ref
    assert seed.props["refresh_reason"] == "explicit"


def test_missing_raw_snapshot_does_not_reconstruct_from_fragments(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    source = _source(payload=SNAPSHOT_V1, artifact_id=None)

    _assert_gap_without_url_fallback(monkeypatch, cas=cas, source=source)


def test_denied_raw_snapshot_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    raw_ref = _write_snapshot(cas=cas, index_path=tmp_path / "cache.json", payload=SNAPSHOT_V1)
    source = _source(payload=SNAPSHOT_V1, artifact_id=raw_ref)

    def _deny(_artifact_id: object) -> bytes:
        raise PermissionError("fixture access denied")

    monkeypatch.setattr(cas, "get_bytes", _deny)
    _assert_gap_without_url_fallback(monkeypatch, cas=cas, source=source)


def test_mismatched_raw_snapshot_digest_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    v1_ref = _write_snapshot(cas=cas, index_path=tmp_path / "cache.json", payload=SNAPSHOT_V1)
    source = _source(
        payload=SNAPSHOT_V2,
        artifact_id=v1_ref,
        content_sha256=SNAPSHOT_V2_SHA256,
    )

    _assert_gap_without_url_fallback(monkeypatch, cas=cas, source=source)


def test_cache_refresh_keeps_v1_and_exposes_v2_as_distinct_cas_lineage(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    cache = UrlFetchCache(index_path=tmp_path / "cache.json", cas=cas, ttl_seconds=3600)

    def _result(payload: bytes, *, etag: str) -> FetchResult:
        return FetchResult(
            url=SOURCE_URL,
            final_url=FINAL_URL,
            text=payload.decode("utf-8"),
            content_type="text/plain",
            fetched_at=datetime.now(UTC),
            status="ok",
            content_sha256=hashlib.sha256(payload).hexdigest(),
            etag=etag,
            source_type="government",
        )

    first = cache.put(_result(SNAPSHOT_V1, etag="v1"), raw_bytes=SNAPSHOT_V1)
    second = cache.put(_result(SNAPSHOT_V2, etag="v2"), raw_bytes=SNAPSHOT_V2)

    assert first.artifact_id != second.artifact_id
    assert cas.get_bytes(first.artifact_id) == SNAPSHOT_V1
    assert cas.get_bytes(second.artifact_id) == SNAPSHOT_V2
    assert cache.get(SOURCE_URL).artifact_id == second.artifact_id


def test_manual_url_seed_keeps_scl01_raw_transport_and_mime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "polisyos.scholar.discover.transport.urllib.request.build_opener",
        lambda *handlers: _FakeOpener(SNAPSHOT_V1),
    )
    monkeypatch.setattr(
        "polisyos.scholar.search.security.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
    )
    source = SourceSpec(
        kind="url",
        canonical_url=SOURCE_URL,
        license="CC-BY-4.0",
        url=SOURCE_URL,
    )

    result = fetch_url(
        source,
        timeout_s=2,
        user_agent="scl03-fixture",
        max_bytes=4096,
        constraints=SearchConstraints(allowed_domains=["agency.gov"]),
    )

    assert result.raw_bytes == SNAPSHOT_V1
    assert result.mime == "text/plain"
    assert result.doc_source.canonical_url == SOURCE_URL
    assert result.doc_source.license == "CC-BY-4.0"


def test_manual_url_seed_keeps_scl01_private_network_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "polisyos.scholar.search.security.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 80))],
    )
    source = SourceSpec(
        kind="url",
        canonical_url="http://localhost/private",
        license="CC-BY-4.0",
        url="http://localhost/private",
    )

    with pytest.raises(ScholarAcquireError, match="blocked URL fetch"):
        fetch_url(
            source,
            timeout_s=2,
            user_agent="scl03-fixture",
            max_bytes=4096,
        )
