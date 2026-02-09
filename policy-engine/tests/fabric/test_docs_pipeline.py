from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.world.materialize import materialize_world_duckdb_from_fact_log
from polisyos.ir.world.abi import EdgeKind

from polisyos.fabric.docs import (
    DocChunkOptions,
    DocNormalizeOptions,
    DocSourceSpec,
    DocStructureOptions,
    chunk_doc,
    ingest_doc_bytes,
    normalize_doc,
    structure_doc,
)


def _load_json_artifact(cas: FileSystemCAS, artifact_id: str) -> dict:
    data = cas.get_bytes(ArtifactID.model_validate(artifact_id))
    payload = json.loads(data)
    assert isinstance(payload, dict)
    return payload


def _source_spec(retrieved_at: datetime) -> DocSourceSpec:
    return DocSourceSpec(
        canonical_url="https://example.com/doc",
        official_id=None,
        source_locator=None,
        license="public",
        retrieved_at=retrieved_at,
        jurisdiction="US",
        language="en",
        source_type="test",
        title="Example Doc",
        publisher="Example Publisher",
    )


def test_ingest_same_bytes_same_doc_version_id(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    retrieved_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    source = _source_spec(retrieved_at)

    raw_bytes = b"Hello, world!"

    res1 = ingest_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=source,
        raw_bytes=raw_bytes,
        mime="text/plain",
        segment_name="doc_ingest_1",
    )
    res2 = ingest_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=source,
        raw_bytes=raw_bytes,
        mime="text/plain",
        segment_name="doc_ingest_2",
    )

    assert res1.doc_version_id == res2.doc_version_id
    assert res1.raw_ref == res2.raw_ref


def test_structure_offsets_are_valid(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    retrieved_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    source = _source_spec(retrieved_at)

    text = "1. INTRODUCTION\nThis is a test document.\n\n2. SCOPE\nMore text."
    ingest = ingest_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=source,
        raw_bytes=text.encode("utf-8"),
        mime="text/plain",
        segment_name="doc_ingest",
    )
    normalized = normalize_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=ingest.doc_meta_artifact_id,
        options=DocNormalizeOptions(),
        segment_name="doc_normalize",
    )
    structured = structure_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=normalized.doc_meta_artifact_id,
        options=DocStructureOptions(),
        segment_name="doc_structure",
    )

    normalized_payload = _load_json_artifact(cas, normalized.normalized_ref)
    normalized_text = normalized_payload["text"]
    structure_payload = _load_json_artifact(cas, structured.structure_ref)

    anchors = structure_payload["anchors"]
    assert anchors
    text_len = len(normalized_text)
    for anchor in anchors:
        start = anchor["offset_start"]
        end = anchor["offset_end"]
        assert 0 <= start <= end <= text_len


def test_chunking_is_deterministic(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    retrieved_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    source = _source_spec(retrieved_at)

    text = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 200).strip()
    ingest = ingest_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=source,
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

    chunk1 = chunk_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=normalized.doc_meta_artifact_id,
        options=DocChunkOptions(),
        segment_name="doc_chunk_1",
    )
    chunk2 = chunk_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=normalized.doc_meta_artifact_id,
        options=DocChunkOptions(),
        segment_name="doc_chunk_2",
    )

    assert chunk1.chunk_fragment_ids == chunk2.chunk_fragment_ids


def test_docs_pipeline_end_to_end_materialization(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))

    retrieved_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    source = _source_spec(retrieved_at)
    text = "Policy Document\n\n1. SCOPE\nThis is a sample policy text."

    ingest = ingest_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=source,
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
    structured = structure_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=normalized.doc_meta_artifact_id,
        segment_name="doc_structure",
    )
    chunked = chunk_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=structured.doc_meta_artifact_id,
        segment_name="doc_chunk",
    )

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    assert db.conn.execute("SELECT COUNT(*) FROM world.doc_sources").fetchone()[0] == 1
    assert db.conn.execute("SELECT COUNT(*) FROM world.doc_versions").fetchone()[0] == 1
    assert db.conn.execute("SELECT COUNT(*) FROM world.doc_fragments").fetchone()[0] > 0

    row = db.conn.execute(
        "SELECT normalized_ref, structure_ref, chunks_ref FROM world.doc_versions"
    ).fetchone()
    assert row is not None
    assert all(row)

    events_count = db.conn.execute("SELECT COUNT(*) FROM world.world_events").fetchone()[0]
    assert events_count >= 4

    edge_kinds = {
        row[0]
        for row in db.conn.execute(
            "SELECT DISTINCT kind FROM world.world_edges"
        ).fetchall()
    }
    assert EdgeKind.DOC_HAS_VERSION.value in edge_kinds
    assert EdgeKind.DOC_HAS_FRAGMENT.value in edge_kinds

    # Ensure the latest meta points to the chunked artifact
    assert chunked.chunks_ref


def test_docs_pipeline_idempotent_semantics(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))

    retrieved_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    source = _source_spec(retrieved_at)
    text = "Idempotent test doc\n\n1. SECTION\nContent."

    ingest = ingest_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=source,
        raw_bytes=text.encode("utf-8"),
        mime="text/plain",
        segment_name="doc_ingest",
    )

    normalized1 = normalize_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=ingest.doc_meta_artifact_id,
        segment_name="doc_normalize_1",
    )
    structured1 = structure_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=normalized1.doc_meta_artifact_id,
        segment_name="doc_structure_1",
    )
    chunk_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=structured1.doc_meta_artifact_id,
        segment_name="doc_chunk_1",
    )

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)
    versions_before = db.conn.execute("SELECT COUNT(*) FROM world.doc_versions").fetchone()[0]
    fragments_before = db.conn.execute("SELECT COUNT(*) FROM world.doc_fragments").fetchone()[0]
    events_before = db.conn.execute("SELECT COUNT(*) FROM world.world_events").fetchone()[0]

    normalized2 = normalize_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=ingest.doc_meta_artifact_id,
        segment_name="doc_normalize_2",
    )
    structured2 = structure_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=normalized2.doc_meta_artifact_id,
        segment_name="doc_structure_2",
    )
    chunk_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=structured2.doc_meta_artifact_id,
        segment_name="doc_chunk_2",
    )

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)
    versions_after = db.conn.execute("SELECT COUNT(*) FROM world.doc_versions").fetchone()[0]
    fragments_after = db.conn.execute("SELECT COUNT(*) FROM world.doc_fragments").fetchone()[0]
    events_after = db.conn.execute("SELECT COUNT(*) FROM world.world_events").fetchone()[0]

    assert versions_before == versions_after == 1
    assert fragments_before == fragments_after
    assert events_after > events_before
