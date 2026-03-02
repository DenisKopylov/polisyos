from __future__ import annotations

import json
import logging

import duckdb

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.parameters import load_context_adaptive_parameter_bundle
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.causal.resolve_parameters import ResolveParametersNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)


def _build_ctx(tmp_path, *, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path / "cas")
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(f"test.{run_id}"))


def _seed_skg(db_path) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE ac_skg_parameters (
                param_id VARCHAR,
                canonical_name VARCHAR,
                openalex_id VARCHAR,
                parameter_json VARCHAR,
                context_json VARCHAR
            )
            """
        )
        con.execute("CREATE TABLE ac_skg_versions (version_id INTEGER)")
        con.execute("INSERT INTO ac_skg_versions VALUES (12)")
        con.executemany(
            "INSERT INTO ac_skg_parameters VALUES (?, ?, ?, ?, ?)",
            [
                (
                    "p_cee",
                    "fiscal_multiplier",
                    "W_CEE",
                    json.dumps(
                        {
                            "name": "fiscal_multiplier",
                            "value": 1.35,
                            "parameter_type": "quantitative",
                            "evidence_strength": "observational",
                        }
                    ),
                    json.dumps(
                        {
                            "context_id": "PL",
                            "income_level": "lower_middle",
                            "institutional_quality": 0.45,
                            "post_communist": True,
                        }
                    ),
                ),
                (
                    "p_far",
                    "fiscal_multiplier",
                    "W_FAR",
                    json.dumps(
                        {
                            "name": "fiscal_multiplier",
                            "value": 2.1,
                            "parameter_type": "quantitative",
                            "evidence_strength": "theoretical",
                        }
                    ),
                    json.dumps(
                        {
                            "context_id": "US",
                            "income_level": "high",
                            "institutional_quality": 0.9,
                            "post_communist": False,
                        }
                    ),
                ),
            ],
        )
    finally:
        con.close()


def test_resolve_parameters_node_persists_bundle_and_bridge_payload(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_phase15_resolve")
    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path)
    graph_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["fiscal_multiplier"],
            edges=[],
        ),
    )
    state = ExperimentState(
        run_id="R_phase15_resolve",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {
                "context_id": "UA",
                "income_level": "lower_middle",
                "institutional_quality": 0.4,
                "post_communist": True,
            },
            "required_parameters": ["fiscal_multiplier", "missing_parameter"],
            "skg_db_path": str(db_path),
            "skg_index_dir": str(tmp_path / "idx"),
            "domain": "fiscal",
        },
    )

    outcome = ResolveParametersNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF in outcome.state.artifacts_index
    bundle_ref = outcome.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    bundle = load_context_adaptive_parameter_bundle(ctx.store, bundle_ref)

    # E2E scenario from phase DoD: UA should select CEE-like estimate.
    assert bundle.parameters["fiscal_multiplier"].value == 1.35
    assert "missing_parameter" in bundle.unsupported_parameters
    assert outcome.state.params["literature_priors"]["fiscal_multiplier"]["__intercept__"]["mean"] == 1.35
    assert "fiscal_multiplier" in outcome.state.params["parameter_uncertainty_multipliers"]
    assert any(event.code == "PARAMS_WITHOUT_EVIDENCE" for event in outcome.events)


def test_resolve_parameters_node_skips_on_missing_inputs(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_phase15_resolve_skip")
    state = ExperimentState(run_id="R_phase15_resolve_skip", params={})

    outcome = ResolveParametersNode().execute(ctx, state)

    assert outcome.status == "skip"
    assert outcome.events
    assert outcome.events[0].level == "warn"
