from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime

import duckdb

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.parameters import load_context_adaptive_parameter_bundle
from polisyos.scientist.nodes.builtins.causal.resolve_parameters import ResolveParametersNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.idempotency import compute_idempotency_key
from polisyos.scientist.orchestration.engine.state import ExperimentState


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
    assert (
        outcome.state.params["literature_priors"]["fiscal_multiplier"]["__intercept__"]["mean"]
        == 1.35
    )
    assert "fiscal_multiplier" in outcome.state.params["parameter_uncertainty_multipliers"]
    assert outcome.state.params["phase15_runtime_ready"] is True
    assert outcome.state.params["phase15_runtime_backend_used"] in {"jax", "numpy", "numpyro"}
    assert (
        outcome.state.params["phase15_runtime_parameter_intervals"]["fiscal_multiplier"]["ci_low"]
        < outcome.state.params["phase15_runtime_parameter_intervals"]["fiscal_multiplier"][
            "ci_high"
        ]
    )
    assert any(event.code == "PARAMS_WITHOUT_EVIDENCE" for event in outcome.events)


def test_existing_bundle_is_revalidated_for_changed_request(tmp_path) -> None:
    """A bundle ref is a reuse candidate, not proof for a changed request."""
    ctx = _build_ctx(tmp_path, run_id="R_phase15_changed_request")
    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path)
    graph_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
    )
    state = ExperimentState(
        run_id="R_phase15_changed_request",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {
                "context_id": "UA",
                "income_level": "lower_middle",
                "institutional_quality": 0.4,
                "post_communist": True,
            },
            "required_parameters": ["fiscal_multiplier"],
            "skg_db_path": str(db_path),
            "skg_index_dir": str(tmp_path / "idx"),
            "domain": "fiscal",
        },
    )

    first = ResolveParametersNode().execute(ctx, state)
    assert first.status == "ok"
    first_ref = first.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]

    changed = first.state.model_copy(deep=True)
    changed.params["target_context"] = {
        "context_id": "US",
        "income_level": "high",
        "institutional_quality": 0.9,
        "post_communist": False,
    }

    second = ResolveParametersNode().execute(ctx, changed)
    assert second.status == "ok"
    second_ref = second.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    assert second_ref != first_ref

    second_bundle = load_context_adaptive_parameter_bundle(ctx.store, second_ref)
    assert second_bundle.target_context == ContextProfile(
        context_id="US",
        income_level="high",
        institutional_quality=0.9,
        post_communist=False,
    )
    assert second_bundle.simulation_domain == "fiscal"


def test_matching_source_unbound_bundle_reselects_configured_source(tmp_path, monkeypatch) -> None:
    """A v1 bundle without a selector-read binding cannot bypass a current source."""
    ctx = _build_ctx(tmp_path, run_id="R_phase15_reuse")
    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path)
    graph_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
    )
    state = ExperimentState(
        run_id="R_phase15_reuse",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {
                "context_id": "UA",
                "income_level": "lower_middle",
                "institutional_quality": 0.4,
                "post_communist": True,
            },
            "required_parameters": ["fiscal_multiplier"],
            "skg_db_path": str(db_path),
            "skg_index_dir": str(tmp_path / "idx"),
            "domain": "fiscal",
        },
    )

    node = ResolveParametersNode()
    first_started = datetime.now(UTC).replace(microsecond=0)
    first = node.execute(ctx, state)
    first_finished = datetime.now(UTC).replace(microsecond=0)
    assert first.status == "ok"
    first_ref = first.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]

    from polisyos.scientist.nodes.builtins.causal import resolve_parameters

    original_selector = resolve_parameters.ParameterSelector
    selections = 0

    def counted_selector(*args, **kwargs):
        nonlocal selections
        selections += 1
        return original_selector(*args, **kwargs)

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_parameters.ParameterSelector",
        counted_selector,
    )
    # A fresh selection has its own producer timestamp, and therefore may have
    # another immutable CAS identity despite equivalent selected parameters.
    time.sleep(1.01)
    replay_started = datetime.now(UTC).replace(microsecond=0)
    replay = node.execute(ctx, first.state.model_copy(deep=True))
    replay_finished = datetime.now(UTC).replace(microsecond=0)

    assert replay.status == "ok"
    assert selections == 1
    replay_ref = replay.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    assert ctx.store.verify(first_ref.artifact_id).ok
    assert ctx.store.verify(replay_ref.artifact_id).ok
    first_bundle = load_context_adaptive_parameter_bundle(ctx.store, first_ref)
    replay_bundle = load_context_adaptive_parameter_bundle(ctx.store, replay_ref)
    assert replay_bundle.model_dump(exclude={"selection_timestamp"}) == first_bundle.model_dump(
        exclude={"selection_timestamp"}
    )
    first_time = datetime.fromisoformat(first_bundle.selection_timestamp)
    replay_time = datetime.fromisoformat(replay_bundle.selection_timestamp)
    assert first_time.utcoffset() == replay_time.utcoffset() == UTC.utcoffset(None)
    assert first_started <= first_time <= first_finished
    assert replay_started <= replay_time <= replay_finished
    assert first_time < replay_time
    assert first_ref != replay_ref
    for ref in (first_ref, replay_ref):
        manifest = ctx.store.get_manifest(ref.artifact_id)
        assert [(item.role, str(item.artifact_id)) for item in manifest.inputs] == [
            ("causal_graph", str(graph_ref.artifact_id))
        ]
    assert replay.state.params == first.state.params
    # Keeping the valid v1 artifact cannot authorize a missing current source.
    db_path.rename(tmp_path / "unavailable.duckdb")
    unavailable = node.execute(ctx, replay.state.model_copy(deep=True))
    assert unavailable.status == "skip"
    assert selections == 1


def test_changed_domain_invalidates_bundle_and_idempotency_key(tmp_path) -> None:
    """Domain participates in both bundle reuse and node idempotency identity."""
    ctx = _build_ctx(tmp_path, run_id="R_phase15_domain")
    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path)
    graph_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
    )
    state = ExperimentState(
        run_id="R_phase15_domain",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {
                "context_id": "UA",
                "income_level": "lower_middle",
                "institutional_quality": 0.4,
                "post_communist": True,
            },
            "required_parameters": ["fiscal_multiplier"],
            "skg_db_path": str(db_path),
            "skg_index_dir": str(tmp_path / "idx"),
            "domain": "fiscal",
        },
    )

    node = ResolveParametersNode()
    first = node.execute(ctx, state)
    assert first.status == "ok"
    first_ref = first.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]

    changed = first.state.model_copy(deep=True)
    changed.params["domain"] = "monetary"
    assert compute_idempotency_key(node.spec, first.state) != compute_idempotency_key(
        node.spec, changed
    )

    second = node.execute(ctx, changed)
    assert second.status == "ok"
    second_ref = second.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    assert second_ref != first_ref
    second_bundle = load_context_adaptive_parameter_bundle(ctx.store, second_ref)
    assert second_bundle.simulation_domain == "monetary"


def test_resolve_parameters_node_skips_on_missing_inputs(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_phase15_resolve_skip")
    state = ExperimentState(run_id="R_phase15_resolve_skip", params={})

    outcome = ResolveParametersNode().execute(ctx, state)

    assert outcome.status == "skip"
    assert outcome.events
    assert outcome.events[0].level == "warn"
