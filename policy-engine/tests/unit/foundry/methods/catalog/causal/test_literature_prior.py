from __future__ import annotations

import duckdb

from polisyos.foundry.methods.catalog.causal.literature_prior import BuildLiteraturePrior
from polisyos.foundry.methods.catalog.causal.protocols import LiteraturePriorBuildData
from polisyos.ir.analytics.literature import (
    ClaimVocabularyAxisStatus,
    EnvironmentAuditReport,
)


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
    assert prior.metadata["build_status"] == "skg_query_failed"
    assert prior.metadata["matched_edge_count"] == 0
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
    assert prior.metadata["build_status"] == "ok"
    assert prior.metadata["matched_edge_count"] == 1
    assert prior.metadata["matched_variable_count"] == 2
    assert prior.metadata["query_domain"] is None
    assert prior.metadata["confidence_threshold"] == 0.5
    assert prior.metadata["query_limit"] == 10
    assert graph.discovery_method == "literature_prior"
    assert graph.skg_version_id == 9
    assert len(graph.edges) == 1
    assert result["warnings"] == []


def test_build_literature_prior_decodes_persisted_declared_absence(tmp_path) -> None:
    db_path = tmp_path / "skg.duckdb"
    _seed_skg_db(db_path)
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            "UPDATE ac_skg_edges SET evidence_strength = 'not_established' "
            "WHERE edge_id = 'e1'"
        )
    finally:
        con.close()
    payload = LiteraturePriorBuildData(
        variables=["tax", "employment"],
        skg_db_path=str(db_path),
        skg_index_dir=str(tmp_path / "idx"),
        min_confidence=0.5,
    )

    result = BuildLiteraturePrior.pure_step(payload, params={})

    edge = result["literature_prior"].edges[0]
    assert edge.evidence_strength is None
    assert edge.evidence_strength_status is ClaimVocabularyAxisStatus.NOT_ESTABLISHED
    assert edge.model_dump(mode="json")["evidence_strength"] is None
    graph_edge = result["literature_prior_graph"].edges[0]
    assert graph_edge.metadata.get("evidence_strength") is None
    assert graph_edge.metadata["evidence_strength_status"] == "not_established"


def test_build_literature_prior_preserves_typed_environment_audit_when_attached(tmp_path) -> None:
    db_path = tmp_path / "skg.duckdb"
    _seed_skg_db(db_path)
    payload = LiteraturePriorBuildData(
        variables=["tax", "employment"],
        skg_db_path=str(db_path),
        skg_index_dir=str(tmp_path / "idx"),
    )

    result = BuildLiteraturePrior.pure_step(payload, params={})
    prior = result["literature_prior"].model_copy(
        update={
            "environment_audit": EnvironmentAuditReport(
                status="ok",
                n_environments=2,
                ks_passed=True,
                icp_run=False,
            )
        }
    )

    assert prior.environment_audit is not None
    assert prior.environment_audit.status == "ok"
    graph = prior.to_causal_graph_model(nodes=["tax", "employment"])
    assert graph.metadata["environment_audit_status"] == "ok"
