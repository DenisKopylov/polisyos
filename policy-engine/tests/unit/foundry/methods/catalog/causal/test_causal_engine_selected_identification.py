"""Actual static ID/IDC producer, selected CAS and fresh conditional-proof consumers."""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from polisyos.core.artifacts import artifact_manifest_profile_sha256, ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.ir.analytics.causal import load_proof_bundle, persist_proof_bundle
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.estimand import EstimandAST, RatioNode
from polisyos.ir.analytics.evidence_bundle import (
    _fingerprint,
    load_causal_evidence_bundle,
    persist_causal_evidence_bundle,
)
from polisyos.ir.artifacts import InputRef
from polisyos.ir.registry.refs import CausalGraphModelRef, ProofBundleRef


def _graph(*, confounded: bool = False, revision: str = "r1") -> CausalGraphModel:
    edges = [CausalEdge(src=src, dst=dst) for src, dst in [("Z", "X"), ("Z", "Y"), ("X", "Y")]]
    if confounded:
        edges.append(CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW))
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y", "Z"],
        edges=edges,
        metadata={"basis_role": "hypothesis", "revision": revision},
    )


def _produce(
    root: Path,
    *,
    conditions: frozenset[str] = frozenset(),
    confounded: bool = False,
    graph_model: CausalGraphModel | None = None,
) -> tuple[ProofBundleRef, CausalGraphModelRef]:
    store = FileSystemCAS(root)
    engine = CausalEngine(artifact_store=store)
    ir_store = ensure_ir_artifact_store(store)
    graph = graph_model if graph_model is not None else _graph(confounded=confounded)
    initial = persist_causal_graph_model(ir_store, graph, return_selected_profile=True)
    selected_ref = persist_causal_graph_model(
        ir_store,
        graph,
        inputs=[
            InputRef(
                artifact_id=initial.artifact_id,
                role="hypothesis_source",
                manifest_profile_sha256=initial.manifest_profile_sha256,
            )
        ],
        return_selected_profile=True,
    )
    _, bundle, _ = engine.run("X", "Y", graph, graph_ref=selected_ref, conditions=conditions)
    assert bundle.proof_bundle_ref is not None
    assert bundle.proof_bundle_ref.manifest_profile_sha256 is not None
    ir_store = ensure_ir_artifact_store(store)
    manifest = ir_store.get_manifest(bundle.proof_bundle_ref)
    graphs = [item for item in manifest.inputs if item.role == "graph"]
    assert len(graphs) == 1
    selected = graphs[0]
    graph_ref = CausalGraphModelRef(
        artifact_id=selected.artifact_id,
        manifest_profile_sha256=selected.manifest_profile_sha256,
    )
    assert graph_ref == selected_ref
    return bundle.proof_bundle_ref, graph_ref


def _read(root: Path, ref: ProofBundleRef, graph_ref: CausalGraphModelRef, **kwargs):
    return CausalEngine(artifact_store=FileSystemCAS(root)).load_identification(
        ref, graph_ref=graph_ref, treatment="X", outcome="Y", **kwargs
    )


@pytest.mark.parametrize("conditions", [frozenset(), frozenset({"Z"})])
def test_actual_id_idc_persist_and_fresh_reader_preserve_whole_structural_proof(
    tmp_path: Path, conditions: frozenset[str]
) -> None:
    ref, graph_ref = _produce(tmp_path / "cas", conditions=conditions)
    proof = _read(tmp_path / "cas", ref, graph_ref, conditions=conditions)
    assert proof.proof_status == "identified"
    assert proof.estimand_ast
    assert proof.proof_trace_ref is not None
    assert proof.proof_trace_ref.manifest_profile_sha256 is not None
    assert proof.metadata["structural_basis"] == "conditional_on_selected_graph"
    assert proof.metadata["empirical_graph_validity"] == "not_established"
    assert proof.metadata["policy_authority"] is False
    assert proof.metadata["selected_graph_ref"] == graph_ref.model_dump(mode="json")
    if conditions:
        trace = load_causal_evidence_bundle(
            ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas")), proof.proof_trace_ref
        )
        assert isinstance(EstimandAST.model_validate(proof.estimand_ast).root, RatioNode)
        positivity = [step for step in trace.proof_steps if step.rule_name == "IDC_POSITIVITY"]
        assert len(positivity) == 1
        assert "P(['Z']|do(['X'])) > 0" in positivity[0].description

    code = """
import json,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.ir.registry.refs import ProofBundleRef,CausalGraphModelRef
result=CausalEngine(artifact_store=FileSystemCAS(sys.argv[1])).load_identification(
    ProofBundleRef.model_validate_json(sys.argv[2]),
    graph_ref=CausalGraphModelRef.model_validate_json(sys.argv[3]),
    treatment='X',outcome='Y',conditions=frozenset(json.loads(sys.argv[4])))
print(result.model_dump_json())
"""
    fresh = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            str(tmp_path / "cas"),
            ref.model_dump_json(),
            graph_ref.model_dump_json(),
            json.dumps(sorted(conditions)),
        ],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
    )
    assert fresh.returncode == 0, fresh.stderr
    assert json.loads(fresh.stdout) == proof.model_dump(mode="json")


def test_nonidentifiable_bow_graph_preserves_actual_certificate_and_fresh_limitation(
    tmp_path: Path,
):
    ref, graph_ref = _produce(tmp_path / "cas", confounded=True)
    proof = _read(tmp_path / "cas", ref, graph_ref)
    assert proof.proof_status == "non_identified"
    assert proof.estimand_ast is None
    assert proof.negative_certificate_summary
    assert proof.metadata["policy_authority"] is False


def test_bound_producer_result_cannot_be_audited_against_another_graph() -> None:
    engine = CausalEngine()
    result = engine.identify("X", "Y", _graph())
    assert result.source_graph_ref == engine._graph_artifact_ref(_graph())
    with pytest.raises(ValueError, match="identification_source_graph_mismatch"):
        engine.audit(result, None, run_id="wrong-graph", graph=_graph(revision="r2"))
    # Historical direct-leaf inspection stays distinct from the new selected reader.
    legacy = dataclasses.replace(result, source_graph_ref=None)
    inspected = engine.audit(legacy, None, run_id="historical-inspection", graph=_graph())
    assert inspected.proof_bundle_ref is None
    omitted_graph = engine.audit(result, None, run_id="bound-result-inspection")
    assert omitted_graph.identification_status == "identified"
    assert omitted_graph.proof_bundle_ref is None


@pytest.mark.parametrize("mismatch", ["graph", "same_bytes_foreign_profile", "query", "unselected"])
def test_fresh_reader_refuses_foreign_graph_profile_query_and_unselected_ref(
    tmp_path: Path, mismatch
):
    root = tmp_path / "cas"
    ref, graph_ref = _produce(root)
    ir_store = ensure_ir_artifact_store(FileSystemCAS(root))
    kwargs = {}
    if mismatch == "graph":
        graph_ref = persist_causal_graph_model(
            ir_store, _graph(revision="r2"), return_selected_profile=True
        )
    elif mismatch == "same_bytes_foreign_profile":
        original = graph_ref
        graph_ref = persist_causal_graph_model(
            ir_store,
            _graph(),
            inputs=[
                InputRef(
                    artifact_id=original.artifact_id,
                    role="historical_basis",
                    manifest_profile_sha256=original.manifest_profile_sha256,
                )
            ],
            return_selected_profile=True,
        )
        assert graph_ref.artifact_id == original.artifact_id
        assert graph_ref.manifest_profile_sha256 != original.manifest_profile_sha256
    elif mismatch == "query":
        kwargs["conditions"] = frozenset({"Z"})
    else:
        ref = ref.model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(
        ValueError, match="identification_(graph_selection|graph_or_query_binding|selected_profile)"
    ):
        _read(root, ref, graph_ref, **kwargs)


@pytest.mark.parametrize("substitute", ["proof_and_trace", "trace_only"])
def test_proof_and_trace_substitution_are_independently_rejected_by_actual_replay(
    tmp_path: Path, substitute
):
    root = tmp_path / "cas"
    ref, graph_ref = _produce(root)
    ir_store = ensure_ir_artifact_store(FileSystemCAS(root))
    proof = load_proof_bundle(ir_store, ref)
    assert proof.proof_trace_ref is not None
    trace = load_causal_evidence_bundle(ir_store, proof.proof_trace_ref)
    foreign = CausalEngine().identify("Z", "Y", _graph()).estimand_ast.model_dump(mode="json")
    changed_trace = trace.model_copy(
        update={"estimand_ast": foreign, "estimand_fingerprint": _fingerprint(foreign)}
    )
    trace_ref = persist_causal_evidence_bundle(ir_store, changed_trace)
    trace_ref = trace_ref.model_copy(
        update={
            "manifest_profile_sha256": artifact_manifest_profile_sha256(
                ir_store.get_manifest(trace_ref)
            )
        }
    )
    manifest = ir_store.get_manifest(ref)
    inputs = [
        item
        if item.role != "proof_trace"
        else InputRef(
            artifact_id=trace_ref.artifact_id,
            role="proof_trace",
            manifest_profile_sha256=trace_ref.manifest_profile_sha256,
        )
        for item in manifest.inputs
    ]
    changed = proof.model_copy(
        update={
            "proof_trace_ref": trace_ref,
            **({"estimand_ast": foreign} if substitute == "proof_and_trace" else {}),
        }
    )
    changed_ref = persist_proof_bundle(ir_store, changed, inputs=inputs)
    changed_ref = changed_ref.model_copy(
        update={
            "manifest_profile_sha256": artifact_manifest_profile_sha256(
                ir_store.get_manifest(changed_ref)
            )
        }
    )
    reason = (
        "identification_proof_replay_mismatch"
        if substitute == "proof_and_trace"
        else "identification_proof_trace_replay_mismatch"
    )
    with pytest.raises(ValueError, match=reason):
        _read(root, changed_ref, graph_ref)


def test_removing_producer_binding_leaves_legacy_inspection_unadmitted(tmp_path: Path, monkeypatch):
    engine = CausalEngine(artifact_store=FileSystemCAS(tmp_path / "cas"))
    monkeypatch.setattr(
        engine, "_bind_identification_graph", lambda result, graph, selection=None: result
    )
    selected = persist_causal_graph_model(
        engine._ir_artifact_store, _graph(), return_selected_profile=True
    )
    _, bundle, _ = engine.run("X", "Y", _graph(), graph_ref=selected)
    assert bundle.proof_bundle_ref is not None
    assert (
        load_proof_bundle(engine._ir_artifact_store, bundle.proof_bundle_ref).proof_status
        == "identified"
    )
    graph_ref = persist_causal_graph_model(
        engine._ir_artifact_store, _graph(), return_selected_profile=True
    )
    with pytest.raises(ValueError, match="identification_graph_selection_mismatch"):
        _read(tmp_path / "cas", bundle.proof_bundle_ref, graph_ref)


def test_omitted_graph_audit_keeps_persisted_legacy_inspection_without_selected_graph(
    tmp_path: Path,
):
    store = FileSystemCAS(tmp_path / "cas")
    engine = CausalEngine(artifact_store=store)
    result = engine.identify("X", "Y", _graph())
    bundle = engine.audit(result, None, run_id="persisted-inspection")
    assert bundle.identification_status == "identified"
    assert bundle.proof_bundle_ref is not None
    ir_store = ensure_ir_artifact_store(store)
    manifest = ir_store.get_manifest(bundle.proof_bundle_ref)
    assert not [item for item in manifest.inputs if item.role == "graph"]
    assert load_proof_bundle(ir_store, bundle.proof_bundle_ref).proof_status == "identified"
    graph_ref = persist_causal_graph_model(ir_store, _graph(), return_selected_profile=True)
    with pytest.raises(ValueError, match="identification_graph_selection_mismatch"):
        _read(tmp_path / "cas", bundle.proof_bundle_ref, graph_ref)


def test_unresolved_pag_remains_useful_persisted_hypothesis_without_static_identification(
    tmp_path: Path,
):
    graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW)],
        metadata={"basis_role": "llm_proposed_hypothesis", "revision": "unresolved"},
    )
    ref, graph_ref = _produce(tmp_path / "cas", graph_model=graph)
    proof = _read(tmp_path / "cas", ref, graph_ref)
    assert proof.proof_status == "oracle_needed"
    assert proof.estimand_ast is None
    assert proof.metadata["limitation_code"] == "partial_graph_completion_semantics_not_established"
    assert proof.metadata["empirical_graph_validity"] == "not_established"
    assert proof.metadata["policy_authority"] is False


@pytest.mark.parametrize("confounded", [False, True])
def test_caller_cannot_rebind_selected_producer_result_before_audit(
    tmp_path: Path, confounded: bool
):
    root = tmp_path / "cas"
    store = FileSystemCAS(root)
    ir_store = ensure_ir_artifact_store(store)
    graph = _graph(confounded=confounded)
    first = persist_causal_graph_model(ir_store, graph, return_selected_profile=True)
    foreign = persist_causal_graph_model(
        ir_store,
        graph,
        inputs=[
            InputRef(
                artifact_id=first.artifact_id,
                role="foreign_generation",
                manifest_profile_sha256=first.manifest_profile_sha256,
            )
        ],
        return_selected_profile=True,
    )
    assert first.artifact_id == foreign.artifact_id
    assert first.manifest_profile_sha256 != foreign.manifest_profile_sha256
    engine = CausalEngine(artifact_store=store)
    actual = engine.identify("X", "Y", graph, graph_ref=first)
    selection = (str(foreign.artifact_id), foreign.manifest_profile_sha256)
    if confounded:
        forged = actual.model_copy(
            update={
                "quantitative_diagnostics": {
                    **actual.quantitative_diagnostics,
                    "source_graph_selection": selection,
                }
            }
        )
        args = {"identification_result": None, "negative_certificate": forged}
    else:
        forged = dataclasses.replace(actual, source_graph_selection=selection)
        args = {"identification_result": forged}
    before = sorted(str(path.relative_to(root)) for path in root.rglob("*") if path.is_file())
    with pytest.raises(ValueError, match="identification_selected_producer_context_unavailable"):
        engine.audit(estimation_result=None, run_id="forged-before-audit", graph=graph, **args)
    assert (
        sorted(str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()) == before
    )


def test_selected_producer_context_rejects_nested_result_mutation(tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    ir_store = ensure_ir_artifact_store(store)
    graph = _graph()
    selected = persist_causal_graph_model(ir_store, graph, return_selected_profile=True)
    engine = CausalEngine(artifact_store=store)
    actual = engine.identify("X", "Y", graph, graph_ref=selected)
    actual.metadata["intervention_query"]["target"]["outcome_variables"] = ["Z"]
    with pytest.raises(ValueError, match="identification_producer_result_changed"):
        engine.audit(actual, None, run_id="changed-nested-result", graph=graph)


def test_selected_static_profile_refuses_unwired_family_but_preserves_plain_route(tmp_path: Path):
    from polisyos.foundry.methods.catalog.causal.id_engine import CtfQuery

    store = FileSystemCAS(tmp_path / "cas")
    ir_store = ensure_ir_artifact_store(store)
    graph = _graph()
    selected = persist_causal_graph_model(ir_store, graph, return_selected_profile=True)
    engine = CausalEngine(artifact_store=store)
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world")
    with pytest.raises(ValueError, match="identification_selected_profile_route_unsupported"):
        engine.identify("X", "Y", graph, graph_ref=selected, counterfactual_query=query)
    assert engine.identify("X", "Y", graph, counterfactual_query=query).estimand_ast is not None


def test_selected_producer_context_is_weak_and_does_not_retain_old_results(tmp_path: Path):
    import gc
    import weakref

    store = FileSystemCAS(tmp_path / "cas")
    selected = persist_causal_graph_model(
        ensure_ir_artifact_store(store), _graph(), return_selected_profile=True
    )
    engine = CausalEngine(artifact_store=store)
    result = engine.identify("X", "Y", _graph(), graph_ref=selected)
    reference = weakref.ref(result)
    key = id(result)
    assert key in engine._selected_identification_context
    del result
    gc.collect()
    assert reference() is None
    assert key not in engine._selected_identification_context


def test_plain_original_producer_result_stays_inspection_without_selected_input(tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    engine = CausalEngine(artifact_store=store)
    actual = engine.identify("X", "Y", _graph())
    assert actual.source_graph_selection is None
    assert not engine._selected_identification_context
    bundle = engine.audit(actual, None, run_id="plain-inspection-with-graph", graph=_graph())
    assert bundle.proof_bundle_ref is not None
    ir_store = ensure_ir_artifact_store(store)
    assert not [
        item
        for item in ir_store.get_manifest(bundle.proof_bundle_ref).inputs
        if item.role == "graph"
    ]
    _, run_bundle, _ = engine.run("X", "Y", _graph())
    assert run_bundle.proof_bundle_ref is not None
    assert load_proof_bundle(ir_store, run_bundle.proof_bundle_ref).graph_ref is None
    assert not [
        item
        for item in ir_store.get_manifest(run_bundle.proof_bundle_ref).inputs
        if item.role == "graph"
    ]
    selected = persist_causal_graph_model(ir_store, _graph(), return_selected_profile=True)
    with pytest.raises(ValueError, match="identification_graph_selection_mismatch"):
        _read(tmp_path / "cas", bundle.proof_bundle_ref, selected)


def test_selected_capacity_refuses_without_eviction_and_releases_for_new_producer(tmp_path: Path):
    import gc

    store = FileSystemCAS(tmp_path / "cas")
    ir_store = ensure_ir_artifact_store(store)
    graph = _graph()
    selected = persist_causal_graph_model(ir_store, graph, return_selected_profile=True)
    engine = CausalEngine(artifact_store=store)
    live = [engine.identify("X", "Y", graph, graph_ref=selected) for _ in range(128)]
    assert len(engine._selected_identification_context) == 128
    oldest = live[0]
    with pytest.raises(ValueError, match="identification_selected_producer_context_capacity"):
        engine.identify("X", "Y", graph, graph_ref=selected)
    unselected = engine.identify("X", "Y", graph)
    assert unselected.source_graph_selection is None
    assert len(engine._selected_identification_context) == 128
    bundle = engine.audit(oldest, None, run_id="oldest-context-survives", graph=graph)
    assert bundle.proof_bundle_ref is not None
    proof = _read(tmp_path / "cas", bundle.proof_bundle_ref, selected)
    assert proof.proof_status == "identified"
    live.pop()
    gc.collect()
    assert len(engine._selected_identification_context) == 127
    fresh = engine.identify("X", "Y", graph, graph_ref=selected)
    assert fresh.source_graph_selection == (
        str(selected.artifact_id),
        selected.manifest_profile_sha256,
    )
    assert len(engine._selected_identification_context) == 128


def test_plain_proximal_route_preserves_actual_producer_identity_and_metadata(monkeypatch):
    from copy import deepcopy

    from polisyos.ir.analytics.proximal import ProximalIdentificationCertificate, ProxyAnnotation

    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "A", "Y", "Z", "W"],
        edges=[
            CausalEdge(src=src, dst=dst)
            for src, dst in [("X", "A"), ("X", "Y"), ("Z", "A"), ("A", "Y")]
        ]
        + [
            CausalEdge(src=src, dst=dst, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)
            for src, dst in [("A", "Y"), ("A", "Z"), ("Y", "W")]
        ],
    )
    engine = CausalEngine()
    producer = engine._maybe_proximal_identify
    observed = {}

    def observe(*args, **kwargs):
        result = producer(*args, **kwargs)
        if isinstance(result, ProximalIdentificationCertificate):
            observed["result"] = result
            observed["metadata"] = deepcopy(result.metadata)
        return result

    monkeypatch.setattr(engine, "_maybe_proximal_identify", observe)
    actual = engine.identify(
        "A",
        "Y",
        graph,
        proximal_annotation=ProxyAnnotation(
            treatment_inducing=("Z",),
            outcome_inducing=("W",),
            covariates=("X",),
        ),
    )
    assert isinstance(actual, ProximalIdentificationCertificate)
    assert actual is observed["result"]
    assert actual.metadata == observed["metadata"]
    assert "source_graph_ref" not in actual.metadata
    assert "source_graph_selection" not in actual.metadata
