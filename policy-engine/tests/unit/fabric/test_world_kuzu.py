from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.world.materialize import (
    materialize_world_duckdb_from_fact_log,
    materialize_world_kuzu_from_duckdb,
)
from polisyos.fabric.world.store import (
    append_world_segment_index,
    emit_doc_fragment_facts,
    emit_doc_meta_facts,
    persist_doc_fragment,
    persist_doc_meta,
    stable_world_provenance_v1,
    write_world_fact_segment,
)
from polisyos.ir.loading.citations import AnchorKind, FragmentLocator
from polisyos.ir.world.doc import DocFragment, DocMeta
from polisyos.ir.world.ids import (
    doc_fragment_id,
    doc_source_id,
    doc_version_id_from_raw_artifact,
)


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


def _build_doc_fragment(doc_version_id: str) -> DocFragment:
    locator = FragmentLocator(anchor_kind=AnchorKind.SECTION, anchor_path="1")
    fragment_id = doc_fragment_id(
        doc_version_id=doc_version_id,
        locator=locator,
        text_artifact_id=_artifact_id("1"),
    )
    return DocFragment(
        fragment_id=fragment_id,
        doc_version_id=doc_version_id,
        locator=locator,
        text_hash=_artifact_id("1"),
        quote_preview="excerpt",
    )


def test_kuzu_rebuild_smoke(tmp_path: Path) -> None:
    kuzu = pytest.importorskip("kuzu")

    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))

    meta = _build_doc_meta()
    meta_ref = persist_doc_meta(cas, meta)
    fragment = _build_doc_fragment(meta.doc_version_id)
    fragment_ref = persist_doc_fragment(cas, fragment)

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
        emit_doc_fragment_facts(
            fragment,
            fragment_artifact_id=str(fragment_ref.artifact_id),
            provenance=provenance,
        )
    )

    manifest = write_world_fact_segment(
        facts,
        fact_log_root=tmp_path,
        segment_name="world_segment",
    )
    append_world_segment_index(manifest, fact_log_root=tmp_path)

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    kuzu_path = tmp_path / "world.kuzu"
    materialize_world_kuzu_from_duckdb(
        db,
        kuzu_path=kuzu_path,
        mode="rebuild",
        clear_on_start=True,
        kuzu_enabled=True,
    )

    duckdb_nodes = int(db.conn.execute("SELECT COUNT(*) FROM world.world_nodes").fetchone()[0])
    duckdb_edges = int(db.conn.execute("SELECT COUNT(*) FROM world.world_edges").fetchone()[0])

    kuzu_db = kuzu.Database(str(kuzu_path))
    kuzu_conn = kuzu.Connection(kuzu_db)
    kuzu_nodes = int(
        kuzu_conn.execute("MATCH (n:WorldNode) RETURN COUNT(n) AS c").get_as_df().iloc[0, 0]
    )
    kuzu_edges = int(
        kuzu_conn.execute("MATCH ()-[e:WorldEdge]->() RETURN COUNT(e) AS c").get_as_df().iloc[0, 0]
    )

    assert duckdb_nodes == kuzu_nodes
    assert duckdb_edges == kuzu_edges

    has_fragment = int(
        kuzu_conn.execute(
            "MATCH ()-[e:WorldEdge]->() WHERE e.kind='doc.has_fragment' RETURN COUNT(e) AS c"
        )
        .get_as_df()
        .iloc[0, 0]
    )
    assert has_fragment == 1

    path_count = int(
        kuzu_conn.execute(
            """
            MATCH (s:WorldNode)-[e1:WorldEdge]->(v:WorldNode)-[e2:WorldEdge]->(f:WorldNode)
            WHERE s.id = $doc_source_id
              AND e1.kind = 'doc.has_version'
              AND e2.kind = 'doc.has_fragment'
            RETURN COUNT(f) AS c
            """,
            {"doc_source_id": meta.doc_source_id},
        )
        .get_as_df()
        .iloc[0, 0]
    )
    assert path_count == 1
