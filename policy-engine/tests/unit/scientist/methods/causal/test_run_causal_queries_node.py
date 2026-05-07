from __future__ import annotations

import logging

import pytest
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
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
from polisyos.scientist.compute.job_spec import JobKey, JobResult
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.causal.run_causal_queries import RunCausalQueriesNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_QUERY_ENVELOPE_REF,
    ARTIFACT_CAUSAL_QUERY_METHOD_EVIDENCE_REF,
    ARTIFACT_CAUSAL_QUERY_METHOD_RESULT_REF,
    ARTIFACT_CAUSAL_QUERY_RESULT_REF,
    ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF,
)


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
                source=MechanismSource.DATA_FITTED,
            )
        ],
        fitted=True,
        fit_method="gcm",
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


def test_run_causal_queries_node_success_persists_artifacts_and_dual_writes(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_query_ok")
    scm_ref = persist_structural_causal_model_spec(ctx.store, _minimal_scm())

    method_result_ref = ctx.store.put_json(
        {"slot": "result"},
        PutOptions(
            kind="scientist.method_result.test",
            media_type="application/json",
            schema=SchemaInfo(name="test.MethodResult", version="1.0"),
        ),
    )
    method_evidence_ref = ctx.store.put_json(
        {"slot": "evidence"},
        PutOptions(
            kind="scientist.method_evidence.test",
            media_type="application/json",
            schema=SchemaInfo(name="test.MethodEvidence", version="1.0"),
        ),
    )

    def _fake_run_job(*args, **kwargs):
        del args, kwargs
        return JobResult(
            job_key=JobKey(value="job:test:gcm_query"),
            final_state={
                "query_result": {
                    "query": {
                        "query_type": "interventional",
                        "treatment_variable": "X",
                        "treatment_value": 1.0,
                        "outcome_variable": "Y",
                        "condition": {},
                        "n_samples": 128,
                        "intervention_spec": None,
                    },
                    "result_mean": 0.95,
                    "result_std": 0.12,
                    "result_ci": [0.71, 1.20],
                    "result_distribution": [0.8, 1.0, 1.05],
                    "computation_time_seconds": 0.01,
                },
                "warnings": [],
            },
            method_result_ref=method_result_ref,
            method_evidence_ref=method_evidence_ref,
            issues=[],
        )

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_queries.ensure_causal_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_queries.run_job",
        _fake_run_job,
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
    assert outcome.status == "ok"

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
