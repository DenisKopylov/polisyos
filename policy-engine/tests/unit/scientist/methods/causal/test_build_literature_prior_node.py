from __future__ import annotations

import logging

import duckdb
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.literature import load_literature_causal_prior
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.causal.build_literature_prior import (
    BuildLiteraturePriorNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_LITERATURE_PRIOR_GRAPH_REF,
    ARTIFACT_LITERATURE_PRIOR_REF,
)


def _build_ctx(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_phase9_lit")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.phase9.lit"))
    return ctx


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
            ('e1', 'tax', 'employment', 'negative', 5, '["W1","W2"]', 'rct', 0.8, '["OECD"]')
            """
        )
        con.execute("INSERT INTO ac_skg_versions VALUES (7)")
    finally:
        con.close()


def test_build_literature_prior_node_persists_prior_and_graph(tmp_path) -> None:
    ctx = _build_ctx(tmp_path)
    db_path = tmp_path / "skg.duckdb"
    _seed_skg_db(db_path)
    state = ExperimentState(
        run_id="R_phase9_lit",
        params={
            "causal_variables": ["tax", "employment"],
            "skg_db_path": str(db_path),
            "skg_index_dir": str(tmp_path / "idx"),
            "discovery_data": [[0.0, 1.0], [0.1, 1.1], [2.0, 3.0], [2.1, 3.1]],
            "discovery_variable_names": ["tax", "employment"],
            "discovery_environment_labels": ["a", "a", "b", "b"],
        },
    )

    outcome = BuildLiteraturePriorNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_LITERATURE_PRIOR_REF in outcome.state.artifacts_index
    assert ARTIFACT_LITERATURE_PRIOR_GRAPH_REF in outcome.state.artifacts_index
    prior_ref = outcome.state.artifacts_index[ARTIFACT_LITERATURE_PRIOR_REF]
    prior = load_literature_causal_prior(ctx.store, prior_ref)
    assert len(prior.edges) == 1
    assert prior.skg_version_id == 7
    assert prior.environment_audit is not None
    assert prior.environment_audit.status == "ok"
    assert outcome.state.params["environment_audit_status"] == "ok"


def test_build_literature_prior_node_skips_without_variables(tmp_path) -> None:
    ctx = _build_ctx(tmp_path)
    state = ExperimentState(run_id="R_phase9_lit_skip", params={})

    outcome = BuildLiteraturePriorNode().execute(ctx, state)

    assert outcome.status == "skip"


def test_build_literature_prior_node_runs_environment_audit_when_skg_missing(tmp_path) -> None:
    ctx = _build_ctx(tmp_path)
    state = ExperimentState(
        run_id="R_phase9_lit_missing_skg",
        params={
            "causal_variables": ["tax", "employment"],
            "skg_db_path": str(tmp_path / "missing.duckdb"),
            "discovery_data": [[0.0, 1.0], [0.1, 1.1], [2.0, 3.0], [2.1, 3.1]],
            "discovery_variable_names": ["tax", "employment"],
            "discovery_environment_labels": ["a", "a", "b", "b"],
        },
    )

    outcome = BuildLiteraturePriorNode().execute(ctx, state)

    assert outcome.status == "ok"
    prior_ref = outcome.state.artifacts_index[ARTIFACT_LITERATURE_PRIOR_REF]
    prior = load_literature_causal_prior(ctx.store, prior_ref)
    assert prior.edges == []
    assert prior.environment_audit is not None
    assert prior.environment_audit.status == "ok"
    assert outcome.state.params["literature_prior_warnings"]
