from __future__ import annotations

import logging

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
    persist_structural_causal_model_spec,
)
from polisyos.scientist.nodes.builtins.causal.run_causal_queries import RunCausalQueriesNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_QUERY_ENVELOPE_REF,
    ARTIFACT_CAUSAL_QUERY_METHOD_EVIDENCE_REF,
    ARTIFACT_CAUSAL_QUERY_METHOD_RESULT_REF,
    ARTIFACT_CAUSAL_QUERY_RESULT_REF,
    ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _build_ctx(tmp_path, *, run_id: str) -> ExecutionContext:
    from polisyos.core.artifacts.store import FileSystemCAS

    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(f"test.{run_id}"))


def _minimal_scm() -> StructuralCausalModelSpec:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    return StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="Y",
                parents=["X"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.0,
                    "coefficients": {"X": 1.0},
                    "noise_std": 0.05,
                },
                source=MechanismSource.DEFAULT,
            )
        ],
        fitted=False,
        fit_method="manual",
    )


def test_run_causal_queries_node_skips_without_query(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_query_skip_query")
    state = ExperimentState(run_id="R_query_skip_query")

    outcome = RunCausalQueriesNode().execute(ctx, state)
    assert outcome.status == "skip"


def test_run_causal_queries_node_skips_without_structural_model(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_query_skip_scm")
    state = ExperimentState(
        run_id="R_query_skip_scm",
        params={
            "causal_query": {
                "query_type": "interventional",
                "treatment_variable": "X",
                "treatment_value": 1.0,
                "outcome_variable": "Y",
                "n_samples": 128,
            }
        },
    )

    outcome = RunCausalQueriesNode().execute(ctx, state)
    assert outcome.status == "skip"


def test_run_causal_queries_node_success_persists_artifacts_and_dual_writes(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_query_ok")
    scm_ref = persist_structural_causal_model_spec(
        _ensure_ir_artifact_store(ctx.store), _minimal_scm()
    )

    state = ExperimentState(
        run_id="R_query_ok",
        params={
            "random_seed": 7,
            "causal_query": {
                "query_type": "interventional",
                "treatment_variable": "X",
                "treatment_value": 1.0,
                "outcome_variable": "Y",
                "n_samples": 128,
            },
            "structural_causal_model_ref": scm_ref.model_dump(mode="json"),
        },
    )

    outcome = RunCausalQueriesNode().execute(ctx, state)
    assert outcome.status == "ok", outcome.error

    artifacts = outcome.state.artifacts_index
    assert outcome.state.params.get("query_treatment") == "X"
    assert ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF in artifacts
    assert ARTIFACT_CAUSAL_QUERY_RESULT_REF in artifacts
    assert ARTIFACT_CAUSAL_QUERY_ENVELOPE_REF in artifacts
    assert ARTIFACT_CAUSAL_QUERY_METHOD_RESULT_REF in artifacts
    assert ARTIFACT_CAUSAL_QUERY_METHOD_EVIDENCE_REF in artifacts
    assert ARTIFACT_CAUSAL_ENVELOPE_REF in artifacts
    assert (
        artifacts[ARTIFACT_CAUSAL_QUERY_ENVELOPE_REF].artifact_id
        == artifacts[ARTIFACT_CAUSAL_ENVELOPE_REF].artifact_id
    )
