from __future__ import annotations

import duckdb

from polisyos.foundry.methods.catalog.causal.literature_prior import BuildLiteraturePrior
from polisyos.foundry.methods.catalog.causal.protocols import LiteraturePriorBuildData


def _seed_skg_db(path) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """
            CREATE TABLE ac_skg_edges (
                edge_id VARCHAR,
                src VARCHAR,
                dst VARCHAR,
                direction VARCHAR,
                n_articles INTEGER,
                article_refs VARCHAR,
                evidence_strength VARCHAR,
                confidence DOUBLE,
                scope_conditions VARCHAR
            )
            """
        )
        con.execute("CREATE TABLE ac_skg_versions (version_id INTEGER)")
        con.execute(
            """
            INSERT INTO ac_skg_edges VALUES
            ('e1', 'tax', 'employment', 'negative', 5, '["W1","W2"]', 'rct', 0.81, '["OECD"]')
            """
        )
        con.execute("INSERT INTO ac_skg_versions VALUES (9)")
    finally:
        con.close()


def test_build_literature_prior_graceful_degradation_when_skg_missing(tmp_path) -> None:
    payload = LiteraturePriorBuildData(
        variables=["tax", "employment"],
        skg_db_path=str(tmp_path / "missing.duckdb"),
    )

    result = BuildLiteraturePrior.pure_step(payload, params={})

    prior = result["literature_prior"]
    graph = result["literature_prior_graph"]
    assert prior.edges == []
    assert graph.edges == []
    assert result["warnings"]


def test_build_literature_prior_builds_prior_and_graph(tmp_path) -> None:
    db_path = tmp_path / "skg.duckdb"
    _seed_skg_db(db_path)
    payload = LiteraturePriorBuildData(
        variables=["tax", "employment"],
        skg_db_path=str(db_path),
        skg_index_dir=str(tmp_path / "idx"),
        min_confidence=0.5,
        limit=10,
    )

    result = BuildLiteraturePrior.pure_step(payload, params={})

    prior = result["literature_prior"]
    graph = result["literature_prior_graph"]
    assert len(prior.edges) == 1
    assert prior.skg_version_id == 9
    assert prior.skg_snapshot_ref == f"duckdb://{db_path}#v9"
    assert graph.discovery_method == "literature_prior"
    assert graph.skg_version_id == 9
    assert len(graph.edges) == 1
    assert result["warnings"] == []
