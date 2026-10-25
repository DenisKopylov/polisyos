from __future__ import annotations

import logging

import pytest

from polisyos.core.artifacts import (
    InputRef,
    input_ref_from_artifact_ref,
    profile_bound_ref,
)
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
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
from polisyos.ir.registry.refs import CausalGraphModelRef
from polisyos.scientist.compute.job_spec import JobKey, JobResult
from polisyos.scientist.nodes.builtins.causal.run_causal_ensemble import RunCausalEnsembleNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENSEMBLE_ENVELOPE_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


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
                source=MechanismSource.DEFAULT,
            )
        )

    return StructuralCausalModelSpec(
        graph=graph,
        mechanisms=mechanisms,
        fitted=False,
        fit_method="manual",
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


def _bound_test_input(store: FileSystemCAS, *, label: str) -> InputRef:
    source_ref = store.put_json(
        {"label": label},
        PutOptions(kind="test.selected_profile_anchor", media_type="application/json"),
    )
    return input_ref_from_artifact_ref(
        profile_bound_ref(store, source_ref), role="selected_profile_anchor"
    )


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
    scm_spec = _build_scm(graph=graph, coefficient_scale=1.2)
    ir_store = _ensure_ir_artifact_store(ctx.store)
    scm_ref = persist_structural_causal_model_spec(
        ir_store,
        scm_spec,
        inputs=[_bound_test_input(ctx.store, label="producer-input-selected")],
    )
    latest_scm_ref = persist_structural_causal_model_spec(
        ir_store,
        scm_spec,
        inputs=[_bound_test_input(ctx.store, label="producer-input-alternative")],
    )
    current_default_scm_ref = profile_bound_ref(
        ctx.store, scm_ref.model_copy(update={"manifest_profile_sha256": None})
    )
    assert str(scm_ref.artifact_id) == str(latest_scm_ref.artifact_id)
    assert ctx.store.get_bytes(scm_ref) == ctx.store.get_bytes(latest_scm_ref)
    assert scm_ref.manifest_profile_sha256 is not None
    assert latest_scm_ref.manifest_profile_sha256 is not None
    assert scm_ref.manifest_profile_sha256 != latest_scm_ref.manifest_profile_sha256
    selected_scm_ref = next(
        candidate_ref
        for candidate_ref in (scm_ref, latest_scm_ref)
        if candidate_ref.manifest_profile_sha256 != current_default_scm_ref.manifest_profile_sha256
    )
    assert selected_scm_ref.manifest_profile_sha256 is not None
    assert (
        selected_scm_ref.manifest_profile_sha256 != current_default_scm_ref.manifest_profile_sha256
    )
    scm_ref = selected_scm_ref

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
    ensemble = load_causal_model_ensemble(_ensure_ir_artifact_store(ctx.store), ensemble_ref)
    assert len(ensemble.members) == 1
    assert ensemble.members[0].discovery_method == "pc"
    assert outcome.state.params["causal_ensemble_member_count"] == 1

    manifest = ctx.store.get_manifest(ensemble_ref)
    scm_edges = [edge for edge in manifest.inputs if edge.role == "member_0.scm_ref"]
    assert len(scm_edges) == 1
    assert scm_edges[0].manifest_profile_sha256 == scm_ref.manifest_profile_sha256
    assert scm_edges[0].manifest_profile_sha256 != current_default_scm_ref.manifest_profile_sha256
    consensus_edges = [edge for edge in manifest.inputs if edge.role == "consensus_graph_ref"]
    assert ensemble.consensus_graph_ref is not None
    assert len(consensus_edges) == 1
    consensus_edge = consensus_edges[0]
    assert str(consensus_edge.artifact_id) == ensemble.consensus_graph_ref
    assert consensus_edge.manifest_profile_sha256 is not None
    selected_consensus_ref = CausalGraphModelRef.model_validate(
        {
            "artifact_id": str(consensus_edge.artifact_id),
            "kind": "ir.causal_graph_model",
            "media_type": "application/json",
            "manifest_profile_sha256": consensus_edge.manifest_profile_sha256,
        }
    )
    assert load_causal_graph_model(
        _ensure_ir_artifact_store(ctx.store), selected_consensus_ref
    ).nodes == ["X", "Y"]

    member_edges = [edge for edge in manifest.inputs if edge.role == "member_0.graph_ref"]
    assert len(member_edges) == 1
    assert member_edges[0].manifest_profile_sha256 is not None
    selected_member_ref = CausalGraphModelRef.model_validate(
        {
            "artifact_id": str(member_edges[0].artifact_id),
            "kind": "ir.causal_graph_model",
            "media_type": "application/json",
            "manifest_profile_sha256": member_edges[0].manifest_profile_sha256,
        }
    )
    member_graph_manifest = ctx.store.get_manifest(selected_member_ref)
    member_scm_edges = [
        edge for edge in member_graph_manifest.inputs if edge.role == "member_0.scm"
    ]
    assert len(member_scm_edges) == 1
    assert member_scm_edges[0].manifest_profile_sha256 == scm_ref.manifest_profile_sha256
    assert (
        member_scm_edges[0].manifest_profile_sha256
        != current_default_scm_ref.manifest_profile_sha256
    )
    assert load_causal_graph_model(
        _ensure_ir_artifact_store(ctx.store), selected_member_ref
    ).nodes == ["X", "Y"]


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
        _ensure_ir_artifact_store(ctx.store),
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
        _ensure_ir_artifact_store(ctx.store),
        outcome.state.artifacts_index[ARTIFACT_CAUSAL_ENSEMBLE_REF],
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
            _ensure_ir_artifact_store(ctx.store),
            _build_scm(graph=graph_a, coefficient_scale=0.8),
        ),
        persist_structural_causal_model_spec(
            _ensure_ir_artifact_store(ctx.store),
            _build_scm(graph=graph_b, coefficient_scale=1.1),
        ),
        persist_structural_causal_model_spec(
            _ensure_ir_artifact_store(ctx.store),
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
        _ensure_ir_artifact_store(ctx.store),
        outcome.state.artifacts_index[ARTIFACT_CAUSAL_ENSEMBLE_REF],
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
    consensus_graph = load_causal_graph_model(_ensure_ir_artifact_store(ctx.store), consensus_ref)
    consensus_edges = {(edge.src, edge.dst) for edge in consensus_graph.edges}
    assert consensus_edges == {("X", "M"), ("M", "Y"), ("X", "Y")}
