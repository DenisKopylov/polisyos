from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.claims import (
    ConflictDetectOptions,
    ConflictResolveOptions,
    detect_conflicts,
    extract_claims_from_doc,
    normalize_claims,
    resolve_conflicts,
)
from polisyos.fabric.claims.persist import load_json_artifact
from polisyos.fabric.claims.conflicts.key import conflict_key_v1
from polisyos.fabric.docs import (
    DocChunkOptions,
    DocSourceSpec,
    chunk_doc,
    ingest_doc_bytes,
    normalize_doc,
)
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.world.materialize import materialize_world_duckdb_from_fact_log
from polisyos.ir.world.claim import Claim, ClaimSourceKind
from polisyos.ir.world.conflict import ConflictKind, ConflictSet
from polisyos.ir.world.ids import conflict_set_id_from_key

_POLICY_ID = "policy.conflicts.default_v1"


def _source_spec() -> DocSourceSpec:
    return DocSourceSpec(
        canonical_url="https://example.com/conflicts",
        official_id=None,
        source_locator=None,
        license="public",
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        jurisdiction="US",
        language="en",
        source_type="test",
        title="Conflict Test Doc",
        publisher="Example Publisher",
    )


def _chunked_doc_meta_id(cas: FileSystemCAS, tmp_path: Path, text: str) -> str:
    ingest = ingest_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=_source_spec(),
        raw_bytes=text.encode("utf-8"),
        mime="text/plain",
        segment_name="doc_ingest_conflicts",
    )
    normalized = normalize_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=ingest.doc_meta_artifact_id,
        segment_name="doc_normalize_conflicts",
    )
    chunked = chunk_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=normalized.doc_meta_artifact_id,
        options=DocChunkOptions(
            chunk_size_chars=512,
            overlap_chars=16,
            min_chunk_chars=1,
        ),
        segment_name="doc_chunk_conflicts",
    )
    return chunked.doc_meta_artifact_id


def _claims_ready(
    *,
    cas: FileSystemCAS,
    tmp_path: Path,
    text: str,
) -> tuple[str, list[str]]:
    doc_meta_artifact_id = _chunked_doc_meta_id(cas, tmp_path, text)
    extracted = extract_claims_from_doc(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=doc_meta_artifact_id,
        extractor_id="explicit_lines_v1",
        segment_name="claims_extract_conflicts",
    )
    normalized = normalize_claims(
        cas=cas,
        fact_log_root=tmp_path,
        claim_set_artifact_id=extracted.claim_set_artifact_id,
        segment_name="claims_normalize_conflicts",
    )
    return normalized.claim_set_artifact_id, normalized.claim_ids


def test_conflict_key_deterministic() -> None:
    claim = Claim(
        claim_id="claim.dataset_demo",
        predicate_id="policy.tax_rate",
        subject_id="entity.tax",
        subject_text=None,
        value_text="20",
        value_decimal=Decimal("20"),
        unit_id="percent",
        confidence=Decimal("1"),
        source_kind=ClaimSourceKind.DATASET,
        citations=[],
        source_artifacts=["sha256:" + "a" * 64],
        jurisdiction="US",
        domain="tax",
        qualifiers={"year": 2026, "region": "national"},
    )

    first = conflict_key_v1(claim)
    second = conflict_key_v1(claim)
    assert first == second


def test_conflict_set_id_stable_container() -> None:
    conflict_key = "a" * 64
    first = ConflictSet(
        conflict_set_id=conflict_set_id_from_key(conflict_key=conflict_key),
        conflict_key=conflict_key,
        conflict_kind=ConflictKind.VALUE_MISMATCH,
        member_claim_ids=["claim.a", "claim.b"],
    )
    second = ConflictSet(
        conflict_set_id=conflict_set_id_from_key(conflict_key=conflict_key),
        conflict_key=conflict_key,
        conflict_kind=ConflictKind.UNIT_MISMATCH,
        member_claim_ids=["claim.a", "claim.c"],
    )

    assert first.conflict_set_id == second.conflict_set_id


def test_resolution_tie_break_deterministic(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))
    text = "\n".join(
        [
            "claim: policy.tax_rate = 20 [percent]",
            "claim: policy.tax_rate = 25 [percent]",
        ]
    )
    claim_set_artifact_id, claim_ids = _claims_ready(cas=cas, tmp_path=tmp_path, text=text)
    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    detected = detect_conflicts(
        cas=cas,
        fact_log_root=tmp_path,
        db=db,
        claim_set_artifact_ids=[claim_set_artifact_id],
        policy_id=_POLICY_ID,
        options=ConflictDetectOptions(),
        segment_name="claims_detect_tie",
    )
    resolved = resolve_conflicts(
        cas=cas,
        fact_log_root=tmp_path,
        db=db,
        conflict_set_ids=detected.conflict_set_ids,
        claim_set_artifact_ids=[claim_set_artifact_id],
        policy_id=_POLICY_ID,
        options=ConflictResolveOptions(),
        segment_name="claims_resolve_tie",
    )

    winner = next(iter(resolved.winner_by_conflict_set.values()))
    assert winner == min(claim_ids)
    assert len(resolved.uncertainty_envelope_artifact_ids) == len(resolved.conflict_set_ids)

    for conflict_artifact_id in resolved.conflict_set_artifact_ids:
        payload = load_json_artifact(cas, conflict_artifact_id)
        assert "uncertainty_envelope_artifact_id" in payload["props"]


def test_conflict_emits_world_facts(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))
    text = "\n".join(
        [
            "claim: policy.tax_rate = 20 [percent]",
            "claim: policy.tax_rate = 25 [percent]",
            "claim: policy.tax_rate = 30 [percent]",
        ]
    )
    claim_set_artifact_id, _ = _claims_ready(cas=cas, tmp_path=tmp_path, text=text)
    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    detected = detect_conflicts(
        cas=cas,
        fact_log_root=tmp_path,
        db=db,
        claim_set_artifact_ids=[claim_set_artifact_id],
        policy_id=_POLICY_ID,
        segment_name="claims_detect_e2e",
    )
    resolve_conflicts(
        cas=cas,
        fact_log_root=tmp_path,
        db=db,
        conflict_set_ids=detected.conflict_set_ids,
        claim_set_artifact_ids=[claim_set_artifact_id],
        policy_id=_POLICY_ID,
        segment_name="claims_resolve_e2e",
    )
    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    assert db.conn.execute("SELECT COUNT(*) FROM world.conflict_sets").fetchone()[0] >= 1
    assert db.conn.execute("SELECT COUNT(*) FROM world.conflict_members").fetchone()[0] >= 2
    assert (
        db.conn.execute(
            "SELECT COUNT(*) FROM world.world_edges WHERE kind='conflict.resolves_to'"
        ).fetchone()[0]
        >= 1
    )


def test_conflict_idempotent_semantics_events_grow(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))
    text = "\n".join(
        [
            "claim: policy.tax_rate = 20 [percent]",
            "claim: policy.tax_rate = 25 [percent]",
        ]
    )
    claim_set_artifact_id, _ = _claims_ready(cas=cas, tmp_path=tmp_path, text=text)
    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    detected_1 = detect_conflicts(
        cas=cas,
        fact_log_root=tmp_path,
        db=db,
        claim_set_artifact_ids=[claim_set_artifact_id],
        policy_id=_POLICY_ID,
        segment_name="claims_detect_idem_1",
    )
    resolve_conflicts(
        cas=cas,
        fact_log_root=tmp_path,
        db=db,
        conflict_set_ids=detected_1.conflict_set_ids,
        claim_set_artifact_ids=[claim_set_artifact_id],
        policy_id=_POLICY_ID,
        segment_name="claims_resolve_idem_1",
    )
    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    csets_before = db.conn.execute("SELECT COUNT(*) FROM world.conflict_sets").fetchone()[0]
    members_before = db.conn.execute("SELECT COUNT(*) FROM world.conflict_members").fetchone()[0]
    resolves_before = db.conn.execute(
        "SELECT COUNT(*) FROM world.world_edges WHERE kind='conflict.resolves_to'"
    ).fetchone()[0]
    events_before = db.conn.execute("SELECT COUNT(*) FROM world.world_events").fetchone()[0]

    detected_2 = detect_conflicts(
        cas=cas,
        fact_log_root=tmp_path,
        db=db,
        claim_set_artifact_ids=[claim_set_artifact_id],
        policy_id=_POLICY_ID,
        segment_name="claims_detect_idem_2",
    )
    resolve_conflicts(
        cas=cas,
        fact_log_root=tmp_path,
        db=db,
        conflict_set_ids=detected_2.conflict_set_ids,
        claim_set_artifact_ids=[claim_set_artifact_id],
        policy_id=_POLICY_ID,
        segment_name="claims_resolve_idem_2",
    )
    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    csets_after = db.conn.execute("SELECT COUNT(*) FROM world.conflict_sets").fetchone()[0]
    members_after = db.conn.execute("SELECT COUNT(*) FROM world.conflict_members").fetchone()[0]
    resolves_after = db.conn.execute(
        "SELECT COUNT(*) FROM world.world_edges WHERE kind='conflict.resolves_to'"
    ).fetchone()[0]
    events_after = db.conn.execute("SELECT COUNT(*) FROM world.world_events").fetchone()[0]

    assert csets_before == csets_after
    assert members_before == members_after
    assert resolves_before == resolves_after
    assert events_after > events_before
