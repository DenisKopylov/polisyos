from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.claims import (
    detect_conflicts,
    extract_claims_from_doc,
    normalize_claims,
    resolve_conflicts,
)
from polisyos.fabric.docs import (
    DocChunkOptions,
    DocSourceSpec,
    chunk_doc,
    ingest_doc_bytes,
    normalize_doc,
)
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.world.materialize import materialize_world_duckdb_from_fact_log

_POLICY_ID = "policy.conflicts.default_v1"


def _source_spec() -> DocSourceSpec:
    return DocSourceSpec(
        canonical_url="https://example.com/trust",
        official_id=None,
        source_locator=None,
        license="public",
        retrieved_at=datetime(2026, 1, 2, tzinfo=UTC),
        jurisdiction="US",
        language="en",
        source_type="official",
        title="Trust Test Doc",
        publisher="Example Publisher",
    )


def _claims_ready(
    *,
    cas: FileSystemCAS,
    tmp_path: Path,
    text: str,
) -> str:
    ingest = ingest_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=_source_spec(),
        raw_bytes=text.encode("utf-8"),
        mime="text/plain",
        segment_name="doc_ingest_trust",
    )
    normalized_doc = normalize_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=ingest.doc_meta_artifact_id,
        segment_name="doc_normalize_trust",
    )
    chunked = chunk_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=normalized_doc.doc_meta_artifact_id,
        options=DocChunkOptions(
            chunk_size_chars=512,
            overlap_chars=16,
            min_chunk_chars=1,
        ),
        segment_name="doc_chunk_trust",
    )
    extracted = extract_claims_from_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=chunked.doc_meta_artifact_id,
        extractor_id="explicit_lines_v1",
        segment_name="claims_extract_trust",
    )
    normalized_claims = normalize_claims(
        cas=cas,
        fact_log_root=tmp_path,
        claim_set_artifact_id=extracted.claim_set_artifact_id,
        segment_name="claims_normalize_trust",
    )
    return normalized_claims.claim_set_artifact_id


def test_trust_assessment_emitted_and_queryable(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))
    claim_set_artifact_id = _claims_ready(
        cas=cas,
        tmp_path=tmp_path,
        text="\n".join(
            [
                "claim: policy.tax_rate = 20 [percent]",
                "claim: policy.tax_rate = 25 [percent]",
            ]
        ),
    )
    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    detected = detect_conflicts(
        cas=cas,
        fact_log_root=tmp_path,
        db=db,
        claim_set_artifact_ids=[claim_set_artifact_id],
        policy_id=_POLICY_ID,
        segment_name="claims_detect_trust",
    )
    resolve_conflicts(
        cas=cas,
        fact_log_root=tmp_path,
        db=db,
        conflict_set_ids=detected.conflict_set_ids,
        claim_set_artifact_ids=[claim_set_artifact_id],
        policy_id=_POLICY_ID,
        segment_name="claims_resolve_trust",
    )
    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    total = db.conn.execute("SELECT COUNT(*) FROM world.trust_assessments").fetchone()[0]
    assert total > 0
    assert (
        db.conn.execute(
            "SELECT COUNT(*) FROM world.trust_assessments WHERE target_world_id LIKE 'docv.%'"
        ).fetchone()[0]
        >= 1
    )
    assert (
        db.conn.execute(
            "SELECT COUNT(*) FROM world.trust_assessments WHERE target_world_id LIKE 'claim.%'"
        ).fetchone()[0]
        >= 1
    )
    assert (
        db.conn.execute(
            "SELECT COUNT(*) FROM world.trust_assessments WHERE target_world_id LIKE 'cset.%'"
        ).fetchone()[0]
        >= 1
    )
    assert (
        db.conn.execute(
            "SELECT COUNT(*) FROM world.world_nodes WHERE kind='trust.assessment'"
        ).fetchone()[0]
        >= total
    )
    assert (
        db.conn.execute(
            """
            SELECT COUNT(*)
            FROM world.world_edges
            WHERE kind='report.about' AND src_id LIKE 'trust.%'
            """
        ).fetchone()[0]
        >= total
    )
