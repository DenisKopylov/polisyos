from __future__ import annotations

import logging

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.causal_ensemble import load_causal_model_ensemble
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    load_causal_graph_model,
)
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
    persist_structural_causal_model_spec,
)
from polisyos.ir.refs import CausalGraphModelRef
from polisyos.scientist.compute.job_spec import JobKey, JobResult
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.causal.run_causal_ensemble import RunCausalEnsembleNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENSEMBLE_ENVELOPE_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF,
)


def _build_ctx(tmp_path, *, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(f"test.{run_id}"))


def _build_scm(
    *,
    graph: CausalGraphModel,
    coefficient_scale: float,
) -> StructuralCausalModelSpec:
    parents_by_node: dict[str, list[str]] = {node: [] for node in graph.nodes}
    for edge in graph.edges:
        parents_by_node.setdefault(edge.dst, []).append(edge.src)

    mechanisms: list[NodeMechanism] = []
    for node, parents in parents_by_node.items():
        if not parents:
            continue
        mechanisms.append(
            NodeMechanism(
                variable=node,
                parents=parents,
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.0,
                    "coefficients": {parent: float(coefficient_scale) for parent in parents},
                    "noise_std": 0.05,
                },
                source=MechanismSource.DATA_FITTED,
            )
        )

    return StructuralCausalModelSpec(
        graph=graph,
        mechanisms=mechanisms,
        fitted=True,
        fit_method="gcm",
    )


def _fake_run_job_factory() -> callable:
    def _fake_run_job(*args, **kwargs):
        del args
        method_state = kwargs["method_state"]
        coef = 1.0
        for mechanism in method_state.scm_spec.mechanisms:
            coefficients = mechanism.family_params.get("coefficients", {})
            if isinstance(coefficients, dict) and coefficients:
                coef = float(next(iter(coefficients.values())))
                break
        query = method_state.query.model_dump(mode="json")
        mean = float(coef)
        return JobResult(
            job_key=JobKey(value="job:test:gcm_query"),
            final_state={
                "query_result": {
                    "query": query,
                    "result_mean": mean,
                    "result_std": 0.1,
                    "result_ci": [mean - 0.2, mean + 0.2],
                    "result_distribution": [mean - 0.1, mean, mean + 0.1],
                    "computation_time_seconds": 0.01,
                }
            },
            issues=[],
        )

    return _fake_run_job


def test_run_causal_ensemble_node_skips_without_enable_flag(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_ensemble_skip")
    state = ExperimentState(
        run_id="R_ensemble_skip",
        params={
            "causal_query": {
                "query_type": "interventional",
                "treatment_variable": "X",
                "treatment_value": 1.0,
                "outcome_variable": "Y",
                "n_samples": 64,
            }
        },
    )

    outcome = RunCausalEnsembleNode().execute(ctx, state)
    assert outcome.status == "skip"


def test_run_causal_ensemble_node_persists_ensemble_and_dual_writes_envelope(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_ensemble_ok")
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
        discovery_method="pc",
    )
    scm_ref = persist_structural_causal_model_spec(
        ctx.store,
        _build_scm(graph=graph, coefficient_scale=1.2),
    )

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.ensure_causal_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.run_job",
        _fake_run_job_factory(),
    )

    state = ExperimentState(
        run_id="R_ensemble_ok",
        artifacts_index={ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF: scm_ref},
        params={
            "causal_ensemble_enabled": True,
            "causal_query": {
                "query_type": "interventional",
                "treatment_variable": "X",
                "treatment_value": 1.0,
                "outcome_variable": "Y",
                "n_samples": 64,
            },
            "causal_ensemble_members": [
                {
                    "structural_causal_model_spec_ref": scm_ref.model_dump(mode="json"),
                    "discovery_method": "pc",
                }
            ],
        },
    )

    outcome = RunCausalEnsembleNode().execute(ctx, state)
    assert outcome.status == "ok"

    artifacts = outcome.state.artifacts_index
    assert ARTIFACT_CAUSAL_ENSEMBLE_REF in artifacts
    assert ARTIFACT_CAUSAL_ENSEMBLE_ENVELOPE_REF in artifacts
    assert ARTIFACT_CAUSAL_ENVELOPE_REF in artifacts
    assert (
        artifacts[ARTIFACT_CAUSAL_ENSEMBLE_ENVELOPE_REF].artifact_id
        == artifacts[ARTIFACT_CAUSAL_ENVELOPE_REF].artifact_id
    )

    ensemble_ref = artifacts[ARTIFACT_CAUSAL_ENSEMBLE_REF]
    ensemble = load_causal_model_ensemble(ctx.store, ensemble_ref)
    assert len(ensemble.members) == 1
    assert ensemble.members[0].discovery_method == "pc"
    assert outcome.state.params["causal_ensemble_member_count"] == 1


def test_run_causal_ensemble_node_applies_budget_cap_10(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_ensemble_cap")
    base_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
        discovery_method="ges",
    )
    scm_ref = persist_structural_causal_model_spec(
        ctx.store,
        _build_scm(graph=base_graph, coefficient_scale=1.0),
    )

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.ensure_causal_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.run_job",
        _fake_run_job_factory(),
    )

    members = [
        {
            "structural_causal_model_spec_ref": scm_ref.model_dump(mode="json"),
            "discovery_method": f"m{i}",
            "explicit_weight": float(1.0 - (i / 20.0)),
        }
        for i in range(12)
    ]
    state = ExperimentState(
        run_id="R_ensemble_cap",
        params={
            "causal_ensemble_enabled": True,
            "causal_query": {
                "query_type": "interventional",
                "treatment_variable": "X",
                "treatment_value": 1.0,
                "outcome_variable": "Y",
                "n_samples": 32,
            },
            "causal_ensemble_members": members,
        },
    )

    outcome = RunCausalEnsembleNode().execute(ctx, state)
    assert outcome.status == "ok"
    ensemble = load_causal_model_ensemble(
        ctx.store, outcome.state.artifacts_index[ARTIFACT_CAUSAL_ENSEMBLE_REF]
    )
    assert len(ensemble.members) == 10
    assert "deterministic cap applied" in str(
        outcome.state.params.get("causal_ensemble_warning", "")
    )


def test_run_causal_ensemble_node_builds_consensus_graph_from_three_members(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_ensemble_consensus")
    graph_a = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "M", "Y"],
        edges=[CausalEdge(src="X", dst="M"), CausalEdge(src="M", dst="Y")],
        discovery_method="pc",
    )
    graph_b = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "M", "Y"],
        edges=[CausalEdge(src="X", dst="M"), CausalEdge(src="X", dst="Y")],
        discovery_method="fci",
    )
    graph_c = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "M", "Y"],
        edges=[CausalEdge(src="M", dst="Y"), CausalEdge(src="X", dst="Y")],
        discovery_method="ges",
    )
    scm_refs = [
        persist_structural_causal_model_spec(
            ctx.store,
            _build_scm(graph=graph_a, coefficient_scale=0.8),
        ),
        persist_structural_causal_model_spec(
            ctx.store,
            _build_scm(graph=graph_b, coefficient_scale=1.1),
        ),
        persist_structural_causal_model_spec(
            ctx.store,
            _build_scm(graph=graph_c, coefficient_scale=1.4),
        ),
    ]

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.ensure_causal_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.run_job",
        _fake_run_job_factory(),
    )

    state = ExperimentState(
        run_id="R_ensemble_consensus",
        params={
            "causal_ensemble_enabled": True,
            "causal_query": {
                "query_type": "interventional",
                "treatment_variable": "X",
                "treatment_value": 1.0,
                "outcome_variable": "Y",
                "n_samples": 64,
            },
            "causal_ensemble_members": [
                {
                    "structural_causal_model_spec_ref": ref.model_dump(mode="json"),
                    "discovery_method": method,
                }
                for ref, method in zip(scm_refs, ("pc", "fci", "ges"), strict=True)
            ],
        },
    )

    outcome = RunCausalEnsembleNode().execute(ctx, state)
    assert outcome.status == "ok"

    ensemble = load_causal_model_ensemble(
        ctx.store, outcome.state.artifacts_index[ARTIFACT_CAUSAL_ENSEMBLE_REF]
    )
    assert len(ensemble.members) == 3
    assert ensemble.consensus_graph_ref is not None
    assert pytest.approx(ensemble.edge_inclusion_frequency["X→M"], rel=1e-6) == (2.0 / 3.0)
    assert pytest.approx(ensemble.edge_inclusion_frequency["M→Y"], rel=1e-6) == (2.0 / 3.0)
    assert pytest.approx(ensemble.edge_inclusion_frequency["X→Y"], rel=1e-6) == (2.0 / 3.0)

    consensus_ref = CausalGraphModelRef.model_validate(
        {
            "artifact_id": ensemble.consensus_graph_ref,
            "kind": "ir.causal_graph_model",
            "media_type": "application/json",
        }
    )
    consensus_graph = load_causal_graph_model(ctx.store, consensus_ref)
    consensus_edges = {(edge.src, edge.dst) for edge in consensus_graph.edges}
    assert consensus_edges == {("X", "M"), ("M", "Y"), ("X", "Y")}
