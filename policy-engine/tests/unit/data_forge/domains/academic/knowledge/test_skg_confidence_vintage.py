"""Exercise snapshot restrictions through real confidence readers and copying."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from polisyos.data_forge.domains.academic.batch import best_snapshot
from polisyos.data_forge.domains.academic.knowledge import skg_versioning
from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
from polisyos.data_forge.domains.academic.knowledge.skg_store import ensure_skg_schema


@pytest.fixture
def historical_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Substitute only the registered byte identity; exercise the real resolver."""
    path = tmp_path / "renamed.duckdb"
    with duckdb.connect(str(path)) as con:
        ensure_skg_schema(con)
        con.execute(
            "INSERT INTO ac_skg_edges "
            "(edge_id,src,dst,direction,article_refs,evidence_strength,confidence) "
            "VALUES ('e','tax','employment','positive','[\"w\"]','rct',0.83)"
        )
        con.execute(
            "INSERT INTO ac_skg_family_edges "
            "(family_edge_id,src_family,dst_family,direction,article_refs,claim_refs,"
            "evidence_strength,confidence) "
            "VALUES ('f','tax','employment','positive','[\"w\"]','[\"c\"]','rct',0.73)"
        )
        con.execute(
            "INSERT INTO ac_skg_transport_scores "
            "(transport_id,edge_id,target_context_id,base_confidence,transport_confidence,skg_version) "
            "VALUES ('t','e','ctx',0.83,0.7,1)"
        )
        # Lookalike markers and numeric-parameter vocabulary do not identify claim evidence.
        con.execute("CREATE TABLE metadata (payload VARCHAR)")
        con.execute(
            "INSERT INTO metadata VALUES (?)",
            [json.dumps({"evidence_strength": "rct", "layer_vintage": "current"})],
        )
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    monkeypatch.setattr(skg_versioning, "_HISTORICAL_SNAPSHOT_SHA256", digest, raising=False)
    return path


@pytest.mark.parametrize("layer", ["exact", "family", "hybrid"])
def test_declared_snapshot_cannot_forward_prior_confidence(historical_db: Path, layer: str) -> None:
    query = SKGQuery(historical_db, historical_db.parent)
    try:
        with pytest.raises(ValueError, match="not_reproducible_under_current_rule"):
            query.query_prior_for_variables([], edge_layer=layer)
    finally:
        query.close()


def test_declaration_keeps_non_emission_and_contradiction_separate(historical_db: Path) -> None:
    declaration = SKGQuery.confidence_layer_vintage(historical_db)
    assert declaration is not None
    payload = json.loads(json.dumps(declaration.to_payload()))
    assert payload["claim_evidence_axis"] == "absent"
    assert payload["confidence_reproducibility"] == "not_reproducible_under_current_rule"
    assert payload["layers"] == [
        {"table": "ac_skg_edges", "row_count": 7607, "current_rule_outcome": "zero_confidence"},
        {"table": "ac_skg_family_edges", "row_count": 15945,
         "current_rule_outcome": "zero_confidence"},
        {"table": "ac_skg_contested_edges", "row_count": 723,
         "current_rule_outcome": "not_emitted"},
    ]
    assert payload["adjudication_contradicting_evidence_rows"] == 342
    assert payload["published_evidence_rows"] == 7868
    assert "HC-F06/HC-F07" in payload["contradiction_basis"]
    with duckdb.connect(str(historical_db), read_only=True) as con:
        assert con.execute("SELECT confidence FROM ac_skg_edges").fetchall() == [(0.83,)]


def test_transport_and_store_summary_cannot_bypass_declaration(historical_db: Path) -> None:
    query = SKGQuery(historical_db, historical_db.parent)
    try:
        with pytest.raises(ValueError, match="not_reproducible_under_current_rule"):
            query.query_edge_transport(["e"], target_context_id="ctx")
        with pytest.raises(ValueError, match="not_reproducible_under_current_rule"):
            query._transport_confidence_for_edges(("e",), "ctx")
        with pytest.raises(ValueError, match="not_reproducible_under_current_rule"):
            query._store.project_edge_summary(
                source_table="ac_skg_edges", source_identity="e",
                cause="tax", effect="employment", direction="positive", evidence_strength="rct",
                mechanism="exact_support", domain="", trust_score=0.83, work_title="one work",
            )
    finally:
        query.close()


def test_unreadable_snapshot_is_ambiguous(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ambiguous snapshot bytes"):
        SKGQuery.require_forwardable_confidence(tmp_path / "missing.duckdb")


@pytest.mark.parametrize("cached", [False, True])
def test_historical_floor_cannot_control_bounds_even_when_cached(historical_db: Path, cached: bool) -> None:
    query = SKGQuery(historical_db, historical_db.parent)
    try:
        if cached:
            query._transport_confidence_floor = 0.7
        with pytest.raises(ValueError, match="not_reproducible_under_current_rule"):
            query._transport_confidence_floor_from_data()
    finally:
        query.close()


def test_rowwise_rewrite_is_an_explicit_unbound_residual(historical_db: Path, tmp_path: Path) -> None:
    """Falsify universal copy coverage without mistaking the residual for currentness."""
    rewritten = tmp_path / "rowwise.duckdb"
    with duckdb.connect(str(rewritten)) as con:
        con.execute(f"ATTACH '{historical_db}' AS source (READ_ONLY)")
        con.execute("CREATE TABLE ac_skg_edges AS SELECT * FROM source.ac_skg_edges")
    assert SKGQuery.confidence_layer_vintage(historical_db) is not None
    assert SKGQuery.confidence_layer_vintage(rewritten) is None
    query = SKGQuery(rewritten, tmp_path)
    try:
        assert query.query_prior_for_variables([])[0]["confidence"] == 0.83
    finally:
        query.close()


@pytest.mark.parametrize("layer", ["exact", "family", "contested", "hybrid"])
def test_declared_snapshot_cannot_forward_support_confidence(historical_db: Path, layer: str) -> None:
    query = SKGQuery(historical_db, historical_db.parent)
    try:
        with pytest.raises(ValueError, match="not_reproducible_under_current_rule"):
            query.query_edge_support(cause="tax", effect="employment", support_mode=layer)
    finally:
        query.close()


def test_snapshot_copy_refuses_before_deleting_destination(historical_db: Path) -> None:
    with duckdb.connect(":memory:") as con:
        ensure_skg_schema(con)
        con.execute(
            "INSERT INTO ac_skg_edges "
            "(edge_id,src,dst,direction,article_refs,evidence_strength,confidence) "
            "VALUES ('keep','x','y','positive','[]','rct',0.9)"
        )
        con.execute(f"ATTACH '{historical_db}' AS source (READ_ONLY)")
        with pytest.raises(ValueError, match="not_reproducible_under_current_rule"):
            best_snapshot._replace_table_contents(
                con, target_table="ac_skg_edges", source_alias="source",
                source_table="ac_skg_edges", version_id=None,
            )
        assert con.execute("SELECT edge_id, confidence FROM ac_skg_edges").fetchall() == [
            ("keep", 0.9)
        ]


def test_removing_declaration_changes_forwarding_while_markers_stay(
    historical_db: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = SKGQuery(historical_db, historical_db.parent)
    try:
        with pytest.raises(ValueError, match="not_reproducible_under_current_rule"):
            query.query_prior_for_variables([])
        # Removal probe: same database/field names/values; only registration is absent.
        monkeypatch.setattr(skg_versioning, "_HISTORICAL_SNAPSHOT_SHA256", "0" * 64)
        rows = query.query_prior_for_variables([])
        assert [(row["edge_id"], row["confidence"]) for row in rows] == [("e", 0.83)]
        with duckdb.connect(str(historical_db), read_only=True) as con:
            assert json.loads(con.execute("SELECT payload FROM metadata").fetchone()[0]) == {
                "evidence_strength": "rct", "layer_vintage": "current",
            }
    finally:
        query.close()
