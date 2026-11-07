"""Test-first witnesses for SCL-03 raw-snapshot handoff into Scholar enrich."""

from __future__ import annotations

import hashlib
import json
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.scholar import (
    EnrichmentReportV1,
    EnrichResultV1,
    KnowledgeBundleRef,
    ResearchIntent,
    SourceSpec,
)
from polisyos.scholar.api import (
    _seed_sources_from_web_bundle,
    _source_spec_from_snapshot,
    enrich_topic,
)
from polisyos.scholar.discover.http_fetch import fetch_url
from polisyos.scholar.discover.manual import normalize_seed_sources
from polisyos.scholar.orchestrator.errors import ScholarAcquireError
from polisyos.scholar.search.cache import UrlFetchCache
from polisyos.scholar.search.fetcher import fetch_open_page, source_id_from_url
from polisyos.scholar.search.models import (
    FetchResult,
    QueryGraph,
    ResearchBrief,
    SearchConstraints,
    SourceMetadata,
    SourceSnippet,
    WebEvidenceBundle,
    WebSearchHit,
)
from polisyos.scholar.search.scoring import build_source_metadata
from polisyos.scholar.search.service import ScholarDeepSearchService

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

    def __init__(self, bundle: WebEvidenceBundle, *, cas: FileSystemCAS) -> None:
        self._bundle = bundle
        self._persister = ScholarDeepSearchService(cas=cas, cache=UrlFetchCache(cas=cas))
        self.deep_search_calls = 0

    async def deep_search(self, **_kwargs: object) -> WebEvidenceBundle:
        self.deep_search_calls += 1
        return self._bundle

    def persist_bundle(self, bundle: WebEvidenceBundle) -> ArtifactRef:
        return self._persister.persist_bundle(bundle)


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
        assert request.full_url == SOURCE_URL
        assert timeout == 2
        return _FakeResponse(self._body)


def _source(fetch: FetchResult) -> SourceMetadata:
    """Build metadata from the exact fetch result mutated by the CAS cache."""
    hit = WebSearchHit(
        url=fetch.url,
        title=fetch.title,
        provider="fixture",
        query="employment policy",
        rank=1,
        source_type=fetch.source_type,
    )
    return build_source_metadata(
        source_id=source_id_from_url(fetch.final_url, fetch.content_sha256),
        hit=hit,
        fetch=fetch,
    )


def _bundle(source: SourceMetadata) -> WebEvidenceBundle:
    brief = ResearchBrief(question="employment policy")
    fragment = SourceSnippet(
        snippet_id=f"snip.{source.source_id}.1",
        source_id=source.source_id,
        url=source.url,
        query_node_id="q1",
        perspective="overview",
        text="employment",
        start_char=11,
        end_char=21,
    )
    return WebEvidenceBundle(
        bundle_id="webkb.scl03.fixture",
        brief=brief,
        query_graph=QueryGraph(brief=brief),
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


def _write_snapshot(
    *,
    cas: FileSystemCAS,
    index_path: Path,
    payload: bytes,
    status: Literal["ok", "cached"] = "cached",
    lineage_parent_artifact_id: str | None = None,
    refresh_reason: str | None = None,
) -> FetchResult:
    cache = UrlFetchCache(index_path=index_path, cas=cas, ttl_seconds=3600)
    result = FetchResult(
        url=SOURCE_URL,
        final_url=FINAL_URL,
        title="Employment policy report",
        text=payload.decode("utf-8"),
        content_type="text/plain",
        fetched_at=datetime.now(UTC),
        status=status,
        content_sha256=hashlib.sha256(payload).hexdigest(),
        etag="fixture-v1",
        last_modified="Wed, 01 Jan 2026 00:00:00 GMT",
        redirect_chain=[SOURCE_URL, FINAL_URL],
        source_type="government",
        license="CC-BY-4.0",
        fetch_profile=dict(FETCH_PROFILE),
        lineage_parent_artifact_id=lineage_parent_artifact_id,
        refresh_reason=refresh_reason,
    )
    cache.put(result, raw_bytes=payload)
    assert result.artifact_id is not None
    assert result.raw_artifact_ref is not None
    return result


def _bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    *,
    cas: FileSystemCAS,
    source: SourceMetadata,
) -> tuple[SourceSpec, dict[str, object]]:
    captured: dict[str, object] = {}

    def _capture_enrich(**kwargs: object) -> EnrichResultV1:
        captured.update(kwargs)
        return _fake_result()

    monkeypatch.setattr("polisyos.scholar.api._enrich_topic", _capture_enrich)
    service = _FixtureSearchService(_bundle(source), cas=cas)
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


def _assert_redirected_source_identity(
    source: SourceMetadata,
    payload_sha256: str,
) -> str:
    """Pin source identity to final URL for this redirected fetch."""
    expected_source_id = source_id_from_url(FINAL_URL, payload_sha256)
    requested_url_source_id = source_id_from_url(SOURCE_URL, payload_sha256)

    assert FINAL_URL != SOURCE_URL
    assert expected_source_id != requested_url_source_id
    assert source.source_id == expected_source_id
    return expected_source_id


def _assert_persisted_bundle_source_identity(
    bundle: WebEvidenceBundle,
    cas: FileSystemCAS,
    bundle_artifact_id: str,
    expected_source_id: str,
) -> None:
    """Check source identity joins in memory and in the persisted CAS bundle."""
    assert len(bundle.sources) == 1
    assert len(bundle.snippets) == 1
    assert bundle.sources[0].source_id == expected_source_id
    assert bundle.snippets[0].source_id == expected_source_id

    persisted_bundle = json.loads(cas.get_bytes(bundle_artifact_id))
    assert persisted_bundle["bundle_id"] == bundle.bundle_id
    assert persisted_bundle["sources"][0]["source_id"] == expected_source_id
    assert persisted_bundle["snippets"][0]["source_id"] == expected_source_id


def _assert_gap_without_url_fallback(
    monkeypatch: pytest.MonkeyPatch,
    *,
    cas: FileSystemCAS,
    source: SourceMetadata,
    expected_violation: Literal["source_artifact_unavailable", "source_artifact_digest_mismatch"],
) -> None:
    called = False
    assert source.content_sha256 is not None
    _assert_redirected_source_identity(source, source.content_sha256)
    assert source.license == "CC-BY-4.0"
    assert source.fetch_profile == FETCH_PROFILE
    bundle = _bundle(source)
    assert len(bundle.sources) == 1
    assert len(bundle.snippets) == 1
    assert bundle.snippets[0].source_id == bundle.sources[0].source_id

    def _unexpected_enrich(**_kwargs: object) -> EnrichResultV1:
        nonlocal called
        called = True
        raise AssertionError("raw snapshot gap must not fall back to a second URL fetch")

    monkeypatch.setattr("polisyos.scholar.api._enrich_topic", _unexpected_enrich)
    service = _FixtureSearchService(bundle, cas=cas)
    with pytest.raises(ScholarAcquireError) as caught:
        enrich_topic(
            cas=cas,
            fact_log_root=cas.root / "facts",
            intent=ResearchIntent(domain="labor", topic="employment policy"),
            web_search_service=service,
        )

    assert called is False
    violations = caught.value.details.get("violations", ())
    assert isinstance(violations, list)
    assert any(
        isinstance(violation, str) and violation.startswith(f"{expected_violation}:")
        for violation in violations
    )


def test_source_metadata_carries_raw_binding_license_and_fetch_profile(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    fetch = _write_snapshot(
        cas=cas,
        index_path=tmp_path / "cache.json",
        payload=SNAPSHOT_V1,
    )
    source = _source(fetch)
    _assert_redirected_source_identity(source, SNAPSHOT_V1_SHA256)

    assert fetch.raw_artifact_ref is not None
    assert source.raw_artifact_ref == fetch.raw_artifact_ref
    assert source.artifact_id == str(fetch.raw_artifact_ref.artifact_id)
    assert source.content_sha256 == SNAPSHOT_V1_SHA256
    assert source.license == "CC-BY-4.0"
    assert source.fetch_profile == FETCH_PROFILE


@pytest.mark.parametrize("deny_selected", [False, True])
def test_normalized_snapshot_rechecks_selected_view_before_docs_publication(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    deny_selected: bool,
) -> None:
    """A selected view survives discover and is reread by the real acquire stage."""
    from polisyos.core.artifacts import ArtifactWriteOptions, ProducerInfo, SchemaInfo

    cas = FileSystemCAS(tmp_path / "cas")
    # Establish a different default manifest for exactly the same bytes. An ID-only
    # read cannot establish that the selected Scholar view remains available.
    default_ref = cas.put_bytes(
        SNAPSHOT_V1,
        ArtifactWriteOptions(
            kind="fixture.manual_payload",
            media_type="text/plain",
            schema=SchemaInfo(name="fixture.manual_payload", version="1.0"),
            producer=ProducerInfo(component="fixture.manual", version="1.0.0"),
        ),
    )
    fetched = _write_snapshot(cas=cas, index_path=tmp_path / "cache.json", payload=SNAPSHOT_V1)
    selected_ref = fetched.raw_artifact_ref
    assert selected_ref is not None
    assert default_ref.artifact_id == selected_ref.artifact_id
    assert default_ref.manifest_profile_sha256 != selected_ref.manifest_profile_sha256
    seed = _source_spec_from_snapshot(_source(fetched), cas=cas)
    normalized = normalize_seed_sources([seed])[0]
    assert normalized.raw_artifact_ref == selected_ref
    assert normalized.props == seed.props
    assert normalized.data == seed.data

    original_get_bytes = cas.get_bytes
    selected_reads: list[ArtifactRef] = []

    def _read(reference: object, **kwargs: object) -> bytes:
        if reference == selected_ref:
            selected_reads.append(reference)
            if deny_selected:
                raise PermissionError("selected view withdrawn after API preflight")
        return original_get_bytes(reference, **kwargs)

    monkeypatch.setattr(cas, "get_bytes", _read)
    intent = ResearchIntent(domain="labor", topic="selected source", seed_sources=[seed])
    if deny_selected:
        with pytest.raises(ScholarAcquireError, match="selected raw artifact view is unavailable"):
            enrich_topic(cas=cas, fact_log_root=tmp_path / "facts", intent=intent)
        assert selected_reads == [selected_ref]
        assert all(
            cas.get_manifest(item).kind != "fabric.world.doc_meta"
            for item in cas.iter_artifact_ids()
        )
    else:
        result = enrich_topic(cas=cas, fact_log_root=tmp_path / "facts", intent=intent)
        assert selected_reads == [selected_ref]
        assert result.report.docs["count"] == 1


@pytest.mark.parametrize("corruption", ["payload", "digest", "size", "selected_profile"])
def test_normalized_snapshot_mismatch_refusal_matches_direct_acquisition(
    tmp_path: Path, corruption: str
) -> None:
    """The same selected-source refusal reaches direct and whole native routes."""
    from polisyos.scholar.orchestrator.enrich import _acquire_bytes

    cas = FileSystemCAS(tmp_path / "cas")
    fetched = _write_snapshot(cas=cas, index_path=tmp_path / "cache.json", payload=SNAPSHOT_V1)
    seed = _source_spec_from_snapshot(_source(fetched), cas=cas)
    updates: dict[str, object] = {}
    if corruption == "payload":
        updates["data"] = SNAPSHOT_V2
    elif corruption == "digest":
        updates["props"] = {**seed.props, "content_sha256": SNAPSHOT_V2_SHA256}
    elif corruption == "size":
        updates["props"] = {**seed.props, "byte_size": str(len(SNAPSHOT_V1) + 1)}
    else:
        assert seed.raw_artifact_ref is not None
        updates["raw_artifact_ref"] = seed.raw_artifact_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "e" * 64}
        )
    invalid = seed.model_copy(update=updates)
    normalized = normalize_seed_sources([invalid])[0]
    with pytest.raises(ScholarAcquireError) as direct:
        _acquire_bytes(normalized, cas=cas, max_bytes=4096)
    with pytest.raises(ScholarAcquireError) as whole:
        enrich_topic(
            cas=cas,
            fact_log_root=tmp_path / "facts",
            intent=ResearchIntent(domain="labor", topic="invalid snapshot", seed_sources=[invalid]),
        )
    assert str(whole.value) == str(direct.value)
    assert whole.value.details == direct.value.details
    assert all(
        cas.get_manifest(item).kind != "fabric.world.doc_meta" for item in cas.iter_artifact_ids()
    )


@pytest.mark.parametrize("cache_backed", [False, True])
@pytest.mark.parametrize(("timeout_s", "user_agent"), [(3.0, "scl03-a/1"), (4.0, "scl03-b/2")])
def test_actual_fetch_profile_survives_metadata_and_seed_handoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cache_backed: bool,
    timeout_s: float,
    user_agent: str,
) -> None:
    """Actual producer arguments, not a synthetic FetchResult, bind provenance."""
    import asyncio

    cas = FileSystemCAS(tmp_path / "cas")
    cache_path = tmp_path / "cache.json"
    cache = UrlFetchCache(index_path=cache_path, cas=cas)
    constraints = SearchConstraints(
        allowed_domains=["agency.gov"],
        allowed_content_types=["text/plain"],
        locale="en-GB",
    )
    calls: list[tuple[object, ...]] = []

    def _transport(*args: object) -> tuple[bytes, str, str, dict[str, str], list[str]]:
        calls.append(args)
        return SNAPSHOT_V1, FINAL_URL, "text/plain", {}, [SOURCE_URL, FINAL_URL]

    monkeypatch.setattr("polisyos.scholar.search.fetcher._fetch_url_bytes_sync", _transport)
    monkeypatch.setattr(
        "polisyos.scholar.search.security.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443))
        ],
    )
    fetched = asyncio.run(
        fetch_open_page(
            SOURCE_URL,
            constraints=constraints,
            cache=cache if cache_backed else None,
            timeout_s=timeout_s,
            user_agent=user_agent,
            max_bytes=4096,
        )
    )
    assert len(calls) == 1
    assert calls[0][0] == SOURCE_URL
    assert calls[0][1] == constraints
    assert calls[0][3:] == (timeout_s, user_agent, 4096)
    expected = {
        "profile_version": "1.0",
        "transport": "polisyos.scholar.discover.transport",
        "transport_version": "1.0",
        "constraints": constraints.model_dump(mode="json"),
        "max_bytes": 4096,
        "timeout_s": timeout_s,
        "user_agent": user_agent,
    }
    assert fetched.fetch_profile == expected
    assert fetched.byte_size == len(SNAPSHOT_V1)
    if not cache_backed:
        # Persist the real result solely to exercise the ordinary metadata handoff.
        # The producer assertions above already cover the no-cache route.
        cache.put(fetched, raw_bytes=SNAPSHOT_V1)
    restored_cache = UrlFetchCache(index_path=cache_path, cas=cas)
    restored = restored_cache.get(SOURCE_URL)
    assert restored is not None
    assert restored.fetch_profile == expected
    source = _source(restored.to_fetch_result())
    seed = _seed_sources_from_web_bundle(
        _bundle(source), cas=cas, cache=restored_cache, max_docs=1
    )[0]
    assert seed.raw_artifact_ref == fetched.raw_artifact_ref
    assert json.loads(seed.props["fetch_profile"]) == expected
    assert seed.props["fetch_profile_status"] == "recorded"
    assert seed.props["byte_size"] == str(len(SNAPSHOT_V1))


@pytest.mark.parametrize("same_bytes", [False, True])
def test_historical_snapshot_does_not_inherit_later_cache_provenance(
    tmp_path: Path,
    same_bytes: bool,
) -> None:
    """Neither same URL nor same bytes establish the same acquisition facts."""
    from datetime import timedelta

    cas = FileSystemCAS(tmp_path / "cas")
    index = tmp_path / "cache.json"
    v1 = _write_snapshot(cas=cas, index_path=index, payload=SNAPSHOT_V1)
    historical = _source(v1).model_copy(
        update={
            "fetch_profile": {},
            "redirect_chain": [],
            "final_url": None,
            "etag": None,
            "last_modified": None,
            "lineage_parent_artifact_id": None,
            "refresh_reason": None,
            "license": "public-web",
        }
    )
    cache = UrlFetchCache(index_path=index, cas=cas)
    later = FetchResult(
        url=SOURCE_URL,
        final_url="https://agency.gov/later-acquisition",
        text=(SNAPSHOT_V1 if same_bytes else SNAPSHOT_V2).decode(),
        content_type="text/plain",
        fetched_at=v1.fetched_at + timedelta(seconds=1),
        status="ok",
        etag="later-only",
        redirect_chain=[SOURCE_URL, "https://agency.gov/later-acquisition"],
        content_sha256=hashlib.sha256(SNAPSHOT_V1 if same_bytes else SNAPSHOT_V2).hexdigest(),
        fetch_profile={"later-only": "not-historical"},
        license="CC0",
    )
    cache.put(later, raw_bytes=SNAPSHOT_V1 if same_bytes else SNAPSHOT_V2)
    seed = _source_spec_from_snapshot(historical, cas=cas, cache=cache)
    assert seed.data == SNAPSHOT_V1
    assert seed.raw_artifact_ref == v1.raw_artifact_ref
    assert json.loads(seed.props["fetch_profile"]) == {}
    assert seed.props["fetch_profile_status"] == "unknown"
    assert json.loads(seed.props["redirect_chain"]) == []
    assert seed.props["final_url"] == SOURCE_URL
    assert seed.license == "public-web"
    assert "etag" not in seed.props
    assert "last_modified" not in seed.props
    assert "lineage_parent_artifact_id" not in seed.props
    assert "refresh_reason" not in seed.props


def test_same_selected_acquisition_can_supply_saved_profile(tmp_path: Path) -> None:
    """Exact selected identity and acquisition keep legitimate cache fallback."""
    cas = FileSystemCAS(tmp_path / "cas")
    index = tmp_path / "cache.json"
    fetched = _write_snapshot(cas=cas, index_path=index, payload=SNAPSHOT_V1)
    source = _source(fetched).model_copy(update={"fetch_profile": {}})
    seed = _source_spec_from_snapshot(
        source, cas=cas, cache=UrlFetchCache(index_path=index, cas=cas)
    )
    assert json.loads(seed.props["fetch_profile"]) == FETCH_PROFILE


@pytest.mark.parametrize(("budget", "count"), [({"max_docs": 1}, 1), ({"max_bytes_total": 1}, 0)])
def test_real_manual_bytes_enrichment_preserves_document_and_total_byte_limits(
    tmp_path: Path, budget: dict[str, int], count: int
) -> None:
    """Manual bytes remain useful without CAS references, under actual budgets."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.contracts.scholar import BudgetsV1, KnowledgeBundlePayloadV1

    cas = FileSystemCAS(tmp_path / "cas")
    intent = ResearchIntent(
        domain="labor",
        topic="manual source limits",
        seed_sources=[
            SourceSpec(
                kind="bytes",
                data=payload,
                license="CC-BY-4.0",
                mime_hint="text/plain",
                source_locator=f"bytes.sha256_{hashlib.sha256(payload).hexdigest()}",
            )
            for payload in (SNAPSHOT_V1, SNAPSHOT_V2)
        ],
        budgets_v1=BudgetsV1(**budget),
    )
    result = enrich_topic(cas=cas, fact_log_root=tmp_path / "facts", intent=intent)
    fresh = FileSystemCAS(cas.root)
    knowledge = KnowledgeBundlePayloadV1.model_validate(
        load_core_json_artifact(fresh, result.knowledge_bundle_ref)
    )
    assert result.report.docs["count"] == count
    assert len(knowledge.doc_version_ids) == count
    if count == 0:
        assert result.report.notes == ["stopped:max_bytes_total"]


def test_physically_corrupt_snapshot_is_refused_without_losing_an_independent_document(
    tmp_path: Path,
) -> None:
    """Raw corruption cannot become knowledge or trigger a hidden network fallback."""
    from polisyos.core.artifacts import load_core_json_artifact

    cas = FileSystemCAS(tmp_path / "cas")
    independent = enrich_topic(
        cas=cas,
        fact_log_root=tmp_path / "independent-facts",
        intent=ResearchIntent(
            domain="labor",
            topic="independent source",
            seed_sources=[
                SourceSpec(
                    kind="bytes",
                    data=b"Independent useful document.",
                    source_locator="manual.independent",
                    license="CC-BY-4.0",
                    mime_hint="text/plain",
                )
            ],
        ),
    )
    before = load_core_json_artifact(cas, independent.knowledge_bundle_ref)
    fetched = _write_snapshot(cas=cas, index_path=tmp_path / "cache.json", payload=SNAPSHOT_V1)
    selected_ref = fetched.raw_artifact_ref
    assert selected_ref is not None
    service = _FixtureSearchService(_bundle(_source(fetched)), cas=cas)
    blob_path, _ = cas._paths(selected_ref.artifact_id)
    blob_path.write_bytes(b"corrupt raw snapshot")
    with pytest.raises(ScholarAcquireError, match="source-content verification") as caught:
        enrich_topic(
            cas=cas,
            fact_log_root=tmp_path / "invalid-facts",
            intent=ResearchIntent(domain="labor", topic="employment policy"),
            web_search_service=service,
        )
    assert any("source_artifact_unavailable" in item for item in caught.value.details["violations"])
    fresh = FileSystemCAS(cas.root)
    assert load_core_json_artifact(fresh, independent.knowledge_bundle_ref) == before


def test_web_bootstrap_hands_cached_snapshot_to_enrich_without_second_url_fetch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    fetch = _write_snapshot(cas=cas, index_path=tmp_path / "cache.json", payload=SNAPSHOT_V1)
    source = _source(fetch)

    seed, captured = _bootstrap(monkeypatch, cas=cas, source=source)
    expected_source_id = _assert_redirected_source_identity(source, SNAPSHOT_V1_SHA256)
    bundle = captured["web_evidence_bundle"]
    bundle_artifact_id = captured["web_evidence_artifact_id"]
    assert isinstance(bundle, WebEvidenceBundle)
    assert isinstance(bundle_artifact_id, str)
    _assert_persisted_bundle_source_identity(bundle, cas, bundle_artifact_id, expected_source_id)

    assert seed.kind == "bytes"
    assert seed.data == SNAPSHOT_V1
    assert seed.source_locator == str(fetch.raw_artifact_ref.artifact_id)
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
    assert source.raw_artifact_ref is not None
    assert cas.get_bytes(source.raw_artifact_ref) == SNAPSHOT_V1
    assert hashlib.sha256(seed.data).hexdigest() == source.content_sha256
    assert bundle.snippets[0].text.encode("utf-8") in seed.data
    assert cas.get_manifest(bundle_artifact_id).kind == "scholar.web_evidence_bundle"


def test_explicit_refresh_hands_off_v2_with_new_lineage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    v1_fetch = _write_snapshot(
        cas=cas,
        index_path=tmp_path / "cache.json",
        payload=SNAPSHOT_V1,
    )
    assert v1_fetch.artifact_id is not None
    assert v1_fetch.raw_artifact_ref is not None
    v2_fetch = _write_snapshot(
        cas=cas,
        index_path=tmp_path / "cache.json",
        payload=SNAPSHOT_V2,
        status="ok",
        lineage_parent_artifact_id=v1_fetch.artifact_id,
        refresh_reason="explicit",
    )
    assert v2_fetch.artifact_id is not None
    assert v2_fetch.raw_artifact_ref is not None
    source = _source(v2_fetch)

    seed, captured = _bootstrap(monkeypatch, cas=cas, source=source)
    expected_source_id = _assert_redirected_source_identity(source, SNAPSHOT_V2_SHA256)
    bundle = captured["web_evidence_bundle"]
    bundle_artifact_id = captured["web_evidence_artifact_id"]
    assert isinstance(bundle, WebEvidenceBundle)
    assert isinstance(bundle_artifact_id, str)
    _assert_persisted_bundle_source_identity(bundle, cas, bundle_artifact_id, expected_source_id)

    assert seed.kind == "bytes"
    assert seed.data == SNAPSHOT_V2
    assert seed.source_locator == str(v2_fetch.raw_artifact_ref.artifact_id)
    assert seed.source_locator != str(v1_fetch.raw_artifact_ref.artifact_id)
    assert seed.props["content_sha256"] == SNAPSHOT_V2_SHA256
    assert seed.props["lineage_parent_artifact_id"] == v1_fetch.artifact_id
    assert seed.props["refresh_reason"] == "explicit"


def test_missing_raw_snapshot_does_not_reconstruct_from_fragments(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    missing_fetch = FetchResult(
        url=SOURCE_URL,
        final_url=FINAL_URL,
        title="Employment policy report",
        text=SNAPSHOT_V1.decode("utf-8"),
        content_type="text/plain",
        fetched_at=datetime.now(UTC),
        status="cached",
        content_sha256=SNAPSHOT_V1_SHA256,
        license="CC-BY-4.0",
        fetch_profile=dict(FETCH_PROFILE),
        source_type="government",
    )
    source = _source(missing_fetch)

    _assert_gap_without_url_fallback(
        monkeypatch,
        cas=cas,
        source=source,
        expected_violation="source_artifact_unavailable",
    )


def test_denied_raw_snapshot_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    fetch = _write_snapshot(cas=cas, index_path=tmp_path / "cache.json", payload=SNAPSHOT_V1)
    source = _source(fetch)

    def _deny(_artifact_id: object) -> bytes:
        raise PermissionError("fixture access denied")

    monkeypatch.setattr(cas, "get_bytes", _deny)
    _assert_gap_without_url_fallback(
        monkeypatch,
        cas=cas,
        source=source,
        expected_violation="source_artifact_unavailable",
    )


def test_mismatched_raw_snapshot_digest_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    fetch = _write_snapshot(cas=cas, index_path=tmp_path / "cache.json", payload=SNAPSHOT_V1)
    mismatched_fetch = fetch.model_copy(update={"content_sha256": SNAPSHOT_V2_SHA256})
    source = _source(mismatched_fetch)

    _assert_gap_without_url_fallback(
        monkeypatch,
        cas=cas,
        source=source,
        expected_violation="source_artifact_digest_mismatch",
    )


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


def test_manual_url_seed_keeps_scl01_raw_transport_and_mime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "polisyos.scholar.discover.transport.urllib.request.build_opener",
        lambda *handlers: _FakeOpener(SNAPSHOT_V1),
    )
    monkeypatch.setattr(
        "polisyos.scholar.search.security.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443))
        ],
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
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 80))
        ],
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
