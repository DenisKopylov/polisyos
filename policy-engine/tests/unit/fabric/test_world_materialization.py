from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from polisyos.ir.loading.citations import AnchorKind, CitationRef, DocumentRef, FragmentLocator

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.observability import get_metrics, get_tracer
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.security import DataClassification
from polisyos.fabric.world.events import build_deterministic_world_event
from polisyos.fabric.world.materialize import (
    WorldMaterializationError,
    WorldMaterializationPolicy,
    WorldMergeConflict,
    WorldProjectionFailureMode,
    build_world_materialization_plan,
    ensure_world_schema,
    materialize_world_duckdb_from_fact_log,
)
from polisyos.fabric.world.materialize.duckdb import _load_applied_segments
from polisyos.fabric.world.materialize.projections import (
    build_projection_refresh_plan,
    update_projections,
)
from polisyos.fabric.world.materialize.sql import sql_update_world_nodes
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
from polisyos.ir.loading.fact_log import FactSegmentManifest
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
from polisyos.ir.world.predicates import WORLD_KIND, rel


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
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
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
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        ended_at=datetime(2026, 1, 1, 0, 10, tzinfo=UTC),
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


def _write_single_segment(
    tmp_path: Path,
) -> tuple[SimulationDB, FileSystemCAS, DocMeta, WorldEvent]:
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


def test_persist_doc_meta_records_governance_manifest(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas_governed")
    meta = _build_doc_meta()

    ref = persist_doc_meta(
        cas,
        meta,
        classification=DataClassification.INTERNAL,
        encrypted_at_rest=True,
        encryption_key_reference="kms://fabric/world",
    )
    manifest = cas.get_manifest(ref.artifact_id)

    assert manifest.governance is not None
    assert manifest.governance.classification == "internal"
    assert manifest.governance.retention is not None
    assert manifest.governance.retention.scope == "cas"
    assert manifest.governance.encryption is not None
    assert manifest.governance.encryption.mode == "envelope"
    assert manifest.governance.encryption.verified is True


def test_materialize_single_segment_creates_nodes_edges_projections(tmp_path: Path) -> None:
    db, cas, meta, event = _write_single_segment(tmp_path)

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    schema_rows = db.conn.execute(
        "SELECT schema_name FROM information_schema.schemata WHERE schema_name='world'"
    ).fetchall()
    assert schema_rows

    kinds = {
        row[0] for row in db.conn.execute("SELECT DISTINCT kind FROM world.world_nodes").fetchall()
    }
    assert NodeKind.DOC_SOURCE.value in kinds
    assert NodeKind.DOC_VERSION.value in kinds
    assert NodeKind.WORLD_EVENT.value in kinds
    assert NodeKind.PROV_AGENT.value in kinds

    edge_kinds = {
        row[0] for row in db.conn.execute("SELECT DISTINCT kind FROM world.world_edges").fetchall()
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


def test_materialize_world_duckdb_uses_injected_observability_providers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, cas, _, _ = _write_single_segment(tmp_path)
    tracer = get_tracer()
    metrics = get_metrics()
    resolved_calls: list[tuple[object | None, object | None]] = []

    monkeypatch.setattr(
        "polisyos.fabric.world.materialize.duckdb.resolve_world_observability",
        lambda **kwargs: (
            resolved_calls.append((kwargs.get("tracer"), kwargs.get("metrics")))
            or SimpleNamespace(tracer=tracer, metrics=metrics)
        ),
    )

    stats = materialize_world_duckdb_from_fact_log(
        tmp_path,
        db,
        cas,
        tracer=tracer,
        metrics=metrics,
    )

    assert stats.segments_applied == 1
    assert resolved_calls[0] == (tracer, metrics)


def test_deterministic_world_event_records_activity_duration_and_edge() -> None:
    started_at = datetime(2026, 1, 1, tzinfo=UTC)
    ended_at = datetime(2026, 1, 1, 0, 0, 10, tzinfo=UTC)
    event = build_deterministic_world_event(
        event_kind=EventKind.FETCH_DOC,
        agent_id="prov.agent.test",
        agent_type=ProvAgentType.SYSTEM,
        agent_label="System",
        activity_id="prov.activity.test",
        activity_type=ProvActivityType.FETCH_DOC,
        activity_label="Fetch",
        inputs=[],
        outputs=[],
        evidence_ref="sha256:" + ("b" * 64),
        started_at=started_at,
        ended_at=ended_at,
    )

    facts = emit_world_event_facts(
        event,
        event_artifact_id="sha256:" + ("c" * 64),
        provenance=stable_world_provenance_v1(),
    )

    assert event.props["activity_duration_ms"] == 10000
    assert event.props["activity_started_at"] == started_at.isoformat()
    assert event.props["activity_ended_at"] == ended_at.isoformat()
    assert event.props["evidence_ref"] == "sha256:" + ("b" * 64)
    assert any(
        fact.subject_id == event.event_id
        and fact.predicate_id == rel(EdgeKind.PROV_WAS_GENERATED_BY)
        and fact.target_id == event.activity.activity_id
        for fact in facts
    )


def test_simulation_db_context_can_close_delete_and_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "sim.duckdb"
    with SimulationDB(db_path=str(db_path)) as db:
        assert not db.closed
        db.conn.execute("SELECT 1").fetchone()

    assert db.closed
    db_path.unlink()

    reopened = SimulationDB(db_path=str(db_path))
    try:
        assert db_path.exists()
        reopened.conn.execute("SELECT 1").fetchone()
    finally:
        reopened.close()


def test_materialize_idempotent_on_reapply(tmp_path: Path) -> None:
    db, cas, _, _ = _write_single_segment(tmp_path)

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)
    edges_count_1 = db.conn.execute("SELECT COUNT(*) FROM world.world_edges").fetchone()[0]
    facts_count_1 = db.conn.execute("SELECT COUNT(*) FROM world.world_facts").fetchone()[0]

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)
    edges_count_2 = db.conn.execute("SELECT COUNT(*) FROM world.world_edges").fetchone()[0]
    facts_count_2 = db.conn.execute("SELECT COUNT(*) FROM world.world_facts").fetchone()[0]

    assert edges_count_1 == edges_count_2
    assert facts_count_1 == facts_count_2

    meta_rows = db.conn.execute("SELECT COUNT(*) FROM world._meta_world_segments").fetchone()[0]
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


def test_load_applied_segments_fails_closed_on_read_error() -> None:
    class BrokenConnection:
        def execute(self, _sql):
            raise RuntimeError("catalog read failed")

    class BrokenDB:
        conn = BrokenConnection()

    with pytest.raises(WorldMaterializationError, match="uncertain"):
        _load_applied_segments(BrokenDB())


def test_update_projections_starts_transaction_when_called_publicly(tmp_path: Path) -> None:
    class EmptyResult:
        def df(self):
            return pd.DataFrame()

    class RecordingConnection:
        def __init__(self) -> None:
            self.statements: list[str] = []

        def execute(self, sql: str):
            self.statements.append(sql.strip())
            if sql.strip().upper().startswith("SELECT"):
                return EmptyResult()
            return self

        def unregister(self, _name: str) -> None:
            return None

        def register(self, _name: str, _df) -> None:
            return None

    conn = RecordingConnection()
    cas = FileSystemCAS(tmp_path / "cas")

    stats = update_projections(conn, cas, touched_node_ids=[])

    assert stats.total_updates == 0
    assert conn.statements == ["BEGIN", "COMMIT"]


def test_projection_refresh_plan_prunes_unaffected_projections() -> None:
    plan = build_projection_refresh_plan(
        touched_node_kinds=("claim",),
    )

    assert plan.impacted_projection_names == (
        "claims",
        "claim_citations",
        "conflict_members",
    )
    assert all("doc_" not in name for name in plan.impacted_projection_names)


def test_world_materialization_plan_is_topologically_sorted() -> None:
    manifest = FactSegmentManifest(
        segment_id="segment.plan",
        path="/tmp/segment.plan.parquet",
        row_count=3,
        sha256="a" * 64,
    )

    plan = build_world_materialization_plan(
        manifest=manifest,
        touched_node_kinds=("claim", "doc.fragment"),
        refresh_policy=WorldMaterializationPolicy(),
    )
    names = [step.name for step in plan.steps]

    assert names.index("world.world_facts") < names.index("world.world_nodes")
    assert names.index("world.world_nodes") < names.index("projection:claims")
    assert names.index("projection:claims") < names.index("projection:claim_citations")
    assert names[-1] == "kuzu.export"
    assert plan.explain()


def test_update_projections_reports_actual_row_counts(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))

    meta1 = _build_doc_meta()
    meta2 = meta1.model_copy(
        update={
            "canonical_url": "https://example.com/doc-2",
            "doc_source_id": doc_source_id(
                canonical_url="https://example.com/doc-2",
                official_id=None,
            ),
            "doc_version_id": doc_version_id_from_raw_artifact(raw_artifact_id=_artifact_id("9")),
            "raw_ref": _artifact_id("9"),
        }
    )
    ref1 = persist_doc_meta(cas, meta1)
    ref2 = persist_doc_meta(cas, meta2)

    provenance = stable_world_provenance_v1()
    facts = [
        *emit_doc_meta_facts(
            meta1,
            meta_artifact_id=str(ref1.artifact_id),
            provenance=provenance,
        ),
        *emit_doc_meta_facts(
            meta2,
            meta_artifact_id=str(ref2.artifact_id),
            provenance=provenance,
        ),
    ]
    manifest = write_world_fact_segment(
        facts,
        fact_log_root=tmp_path,
        segment_name="doc_versions",
    )
    append_world_segment_index(manifest, fact_log_root=tmp_path)

    stats = materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    assert stats.segments[0].projections_updated >= 4

    rerun = update_projections(
        db.conn,
        cas,
        touched_node_ids=[meta1.doc_version_id, meta2.doc_version_id],
    )
    assert rerun.doc_versions == 2
    assert rerun.doc_sources == 2


def test_ranked_world_node_updates_prefer_non_null_values(tmp_path: Path) -> None:
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))
    ensure_world_schema(db)
    db.conn.execute("INSERT INTO world.world_nodes (node_id, kind) VALUES ('claim.test', 'claim')")
    db.conn.execute(
        """
        INSERT INTO world.world_facts (
            fact_id,
            schema_version,
            subject_id,
            predicate_id,
            object_value,
            target_id,
            valid_time,
            tx_time,
            provenance_json,
            trust_json,
            legal_json,
            segment_id
        )
        VALUES
            (?, '1.0', 'claim.test', ?, 'Stable label', NULL, NULL, ?, '{}', NULL, NULL, 'seg.old'),
            (?, '1.0', 'claim.test', ?, NULL, NULL, NULL, ?, '{}', NULL, NULL, 'seg.new')
        """,
        [
            "sha256:" + ("1" * 64),
            "world.label",
            "2026-01-01T00:00:00Z",
            "sha256:" + ("2" * 64),
            "world.label",
            "2026-02-01T00:00:00Z",
        ],
    )
    db.conn.register("touched_nodes_test", pd.DataFrame({"node_id": ["claim.test"]}))
    try:
        db.conn.execute(sql_update_world_nodes("touched_nodes_test"))
    finally:
        db.conn.unregister("touched_nodes_test")

    label = db.conn.execute(
        "SELECT label FROM world.world_nodes WHERE node_id = 'claim.test'"
    ).fetchone()[0]
    assert label == "Stable label"


def test_materialize_stale_if_error_preserves_existing_projections(tmp_path: Path) -> None:
    db, cas, meta, _ = _write_single_segment(tmp_path)
    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    existing_row = db.conn.execute("SELECT COUNT(*) FROM world.doc_versions").fetchone()[0]
    assert existing_row == 1

    broken_meta = meta.model_copy(
        update={
            "doc_version_id": doc_version_id_from_raw_artifact(raw_artifact_id=_artifact_id("e")),
            "raw_ref": _artifact_id("e"),
        }
    )
    broken_facts = emit_doc_meta_facts(
        broken_meta,
        meta_artifact_id=_artifact_id("f"),
        provenance=stable_world_provenance_v1(),
    )
    broken_manifest = write_world_fact_segment(
        broken_facts,
        fact_log_root=tmp_path,
        segment_name="broken_doc_meta",
    )
    append_world_segment_index(broken_manifest, fact_log_root=tmp_path)

    stats = materialize_world_duckdb_from_fact_log(
        tmp_path,
        db,
        cas,
        refresh_policy=WorldMaterializationPolicy(
            projection_failure_mode=WorldProjectionFailureMode.STALE_IF_ERROR,
        ),
    )

    assert stats.segments[-1].projections_updated == 0
    assert any("stale" in note for note in stats.segments[-1].notes)
    assert db.conn.execute("SELECT COUNT(*) FROM world.doc_versions").fetchone()[0] == 1
