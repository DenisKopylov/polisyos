from __future__ import annotations

import json
import logging

import duckdb

import polisyos.data_forge.read_api.academic as academic_read_api
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import ComponentId
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.data_forge.read_api.academic import SKGQuery
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.parameters import load_context_adaptive_parameter_bundle
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.idempotency import compute_idempotency_key
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
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


def _seed_skg(db_path, *, version_id: int = 12, fiscal_value: float = 1.35) -> None:
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
        con.execute("INSERT INTO ac_skg_versions VALUES (?)", [version_id])
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
                            "value": fiscal_value,
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


def _bind_owner_snapshot(state: ExperimentState, db_path) -> ExperimentState:
    """Build the effective state from the real SKG owner before cache admission."""
    skg_query = SKGQuery(db_path=db_path, index_dir=db_path.parent / "idx")
    try:
        version_id = skg_query.latest_skg_version_id()
        snapshot_ref = skg_query.skg_snapshot_ref(version_id=version_id)
    finally:
        skg_query.close()

    assert version_id is not None
    assert snapshot_ref is not None
    bound = state.model_copy(deep=True)
    bound.params["skg_snapshot_ref"] = snapshot_ref
    bound.params["skg_version_id"] = version_id
    return bound


def _snapshot_bundle(ctx: ExecutionContext, result) -> object:
    return load_context_adaptive_parameter_bundle(
        ctx.store,
        result.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF],
    )


def _trace_events(ctx: ExecutionContext) -> list[dict[str, object]]:
    trace_ref = ctx.run.run_manifest.trace_ref
    assert trace_ref is not None
    payload = ctx.store.get_bytes(trace_ref.artifact_id).decode("utf-8")
    return [json.loads(line) for line in payload.splitlines() if line.strip()]


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


def test_resolve_parameters_node_skips_on_missing_inputs(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_phase15_resolve_skip")
    state = ExperimentState(run_id="R_phase15_resolve_skip", params={})

    outcome = ResolveParametersNode().execute(ctx, state)

    assert outcome.status == "skip"
    assert outcome.events
    assert outcome.events[0].level == "warn"


def test_same_skg_path_binds_version_snapshot_to_idempotency_key(tmp_path) -> None:
    """Live replacement misses and a pinned source snapshot replays safely."""
    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path, version_id=12, fiscal_value=1.35)
    frozen_db_path = tmp_path / "skg-v12-frozen.duckdb"
    frozen_db_path.write_bytes(db_path.read_bytes())

    ctx_a = _build_ctx(tmp_path, run_id="R_phase15_snapshot_identity")

    graph_ref = persist_causal_graph_model(
        ctx_a.store,
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
    )

    def _base_state(*, run_id: str, source_path) -> ExperimentState:
        return ExperimentState(
            run_id=run_id,
            artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
            params={
                "target_context": {
                    "context_id": "UA",
                    "income_level": "lower_middle",
                    "institutional_quality": 0.4,
                    "post_communist": True,
                },
                "required_parameters": ["fiscal_multiplier"],
                "skg_db_path": str(source_path),
                "skg_index_dir": str(tmp_path / "idx"),
                "domain": "fiscal",
            },
        )

    live_state_a = _bind_owner_snapshot(
        _base_state(run_id="R_phase15_snapshot_identity", source_path=db_path),
        db_path,
    )
    workflow = WorkflowSpec(
        workflow_id="resolve_parameters_snapshot_identity",
        nodes=[
            NodeInvocation(
                alias="resolve_parameters",
                node_id=ComponentId.parse("scientist.node_resolve_parameters@1.0.0"),
            )
        ],
    )
    registry = NodeRegistry()
    registry.register(ResolveParametersNode())

    result_a = WorkflowExecutor(ctx_a, registry).execute(workflow, live_state_a)
    assert result_a.report.status == "ok"
    bundle_a = _snapshot_bundle(ctx_a, result_a)

    db_path.unlink()
    _seed_skg(db_path, version_id=13, fiscal_value=2.4)
    live_state_b = _bind_owner_snapshot(
        _base_state(run_id="R_phase15_snapshot_identity", source_path=db_path),
        db_path,
    )
    ctx_b = _build_ctx(tmp_path, run_id="R_phase15_snapshot_identity")
    result_b = WorkflowExecutor(ctx_b, registry).execute(workflow, live_state_b)
    assert result_b.report.status == "ok"
    bundle_b = _snapshot_bundle(ctx_b, result_b)

    frozen_state = _bind_owner_snapshot(
        _base_state(run_id="R_phase15_snapshot_frozen", source_path=frozen_db_path),
        frozen_db_path,
    )
    ctx_frozen_a = _build_ctx(tmp_path, run_id="R_phase15_snapshot_frozen")
    result_frozen_a = WorkflowExecutor(ctx_frozen_a, registry).execute(workflow, frozen_state)
    assert result_frozen_a.report.status == "ok"
    bundle_frozen_a = _snapshot_bundle(ctx_frozen_a, result_frozen_a)

    ctx_frozen_b = _build_ctx(tmp_path, run_id="R_phase15_snapshot_frozen")
    result_frozen_b = WorkflowExecutor(ctx_frozen_b, registry).execute(
        workflow,
        frozen_state.model_copy(deep=True),
    )
    assert result_frozen_b.report.status == "ok"
    bundle_frozen_b = _snapshot_bundle(ctx_frozen_b, result_frozen_b)

    key_a = compute_idempotency_key(ResolveParametersNode().spec, live_state_a)
    key_b = compute_idempotency_key(ResolveParametersNode().spec, live_state_b)
    key_frozen_a = compute_idempotency_key(ResolveParametersNode().spec, frozen_state)
    key_frozen_b = compute_idempotency_key(
        ResolveParametersNode().spec,
        frozen_state.model_copy(deep=True),
    )

    assert bundle_a.skg_snapshot_ref == live_state_a.params["skg_snapshot_ref"]
    assert bundle_b.skg_snapshot_ref == live_state_b.params["skg_snapshot_ref"]
    assert bundle_a.skg_snapshot_ref != bundle_b.skg_snapshot_ref
    assert bundle_a.parameters["fiscal_multiplier"].value != bundle_b.parameters[
        "fiscal_multiplier"
    ].value
    assert key_a != key_b
    assert key_frozen_a == key_frozen_b
    assert bundle_frozen_a.skg_snapshot_ref == frozen_state.params["skg_snapshot_ref"]
    assert bundle_frozen_b.skg_snapshot_ref == frozen_state.params["skg_snapshot_ref"]
    assert bundle_frozen_b.parameters["fiscal_multiplier"].value == 1.35
    assert any(event.get("event") == "NODE_CACHE_HIT" for event in _trace_events(ctx_frozen_b))


def test_skg_key_and_read_share_one_content_bound_snapshot(tmp_path, monkeypatch) -> None:
    """A replacement after key admission must not be read under the old key."""
    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path, version_id=12, fiscal_value=1.35)
    ctx = _build_ctx(tmp_path, run_id="R_phase15_snapshot_content_bound")
    graph_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
    )
    state = ExperimentState(
        run_id="R_phase15_snapshot_content_bound",
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
    workflow = WorkflowSpec(
        workflow_id="resolve_parameters_snapshot_content_bound",
        nodes=[
            NodeInvocation(
                alias="resolve_parameters",
                node_id=ComponentId.parse("scientist.node_resolve_parameters@1.0.0"),
            )
        ],
    )
    registry = NodeRegistry()
    registry.register(ResolveParametersNode())
    admission: dict[str, object] = {}
    real_skg_query = SKGQuery

    class InterposedSKGQuery(real_skg_query):
        """Replace the same source only after the owner has admitted its identity."""

        def latest_skg_version_id(self):
            version_id = super().latest_skg_version_id()
            admission["version_id"] = version_id
            return version_id

        def skg_snapshot_ref(self, *, version_id=None):
            snapshot_ref = super().skg_snapshot_ref(version_id=version_id)
            admission["snapshot_ref"] = snapshot_ref
            return snapshot_ref

        def close(self):
            super().close()
            if not admission.get("replaced"):
                admission["replaced"] = True
                db_path.unlink()
                _seed_skg(db_path, version_id=13, fiscal_value=2.4)

    monkeypatch.setattr(academic_read_api, "SKGQuery", InterposedSKGQuery)
    result = WorkflowExecutor(ctx, registry).execute(workflow, state)

    assert admission == {
        "version_id": 12,
        "snapshot_ref": f"duckdb://{db_path}#v12",
        "replaced": True,
    }
    assert result.report.nodes[0].status != "ok" or (
        (bundle := _snapshot_bundle(ctx, result)).skg_version_id == 12
        and bundle.parameters["fiscal_multiplier"].value == 1.35
    )


def test_prebound_skg_snapshot_without_provenance_cannot_replay_after_replacement(tmp_path) -> None:
    """A stale pre-bound identity must not authorize a frozen cache replay."""
    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path, version_id=12, fiscal_value=1.35)
    ctx_first = _build_ctx(tmp_path, run_id="R_phase15_snapshot_unverified")
    graph_ref = persist_causal_graph_model(
        ctx_first.store,
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
    )

    def _state() -> ExperimentState:
        return ExperimentState(
            run_id="R_phase15_snapshot_unverified",
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

    workflow = WorkflowSpec(
        workflow_id="resolve_parameters_snapshot_unverified",
        nodes=[
            NodeInvocation(
                alias="resolve_parameters",
                node_id=ComponentId.parse("scientist.node_resolve_parameters@1.0.0"),
            )
        ],
    )
    registry = NodeRegistry()
    registry.register(ResolveParametersNode())
    first_state = _bind_owner_snapshot(_state(), db_path)
    result_first = WorkflowExecutor(ctx_first, registry).execute(workflow, first_state)
    assert result_first.report.status == "ok"

    db_path.unlink()
    _seed_skg(db_path, version_id=13, fiscal_value=2.4)
    stale_state = _state()
    stale_state.params["skg_snapshot_ref"] = first_state.params["skg_snapshot_ref"]
    stale_state.params["skg_version_id"] = first_state.params["skg_version_id"]
    ctx_after = _build_ctx(tmp_path, run_id="R_phase15_snapshot_unverified")
    result_after = WorkflowExecutor(ctx_after, registry).execute(workflow, stale_state)

    assert result_after.report.nodes[0].status != "ok" or (
        (bundle_after := _snapshot_bundle(ctx_after, result_after)).skg_version_id == 13
        and bundle_after.parameters["fiscal_multiplier"].value == 2.4
    )
