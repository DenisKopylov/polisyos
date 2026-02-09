from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.world.materialize import (
    WorldMergeConflict,
    materialize_world_duckdb_from_fact_log,
)
from polisyos.fabric.world.store import (
    append_world_segment_index,
    emit_attr_fact,
    emit_claim_facts,
    emit_doc_meta_facts,
    emit_world_event_facts,
    persist_claim,
    persist_doc_meta,
    persist_world_event,
    stable_world_provenance_v1,
    write_world_fact_segment,
)
from polisyos.ir.citations import AnchorKind, CitationRef, DocumentRef, FragmentLocator
from polisyos.ir.world.abi import EdgeKind, NodeKind
from polisyos.ir.world.claim import Claim, ClaimSourceKind
from polisyos.ir.world.doc import DocMeta
from polisyos.ir.world.event import (
    EventKind,
    ProvActivity,
    ProvActivityType,
    ProvAgent,
    ProvAgentType,
    WorldEvent,
)
from polisyos.ir.world.ids import (
    claim_id_from_payload,
    doc_fragment_id,
    doc_source_id,
    doc_version_id_from_raw_artifact,
    world_event_id_from_payload,
)
from polisyos.ir.world.predicates import WORLD_KIND


def _artifact_id(value: str) -> str:
    return f"sha256:{value * 64}"


def _build_doc_meta() -> DocMeta:
    raw_ref = _artifact_id("0")
    canonical_url = "https://example.com/doc"
    return DocMeta(
        doc_source_id=doc_source_id(canonical_url=canonical_url, official_id=None),
        doc_version_id=doc_version_id_from_raw_artifact(raw_artifact_id=raw_ref),
        canonical_url=canonical_url,
        official_id=None,
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        mime="text/html",
        license="public",
        raw_ref=raw_ref,
    )


def _build_world_event() -> WorldEvent:
    agent = ProvAgent(
        agent_id="prov.agent.test",
        agent_type=ProvAgentType.SYSTEM,
        label="System",
    )
    activity = ProvActivity(
        activity_id="prov.activity.test",
        activity_type=ProvActivityType.FETCH_DOC,
        label="Fetch",
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ended_at=datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc),
    )
    payload = {
        "event_kind": EventKind.FETCH_DOC,
        "agent": agent,
        "activity": activity,
        "inputs": [],
        "outputs": [],
        "evidence_ref": None,
        "provenance_ref": None,
    }
    event_id = world_event_id_from_payload(event_payload=payload)
    return WorldEvent(
        event_id=event_id,
        event_kind=EventKind.FETCH_DOC,
        agent=agent,
        activity=activity,
        inputs=[],
        outputs=[],
        evidence_ref=None,
        provenance_ref=None,
        props={},
    )


def _build_claim(fragment_id: str, doc_version_id: str, doc_source: str) -> Claim:
    citation = CitationRef(
        doc=DocumentRef(doc_id=doc_source, doc_version_id=doc_version_id),
        fragment_id=fragment_id,
        locator=None,
    )
    payload = {
        "predicate_id": "predicate.test",
        "subject_text": "subject",
        "value_text": "value",
        "confidence": Decimal("0.5"),
        "source_kind": ClaimSourceKind.DOC,
        "citations": [citation],
    }
    claim_id = claim_id_from_payload(claim_payload=payload)
    return Claim(
        claim_id=claim_id,
        predicate_id=payload["predicate_id"],
        subject_text=payload["subject_text"],
        value_text=payload["value_text"],
        confidence=payload["confidence"],
        source_kind=payload["source_kind"],
        citations=payload["citations"],
    )


def _write_single_segment(tmp_path: Path) -> tuple[SimulationDB, FileSystemCAS, DocMeta, WorldEvent]:
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))

    meta = _build_doc_meta()
    meta_ref = persist_doc_meta(cas, meta)
    event = _build_world_event()
    event_ref = persist_world_event(cas, event)

    provenance = stable_world_provenance_v1()
    facts: list = []
    facts.extend(
        emit_doc_meta_facts(
            meta,
            meta_artifact_id=str(meta_ref.artifact_id),
            provenance=provenance,
        )
    )
    facts.extend(
        emit_world_event_facts(
            event,
            event_artifact_id=str(event_ref.artifact_id),
            provenance=provenance,
        )
    )

    manifest = write_world_fact_segment(
        facts,
        fact_log_root=tmp_path,
        segment_name="world_segment",
    )
    append_world_segment_index(manifest, fact_log_root=tmp_path)
    return db, cas, meta, event


def test_materialize_single_segment_creates_nodes_edges_projections(tmp_path: Path) -> None:
    db, cas, meta, event = _write_single_segment(tmp_path)

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    schema_rows = db.conn.execute(
        "SELECT schema_name FROM information_schema.schemata WHERE schema_name='world'"
    ).fetchall()
    assert schema_rows

    kinds = {
        row[0]
        for row in db.conn.execute(
            "SELECT DISTINCT kind FROM world.world_nodes"
        ).fetchall()
    }
    assert NodeKind.DOC_SOURCE.value in kinds
    assert NodeKind.DOC_VERSION.value in kinds
    assert NodeKind.WORLD_EVENT.value in kinds
    assert NodeKind.PROV_AGENT.value in kinds

    edge_kinds = {
        row[0]
        for row in db.conn.execute(
            "SELECT DISTINCT kind FROM world.world_edges"
        ).fetchall()
    }
    assert EdgeKind.DOC_HAS_VERSION.value in edge_kinds
    assert any(kind.startswith("prov.") for kind in edge_kinds)

    row = db.conn.execute(
        """
        SELECT raw_ref, mime, license
        FROM world.doc_versions
        WHERE doc_version_id = ?
        """,
        [meta.doc_version_id],
    ).fetchone()
    assert row == (meta.raw_ref, meta.mime, meta.license)

    event_row = db.conn.execute(
        """
        SELECT event_kind, agent_id, activity_id
        FROM world.world_events
        WHERE event_id = ?
        """,
        [event.event_id],
    ).fetchone()
    assert event_row == (event.event_kind.value, event.agent.agent_id, event.activity.activity_id)


def test_materialize_idempotent_on_reapply(tmp_path: Path) -> None:
    db, cas, _, _ = _write_single_segment(tmp_path)

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)
    edges_count_1 = db.conn.execute(
        "SELECT COUNT(*) FROM world.world_edges"
    ).fetchone()[0]
    facts_count_1 = db.conn.execute(
        "SELECT COUNT(*) FROM world.world_facts"
    ).fetchone()[0]

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)
    edges_count_2 = db.conn.execute(
        "SELECT COUNT(*) FROM world.world_edges"
    ).fetchone()[0]
    facts_count_2 = db.conn.execute(
        "SELECT COUNT(*) FROM world.world_facts"
    ).fetchone()[0]

    assert edges_count_1 == edges_count_2
    assert facts_count_1 == facts_count_2

    meta_rows = db.conn.execute(
        "SELECT COUNT(*) FROM world._meta_world_segments"
    ).fetchone()[0]
    assert meta_rows == 1


def test_merge_rules_world_kind_conflict_fails(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))

    provenance = stable_world_provenance_v1()
    facts = [
        emit_attr_fact(
            subject_id="node.conflict",
            predicate_id=WORLD_KIND,
            object_value=NodeKind.DOC_VERSION.value,
            provenance=provenance,
        ),
        emit_attr_fact(
            subject_id="node.conflict",
            predicate_id=WORLD_KIND,
            object_value=NodeKind.CLAIM.value,
            provenance=provenance,
        ),
    ]

    manifest = write_world_fact_segment(
        facts,
        fact_log_root=tmp_path,
        segment_name="conflict",
    )
    append_world_segment_index(manifest, fact_log_root=tmp_path)

    with pytest.raises(WorldMergeConflict):
        materialize_world_duckdb_from_fact_log(tmp_path, db, cas)


def test_projection_claim_citations(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))

    raw_ref = _artifact_id("1")
    doc_version_id = doc_version_id_from_raw_artifact(raw_artifact_id=raw_ref)
    locator = FragmentLocator(anchor_kind=AnchorKind.SECTION, anchor_path="1")
    fragment_id = doc_fragment_id(
        doc_version_id=doc_version_id,
        locator=locator,
        text_artifact_id=_artifact_id("2"),
    )
    doc_source = doc_source_id(canonical_url="https://example.com/claim", official_id=None)

    claim = _build_claim(fragment_id, doc_version_id, doc_source)
    claim_ref = persist_claim(cas, claim)

    provenance = stable_world_provenance_v1()
    facts = emit_claim_facts(
        claim,
        claim_artifact_id=str(claim_ref.artifact_id),
        provenance=provenance,
    )

    manifest = write_world_fact_segment(
        facts,
        fact_log_root=tmp_path,
        segment_name="claims",
    )
    append_world_segment_index(manifest, fact_log_root=tmp_path)

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    row = db.conn.execute(
        """
        SELECT claim_id, fragment_id
        FROM world.claim_citations
        WHERE claim_id = ? AND fragment_id = ?
        """,
        [claim.claim_id, fragment_id],
    ).fetchone()
    assert row == (claim.claim_id, fragment_id)
