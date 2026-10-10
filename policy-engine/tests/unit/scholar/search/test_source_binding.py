from __future__ import annotations

from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import content_hash
from polisyos.scholar.search.cache import UrlFetchCache
from polisyos.scholar.search.fetcher import _extract_title_and_text, source_id_from_url
from polisyos.scholar.search.models import (
    FetchResult,
    QueryGraph,
    ResearchBrief,
    WebEvidenceBundle,
    WebSearchHit,
)
from polisyos.scholar.search.scoring import build_source_metadata, compress_page_to_snippets
from polisyos.scholar.search.security import sanitize_untrusted_text
from polisyos.scholar.search.source_binding import validate_web_evidence_source_binding
from polisyos.scientist.evidence.verifier import verify_web_evidence_bundle


def _bundle_for_source(
    cas: FileSystemCAS,
    *,
    text: str = "Minimum wage increased earnings for low-wage workers.",
) -> WebEvidenceBundle:
    url = "https://agency.gov/minimum-wage"
    raw_bytes = f"<html><body><p>{text}</p></body></html>".encode()
    title, extracted = _extract_title_and_text(raw_bytes, mime="text/html", final_url=url)
    extracted = sanitize_untrusted_text(extracted)
    digest = content_hash(raw_bytes)
    fetched = FetchResult(
        url=url,
        final_url=url,
        title=title,
        text=extracted,
        content_type="text/html",
        content_sha256=digest,
        byte_size=len(raw_bytes),
        status="ok",
        source_type="government",
    )
    fetched = UrlFetchCache(cas=cas).put(fetched, raw_bytes=raw_bytes).to_fetch_result()
    source_id = source_id_from_url(url, digest)
    hit = WebSearchHit(
        url=url,
        provider="fixture",
        query="minimum wage earnings",
        rank=1,
        source_type="government",
    )
    source = build_source_metadata(source_id=source_id, hit=hit, fetch=fetched)
    snippets = compress_page_to_snippets(
        source_id=source_id,
        url=url,
        text=extracted,
        query_node_id="q1",
        perspective="overview",
        query_terms=["earnings"],
        max_snippets=1,
        window_chars=len(extracted),
    )
    assert len(snippets) == 1
    brief = ResearchBrief(question="minimum wage earnings")
    return WebEvidenceBundle(
        bundle_id="bundle.source-binding",
        brief=brief,
        query_graph=QueryGraph(brief=brief),
        sources=[source],
        snippets=snippets,
    )


def test_source_binding_replays_real_cache_artifact_and_snippet_extraction(
    tmp_path: Path,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    bundle = _bundle_for_source(cas)

    result = validate_web_evidence_source_binding(bundle, cas=cas)

    assert result.passed is True
    assert result.violations == ()
    assert result.source_text_by_id[bundle.sources[0].source_id].startswith("Minimum wage")
    assert bundle.sources[0].raw_artifact_ref is not None
    assert bundle.sources[0].artifact_id == str(bundle.sources[0].raw_artifact_ref.artifact_id)
    assert verify_web_evidence_bundle(bundle, cas=cas).passed is True


def test_source_binding_rejects_plausible_but_invented_snippet_and_shifted_span(
    tmp_path: Path,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    bundle = _bundle_for_source(cas)
    snippet = bundle.snippets[0]

    invented = bundle.model_copy(
        update={"snippets": [snippet.model_copy(update={"text": "invented quote"})]}
    )
    shifted = bundle.model_copy(
        update={
            "snippets": [
                snippet.model_copy(
                    update={
                        "start_char": snippet.start_char + 1,
                    }
                )
            ]
        }
    )

    assert "span_text_mismatch:snip." in ";".join(
        validate_web_evidence_source_binding(invented, cas=cas).violations
    )
    assert "span_text_mismatch:snip." in ";".join(
        validate_web_evidence_source_binding(shifted, cas=cas).violations
    )
    assert verify_web_evidence_bundle(invented, cas=cas).passed is False


def test_source_binding_covers_every_snippet_in_the_bundle(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    bundle = _bundle_for_source(cas)
    source_text = validate_web_evidence_source_binding(bundle, cas=cas).source_text_by_id[
        bundle.sources[0].source_id
    ]
    second_text = source_text[:12]
    second_snippet = bundle.snippets[0].model_copy(
        update={
            "snippet_id": "snip.second",
            "text": second_text,
            "start_char": 0,
            "end_char": len(second_text),
        }
    )
    two_snippets = bundle.model_copy(update={"snippets": [bundle.snippets[0], second_snippet]})
    second_invented = second_snippet.model_copy(update={"text": "invented text"})
    tampered = two_snippets.model_copy(update={"snippets": [bundle.snippets[0], second_invented]})

    assert validate_web_evidence_source_binding(two_snippets, cas=cas).passed is True
    result = validate_web_evidence_source_binding(tampered, cas=cas)
    assert result.passed is False
    assert "span_text_mismatch:snip.second" in result.violations


def test_source_binding_fails_closed_without_resolvable_raw_snapshot(tmp_path: Path) -> None:
    source_cas = FileSystemCAS(tmp_path / "source-cas")
    bundle = _bundle_for_source(source_cas)

    without_cas = validate_web_evidence_source_binding(bundle, cas=None)
    unavailable = validate_web_evidence_source_binding(
        bundle,
        cas=FileSystemCAS(tmp_path / "empty-cas"),
    )

    assert without_cas.passed is False
    assert any("source_cas_unavailable" in item for item in without_cas.violations)
    assert unavailable.passed is False
    assert any("source_artifact_unavailable" in item for item in unavailable.violations)


def test_source_binding_rejects_raw_artifact_with_wrong_manifest_contract(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions

    cas = FileSystemCAS(tmp_path / "cas")
    raw_bytes = b"<html><body>Minimum wage earnings</body></html>"
    ref = cas.put_bytes(
        raw_bytes,
        ArtifactWriteOptions(
            kind="unrelated.payload",
            media_type="text/html",
            schema=SchemaInfo(name="unrelated.payload", version="1.0"),
            producer=ProducerInfo(component="polisyos.scholar.search.cache", version="1.0.0"),
        ),
    )
    bundle = _bundle_for_source(cas)
    source = bundle.sources[0].model_copy(
        update={
            "artifact_id": str(ref.artifact_id),
            "raw_artifact_ref": ref,
            "content_sha256": content_hash(raw_bytes),
            "byte_size": len(raw_bytes),
        }
    )
    mismatched = bundle.model_copy(update={"sources": [source]})

    result = validate_web_evidence_source_binding(mismatched, cas=cas)

    assert result.passed is False
    assert any("source_manifest_contract_mismatch" in item for item in result.violations)


def test_source_binding_honors_selected_nondefault_manifest_view(tmp_path: Path) -> None:
    from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions

    cas = FileSystemCAS(tmp_path / "cas")
    bundle = _bundle_for_source(cas)
    source = bundle.sources[0]
    assert source.raw_artifact_ref is not None
    raw_bytes = cas.get_bytes(source.raw_artifact_ref)
    alternate_ref = cas.put_bytes(
        raw_bytes,
        ArtifactWriteOptions(
            kind="unrelated.payload",
            media_type="text/html",
            schema=SchemaInfo(name="unrelated.payload", version="1.0"),
            producer=ProducerInfo(component="polisyos.scholar.search.cache", version="1.0.0"),
        ),
    )
    assert alternate_ref.manifest_profile_sha256 is not None
    selected_alternate = bundle.model_copy(
        update={
            "sources": [
                source.model_copy(
                    update={
                        "raw_artifact_ref": alternate_ref,
                        "artifact_id": str(alternate_ref.artifact_id),
                    }
                )
            ]
        }
    )

    result = validate_web_evidence_source_binding(selected_alternate, cas=cas)

    assert result.passed is False
    assert any("source_manifest_contract_mismatch" in item for item in result.violations)


def test_source_binding_legacy_id_uses_only_the_default_manifest_view(
    tmp_path: Path,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    bundle = _bundle_for_source(cas)
    source = bundle.sources[0]
    legacy_source = source.model_copy(update={"raw_artifact_ref": None})
    legacy_bundle = bundle.model_copy(update={"sources": [legacy_source]})

    result = validate_web_evidence_source_binding(legacy_bundle, cas=cas)

    assert result.passed is True
    assert f"source_artifact_profileless_default:{source.source_id}" in result.warnings
