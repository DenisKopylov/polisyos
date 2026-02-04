from __future__ import annotations

from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.claims import ClaimExtractOptions, extract_claims_from_doc
from polisyos.fabric.claims.extractor_registry import discover_and_bootstrap_extractors
from polisyos.fabric.docs import DocChunkOptions, DocSourceSpec, chunk_doc, ingest_doc_bytes, normalize_doc


def test_scholar_extractor_discovery_and_run_smoke(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")

    report = discover_and_bootstrap_extractors()
    assert report.errors == []
    assert any(item.startswith("roads.scholar.speed_limit@") for item in report.registered)

    raw = b"Road safety act. The speed limit is 50 km/h in cities."
    ingest = ingest_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=DocSourceSpec(
            source_locator="bytes.roads.speed",
            license="public",
            language="en",
            jurisdiction="UA",
            source_type="test",
        ),
        raw_bytes=raw,
        mime="text/plain",
    )
    normalized = normalize_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=ingest.doc_meta_artifact_id,
    )
    chunked = chunk_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=normalized.doc_meta_artifact_id,
        options=DocChunkOptions(min_chunk_chars=1, chunk_size_chars=200, overlap_chars=1),
    )

    extracted = extract_claims_from_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=chunked.doc_meta_artifact_id,
        extractor_id="roads.scholar.speed_limit@1.0.0",
        options=ClaimExtractOptions(max_chunks=4, max_claims_total=10, max_claims_per_chunk=10),
    )

    assert extracted.claim_set_artifact_id
    assert len(extracted.claim_ids) > 0
