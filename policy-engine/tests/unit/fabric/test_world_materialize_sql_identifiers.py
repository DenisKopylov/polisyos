from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.quality.safety import UnsafeIdentifierError
from polisyos.fabric.world.materialize import ensure_world_schema
from polisyos.fabric.world.materialize.sql import (
    sql_count_new_edges,
    sql_count_new_world_facts,
    sql_insert_missing_nodes,
    sql_insert_world_edges,
    sql_insert_world_facts,
    sql_kind_conflicts,
    sql_load_applied_segments,
    sql_update_world_nodes,
)

_SOURCE_RELATION_BUILDERS: tuple[Callable[[str], str], ...] = (
    sql_count_new_edges,
    sql_count_new_world_facts,
    sql_insert_missing_nodes,
    sql_insert_world_edges,
    sql_insert_world_facts,
    sql_kind_conflicts,
    sql_update_world_nodes,
)
_SOURCE_RELATION = "ingest_stage.candidate_world_rows_20261026"
_SUBJECT_ID = "entity.identifier_probe_20261026"


def test_public_materialization_builders_execute_with_qualified_relations(
    tmp_path: Path,
) -> None:
    """Exercise every public materialization SQL builder on a native DuckDB connection."""
    with SimulationDB(db_path=str(tmp_path / "materialize-sql.duckdb")) as db:
        ensure_world_schema(db)
        db.conn.execute('CREATE SCHEMA "ingest_stage"')
        db.conn.execute(
            """
            CREATE TABLE "ingest_stage"."candidate_world_rows_20261026" (
                fact_id VARCHAR,
                schema_version VARCHAR,
                subject_id VARCHAR,
                predicate_id VARCHAR,
                object_value VARCHAR,
                target_id VARCHAR,
                valid_time VARCHAR,
                tx_time VARCHAR,
                provenance_json VARCHAR,
                trust_json VARCHAR,
                legal_json VARCHAR,
                segment_id VARCHAR,
                edge_id VARCHAR,
                src_id VARCHAR,
                kind VARCHAR,
                dst_id VARCHAR,
                node_id VARCHAR
            )
            """
        )
        db.conn.execute(
            """
            INSERT INTO "ingest_stage"."candidate_world_rows_20261026" VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "fact.identifier_probe_20261026",
                "1.0",
                _SUBJECT_ID,
                "world.kind",
                "claim",
                None,
                None,
                "2026-10-26T00:00:00Z",
                "{}",
                None,
                None,
                "segment.identifier_probe_20261026",
                "edge.identifier_probe_20261026",
                _SUBJECT_ID,
                "supports",
                "entity.target_identifier_probe_20261026",
                _SUBJECT_ID,
            ],
        )

        assert sql_load_applied_segments() == (
            "SELECT segment_id, segment_sha256 FROM world._meta_world_segments"
        )
        assert db.conn.execute(sql_load_applied_segments()).fetchall() == []
        assert db.conn.execute(sql_count_new_world_facts(_SOURCE_RELATION)).fetchone() == (1,)
        db.conn.execute(sql_insert_world_facts(_SOURCE_RELATION))
        assert db.conn.execute(sql_count_new_edges(_SOURCE_RELATION)).fetchone() == (1,)
        db.conn.execute(sql_insert_world_edges(_SOURCE_RELATION))
        assert db.conn.execute(sql_kind_conflicts(_SOURCE_RELATION)).fetchall() == []
        db.conn.execute(sql_insert_missing_nodes(_SOURCE_RELATION))
        db.conn.execute(sql_update_world_nodes(_SOURCE_RELATION))

        assert db.conn.execute(
            "SELECT kind FROM world.world_nodes WHERE node_id = ?",
            [_SUBJECT_ID],
        ).fetchone() == ("claim",)
        assert db.conn.execute(
            "SELECT edge_id, src_id, dst_id FROM world.world_edges WHERE edge_id = ?",
            ["edge.identifier_probe_20261026"],
        ).fetchone() == (
            "edge.identifier_probe_20261026",
            _SUBJECT_ID,
            "entity.target_identifier_probe_20261026",
        )


def test_public_materialization_builders_reject_unsafe_relations_before_execution(
    tmp_path: Path,
) -> None:
    """Reject multi-statement and malformed relations without touching a DB marker."""
    adversarial_relations = (
        "ingest_stage.candidate_rows; DROP TABLE world.safety_marker; --",
        "ingest_stage..candidate_rows",
    )
    with SimulationDB(db_path=str(tmp_path / "materialize-sql-rejection.duckdb")) as db:
        ensure_world_schema(db)
        db.conn.execute("CREATE TABLE world.safety_marker (marker VARCHAR NOT NULL)")
        db.conn.execute("INSERT INTO world.safety_marker VALUES (?)", ["preserved"])

        for relation in adversarial_relations:
            for builder in _SOURCE_RELATION_BUILDERS:
                with pytest.raises(UnsafeIdentifierError):
                    db.conn.execute(builder(relation))
                assert db.conn.execute("SELECT marker FROM world.safety_marker").fetchall() == [
                    ("preserved",)
                ]
