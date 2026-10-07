"""Real current graph content admission, without causal authority claims."""

from __future__ import annotations

import logging

import pytest

from polisyos.core.artifacts import ArtifactRef, PutOptions, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.causal.graph_reconciliation import ReconcileCausalGraph
from polisyos.foundry.methods.catalog.causal.protocols import GraphReconciliationData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_graph import CausalGraphModel, load_causal_graph_model
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job
from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import ReconcileCausalGraphNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_METHOD_RESULT_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


@pytest.fixture
def context(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="graph-content")
    MethodRegistry.get_instance().register(ReconcileCausalGraph, override=True)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger("graph-content"))


def graph(*edges, graph_type="dag", nodes=("X", "Y")):
    return CausalGraphModel.model_validate(
        {
            "graph_type": graph_type,
            "nodes": list(nodes),
            "edges": [
                dict(data_confidence=0.9, combined_confidence=0.9, sources=["data"], **edge)
                for edge in edges
            ],
        }
    )


def produce(ctx, source_graph):
    # Isolate deliberate backend refusals from the process-wide health state.
    # The actual dispatcher and registered scientific method still execute.
    from polisyos.foundry.methods.backends.circuit_breaker import get_circuit_breaker_registry

    get_circuit_breaker_registry().reset_all()
    request = GraphReconciliationData(data_graph=source_graph)
    source = ctx.store.put_json(
        request.model_dump(mode="json"),
        PutOptions(
            kind="tests.synthetic.graph_reconciliation_input",
            media_type="application/json",
            schema=SchemaInfo(name="tests.GraphReconciliationData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    job = run_job(
        JobSpec(
            job_kind="method",
            method_fqn=ReconcileCausalGraph.signature.fqn,
            input_refs={"graph_reconciliation_data": source},
            seed=23,
        ),
        cas_root=ctx.store.root,
        method_state=request,
    )
    return job, source


def state_for(job):
    assert not job.issues and job.method_result_ref is not None, job.issues
    return ExperimentState(
        run_id="graph-content",
        artifacts_index={
            ARTIFACT_CAUSAL_METHOD_RESULT_REF: job.method_result_ref,
        },
    )


def fresh(ctx, outcome):
    assert outcome.status == "ok", outcome.error
    ref = outcome.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]
    return ref, load_causal_graph_model(FileSystemCAS(ctx.store.root), ref)


def relations(value):
    return {
        (edge.src, edge.dst, edge.mark_src.value, edge.mark_dst.value, edge.lag)
        for edge in value.edges
    }


@pytest.mark.parametrize(
    "source_graph, expected",
    [
        (graph({"src": "X", "dst": "Y"}), {("X", "Y", "tail", "arrow", None)}),
        (
            graph(
                {"src": "X", "dst": "Y", "mark_src": "arrow", "mark_dst": "tail"}, graph_type="pag"
            ),
            {("Y", "X", "tail", "arrow", None)},
        ),
        (
            graph(
                {"src": "X", "dst": "Y"},
                {"src": "X", "dst": "Y", "mark_src": "arrow", "mark_dst": "arrow"},
                graph_type="admg",
            ),
            {("X", "Y", "tail", "arrow", None), ("X", "Y", "arrow", "arrow", None)},
        ),
        (
            graph(
                {"src": "Y", "dst": "X", "mark_src": "arrow", "mark_dst": "arrow"},
                graph_type="admg",
            ),
            {("X", "Y", "arrow", "arrow", None)},
        ),
    ],
)
def test_genuine_producer_to_fresh_reader_preserves_known_relations(
    context, source_graph, expected
):
    job, source = produce(context, source_graph)
    outcome = ReconcileCausalGraphNode().execute(context, state_for(job))
    ref, reopened = fresh(context, outcome)
    assert relations(reopened) == expected  # independent exact known edge law
    manifest = context.store.get_manifest(ref)
    assert any(
        row.role == "data_graph" and row.artifact_id == job.method_result_ref.artifact_id
        for row in manifest.inputs
    )
    assert context.store.has(source.artifact_id)
    replay = ReconcileCausalGraphNode().execute(context, outcome.state)
    assert fresh(context, replay)[0] == ref


def test_current_real_producer_direction_supersedes_cache(context):
    old, _ = produce(context, graph({"src": "X", "dst": "Y"}))
    first = ReconcileCausalGraphNode().execute(context, state_for(old))
    old_ref, _ = fresh(context, first)
    new, _ = produce(context, graph({"src": "Y", "dst": "X"}))
    changed = first.state.model_copy(deep=True)
    changed.artifacts_index[ARTIFACT_CAUSAL_METHOD_RESULT_REF] = new.method_result_ref
    next_outcome = ReconcileCausalGraphNode().execute(context, changed)
    new_ref, reopened = fresh(context, next_outcome)
    assert new_ref != old_ref
    assert relations(reopened) == {("Y", "X", "tail", "arrow", None)}
    assert (
        context.store.get_manifest(new_ref).inputs[0].artifact_id
        == new.method_result_ref.artifact_id
    )


def test_current_parameters_recompute_full_content(context):
    job, _ = produce(context, graph({"src": "X", "dst": "Y"}))
    first = ReconcileCausalGraphNode().execute(context, state_for(job))
    old_ref, _ = fresh(context, first)
    changed = first.state.model_copy(deep=True)
    changed.params["reconciliation_min_edge_confidence"] = 0.95
    next_outcome = ReconcileCausalGraphNode().execute(context, changed)
    new_ref, reopened = fresh(context, next_outcome)
    assert new_ref != old_ref and not reopened.edges


@pytest.mark.parametrize(
    "malformed", [None, {}, {"graph_type": "dag", "nodes": ["X"], "edges": "bad"}]
)
def test_supplied_bad_data_is_not_absence_or_producer_fallback(context, malformed):
    job, _ = produce(context, graph({"src": "X", "dst": "Y"}))
    state = state_for(job)
    state.params["data_causal_graph"] = malformed
    result = ReconcileCausalGraphNode().execute(context, state)
    assert result.status == "fail" and not result.artifacts


def test_supplied_data_and_actual_producer_must_agree(context):
    job, _ = produce(context, graph({"src": "X", "dst": "Y"}))
    state = state_for(job)
    state.params["data_causal_graph"] = graph({"src": "Y", "dst": "X"}).model_dump(mode="json")
    result = ReconcileCausalGraphNode().execute(context, state)
    assert result.status == "fail" and "differs" in result.error.message


@pytest.mark.parametrize(
    "marks, lag, source_type",
    [
        (("circle", "circle"), None, "pag"),
        (("circle", "arrow"), None, "pag"),
        (("arrow", "circle"), None, "pag"),
        (("tail", "tail"), None, "cpdag"),
        (("tail", "arrow"), 1, "dag"),
        (("tail", "arrow"), 2, "dag"),
    ],
)
def test_unsupported_static_profile_refuses_before_real_producer_and_node(
    context, marks, lag, source_type
):
    source_graph = graph(
        {"src": "X", "dst": "Y", "mark_src": marks[0], "mark_dst": marks[1], "lag": lag},
        graph_type=source_type,
    )
    job, _ = produce(context, source_graph)
    assert job.issues and job.method_result_ref is None
    state = ExperimentState(
        run_id="graph-content",
        params={
            "data_causal_graph": source_graph.model_dump(mode="json"),
        },
    )
    result = ReconcileCausalGraphNode().execute(context, state)
    assert result.status == "fail" and not result.artifacts
    assert "Unsupported static ADMG profile" in result.error.message


def test_missing_cache_is_not_admitted_even_with_valid_current_source(context):
    job, _ = produce(context, graph({"src": "X", "dst": "Y"}))
    state = state_for(job)
    state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF] = ArtifactRef.model_validate(
        {
            "artifact_id": "sha256:" + "f" * 64,
            "kind": "ir.causal_graph_model",
            "media_type": "application/json",
        }
    )
    result = ReconcileCausalGraphNode().execute(context, state)
    assert result.status == "fail" and not result.artifacts


def test_graph_shaped_wrong_actual_kind_is_not_admitted(context):
    raw = graph({"src": "X", "dst": "Y"}).model_dump(mode="json")
    ref = context.store.put_json(
        raw,
        PutOptions(
            kind="tests.fake_graph",
            media_type="application/json",
            schema=SchemaInfo(name="ir.causal_graph_model", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    fake = ArtifactRef.model_validate(
        {
            "artifact_id": str(ref.artifact_id),
            "kind": "ir.causal_graph_model",
            "media_type": "application/json",
        }
    )
    state = ExperimentState(
        run_id="graph-content", artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: fake}
    )
    result = ReconcileCausalGraphNode().execute(context, state)
    assert result.status == "fail" and not result.artifacts


def test_real_cache_without_current_basis_is_not_source_authority(context):
    job, _ = produce(context, graph({"src": "X", "dst": "Y"}))
    initial = ReconcileCausalGraphNode().execute(context, state_for(job))
    ref, _ = fresh(context, initial)
    state = ExperimentState(
        run_id="graph-content", artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: ref}
    )
    result = ReconcileCausalGraphNode().execute(context, state)
    assert result.status == "fail" and "Current source" in result.error.message


def test_actual_cache_blob_corruption_is_refused(context):
    job, _ = produce(context, graph({"src": "X", "dst": "Y"}))
    initial = ReconcileCausalGraphNode().execute(context, state_for(job))
    ref, _ = fresh(context, initial)
    blob, _ = context.store._paths(ref.artifact_id)
    blob.write_bytes(b'{"graph_type":"dag","nodes":["X"],"edges":[]}')
    result = ReconcileCausalGraphNode().execute(context, initial.state)
    assert result.status == "fail" and not result.artifacts


@pytest.mark.parametrize(
    "parameter, value",
    [
        ("scm_fragment_refs", ["bad:ref"]),
        ("scm_fragment_refs", None),
        ("scm_fragments", [{}]),
        ("scm_fragments", None),
        ("llm_structural_hints", None),
        ("llm_structural_hints", [{}]),
    ],
)
def test_supplied_malformed_sources_refuse_before_graph_admission(context, parameter, value):
    state = ExperimentState(
        run_id="graph-content",
        params={
            "data_causal_graph": graph({"src": "X", "dst": "Y"}).model_dump(mode="json"),
            parameter: value,
        },
    )
    outcome = ReconcileCausalGraphNode().execute(context, state)
    assert outcome.status == "fail" and not outcome.artifacts


def test_cached_graph_schema_is_actual_not_ref_label(context):
    raw = graph({"src": "X", "dst": "Y"}).model_dump(mode="json")
    ref = context.store.put_json(
        raw,
        PutOptions(
            kind="ir.causal_graph_model",
            media_type="application/json",
            schema=SchemaInfo(name="tests.fake_schema", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    state = ExperimentState(
        run_id="graph-content",
        artifacts_index={
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: ref,
        },
    )
    outcome = ReconcileCausalGraphNode().execute(context, state)
    assert outcome.status == "fail" and "manifest/schema" in outcome.error.message


def test_graph_body_version_must_match_actual_schema(context):
    raw = graph({"src": "X", "dst": "Y"}).model_dump(mode="json")
    raw["schema_version"] = "future-unimplemented"
    ref = context.store.put_json(
        raw,
        PutOptions(
            kind="ir.causal_graph_model",
            media_type="application/json",
            schema=SchemaInfo(name="ir.causal_graph_model", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    state = ExperimentState(
        run_id="graph-content",
        artifacts_index={
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: ref,
        },
    )
    outcome = ReconcileCausalGraphNode().execute(context, state)
    assert outcome.status == "fail" and "version differs" in outcome.error.message


def composition_query_state(ctx):
    from polisyos.ir.analytics.causal_graph import persist_causal_graph_model
    from polisyos.ir.analytics.cross_graph import SCMFragment, persist_scm_fragment

    refs = []
    for name, nodes, edge, role in [
        ("a", ("X", "E"), ("X", "E"), "out"),
        ("b", ("E", "Y"), ("E", "Y"), "in"),
    ]:
        source_graph = graph({"src": edge[0], "dst": edge[1]}, nodes=nodes)
        graph_ref = persist_causal_graph_model(ctx.store, source_graph)
        fragment = SCMFragment(
            fragment_id=name,
            graph_ref=str(graph_ref.artifact_id),
            semantic_namespace="synthetic.example",
            interface_variables=["E"],
            exposed_outputs=["E"] if role == "out" else [],
            exposed_inputs=["E"] if role == "in" else [],
            variable_definitions={"E": "Employment rate"},
            variable_units={"E": "percent"},
        )
        refs.append(persist_scm_fragment(ctx.store, fragment))
    initial = ReconcileCausalGraphNode().execute(
        ctx,
        ExperimentState(
            run_id="graph-content",
            params={"scm_fragment_refs": [str(ref.artifact_id) for ref in refs]},
        ),
    )
    assert initial.status == "ok", initial.error
    state = initial.state.model_copy(deep=True)
    state.params.pop("scm_fragment_refs")
    state.params["query_preservation_queries"] = [
        {
            "query_type": "interventional",
            "treatment_variable": "E",
            "treatment_value": 1.0,
            "outcome_variable": "Y",
            "condition": {},
        }
    ]
    return state


def test_query_only_replay_recomputes_operational_cache(context):
    from polisyos.ir.analytics.cross_graph import (
        load_composition_certificate,
        persist_composition_certificate,
    )
    from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_COMPOSITION_CERTIFICATE_REF

    state = composition_query_state(context)
    first = ReconcileCausalGraphNode().execute(context, state)
    assert first.status == "ok", first.error
    ref = first.state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF]
    certificate = load_composition_certificate(context.store, ref)
    assert certificate.checked_queries and set(certificate.checked_queries.values()) == {
        "preserved"
    }
    # Real persisted cache record changes, with all source/result semantics intact.
    corrupted = certificate.model_copy(
        update={
            "checked_queries": dict.fromkeys(certificate.checked_queries, "broken"),
            "query_certificates": {
                key: value.model_copy(update={"status": "broken"})
                for key, value in certificate.query_certificates.items()
            },
        }
    )
    changed = first.state.model_copy(deep=True)
    changed.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF] = persist_composition_certificate(
        context.store, corrupted
    )
    replay = ReconcileCausalGraphNode().execute(context, changed)
    assert replay.status == "ok", replay.error
    restored = load_composition_certificate(
        context.store, replay.state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF]
    )
    assert restored.checked_queries == certificate.checked_queries
    assert (
        replay.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]
        == state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]
    )


def test_query_only_replay_reconciles_current_alignment_result(context):
    from polisyos.ir.analytics.alignment_certification import (
        AlignmentOverallStatus,
        load_alignment_report,
        persist_alignment_report,
    )
    from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_ALIGNMENT_REPORT_REF

    state = composition_query_state(context)
    report = load_alignment_report(
        context.store, state.artifacts_index[ARTIFACT_ALIGNMENT_REPORT_REF]
    )
    incompatible = report.model_copy(
        update={
            "overall_status": AlignmentOverallStatus.INCOMPATIBLE,
            "incompatible_pairs": [("a:E", "b:E")],
        }
    )
    state.artifacts_index[ARTIFACT_ALIGNMENT_REPORT_REF] = persist_alignment_report(
        context.store, incompatible
    )
    result = ReconcileCausalGraphNode().execute(context, state)
    assert result.status == "fail" and not result.artifacts
    assert "composition" in result.error.message


@pytest.mark.parametrize(
    "update",
    [
        {"review_status": "pending_review"},
        {"newly_required_assumptions": ["unproved replacement"]},
        {"metadata": {"completeness_scope": "forged"}},
        {"alignment_report_ref": "sha256:" + "f" * 64},
        {"source_fragment_graph_refs": {}},
        {"witness_ref": "unproved://witness"},
    ],
)
def test_query_only_replay_reconciles_complete_certificate_projection(context, update):
    from polisyos.ir.analytics.cross_graph import (
        load_composition_certificate,
        persist_composition_certificate,
    )
    from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_COMPOSITION_CERTIFICATE_REF

    state = composition_query_state(context)
    certificate = load_composition_certificate(
        context.store, state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF]
    )
    state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF] = persist_composition_certificate(
        context.store, certificate.model_copy(update=update)
    )
    result = ReconcileCausalGraphNode().execute(context, state)
    assert result.status == "fail" and not result.artifacts


def test_query_only_replay_resolves_selected_source_view(context):
    from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_INTERFACE_MAPPING_REF

    state = composition_query_state(context)
    actual = state.artifacts_index[ARTIFACT_INTERFACE_MAPPING_REF]
    invalid_view = ArtifactRef.model_validate(
        dict(
            actual.model_dump(mode="json"),
            manifest_profile_sha256="sha256:" + "f" * 64,
        )
    )
    state.artifacts_index[ARTIFACT_INTERFACE_MAPPING_REF] = invalid_view
    result = ReconcileCausalGraphNode().execute(context, state)
    assert result.status == "fail" and not result.artifacts


def test_query_only_replay_reconciles_persisted_failure_card_body(context):
    from polisyos.foundry.methods.catalog.causal.composition_failure_cards import (
        CompositionFailureCardBundle,
        persist_composition_failure_card_bundle,
    )
    from polisyos.ir.analytics.cross_graph import (
        load_composition_certificate,
        persist_composition_certificate,
    )
    from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_COMPOSITION_CERTIFICATE_REF

    state = composition_query_state(context)
    certificate = load_composition_certificate(
        context.store, state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF]
    )
    altered = persist_composition_failure_card_bundle(
        context.store, CompositionFailureCardBundle(cards=[], metadata={"forged": True})
    )
    state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF] = persist_composition_certificate(
        context.store,
        certificate.model_copy(update={"failure_card_bundle_ref": str(altered.artifact_id)}),
    )
    result = ReconcileCausalGraphNode().execute(context, state)
    assert result.status == "fail" and not result.artifacts
    assert "failure cards" in result.error.message
