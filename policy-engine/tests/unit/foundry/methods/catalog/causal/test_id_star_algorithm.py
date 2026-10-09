from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

import numpy as np

from polisyos.core.artifacts import artifact_manifest_profile_sha256, ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.estimand_compiler import compile_estimand
from polisyos.foundry.methods.catalog.causal.id_engine import (
    CtfQuery,
    IdentificationStatus,
    id_star_algorithm,
    idc_star_algorithm,
)
from polisyos.foundry.methods.catalog.causal.protocols import SCMFitData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import load_proof_bundle
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.estimand import CrossWorldNode, NestedCounterfactualNode, RatioNode
from polisyos.ir.analytics.evidence_bundle import load_causal_evidence_bundle
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    NodeMechanism,
    SCMTrainingRows,
    StructuralCausalModelSpec,
    _payload_digest,
)
from polisyos.ir.analytics.twin_network import TwinNetworkResult, load_twin_network_result
from polisyos.ir.registry.refs import ArtifactRefModel


def _edge(src: str, dst: str, *, bidirected: bool = False) -> CausalEdge:
    if bidirected:
        return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)


def _graph(nodes: list[str], edges: list[CausalEdge]) -> CausalGraphModel:
    return CausalGraphModel(graph_type=GraphType.ADMG, nodes=nodes, edges=edges)


def test_id_star_simple_backdoor_reduces_to_id() -> None:
    graph = _graph(
        ["X", "Y", "Z"],
        [_edge("Z", "X"), _edge("Z", "Y"), _edge("X", "Y")],
    )
    query = CtfQuery(
        outcome="Y", intervention=(("X", 1.0),), conditioning=("Z",), kind="single_world"
    )
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert any(step.rule_name == "ID_STAR_STEP3" for step in result.proof_steps)


def test_id_star_bow_arc_non_identifiable() -> None:
    graph = _graph(
        ["X", "Y"],
        [_edge("X", "Y"), _edge("X", "Y", bidirected=True)],
    )
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world")
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.HEDGE_FOUND
    assert result.hedge_certificate is not None


def test_id_star_ett_query() -> None:
    graph = _graph(
        ["X", "Y", "Z"],
        [_edge("Z", "X"), _edge("Z", "Y"), _edge("X", "Y")],
    )
    query = CtfQuery(
        outcome="Y",
        intervention=(("X", 1.0),),
        evidence=(("X", 1.0),),
        kind="ett",
    )
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED


def test_id_star_pn_query() -> None:
    graph = _graph(["X", "Y"], [_edge("X", "Y")])
    query = CtfQuery(
        outcome="Y",
        intervention=(("X", 1.0),),
        evidence=(("Y", 1.0),),
        kind="pn",
    )
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    assert result.estimand_ast.query_str == "P(Y_{X=0} | X=1, Y=1)"


def test_id_star_pns_query_uses_cross_world_ast() -> None:
    graph = _graph(["X", "Y"], [_edge("X", "Y")])
    query = CtfQuery(
        outcome="Y",
        intervention=(("X", 1.0),),
        reference_intervention=(("X", 0.0),),
        kind="pns",
    )
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    assert result.estimand_ast.query_str == "P(Y_{X=1}, Y_{X=0})"
    assert isinstance(result.estimand_ast.root, CrossWorldNode)
    assert len(result.estimand_ast.root.worlds) == 2
    interventions = [world.intervention for world in result.estimand_ast.root.worlds]
    assert {"X": 1.0} in interventions
    assert {"X": 0.0} in interventions


def test_id_star_frontdoor_ctf() -> None:
    graph = _graph(
        ["X", "M", "Y"],
        [_edge("X", "M"), _edge("M", "Y"), _edge("X", "Y", bidirected=True)],
    )
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), mediators=("M",), kind="frontdoor")
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED


def test_id_star_napkin_graph() -> None:
    graph = _graph(
        ["X", "M", "Y", "U"],
        [_edge("X", "M"), _edge("M", "Y"), _edge("U", "X"), _edge("U", "Y")],
    )
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), mediators=("M",), kind="napkin")
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED


def test_id_star_proof_steps_complete() -> None:
    graph = _graph(["X", "Y"], [_edge("X", "Y")])
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="proof")
    result = id_star_algorithm(query, graph)
    rule_names = {step.rule_name for step in result.proof_steps}
    assert {"ID_STAR_STEP1", "ID_STAR_STEP2", "ID_STAR_STEP3", "ID_STAR_STEP5"} <= rule_names


def test_id_star_nested_ctf() -> None:
    graph = _graph(["X", "Y"], [_edge("X", "Y")])
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="nested")
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    assert isinstance(result.estimand_ast.root, NestedCounterfactualNode)


def test_idc_star_ratio_of_two_calls() -> None:
    graph = _graph(["X", "Y", "Z"], [_edge("Z", "X"), _edge("Z", "Y"), _edge("X", "Y")])
    query = CtfQuery(
        outcome="Y",
        intervention=(("X", 1.0),),
        conditioning=("Z",),
        evidence=(("X", 1.0),),
        kind="ett",
    )
    result = idc_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    assert isinstance(result.estimand_ast.root, RatioNode)
    assert result.query_str == "P(Y_{X=1} | X=1, Z)"


def test_counterfactual_identification_compiles_to_counterfactual_executor() -> None:
    graph = _graph(["X", "Y"], [_edge("X", "Y")])
    engine = CausalEngine()
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world")
    result = engine.identify("X", "Y", graph, counterfactual_query=query)
    assert not isinstance(result, dict)
    assert result.status is IdentificationStatus.IDENTIFIED
    _, executor_graph = compile_estimand(  # type: ignore[arg-type]
        result.estimand_ast,
        run_id="test-id-star",
    )
    assert any("twin_network_query" in node.method_fqn for node in executor_graph.nodes)


def test_counterfactual_run_persists_and_reads_typed_twin_network_result(tmp_path) -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[_edge("X", "Y")],
    )
    store = FileSystemCAS(tmp_path / "cas")
    ir_store = ensure_ir_artifact_store(store)
    rng = np.random.default_rng(7)
    x = rng.binomial(1, 0.5, 300).astype(float)
    y = 0.5 + 1.75 * x + 0.1 * rng.standard_normal(300)
    source_data = SCMFitData(
        data=np.column_stack([x, y]),
        column_names=["X", "Y"],
        graph=graph,
        metadata={"input_scope": "known_synthetic_dgp"},
    )
    source_ref = store.put_json(
        source_data.model_dump(mode="json"),
        PutOptions(
            kind="tests.scm_fit_data",
            media_type="application/json",
            schema=SchemaInfo(name="tests.SCMFitData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    source_profile = artifact_manifest_profile_sha256(store.get_manifest(source_ref))
    source_bytes = store.get_bytes(source_ref)
    source_ref = ArtifactRefModel.model_validate(
        source_ref.model_copy(update={"manifest_profile_sha256": source_profile}).model_dump(
            mode="json"
        )
    )
    columns = ["X", "Y"]
    rows = np.column_stack([x, y]).tolist()
    graph_payload = {
        "nodes": list(graph.nodes),
        "edges": [[edge.src, edge.dst] for edge in graph.edges],
    }
    row_ids = [f"{source_ref.artifact_id}:{index}" for index in range(len(rows))]
    training_rows = SCMTrainingRows(
        rows=rows,
        columns=columns,
        row_ids=row_ids,
        source_ref=source_ref,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        data_sha256=_payload_digest({"columns": columns, "rows": rows}),
        row_sha256=_payload_digest(row_ids),
        graph_sha256=_payload_digest(graph_payload),
        graph_payload=graph_payload,
        fit_input={"data": rows, "column_names": columns},
    )
    scm_spec = StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="X",
                family=MechanismFamily.LINEAR,
                family_params={"intercept": 0.0, "coefficients": {}, "noise_std": 1.0},
            ),
            NodeMechanism(
                variable="Y",
                parents=["X"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.5,
                    "coefficients": {"X": 1.75},
                    "noise_std": 0.1,
                },
            ),
        ],
        fitted=True,
        fit_method="manual",
        training_rows=training_rows,
    )
    engine = CausalEngine(registry=MethodRegistry.get_instance(), artifact_store=store)
    query = CtfQuery(
        outcome="Y",
        intervention=(("X", 1.0),),
        evidence=(("X", 0.0),),
        kind="ett",
    )
    report, bundle, cert = engine.run(
        "X",
        "Y",
        graph,
        data_dict={"X": x, "Y": y, "scm_spec": scm_spec, "n_samples": 128},
        counterfactual_query=query,
        run_id="ctf-run",
    )

    assert cert is None
    assert isinstance(report, TwinNetworkResult)
    assert np.isclose(report.ite_mean, 1.75)
    assert "X=1" in bundle.query_str

    assert bundle.proof_bundle_ref is not None
    assert bundle.proof_bundle_ref.manifest_profile_sha256 is not None
    result_ref = bundle.twin_network_result_ref
    assert result_ref is not None
    ir_store = ensure_ir_artifact_store(store)
    reopened = load_twin_network_result(ir_store, result_ref)
    assert reopened.model_dump(mode="json") == report.model_dump(mode="json")
    assert result_ref.manifest_profile_sha256 is not None
    result_manifest = ir_store.get_manifest(result_ref)
    result_inputs = {item.role: item for item in result_manifest.inputs}
    assert set(result_inputs) == {"query", "source", "structural_causal_model"}
    assert all(item.manifest_profile_sha256 is not None for item in result_inputs.values())
    assert str(result_inputs["source"].artifact_id) == str(source_ref.artifact_id)
    assert result_inputs["source"].manifest_profile_sha256 == source_profile
    selected_manifests = {
        role: ir_store.get_manifest_by_profile(item.artifact_id, item.manifest_profile_sha256)
        for role, item in result_inputs.items()
    }
    assert all(
        str(selected_manifests[role].artifact_id) == str(item.artifact_id)
        for role, item in result_inputs.items()
    )
    scm_input = result_inputs["structural_causal_model"]
    scm_manifest = selected_manifests["structural_causal_model"]
    assert scm_manifest.inputs[0].role == "source"
    assert str(scm_manifest.inputs[0].artifact_id) == str(source_ref.artifact_id)
    assert scm_manifest.inputs[0].manifest_profile_sha256 == source_profile
    query_input = result_inputs["query"]
    query_manifest = selected_manifests["query"]
    assert query_manifest.inputs[0].role == "structural_causal_model"
    assert str(query_manifest.inputs[0].artifact_id) == str(scm_input.artifact_id)
    assert query_manifest.inputs[0].manifest_profile_sha256 == scm_input.manifest_profile_sha256
    proof_bundle = load_proof_bundle(ir_store, bundle.proof_bundle_ref)
    assert proof_bundle.proof_trace_ref is not None
    trace_bundle = load_causal_evidence_bundle(ir_store, proof_bundle.proof_trace_ref)
    assert trace_bundle.twin_network_result_ref == result_ref
    trace_manifest = ir_store.get_manifest(proof_bundle.proof_trace_ref)
    assert trace_manifest.artifact_schema.version == "1.1"
    assert str(trace_manifest.inputs[0].artifact_id) == str(result_ref.artifact_id)
    assert trace_manifest.inputs[0].manifest_profile_sha256 == result_ref.manifest_profile_sha256

    reader = """
import json,sys
from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal import load_proof_bundle
from polisyos.ir.analytics.evidence_bundle import load_causal_evidence_bundle
from polisyos.ir.analytics.twin_network import load_twin_network_result
from polisyos.ir.registry.refs import ProofBundleRef
store=ensure_ir_artifact_store(FileSystemCAS(sys.argv[1]))
proof=load_proof_bundle(store,ProofBundleRef.model_validate_json(sys.argv[2]))
assert proof.proof_trace_ref is not None
trace=load_causal_evidence_bundle(store,proof.proof_trace_ref)
assert trace.twin_network_result_ref is not None
result=load_twin_network_result(store,trace.twin_network_result_ref)
print(json.dumps({'ref':trace.twin_network_result_ref.model_dump(mode="json"),'result':result.model_dump(mode="json")},sort_keys=True))
"""
    fresh = subprocess.run(
        [sys.executable, "-c", reader, str(store.root), bundle.proof_bundle_ref.model_dump_json()],
        capture_output=True,
        text=True,
        env=os.environ,
    )
    assert fresh.returncode == 0, fresh.stderr
    fresh_payload = json.loads(fresh.stdout)
    assert fresh_payload["result"] == report.model_dump(mode="json")
    assert fresh_payload["ref"] == result_ref.model_dump(mode="json")
