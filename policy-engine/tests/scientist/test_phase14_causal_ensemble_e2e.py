from __future__ import annotations

import logging

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    load_causal_effect_report,
    persist_causal_effect_report,
)
from polisyos.ir.analytics.causal_ensemble import load_causal_model_ensemble
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
    persist_structural_causal_model_spec,
)
from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
from polisyos.scientist.compute.job_spec import JobKey, JobResult
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.causal.resolve_transport import RunTransportabilityNode
from polisyos.scientist.nodes.builtins.causal.run_causal_ensemble import RunCausalEnsembleNode
from polisyos.scientist.nodes.builtins.causal.run_causal_queries import RunCausalQueriesNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_QUERY_ENVELOPE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF,
)


def _build_ctx(tmp_path, *, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(f"test.{run_id}"))


def _diamond_graph(method: str) -> CausalGraphModel:
    base_edges = [
        CausalEdge(src="X", dst="M"),
        CausalEdge(src="X", dst="N"),
    ]
    if method in {"pc", "fci"}:
        base_edges.append(CausalEdge(src="M", dst="Y"))
    if method in {"pc", "ges"}:
        base_edges.append(CausalEdge(src="N", dst="Y"))
    return CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "M", "N", "Y"],
        edges=base_edges,
        discovery_method=method,
    )


def _scm_for_graph(graph: CausalGraphModel, coef: float) -> StructuralCausalModelSpec:
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
                    "coefficients": dict.fromkeys(parents, coef),
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


def _fake_run_job(*args, **kwargs):
    del args
    method_state = kwargs["method_state"]
    method = method_state.scm_spec.graph.discovery_method or "pc"
    means = {"pc": 1.0, "fci": 2.0, "ges": 3.0}
    mean = means.get(method, 1.0)
    query_payload = method_state.query.model_dump(mode="json")
    return JobResult(
        job_key=JobKey(value=f"job:test:gcm_query:{method}"),
        final_state={
            "query_result": {
                "query": query_payload,
                "result_mean": mean,
                "result_std": 0.05,
                "result_ci": [mean - 0.05, mean + 0.05],
                "result_distribution": [mean - 0.03, mean, mean + 0.03],
                "computation_time_seconds": 0.01,
            }
        },
        issues=[],
    )


def test_phase14_causal_ensemble_full_e2e_acceptance(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_phase14_e2e")

    scm_refs = {}
    for method, coef in (("pc", 1.0), ("fci", 2.0), ("ges", 3.0)):
        graph = _diamond_graph(method)
        scm_refs[method] = persist_structural_causal_model_spec(
            ctx.store,
            _scm_for_graph(graph, coef=coef),
        )

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_queries.ensure_causal_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.ensure_causal_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_queries.run_job",
        _fake_run_job,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.run_job",
        _fake_run_job,
    )

    query_payload = {
        "query_type": "interventional",
        "treatment_variable": "X",
        "treatment_value": 1.0,
        "outcome_variable": "Y",
        "n_samples": 64,
    }

    state = ExperimentState(
        run_id="R_phase14_e2e",
        artifacts_index={ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF: scm_refs["pc"]},
        params={
            "causal_query": query_payload,
            "structural_causal_model_ref": scm_refs["pc"].model_dump(mode="json"),
        },
    )
    query_outcome = RunCausalQueriesNode().execute(ctx, state)
    assert query_outcome.status == "ok"

    single_envelope_ref = query_outcome.state.artifacts_index[ARTIFACT_CAUSAL_QUERY_ENVELOPE_REF]
    single_envelope = load_uncertainty_envelope(ctx.store, single_envelope_ref)
    single_width = single_envelope.confidence_interval[1] - single_envelope.confidence_interval[0]

    ensemble_state = query_outcome.state.model_copy(deep=True)
    ensemble_state.params["causal_ensemble_enabled"] = True
    ensemble_state.params["causal_ensemble_members"] = [
        {
            "structural_causal_model_spec_ref": scm_refs["pc"].model_dump(mode="json"),
            "discovery_method": "pc",
        },
        {
            "structural_causal_model_spec_ref": scm_refs["fci"].model_dump(mode="json"),
            "discovery_method": "fci",
        },
        {
            "structural_causal_model_spec_ref": scm_refs["ges"].model_dump(mode="json"),
            "discovery_method": "ges",
        },
    ]
    ensemble_outcome = RunCausalEnsembleNode().execute(ctx, ensemble_state)
    assert ensemble_outcome.status == "ok"

    ensemble_ref = ensemble_outcome.state.artifacts_index[ARTIFACT_CAUSAL_ENSEMBLE_REF]
    ensemble = load_causal_model_ensemble(ctx.store, ensemble_ref)
    assert len(ensemble.members) == 3
    assert pytest.approx(ensemble.edge_inclusion_frequency["M→Y"], rel=1e-6) == (2.0 / 3.0)
    assert pytest.approx(ensemble.edge_inclusion_frequency["N→Y"], rel=1e-6) == (2.0 / 3.0)

    assert (
        ensemble_outcome.state.artifacts_index[ARTIFACT_CAUSAL_ENVELOPE_REF].artifact_id
        != single_envelope_ref.artifact_id
    )
    ensemble_envelope = load_uncertainty_envelope(
        ctx.store,
        ensemble_outcome.state.artifacts_index[ARTIFACT_CAUSAL_ENVELOPE_REF],
    )
    ensemble_width = (
        ensemble_envelope.confidence_interval[1] - ensemble_envelope.confidence_interval[0]
    )
    assert ensemble_width > single_width

    report_ref = persist_causal_effect_report(
        ctx.store,
        CausalEffectReport(
            method=CausalMethod.DOWHY_BACKDOOR,
            status=EstimationStatus.SUCCESS,
            estimand="ATE",
            point_estimate=1.0,
            confidence_interval=(0.9, 1.1),
            inference_method="backdoor.linear_regression",
            sample_size=120,
            n_treated=60,
            n_control=60,
            pre_periods=0,
            post_periods=0,
            method_params={"query_treatment": "X", "query_outcome": "Y"},
        ),
    )
    transport_state = ensemble_outcome.state.model_copy(deep=True)
    transport_state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF] = report_ref
    transport_state.params["source_context"] = {"context_id": "DE", "income_level": "high"}
    transport_state.params["target_context"] = {
        "context_id": "UA",
        "income_level": "lower_middle",
    }
    transport_state.params["pag_identification_policy"] = "probabilistic"

    transport_outcome = RunTransportabilityNode().execute(ctx, transport_state)
    assert transport_outcome.status == "ok"

    updated_report_ref = transport_outcome.state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    updated_report = load_causal_effect_report(ctx.store, updated_report_ref)
    assert updated_report.transport_result is not None
    assert updated_report.transport_result.id_confidence_under_pag is not None
