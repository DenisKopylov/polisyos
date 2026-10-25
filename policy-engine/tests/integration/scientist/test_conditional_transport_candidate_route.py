"""Independent end-to-end oracle for conditional transport candidate routing."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from polisyos.foundry.methods.catalog.causal.pag_member_family import (
        PAGMemberBudget,
        PAGMemberFamilyResult,
    )
    from polisyos.ir.registry.refs import (
        CausalEffectReportRef,
        TransportabilityResultRef,
    )


from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.components import ComponentId
from polisyos.core.contracts.control import WorkflowRunRequest
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    load_causal_effect_report,
    persist_causal_effect_report,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    graph_content_sha256,
    load_causal_graph_model,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionRef,
    EstimandAST,
)
from polisyos.ir.analytics.transportability import (
    TransportabilityResult,
    TransportabilityStatus,
    TransportFormula,
    TransportMode,
    load_transportability_result,
    transportability_candidate_query_sha256,
)
from polisyos.scientist.governance.passes.transportability_required_pass import (
    TransportabilityRequiredPass,
)
from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
    RunTransportabilityNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import (
    NodeInvocation,
    WorkflowSpec,
)
from polisyos.scientist.orchestration.workflows.causal_full import (
    CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM,
    causal_full_transport_resource_policy_snapshot,
    causal_full_workflow_spec,
)

_TREATMENT = "consumption_response"
_OUTCOME = "gdp_growth"
_PROFILE = "pag.no_selection.finite_member_sensitivity"
_REVISION = "1"
_SELECTION = "transport-candidate.standard.v1"
_COMPONENT_ID = "scientist.node_run_transportability@1.0.0"
_SHA_A = "sha256:" + "a" * 64
_TENANT_ID = "tenant-transport-candidate"
_CELL_ID = "cell-transport-candidate"
_CANON = CanonSpec(forbid_floats=False, sort_keys=True, exclude_none=False)


@pytest.fixture(autouse=True)
def _controlled_tenant_scope() -> Iterator[None]:
    """Use one explicit tenant/cell for every CAS and timeout-worker boundary."""
    with tenant_scope(None, tenant_id=_TENANT_ID, cell_id=_CELL_ID):
        yield


def _graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=[_TREATMENT, _OUTCOME],
        edges=[
            CausalEdge(
                src=_TREATMENT,
                dst=_OUTCOME,
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.CIRCLE,
            )
        ],
        discovery_method="FCI",
    )


def _partial_pag_graph() -> CausalGraphModel:
    """Return a four-node complete PAG with a bounded selected family."""
    nodes = [_TREATMENT, _OUTCOME, "education", "employment"]
    edges = [
        CausalEdge(
            src=nodes[left],
            dst=nodes[right],
            mark_src=EdgeMark.CIRCLE,
            mark_dst=EdgeMark.CIRCLE,
        )
        for left in range(len(nodes))
        for right in range(left + 1, len(nodes))
    ]
    return CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=nodes,
        edges=edges,
        discovery_method="FCI",
    )


def _contexts() -> tuple[ContextProfile, ContextProfile]:
    return (
        ContextProfile(context_id="source", income_level=IncomeLevel.HIGH),
        ContextProfile(context_id="target", income_level=IncomeLevel.LOW),
    )


def _report() -> CausalEffectReport:
    """Create a synthetic required input artifact, not evidence or legal proof."""
    return CausalEffectReport(
        method=CausalMethod.DOWHY_BACKDOOR,
        status=EstimationStatus.SUCCESS,
        estimand="ATE",
        point_estimate=1.0,
        confidence_interval=(0.8, 1.2),
        inference_method="backdoor.linear_regression",
        sample_size=100,
        n_treated=50,
        n_control=50,
        pre_periods=0,
        post_periods=0,
        method_params={"source_type": "external_literature"},
    )


def _canonical_transport_node_timeout_s() -> float:
    workflow = causal_full_workflow_spec()
    matches = [item for item in workflow.nodes if item.alias == "run_transportability"]
    assert len(matches) == 1
    timeout_s = matches[0].timeout_s
    assert timeout_s is not None
    return timeout_s


def _canonical_transport_node_params() -> dict[str, Any]:
    workflow = causal_full_workflow_spec()
    matches = [item for item in workflow.nodes if item.alias == "run_transportability"]
    assert len(matches) == 1
    params = copy.deepcopy(dict(matches[0].params))
    snapshot = params.get(CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM)
    assert isinstance(snapshot, dict)
    assert snapshot == causal_full_transport_resource_policy_snapshot()
    return params


def _install_spawned_report_persistence_fault(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Install a child-startup fault capsule for the selected report writer."""
    from polisyos.scientist.nodes.builtins.causal import resolve_transport

    capsule_dir = root / "worker-startup-capsule"
    capsule_dir.mkdir(parents=True, exist_ok=True)
    marker = root / "spawned-report-writer-reached.json"
    source_root = Path(resolve_transport.__file__).resolve().parents[5]
    candidate_source = (
        Path(__file__).resolve().parents[3]
        / "src/polisyos/scientist/nodes/builtins/causal/resolve_transport.py"
    )
    prior_pythonpath = os.environ.get("PYTHONPATH")
    pythonpath = [str(capsule_dir), str(source_root)]
    if prior_pythonpath:
        pythonpath.append(prior_pythonpath)
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(pythonpath))
    monkeypatch.setenv("POLICYOS_TEST_REPORT_WRITE_FAULT", "enabled")
    monkeypatch.setenv("POLICYOS_TEST_REPORT_WRITE_FAULT_MARKER", str(marker))
    module_name = "polisyos.scientist.nodes.builtins.causal.resolve_transport"
    fault_flag = json.dumps("POLICYOS_TEST_REPORT_WRITE_FAULT")
    marker_key = json.dumps("POLICYOS_TEST_REPORT_WRITE_FAULT_MARKER")
    schema_key = json.dumps("schema_version")
    schema_value = json.dumps("1.1")
    enabled_value = json.dumps("enabled")
    worker_pid_key = json.dumps("worker_pid")
    injected_error = json.dumps("injected_spawned_candidate_report_write_failure")
    unavailable_error = json.dumps("candidate_transport_source_overlay_unavailable")
    startup_lines = [
        "import importlib.util",
        "import json",
        "import os",
        "import sys",
        "from pathlib import Path",
        "",
        f"_candidate_source = {json.dumps(str(candidate_source))}",
        f"_module_name = {json.dumps(module_name)}",
        "import polisyos.scientist.nodes.builtins.causal as _causal_package",
        "_spec = importlib.util.spec_from_file_location(_module_name, _candidate_source)",
        "if _spec is None or _spec.loader is None:",
        f"    raise RuntimeError({unavailable_error})",
        "_module = importlib.util.module_from_spec(_spec)",
        "sys.modules[_module_name] = _module",
        "_spec.loader.exec_module(_module)",
        "_causal_package.resolve_transport = _module",
        "",
        f"if os.environ.get({fault_flag}) == {enabled_value}:",
        "    original = _module.persist_causal_effect_report",
        "",
        "    def fail_selected_report(*args, **kwargs):",
        f"        if kwargs.get({schema_key}) == {schema_value}:",
        f"            Path(os.environ[{marker_key}]).write_text(",
        "                json.dumps({",
        f"                    {schema_key}: {schema_value},",
        f"                    {worker_pid_key}: os.getpid(),",
        "                }),",
        '                encoding="utf-8",',
        "            )",
        f"            raise OSError({injected_error})",
        "        return original(*args, **kwargs)",
        "",
        "    _module.persist_causal_effect_report = fail_selected_report",
    ]
    startup_source = "\n".join(startup_lines) + "\n"
    (capsule_dir / "sitecustomize.py").write_text(startup_source, encoding="utf-8")
    return marker


def _run(
    root: Path,
    *,
    graph: CausalGraphModel | None = None,
    profile_id: str = _PROFILE,
    query_outcome: str = _OUTCOME,
    source_context: ContextProfile | str | None = None,
    node_timeout_s: float | None = None,
    fail_candidate_report_persist: bool = False,
    selected_report_lineage_probe: str | None = None,
    node_params_override: dict[str, Any] | None = None,
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> dict[str, Any]:
    graph = graph or _graph()
    if node_timeout_s is None:
        node_timeout_s = _canonical_transport_node_timeout_s()
    source, target = _contexts()
    source_context = source if source_context is None else source_context
    store = FileSystemCAS(root / "cas", tenant_id=_TENANT_ID, cell_id=_CELL_ID)
    bundle = build_default_registry_bundle(store, return_selected_profile=True)
    report_ref = persist_causal_effect_report(
        ensure_ir_artifact_store(store), _report(), return_selected_profile=True
    )
    graph_ref = persist_causal_graph_model(
        ensure_ir_artifact_store(store), graph, return_selected_profile=True
    )
    params: dict[str, Any] = {
        "conditional_transport_request": {
            "schema_version": "1.0",
            "profile_id": profile_id,
            "profile_revision": _REVISION,
            "selection_identity": _SELECTION,
        },
        "query_treatment": _TREATMENT,
        "query_outcome": query_outcome,
        "transport_solver_mode": "simplified",
        "source_context": (
            source_context.model_dump(mode="json")
            if isinstance(source_context, ContextProfile)
            else source_context
        ),
        "target_context": target.model_dump(mode="json"),
    }
    before = {
        key: (dict(value) if isinstance(value, dict) else value) for key, value in params.items()
    }
    request = WorkflowRunRequest.model_validate(
        {"data_source": {"data_snapshot_ref": _SHA_A}, "params": params}
    )
    assert params == before
    assert request.params == before

    run_id = f"R_transport_candidate_{root.name}"
    run = RunContext.start(
        store=store,
        registry_bundle=bundle.bundle_ref,
        run_id=run_id,
        tenant_id=_TENANT_ID,
        cell_id=_CELL_ID,
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(f"transport_candidate.{run_id}"),
    )
    registry = NodeRegistry()
    registry.register(RunTransportabilityNode())
    transport_node_params = (
        _canonical_transport_node_params()
        if node_params_override is None
        else copy.deepcopy(node_params_override)
    )
    workflow = WorkflowSpec(
        workflow_id="conditional_transport_candidate_route",
        required_binds=["run_id"],
        nodes=[
            NodeInvocation(
                alias="run_transportability",
                node_id=ComponentId.parse(_COMPONENT_ID),
                params=transport_node_params,
                timeout_s=node_timeout_s,
            )
        ],
    )
    # The lifecycle's existing bridge freezes the typed public params by copy.
    state = ExperimentState(
        run_id=run_id,
        execution_profile="research",
        artifacts_index={
            ARTIFACT_CAUSAL_REPORT_REF: report_ref,
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref,
        },
        params=dict(request.params),
    )
    spawned_report_fault_marker = None
    if fail_candidate_report_persist:
        assert selected_report_lineage_probe is None
        assert monkeypatch is not None
        spawned_report_fault_marker = _install_spawned_report_persistence_fault(
            root,
            monkeypatch,
        )

    spawned_report_lineage_marker = None
    if selected_report_lineage_probe is not None:
        assert selected_report_lineage_probe in {
            "competing_default",
            "wrong_selected_ref",
        }
        assert monkeypatch is not None
        spawned_report_lineage_marker = _install_spawned_selected_report_lineage_probe(
            root,
            monkeypatch,
            mode=selected_report_lineage_probe,
        )

    execution = WorkflowExecutor(ctx, registry).execute(workflow, state)
    assert run.trace_path is not None
    return {
        "execution": execution,
        "trace_path": run.trace_path,
        "cas_root": store.root,
        "graph": graph,
        "graph_ref": graph_ref,
        "report_ref": report_ref,
        "source": source_context,
        "target": target,
        "spawned_report_fault_marker": spawned_report_fault_marker,
        "spawned_report_lineage_marker": spawned_report_lineage_marker,
    }


def _fresh(
    run: dict[str, Any],
) -> tuple[
    FileSystemCAS,
    TransportabilityResultRef,
    CausalEffectReportRef,
    TransportabilityResult,
    CausalEffectReport,
]:
    state = run["execution"].state
    result_ref = state.artifacts_index[ARTIFACT_TRANSPORTABILITY_RESULT_REF]
    report_ref = state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    store = FileSystemCAS(run["cas_root"], tenant_id=_TENANT_ID, cell_id=_CELL_ID)
    ir_store = ensure_ir_artifact_store(store)
    return (
        store,
        result_ref,
        report_ref,
        load_transportability_result(ir_store, result_ref),
        load_causal_effect_report(ir_store, report_ref),
    )


def _sha(value: object) -> str:
    return hashlib.sha256(to_canonical_bytes(value, _CANON)).hexdigest()


def _ref_identity(ref: BaseModel) -> dict[str, Any]:
    """Return every serialized reference field, including selected profile identity."""
    return ref.model_dump(mode="json")


def _assert_same_selected_artifact(
    actual: BaseModel,
    expected: BaseModel,
    *,
    store: FileSystemCAS,
) -> None:
    """Compare artifact value identity and the complete selected manifest profile."""
    assert str(actual.artifact_id) == str(expected.artifact_id)
    if hasattr(actual, "kind"):
        assert actual.kind == expected.kind
    else:
        manifest = store.get_manifest(actual.artifact_id)
        assert str(manifest.artifact_id) == str(expected.artifact_id)
        assert manifest.kind == expected.kind
    if hasattr(actual, "media_type"):
        assert actual.media_type == expected.media_type
    else:
        assert manifest.media_type == expected.media_type
    assert actual.manifest_profile_sha256 == expected.manifest_profile_sha256


def test_ref_identity_includes_selected_manifest_profile() -> None:
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.ir.registry.refs import CausalEffectReportRef

    selected = CausalEffectReportRef(
        artifact_id=_SHA_A,
        manifest_profile_sha256=_SHA_A,
    )
    state_ref = ArtifactRef.model_validate(selected.model_dump(mode="python"))
    changed_profile = CausalEffectReportRef.model_validate(
        {
            **selected.model_dump(mode="json"),
            "manifest_profile_sha256": "sha256:" + "b" * 64,
        }
    )

    assert type(state_ref) is ArtifactRef
    assert _ref_identity(state_ref) == _ref_identity(selected)
    state_identity = _ref_identity(state_ref)
    changed_identity = _ref_identity(changed_profile)
    assert state_identity["artifact_id"] == changed_identity["artifact_id"]
    assert state_identity["kind"] == changed_identity["kind"]
    assert state_identity["media_type"] == changed_identity["media_type"]
    assert state_identity["manifest_profile_sha256"] != changed_identity["manifest_profile_sha256"]


def _assert_supervised_worker_trace(
    run: dict[str, Any],
    *,
    expected_node_event: str = "NODE_OK",
) -> list[Any]:
    """Reconcile exact staged receipt rows and their digest to worker markers."""
    from polisyos.core.trace.record import TraceRecord

    trace_path = run["trace_path"]
    lines = [line for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = [json.loads(line) for line in lines]
    started = [row for row in records if row.get("event") == "WORKER_INVOCATION_STARTED"]
    completed = [row for row in records if row.get("event") == "WORKER_INVOCATION_COMPLETED"]
    assert len(started) == 1
    assert len(completed) == 1
    start, finish = started[0], completed[0]
    assert start["run_id"] == run["execution"].state.run_id
    assert start["worker_invocation_id"]
    assert start["worker_invocation_id"] == finish["worker_invocation_id"]
    assert start["worker_dispatch_sha256"]
    assert start["worker_dispatch_sha256"] == finish["worker_dispatch_sha256"]
    assert start["worker_receipt_phase"] == "started"
    assert finish["worker_receipt_phase"] == "completed"

    invocation_id = start["worker_invocation_id"]
    receipt_events = [
        TraceRecord.model_validate_json(line)
        for line in lines
        if (row := json.loads(line)).get("worker_invocation_id") == invocation_id
        and row.get("worker_receipt_phase") is None
    ]
    receipt_count = start["worker_receipt_count"]
    assert type(receipt_count) is int and receipt_count >= 0
    assert finish["worker_receipt_count"] == receipt_count
    receipt_sha256 = start["worker_receipt_sha256"]
    assert receipt_sha256 == finish["worker_receipt_sha256"]
    assert len(receipt_sha256) == 64
    digest = hashlib.sha256()
    for record in receipt_events:
        digest.update(record.model_dump_json(exclude_none=True).encode("utf-8"))
        digest.update(b"\n")
    assert receipt_count == len(receipt_events)
    assert receipt_sha256 == digest.hexdigest()

    completed_index = records.index(finish)
    assert any(
        index > completed_index
        and row.get("event") == expected_node_event
        and row.get("phase") == "scientist.node.run_transportability"
        for index, row in enumerate(records)
    )
    return receipt_events


def _assert_candidate_outputs_staged(receipt_events: list[Any], run: dict[str, Any]) -> None:
    """Bind the selected result/report refs to their admitted worker events."""
    expected = [
        run["execution"].state.artifacts_index[ARTIFACT_TRANSPORTABILITY_RESULT_REF],
        run["execution"].state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF],
    ]
    actual = [ref for record in receipt_events for ref in record.refs.outputs]
    assert [ref.model_dump(mode="json") for ref in actual] == [
        ref.model_dump(mode="json") for ref in expected
    ]
    assert [record.event for record in receipt_events] == [
        "RUN_OUTPUT_ADDED",
        "RUN_OUTPUT_ADDED",
    ]


def _assert_outer_refusal(result: TransportabilityResult) -> None:
    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.transport_mode is TransportMode.NONE
    assert result.feasible is False
    assert result.unsupported_reason == "legal_source_relation_verification_not_established"
    assert result.candidate_diagnostics is not None
    assert result.candidate_diagnostics.candidate_scope == "candidate_only"


def _member_relation(graph: CausalGraphModel) -> str:
    assert set(graph.nodes) == {_TREATMENT, _OUTCOME}
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    if edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW:
        return "bidirected"
    if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW:
        return f"{edge.src}->{edge.dst}"
    if edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.TAIL:
        return f"{edge.dst}->{edge.src}"
    raise AssertionError(f"Unexpected two-node member endpoints: {edge!r}")


def _assert_g06_math(graph: CausalGraphModel, result: TransportabilityResult) -> str:
    """Check the three member effects against G06's independent graph argument."""
    assert result.status is TransportabilityStatus.IDENTIFIED
    formula = result.transport_formula
    assert formula is not None
    relation = _member_relation(graph)
    assert result.estimand_ast is not None
    ast = EstimandAST.model_validate(result.estimand_ast)
    refs = ast.collect_distribution_refs()
    assert refs
    assert all(ref.domain is DistributionDomain.SOURCE for ref in refs)
    assert all(not ref.intervention_set for ref in refs)
    expected_conditioning = (_TREATMENT,) if relation == f"{_TREATMENT}->{_OUTCOME}" else ()
    assert all(ref.variables == (_OUTCOME,) for ref in refs)
    assert all(ref.conditioning == expected_conditioning for ref in refs)
    assert all(quantity.startswith("P_s(") for quantity in formula.source_quantities)
    assert formula.target_quantities == []
    assert formula.stratification_variables == []
    assert all("do(" not in item for item in formula.source_quantities)
    return relation


def test_public_request_live_attempt_cas_read_and_candidate_fraction_do_not_promote(
    tmp_path: Path,
) -> None:
    canonical_timeout_s = _canonical_transport_node_timeout_s()
    assert canonical_timeout_s == 120.0
    run = _run(tmp_path, node_timeout_s=canonical_timeout_s)
    worker_receipts = _assert_supervised_worker_trace(run)
    assert run["execution"].report.status == "ok", run["execution"].report.model_dump(mode="json")
    _assert_candidate_outputs_staged(worker_receipts, run)
    store, result_ref, report_ref, result, report = _fresh(run)
    _assert_outer_refusal(result)
    diagnostic = result.candidate_diagnostics
    assert diagnostic.disposition == "completed"
    assert diagnostic.generation_coverage == "finite_endpoint_assignment_space_complete"
    assert diagnostic.identified_member_fraction == 1.0
    assert len(diagnostic.evaluations) == 3
    assert all(
        row.disposition == "completed" and row.outcome is not None for row in diagnostic.evaluations
    )

    assert diagnostic.inputs.graph_ref == run["graph_ref"]
    assert diagnostic.inputs.graph_sha256 == graph_content_sha256(run["graph"])
    assert diagnostic.inputs.query_treatment == _TREATMENT
    assert diagnostic.inputs.query_outcome == _OUTCOME
    assert diagnostic.inputs.query_sha256 == transportability_candidate_query_sha256(
        _TREATMENT, _OUTCOME
    )
    assert diagnostic.inputs.source_context_sha256 == _sha(run["source"].model_dump(mode="json"))
    assert diagnostic.inputs.target_context_sha256 == _sha(run["target"].model_dump(mode="json"))
    assert diagnostic.attempt.run_id == run["execution"].state.run_id
    assert diagnostic.attempt.node_alias == "run_transportability"
    assert diagnostic.attempt.attempt_number == 1
    assert diagnostic.parameters["verified_node_hard_deadline_s"] == canonical_timeout_s
    assert diagnostic.resource_resolution.effective_limits["node_timeout_s"] == canonical_timeout_s

    ir_store = ensure_ir_artifact_store(store)
    member_relations: set[str] = set()
    for row in diagnostic.evaluations:
        member = load_causal_graph_model(ir_store, row.member_graph_ref)
        relation = _assert_g06_math(member, row.outcome.result)
        assert relation not in member_relations
        member_relations.add(relation)
    assert member_relations == {
        f"{_TREATMENT}->{_OUTCOME}",
        f"{_OUTCOME}->{_TREATMENT}",
        "bidirected",
    }

    assert report.transport_result == result
    assert report.schema_version == "1.1"
    assert _ref_identity(
        run["execution"].state.artifacts_index[ARTIFACT_TRANSPORTABILITY_RESULT_REF]
    ) == _ref_identity(result_ref)
    assert _ref_identity(
        run["execution"].state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    ) == _ref_identity(report_ref)
    assert result_ref.manifest_profile_sha256 is not None
    assert store.verify(result_ref).ok
    assert report_ref.manifest_profile_sha256 is not None
    assert store.verify(report_ref).ok
    result_manifest = store.get_manifest(result_ref)
    report_manifest = store.get_manifest(report_ref)
    assert result_manifest.artifact_schema.version == "2.2"
    assert report_manifest.artifact_schema.version == "1.1"
    result_inputs = {item.role: item for item in result_manifest.inputs}
    report_inputs = {item.role: item for item in report_manifest.inputs}
    assert {
        "transportability_attempt_basis",
        "transportability_workflow_spec",
        "transportability_input_state",
        "selected_causal_graph",
        "causal_effect_report",
    }.issubset(result_inputs)
    assert _ref_identity(result_inputs["transportability_attempt_basis"]) == _ref_identity(
        diagnostic.attempt.basis_ref
    )
    assert _ref_identity(result_inputs["transportability_workflow_spec"]) == _ref_identity(
        diagnostic.attempt.workflow_spec_ref
    )
    assert _ref_identity(result_inputs["transportability_input_state"]) == _ref_identity(
        diagnostic.attempt.input_state_ref
    )
    _assert_same_selected_artifact(
        result_inputs["selected_causal_graph"],
        diagnostic.inputs.graph_ref,
        store=store,
    )
    _assert_same_selected_artifact(
        result_inputs["causal_effect_report"],
        run["report_ref"],
        store=store,
    )
    _assert_same_selected_artifact(
        report_inputs["transportability_result"],
        result_ref,
        store=store,
    )

    direct = PassContext(
        ir=None,
        state={
            "artifacts_index": {ARTIFACT_TRANSPORTABILITY_RESULT_REF: result_ref},
            "params": {"transport_required": True},
            "_store": store,
        },
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id=run["execution"].state.run_id,
    )
    report_ctx = PassContext(
        ir=None,
        state={
            "artifacts_index": {ARTIFACT_CAUSAL_REPORT_REF: report_ref},
            "_store": store,
        },
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id=run["execution"].state.run_id,
    )
    assert any(
        item.code == "TRANSPORT_UNSUPPORTED"
        for item in TransportabilityRequiredPass().validate(direct)
    )
    assert any(
        item.code == "TRANSPORT_UNSUPPORTED"
        for item in TransportabilityRequiredPass().validate(report_ctx)
    )


def test_bounded_pag_family_persists_real_partial_solver_prefix_without_promotion(
    tmp_path: Path,
) -> None:
    graph = _partial_pag_graph()
    circle_endpoints = sum(
        mark is EdgeMark.CIRCLE for edge in graph.edges for mark in (edge.mark_src, edge.mark_dst)
    )
    selected_assignment_space = 1 << circle_endpoints
    run = _run(tmp_path, graph=graph, node_timeout_s=_canonical_transport_node_timeout_s())
    worker_receipts = _assert_supervised_worker_trace(run)
    assert run["execution"].report.status == "ok", run["execution"].report.model_dump(mode="json")
    _assert_candidate_outputs_staged(worker_receipts, run)

    store, result_ref, report_ref, result, report = _fresh(run)
    _assert_outer_refusal(result)
    diagnostic = result.candidate_diagnostics
    assert diagnostic.disposition == "partial"
    assert diagnostic.assignment_space_size == str(selected_assignment_space)
    assert diagnostic.assignment_space_size == "4096"
    assert diagnostic.generation_coverage == "not_established"
    assert diagnostic.unattempted_proposals is not None
    assert int(diagnostic.unattempted_proposals) > 0
    assert diagnostic.proposals
    assert diagnostic.generation_budget.termination == "budget_exhausted"
    assert diagnostic.generation_budget.admission == "admitted"

    admitted_members = {
        row.member_sha256 for row in diagnostic.proposals if row.disposition == "admitted"
    }
    assert admitted_members
    assert {row.member_sha256 for row in diagnostic.evaluations} == admitted_members
    completed = [row for row in diagnostic.evaluations if row.disposition == "completed"]
    assert completed
    assert all(row.outcome is not None for row in completed)
    identified = sum(
        row.outcome is not None and row.outcome.status is TransportabilityStatus.IDENTIFIED
        for row in completed
    )
    # G04 denominator is completed selected-member outcomes, not generated,
    # attempted, interrupted, or the whole selected PAG class.
    assert diagnostic.identified_member_fraction == identified / len(completed)

    assert report.transport_result == result
    assert _ref_identity(
        run["execution"].state.artifacts_index[ARTIFACT_TRANSPORTABILITY_RESULT_REF]
    ) == _ref_identity(result_ref)
    assert _ref_identity(
        run["execution"].state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    ) == _ref_identity(report_ref)
    assert store.verify(result_ref).ok
    assert store.verify(report_ref).ok
    result_inputs = {item.role: item for item in store.get_manifest(result_ref).inputs}
    report_inputs = {item.role: item for item in store.get_manifest(report_ref).inputs}
    assert "transportability_attempt_basis" in result_inputs
    assert "transportability_workflow_spec" in result_inputs
    assert "transportability_input_state" in result_inputs
    _assert_same_selected_artifact(
        result_inputs["selected_causal_graph"], run["graph_ref"], store=store
    )
    _assert_same_selected_artifact(
        result_inputs["causal_effect_report"], run["report_ref"], store=store
    )
    _assert_same_selected_artifact(
        report_inputs["transportability_result"], result_ref, store=store
    )

    consumer = PassContext(
        ir=None,
        state={
            "artifacts_index": {ARTIFACT_TRANSPORTABILITY_RESULT_REF: result_ref},
            "params": {"transport_required": True},
            "_store": store,
        },
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id=run["execution"].state.run_id,
    )
    assert any(
        item.code == "TRANSPORT_UNSUPPORTED"
        for item in TransportabilityRequiredPass().validate(consumer)
    )


@pytest.mark.parametrize(
    ("drift_kind", "expected_reason"),
    [
        ("missing", "conditional_transport_resource_policy_snapshot_missing"),
        ("changed", "conditional_transport_resource_policy_snapshot_mismatch"),
    ],
)
def test_resource_policy_drift_refuses_before_candidate_family_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift_kind: str,
    expected_reason: str,
) -> None:
    from polisyos.scientist.nodes.builtins.causal import resolve_transport

    params = _canonical_transport_node_params()
    if drift_kind == "missing":
        params.pop(CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM)
    else:
        policy = copy.deepcopy(params[CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM])
        policy["limits"]["max_members"] += 1
        params[CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM] = policy

    family_calls: list[str] = []
    evaluate_family = resolve_transport.evaluate_pag_member_family

    def observe_family(
        graph: CausalGraphModel,
        *,
        profile_id: str,
        profile_revision: str,
        budget: PAGMemberBudget,
    ) -> PAGMemberFamilyResult:
        family_calls.append(graph_content_sha256(graph))
        return evaluate_family(
            graph,
            profile_id=profile_id,
            profile_revision=profile_revision,
            budget=budget,
        )

    monkeypatch.setattr(resolve_transport, "evaluate_pag_member_family", observe_family)
    run = _run(
        tmp_path / drift_kind,
        node_params_override=params,
    )
    report_dump = run["execution"].report.model_dump(mode="json")
    assert run["execution"].report.status == "fail", report_dump
    assert expected_reason in repr(report_dump)
    assert family_calls == []

    state = run["execution"].state
    assert _ref_identity(state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]) == _ref_identity(
        run["report_ref"]
    )
    assert ARTIFACT_TRANSPORTABILITY_RESULT_REF not in state.artifacts_index
    store = FileSystemCAS(run["cas_root"], tenant_id=_TENANT_ID, cell_id=_CELL_ID)
    report = load_causal_effect_report(ensure_ir_artifact_store(store), run["report_ref"])
    assert report.transport_result is None
    assert store.verify(run["report_ref"]).ok


def test_report_write_failure_keeps_candidate_result_unpublished(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _run(
        tmp_path,
        fail_candidate_report_persist=True,
        monkeypatch=monkeypatch,
    )
    worker_receipts = _assert_supervised_worker_trace(run, expected_node_event="NODE_FAIL")
    assert worker_receipts == []
    marker = run["spawned_report_fault_marker"]
    assert isinstance(marker, Path) and marker.is_file()
    marker_payload = json.loads(marker.read_text(encoding="utf-8"))
    assert marker_payload["schema_version"] == "1.1"
    assert marker_payload["worker_pid"] != os.getpid()
    assert run["execution"].report.status == "fail"
    state = run["execution"].state
    assert _ref_identity(state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]) == _ref_identity(
        run["report_ref"]
    )
    assert ARTIFACT_TRANSPORTABILITY_RESULT_REF not in state.artifacts_index

    store = FileSystemCAS(run["cas_root"], tenant_id=_TENANT_ID, cell_id=_CELL_ID)
    ir_store = ensure_ir_artifact_store(store)
    report = load_causal_effect_report(ir_store, run["report_ref"])
    assert report.transport_result is None
    assert store.verify(run["report_ref"]).ok

    trace_records = [
        json.loads(line)
        for line in run["trace_path"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    dead_letter_events = [
        record for record in trace_records if record.get("event") == "NODE_DEAD_LETTER"
    ]
    assert len(dead_letter_events) == 1
    dead_letter_outputs = dead_letter_events[0]["refs"]["outputs"]
    assert len(dead_letter_outputs) == 1
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.scientist.replay import load_dead_letter

    dead_letter_ref = ArtifactRef.model_validate(dead_letter_outputs[0])
    assert dead_letter_ref.kind == "scientist.dead_letter"
    dead_letter = load_dead_letter(store, dead_letter_ref.artifact_id)
    assert dead_letter.alias == "run_transportability"
    assert dead_letter.error_type == "_WorkerNodeError"
    assert dead_letter.error_message == "OSError: injected_spawned_candidate_report_write_failure"


@pytest.mark.parametrize(
    ("graph", "profile_id", "generation_termination"),
    [
        (_graph(), _PROFILE, "not_started"),
        (
            CausalGraphModel(
                graph_type=GraphType.DAG,
                nodes=[_TREATMENT, _OUTCOME],
                edges=[CausalEdge(src=_TREATMENT, dst=_OUTCOME)],
            ),
            "transport.conditional.resolved_graph",
            "not_required",
        ),
        (
            CausalGraphModel(
                graph_type=GraphType.ADMG,
                nodes=[_TREATMENT, _OUTCOME],
                edges=[CausalEdge(src=_TREATMENT, dst=_OUTCOME)],
            ),
            "transport.conditional.resolved_graph",
            "not_required",
        ),
    ],
    ids=("pag", "dag", "admg"),
)
def test_verified_node_deadline_below_phase_budget_refuses_before_graph_work(
    tmp_path: Path,
    graph: CausalGraphModel,
    profile_id: str,
    generation_termination: str,
) -> None:
    run = _run(
        tmp_path,
        graph=graph,
        profile_id=profile_id,
        node_timeout_s=75.0,
    )
    if run["execution"].report.status != "ok":
        pytest.fail(json.dumps(run["execution"].report.model_dump(mode="json"), sort_keys=True))
    _store, _result_ref, _report_ref, result, _report = _fresh(run)
    _assert_outer_refusal(result)
    diagnostic = result.candidate_diagnostics
    assert diagnostic.disposition == "unsupported"
    assert (
        diagnostic.reason.code
        == "conditional_transport_node_timeout_incompatible_with_phase_budget"
    )
    assert diagnostic.parameters["verified_node_hard_deadline_s"] == 75.0
    assert diagnostic.resource_resolution.status == "refused"
    assert (
        diagnostic.resource_resolution.reason_code
        == "conditional_transport_node_timeout_incompatible_with_phase_budget"
    )
    assert diagnostic.generation_budget.termination == generation_termination
    assert diagnostic.evaluation_budget.termination == "not_started"
    assert diagnostic.evaluations == ()


@pytest.mark.parametrize(
    ("effective_timeout", "supervisor_deadline", "remaining"),
    [
        (75.0, 200.0, 100.0),
        (120.0, 174.0, 74.0),
    ],
    ids=("effective-timeout", "live-supervisor-window"),
)
def test_candidate_deadline_evidence_records_each_insufficient_bound(
    monkeypatch: pytest.MonkeyPatch,
    effective_timeout: float,
    supervisor_deadline: float,
    remaining: float,
) -> None:
    from types import SimpleNamespace

    from polisyos.scientist.nodes.builtins.causal import resolve_transport

    monkeypatch.setattr(resolve_transport.time, "monotonic", lambda: 100.0)
    attempt = SimpleNamespace(
        effective_worker_timeout_s=effective_timeout,
        supervisor_deadline_monotonic=supervisor_deadline,
    )
    evidence, refusal = resolve_transport._candidate_worker_deadline_evidence(
        attempt,
        phase_limit=75.0,
    )

    assert refusal == "conditional_transport_candidate_worker_deadline_insufficient"
    assert evidence is not None
    assert evidence["effective_worker_timeout_s_hex"] == effective_timeout.hex()
    assert evidence["supervisor_deadline_monotonic_hex"] == supervisor_deadline.hex()
    assert evidence["supervisor_deadline_remaining_seconds"] == remaining


def test_wrong_graph_profile_query_and_context_fail_closed(tmp_path: Path) -> None:
    wrong_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=[_TREATMENT, _OUTCOME],
        edges=[CausalEdge(src=_TREATMENT, dst=_OUTCOME)],
    )
    graph_run = _run(tmp_path / "wrong-graph", graph=wrong_graph)
    _store, _rr, _cr, graph_result, _report = _fresh(graph_run)
    _assert_outer_refusal(graph_result)
    graph_diag = graph_result.candidate_diagnostics
    assert graph_diag.disposition == "unsupported"
    assert graph_diag.reason.code == "candidate_profile_input_not_supported"
    assert graph_diag.evaluations == ()

    profile_run = _run(
        tmp_path / "wrong-profile",
        profile_id="transport.conditional.resolved_graph",
    )
    _store, _rr, _cr, profile_result, _report = _fresh(profile_run)
    _assert_outer_refusal(profile_result)
    profile_diag = profile_result.candidate_diagnostics
    assert profile_diag.disposition == "unsupported"
    assert profile_diag.reason is not None
    assert profile_diag.reason.code == "candidate_profile_input_not_supported"
    assert profile_diag.evaluations == ()

    query_run = _run(
        tmp_path / "wrong-query",
        query_outcome="outcome_not_in_selected_graph",
    )
    _store, query_result_ref, query_report_ref, query_result, query_report = _fresh(query_run)
    _assert_outer_refusal(query_result)
    query_diag = query_result.candidate_diagnostics
    assert query_diag.inputs.query_treatment == _TREATMENT
    assert query_diag.inputs.query_outcome == "outcome_not_in_selected_graph"
    assert query_diag.inputs.query_sha256 == transportability_candidate_query_sha256(
        _TREATMENT, "outcome_not_in_selected_graph"
    )
    assert query_diag.disposition == "partial"
    assert query_diag.identified_member_fraction is None
    assert query_diag.parameters["evaluation_completed_retained_member_count"] == 0
    assert query_diag.parameters["evaluation_attempted_member_count"] == len(query_diag.evaluations)
    assert query_diag.evaluations
    assert all(row.disposition == "error" for row in query_diag.evaluations)
    assert all(row.outcome is None for row in query_diag.evaluations)
    assert all(
        row.reason is not None and row.reason.code == "candidate_member_query_binding_mismatch"
        for row in query_diag.evaluations
    )
    assert query_run["execution"].state.params["query_outcome"] == ("outcome_not_in_selected_graph")
    assert query_run["execution"].state.params["conditional_transport_request"] == {
        "schema_version": "1.0",
        "profile_id": _PROFILE,
        "profile_revision": _REVISION,
        "selection_identity": _SELECTION,
    }
    assert query_report.transport_result == query_result
    assert _ref_identity(
        query_run["execution"].state.artifacts_index[ARTIFACT_TRANSPORTABILITY_RESULT_REF]
    ) == _ref_identity(query_result_ref)
    assert _ref_identity(
        query_run["execution"].state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    ) == _ref_identity(query_report_ref)
    assert _store.verify(query_result_ref).ok
    assert _store.verify(query_report_ref).ok

    context_run = _run(tmp_path / "wrong-context", source_context="invalid-context")
    context_report = context_run["execution"].report
    assert context_report.status == "fail"
    context_errors = [node.error for node in context_report.nodes if node.error is not None]
    assert len(context_errors) == 1
    assert context_errors[0].code == "node.invalid_state"
    assert context_errors[0].message == "context profile must be an object when supplied"
    assert context_run["execution"].state.params["source_context"] == "invalid-context"
    assert context_run["execution"].state.params["conditional_transport_request"] == {
        "schema_version": "1.0",
        "profile_id": _PROFILE,
        "profile_revision": _REVISION,
        "selection_identity": _SELECTION,
    }
    assert ARTIFACT_TRANSPORTABILITY_RESULT_REF not in (
        context_run["execution"].state.artifacts_index
    )


def test_absent_null_and_malformed_public_request_are_distinct() -> None:
    base = {"data_source": {"data_snapshot_ref": _SHA_A}}
    absent = WorkflowRunRequest.model_validate({**base, "params": {"query_treatment": _TREATMENT}})
    assert "conditional_transport_request" not in absent.params

    with pytest.raises(ValidationError) as null_error:
        WorkflowRunRequest.model_validate(
            {**base, "params": {"conditional_transport_request": None}}
        )
    assert "workflow_conditional_transport_request_explicit_null" in str(null_error.value)

    with pytest.raises(ValidationError) as malformed_error:
        WorkflowRunRequest.model_validate(
            {
                **base,
                "params": {
                    "conditional_transport_request": {
                        "schema_version": "1.0",
                        "profile_id": _PROFILE,
                        "profile_revision": _REVISION,
                        "unknown": "extra",
                    }
                },
            }
        )
    assert "workflow_conditional_transport_request_invalid" in str(malformed_error.value)


def test_solver_property_removal_with_identified_marker_fails_math_oracle() -> None:
    """Formula markers cannot substitute for the independently checked law."""
    forward_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=[_TREATMENT, _OUTCOME],
        edges=[CausalEdge(src=_TREATMENT, dst=_OUTCOME)],
    )
    wrong_source_marginal = EstimandAST(
        query_str=f"P_s({_OUTCOME})",
        root=DistributionRef(
            domain=DistributionDomain.SOURCE,
            variables=(_OUTCOME,),
        ),
        treatment=_TREATMENT,
        outcome=_OUTCOME,
        all_variables=(_TREATMENT, _OUTCOME),
        object_kind="distribution",
        identification_method="marker_only",
    )
    marker_only = TransportabilityResult(
        query=f"P*({_OUTCOME}|do({_TREATMENT}))",
        status=TransportabilityStatus.IDENTIFIED,
        transport_mode=TransportMode.TRANSPORT_FORMULA,
        feasible=True,
        identification_engine="marker_only",
        estimand_ast=wrong_source_marginal.model_dump(mode="json"),
        transport_formula=TransportFormula(
            formula_str=(f"P*({_OUTCOME}|do({_TREATMENT})) = P_s({_OUTCOME}|{_TREATMENT})"),
            stratification_variables=[],
            source_quantities=[f"P_s({_OUTCOME}|{_TREATMENT})"],
            target_quantities=[],
            adjustment_type="marker_only",
        ),
    )
    parsed = EstimandAST.model_validate(marker_only.estimand_ast)
    refs = parsed.collect_distribution_refs()
    assert len(refs) == 1
    assert refs[0].variables == (_OUTCOME,)
    assert refs[0].domain is DistributionDomain.SOURCE
    assert refs[0].conditioning == ()
    assert refs[0].intervention_set == ()
    with pytest.raises(AssertionError):
        _assert_g06_math(forward_graph, marker_only)


def _install_spawned_selected_report_lineage_probe(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str,
) -> Path:
    """Seed a valid alternate selected lineage view through normal typed writers."""
    from polisyos.scientist.nodes.builtins.causal import resolve_transport

    capsule_dir = root / "selected-report-lineage-startup-capsule"
    capsule_dir.mkdir(parents=True, exist_ok=True)
    marker = root / "selected-report-lineage-witness.json"
    source_root = Path(resolve_transport.__file__).resolve().parents[5]
    candidate_source = (
        Path(__file__).resolve().parents[3]
        / "src/polisyos/scientist/nodes/builtins/causal/resolve_transport.py"
    )
    prior_pythonpath = os.environ.get("PYTHONPATH")
    pythonpath = [str(capsule_dir), str(source_root)]
    if prior_pythonpath:
        pythonpath.append(prior_pythonpath)
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(pythonpath))
    monkeypatch.setenv("POLICYOS_TEST_REPORT_LINEAGE_MODE", mode)
    monkeypatch.setenv("POLICYOS_TEST_REPORT_LINEAGE_MARKER", str(marker))
    module_name = "polisyos.scientist.nodes.builtins.causal.resolve_transport"
    mode_key = json.dumps("POLICYOS_TEST_REPORT_LINEAGE_MODE")
    marker_key = json.dumps("POLICYOS_TEST_REPORT_LINEAGE_MARKER")
    startup_lines = [
        "import importlib.util",
        "import json",
        "import os",
        "import sys",
        "from pathlib import Path",
        "",
        f"_candidate_source = {json.dumps(str(candidate_source))}",
        f"_module_name = {json.dumps(module_name)}",
        "import polisyos.scientist.nodes.builtins.causal as _causal_package",
        "_spec = importlib.util.spec_from_file_location(_module_name, _candidate_source)",
        "if _spec is None or _spec.loader is None:",
        "    raise RuntimeError('candidate_transport_source_overlay_unavailable')",
        "_module = importlib.util.module_from_spec(_spec)",
        "sys.modules[_module_name] = _module",
        "_spec.loader.exec_module(_module)",
        "_causal_package.resolve_transport = _module",
        "from polisyos.scientist.orchestration.engine import component_identity",
        "_candidate_owner = component_identity._owner(_module.RunTransportabilityNode)",
        "component_identity._OWNERS[_candidate_owner.component_id] = _candidate_owner",
        "",
        "from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle",
        "",
        "_original_report_writer = _module.persist_causal_effect_report",
        "_original_result_writer = _module.persist_transportability_result",
        "",
        "def _profile(manifest):",
        "    return ManifestLifecycle.profile_sha256(manifest)",
        "",
        "def _lineage_profiles(manifest):",
        "    return [",
        "        edge.manifest_profile_sha256",
        "        for edge in manifest.inputs",
        "        if edge.role == 'transportability_result'",
        "    ]",
        "",
        "def _seed_selected_report_view(*args, **kwargs):",
        "    report = args[1]",
        "    if kwargs.get('schema_version') != '1.1' or report.transport_result is None:",
        "        return _original_report_writer(*args, **kwargs)",
        "    store = args[0]",
        "    actual_inputs = list(kwargs.get('inputs') or [])",
        "    result_edges = [",
        "        edge for edge in actual_inputs if edge.role == 'transportability_result'",
        "    ]",
        "    if len(result_edges) != 1:",
        "        raise RuntimeError('lineage_probe_result_edge_count_invalid')",
        "    actual_result_edge = result_edges[0]",
        "    if actual_result_edge.manifest_profile_sha256 is None:",
        "        raise RuntimeError('lineage_probe_actual_result_profile_missing')",
        "    actual_result_manifest = store.get_manifest_by_profile(",
        "        actual_result_edge.artifact_id, actual_result_edge.manifest_profile_sha256",
        "    )",
        "    alternate_inputs = list(reversed(actual_result_manifest.inputs))",
        "    if alternate_inputs == list(actual_result_manifest.inputs):",
        "        raise RuntimeError('lineage_probe_needs_multiple_distinct_inputs')",
        "    alternate_result_ref = _original_result_writer(",
        "        store,",
        "        report.transport_result,",
        "        inputs=alternate_inputs,",
        "        schema_version=report.transport_result.schema_version,",
        "        return_selected_profile=True,",
        "    )",
        "    if str(alternate_result_ref.artifact_id) != str(actual_result_edge.artifact_id):",
        "        raise RuntimeError('lineage_probe_result_payload_identity_changed')",
        "    alternate_profile = alternate_result_ref.manifest_profile_sha256",
        "    if alternate_profile is None or alternate_profile == actual_result_edge.manifest_profile_sha256:",
        "        raise RuntimeError('lineage_probe_alternate_result_profile_not_distinct')",
        "    alternate_report_inputs = [",
        "        edge.model_copy(update={'manifest_profile_sha256': alternate_profile})",
        "        if edge.role == 'transportability_result'",
        "        else edge",
        "        for edge in actual_inputs",
        "    ]",
        "    seed_kwargs = dict(kwargs)",
        "    seed_kwargs['inputs'] = alternate_report_inputs",
        "    seed_kwargs['return_selected_profile'] = True",
        "    wrong_lineage_ref = _original_report_writer(*args, **seed_kwargs)",
        "    if wrong_lineage_ref.manifest_profile_sha256 is None:",
        "        raise RuntimeError('lineage_probe_seed_report_profile_missing')",
        "    if os.environ.get(" + mode_key + ") == 'wrong_selected_ref':",
        "        returned_ref = wrong_lineage_ref",
        "    else:",
        "        returned_ref = _original_report_writer(*args, **kwargs)",
        "        if str(returned_ref.artifact_id) != str(wrong_lineage_ref.artifact_id):",
        "            raise RuntimeError('lineage_probe_report_payload_identity_changed')",
        "    default_manifest = store.get_manifest(returned_ref.artifact_id)",
        "    selected_manifest = store.get_manifest(returned_ref)",
        "    default_profile = _profile(default_manifest)",
        "    selected_profile = returned_ref.manifest_profile_sha256",
        "    if selected_profile is None or _profile(selected_manifest) != selected_profile:",
        "        raise RuntimeError('lineage_probe_selected_manifest_not_resolved')",
        "    marker_payload = {",
        "        'mode': os.environ.get(" + mode_key + "),",
        "        'worker_pid': os.getpid(),",
        "        'report_artifact_id': str(returned_ref.artifact_id),",
        "        'default_report_profile': default_profile,",
        "        'selected_report_profile': selected_profile,",
        "        'actual_result_profile': actual_result_edge.manifest_profile_sha256,",
        "        'alternate_result_profile': alternate_profile,",
        "        'default_result_edge_profiles': _lineage_profiles(default_manifest),",
        "        'selected_result_edge_profiles': _lineage_profiles(selected_manifest),",
        "    }",
        f"    Path(os.environ[{marker_key}]).write_text(",
        "        json.dumps(marker_payload, sort_keys=True), encoding='utf-8'",
        "    )",
        "    return returned_ref",
        "",
        "_module.persist_causal_effect_report = _seed_selected_report_view",
    ]
    startup_source = "\n".join(startup_lines) + "\n"
    (capsule_dir / "sitecustomize.py").write_text(startup_source, encoding="utf-8")
    return marker


def _load_candidate_transport_module_for_test(
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    """Use the same candidate source and builtin owner in parent and worker."""
    import importlib.util
    import sys

    import polisyos.scientist.nodes.builtins.causal as causal_package
    from polisyos.scientist.orchestration.engine import component_identity

    module_name = "polisyos.scientist.nodes.builtins.causal.resolve_transport"
    candidate_source = (
        Path(__file__).resolve().parents[3]
        / "src/polisyos/scientist/nodes/builtins/causal/resolve_transport.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, candidate_source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(causal_package, "resolve_transport", module)
    owner = component_identity._owner(module.RunTransportabilityNode)
    monkeypatch.setitem(component_identity._OWNERS, owner.component_id, owner)
    monkeypatch.setattr(
        sys.modules[__name__], "RunTransportabilityNode", module.RunTransportabilityNode
    )
    return module


def test_conditional_report_guard_uses_the_selected_manifest_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use exact selected manifest edges even when a valid default view differs."""
    from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle

    _load_candidate_transport_module_for_test(monkeypatch)
    positive = _run(
        tmp_path / "competing-default",
        selected_report_lineage_probe="competing_default",
        monkeypatch=monkeypatch,
    )
    marker = positive["spawned_report_lineage_marker"]
    assert isinstance(marker, Path) and marker.is_file()
    positive_witness = json.loads(marker.read_text(encoding="utf-8"))
    assert positive_witness["mode"] == "competing_default"
    assert positive_witness["worker_pid"] != os.getpid()
    assert positive_witness["default_report_profile"] != positive_witness["selected_report_profile"]
    assert positive_witness["default_result_edge_profiles"] == [
        positive_witness["alternate_result_profile"]
    ]
    assert positive_witness["selected_result_edge_profiles"] == [
        positive_witness["actual_result_profile"]
    ]
    assert positive_witness["actual_result_profile"] != positive_witness["alternate_result_profile"]
    if positive["execution"].report.status != "ok":
        pytest.fail(
            json.dumps(positive["execution"].report.model_dump(mode="json"), sort_keys=True)
        )
    _assert_supervised_worker_trace(positive)
    _store, result_ref, report_ref, result, report = _fresh(positive)
    _assert_outer_refusal(result)
    assert report.transport_result == result
    assert result_ref.manifest_profile_sha256 == positive_witness["actual_result_profile"]
    selected_manifest = _store.get_manifest(report_ref)
    default_manifest = _store.get_manifest(report_ref.artifact_id)
    assert ManifestLifecycle.profile_sha256(selected_manifest) == report_ref.manifest_profile_sha256
    assert (
        ManifestLifecycle.profile_sha256(default_manifest)
        == positive_witness["default_report_profile"]
    )
    selected_edges = [
        edge for edge in selected_manifest.inputs if edge.role == "transportability_result"
    ]
    default_edges = [
        edge for edge in default_manifest.inputs if edge.role == "transportability_result"
    ]
    assert len(selected_edges) == len(default_edges) == 1
    assert selected_edges[0].manifest_profile_sha256 == result_ref.manifest_profile_sha256
    assert default_edges[0].manifest_profile_sha256 != result_ref.manifest_profile_sha256

    negative = _run(
        tmp_path / "wrong-selected-edge",
        selected_report_lineage_probe="wrong_selected_ref",
        monkeypatch=monkeypatch,
    )
    negative_marker = negative["spawned_report_lineage_marker"]
    assert isinstance(negative_marker, Path) and negative_marker.is_file()
    negative_witness = json.loads(negative_marker.read_text(encoding="utf-8"))
    assert negative_witness["mode"] == "wrong_selected_ref"
    assert negative_witness["selected_report_profile"] == negative_witness["default_report_profile"]
    assert negative_witness["selected_result_edge_profiles"] == [
        negative_witness["alternate_result_profile"]
    ]
    assert negative_witness["alternate_result_profile"] != negative_witness["actual_result_profile"]
    negative_dump = negative["execution"].report.model_dump(mode="json")
    assert negative["execution"].report.status == "fail", negative_dump
    dead_letter_events = [
        json.loads(line)
        for line in negative["trace_path"].read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("event") == "NODE_DEAD_LETTER"
    ]
    assert len(dead_letter_events) == 1
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.scientist.replay import load_dead_letter

    dead_letter_ref = ArtifactRef.model_validate(dead_letter_events[0]["refs"]["outputs"][0])
    negative_store = FileSystemCAS(
        negative["cas_root"],
        tenant_id=_TENANT_ID,
        cell_id=_CELL_ID,
    )
    dead_letter = load_dead_letter(negative_store, dead_letter_ref.artifact_id)
    assert (
        dead_letter.error_message
        == "ValueError: conditional_transport_report_result_edge_profile_mismatch"
    )
    assert _assert_supervised_worker_trace(negative, expected_node_event="NODE_FAIL") == []
    negative_state = negative["execution"].state
    assert _ref_identity(
        negative_state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    ) == _ref_identity(negative["report_ref"])
    assert ARTIFACT_TRANSPORTABILITY_RESULT_REF not in negative_state.artifacts_index
