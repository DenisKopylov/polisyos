from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.claims import (
    ChunkContext,
    ClaimExtractOptions,
    extract_claims_from_doc,
    normalize_claims,
)
from polisyos.fabric.claims.backends.explicit_lines_v1 import extract as explicit_lines_extract
from polisyos.fabric.docs import (
    DocChunkOptions,
    DocSourceSpec,
    chunk_doc,
    ingest_doc_bytes,
    normalize_doc,
)
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.world.materialize import materialize_world_duckdb_from_fact_log
from polisyos.ir.kernel.base import ID_PATTERN
from polisyos.ir.world.doc import DocMeta
from polisyos.ir.world.ids import doc_source_id, doc_version_id_from_raw_artifact

_ID_RE = re.compile(ID_PATTERN)


def _artifact_id(seed: str) -> str:
    return f"sha256:{seed * 64}"


def _source_spec() -> DocSourceSpec:
    return DocSourceSpec(
        canonical_url="https://example.com/claims",
        official_id=None,
        source_locator=None,
        license="public",
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        jurisdiction="US",
        language="en",
        source_type="test",
        title="Claims Test Doc",
        publisher="Example Publisher",
    )


def _chunked_doc_meta_id(cas: FileSystemCAS, tmp_path: Path, text: str) -> str:
    ingest = ingest_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=_source_spec(),
        raw_bytes=text.encode("utf-8"),
        mime="text/plain",
        segment_name="doc_ingest",
    )
    normalized = normalize_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=ingest.doc_meta_artifact_id,
        segment_name="doc_normalize",
    )
    chunked = chunk_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=normalized.doc_meta_artifact_id,
        options=DocChunkOptions(
            chunk_size_chars=512,
            overlap_chars=32,
            min_chunk_chars=1,
        ),
        segment_name="doc_chunk",
    )
    return chunked.doc_meta_artifact_id


def test_explicit_lines_backend_extracts_candidates() -> None:
    raw_ref = _artifact_id("a")
    canonical_url = "https://example.com/backend"
    doc_source = doc_source_id(canonical_url=canonical_url, official_id=None)
    doc_version = doc_version_id_from_raw_artifact(raw_artifact_id=raw_ref)
    meta = DocMeta(
        doc_source_id=doc_source,
        doc_version_id=doc_version,
        canonical_url=canonical_url,
        official_id=None,
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        mime="text/plain",
        license="public",
        raw_ref=raw_ref,
    )
    text = "\n".join(
        [
            "claim: policy.tax_rate = 20 [percent]",
            "claim: policy.length (Road network) = 100 [unit.km]",
        ]
    )
    ctx = ChunkContext(
        fragment_id="frag.backend",
        doc_version_id=doc_version,
        offset_start=0,
        offset_end=len(text),
        text_preview="backend preview",
    )

    candidates = explicit_lines_extract(
        ctx=ctx,
        meta=meta,
        normalized_text=text,
        options=ClaimExtractOptions(),
    )

    assert len(candidates) == 2
    assert all(candidate.confidence == Decimal("1") for candidate in candidates)
    assert all(_ID_RE.fullmatch(candidate.predicate_id) for candidate in candidates)
    assert candidates[0].unit_id == "percent"
    assert candidates[1].unit_id == "km"


def test_claims_pipeline_end_to_end_materialization(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))

    text = "\n".join(
        [
            "Policy baseline",
            "claim: policy.tax_rate = 20 [percent]",
            "Details: growth was 3.5 percent in prior year.",
        ]
    )
    doc_meta_artifact_id = _chunked_doc_meta_id(cas, tmp_path, text)

    extracted = extract_claims_from_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=doc_meta_artifact_id,
        extractor_id="explicit_lines_v1",
        segment_name="claims_extract",
    )
    normalized = normalize_claims(
        cas=cas,
        fact_log_root=tmp_path,
        claim_set_artifact_id=extracted.claim_set_artifact_id,
        segment_name="claims_normalize",
    )

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    assert extracted.claim_ids
    assert normalized.claim_ids
    assert db.conn.execute("SELECT COUNT(*) FROM world.claims").fetchone()[0] >= 1
    assert db.conn.execute("SELECT COUNT(*) FROM world.claim_citations").fetchone()[0] >= 1
    assert (
        db.conn.execute(
            "SELECT COUNT(*) FROM world.world_edges WHERE kind = 'claim.cites'"
        ).fetchone()[0]
        >= 1
    )
    assert (
        db.conn.execute(
            """
            SELECT COUNT(*)
            FROM world.world_events
            WHERE event_kind IN ('extract_claims', 'normalize_claims')
            """
        ).fetchone()[0]
        >= 2
    )


def test_claims_pipeline_idempotent_semantics(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))

    text = "\n".join(
        [
            "Idempotency doc",
            "claim: policy.tax_rate = 20 [percent]",
            "claim: policy.length = 100 [km]",
        ]
    )
    doc_meta_artifact_id = _chunked_doc_meta_id(cas, tmp_path, text)

    extracted_1 = extract_claims_from_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=doc_meta_artifact_id,
        extractor_id="explicit_lines_v1",
        segment_name="claims_extract_1",
    )
    normalize_claims(
        cas=cas,
        fact_log_root=tmp_path,
        claim_set_artifact_id=extracted_1.claim_set_artifact_id,
        segment_name="claims_normalize_1",
    )
    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    claims_before = db.conn.execute("SELECT COUNT(*) FROM world.claims").fetchone()[0]
    citations_before = db.conn.execute("SELECT COUNT(*) FROM world.claim_citations").fetchone()[0]
    events_before = db.conn.execute("SELECT COUNT(*) FROM world.world_events").fetchone()[0]

    extracted_2 = extract_claims_from_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=doc_meta_artifact_id,
        extractor_id="explicit_lines_v1",
        segment_name="claims_extract_2",
    )
    normalize_claims(
        cas=cas,
        fact_log_root=tmp_path,
        claim_set_artifact_id=extracted_2.claim_set_artifact_id,
        segment_name="claims_normalize_2",
    )
    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    claims_after = db.conn.execute("SELECT COUNT(*) FROM world.claims").fetchone()[0]
    citations_after = db.conn.execute("SELECT COUNT(*) FROM world.claim_citations").fetchone()[0]
    events_after = db.conn.execute("SELECT COUNT(*) FROM world.world_events").fetchone()[0]

    assert claims_before == claims_after
    assert citations_before == citations_after
    assert events_after > events_before
