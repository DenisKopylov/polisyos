from __future__ import annotations

import logging
from types import SimpleNamespace

import numpy as np
import pytest


def _put_selected(store, payload, *, kind, schema_name, schema_version, inputs=None):
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.canon import CanonSpec

    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def test_selected_plan_is_compiled_dispatched_and_projected(tmp_path, monkeypatch):
    from polisyos.common.async_tools import run_coro_sync
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.artifacts.async_store import ensure_async_artifact_store
    from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagNode
    from polisyos.core.contracts.foundry import (
        ExecuteRequest,
        FoundryExecConfig,
        MethodExecutionBundle,
        MethodMetricBindingRequest,
        MethodOutputPayload,
        ProgramGraph,
    )
    from polisyos.core.registry import build_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.foundry.data_plane import build_input_bindings
    from polisyos.foundry.execute.api import execute as execute_foundry
    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry
    from polisyos.ir.governance.policy_spec import PolicySpec
    from polisyos.ir.governance.problem_frame import ObjectiveSpec, ProblemDomain, ProblemFrame
    from polisyos.ir.kernel import (
        DEFAULT_CONSTRAINT_REGISTRY,
        DEFAULT_MECHANISM_REGISTRY,
        DEFAULT_MERGE_RULE_REGISTRY,
        DEFAULT_METRIC_REGISTRY,
        DEFAULT_SELECTOR_FIELD_REGISTRY,
        DEFAULT_SLOT_REGISTRY,
        DEFAULT_UNITS_REGISTRY,
    )
    from polisyos.ir.kernel.method_metrics import (
        METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
        MethodMetricInputRole,
        MethodMetricSemanticContract,
    )
    from polisyos.ir.kernel.metrics import MetricRegistry, MetricSpec
    from polisyos.ir.kernel.slots import SlotKind, SlotRegistry, SlotScope, SlotSpec, SlotValueType
    from polisyos.ir.kernel.units import GenericUnit
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.model_layer.types import OptimizationDirection
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
    from polisyos.scientist.nodes.builtins.planning.build_execution_plan import (
        BuildExecutionPlanNode,
    )
    from polisyos.scientist.nodes.builtins.state_keys import (
        ARTIFACT_EXEC_PLAN_REF,
        ARTIFACT_METHOD_METRIC_BINDING_SET_REF,
        ARTIFACT_PROGRAM_GRAPH_REF,
        INPUT_REGISTRY_BUNDLE_REF,
        INPUT_TRINITY_BUNDLE_REF,
    )
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.policy_design.schema import (
        PolicyCandidateSchema,
        TargetPopulationSpec,
        persist_policy_candidate_schema,
    )

    store = FileSystemCAS(tmp_path / "cas")
    MethodRegistry.get_instance().register(ExAnteSimulationEstimator, override=True)
    signature = ExAnteSimulationEstimator.signature
    semantics = MethodMetricSemanticContract(
        quantity_kind="value",
        quantity_role="scenario_delta",
        population_id="captured_model_input_rows",
        axes=("n_agents",),
        denominator_id="n_agents",
        time_role="pre_dispatch_state",
        producer_contract_id=METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
        input_roles=(
            MethodMetricInputRole(role_id="baseline", method_input_slot_id="baseline"),
            MethodMetricInputRole(role_id="scenario", method_input_slot_id="scenario"),
        ),
        output_value_path=("mean_change",),
    )
    metric_id = "metric_ex_ante_mean_change"
    objective_id = "objective_ex_ante_mean_change"
    metric_registry = MetricRegistry(
        schema_version="1.1",
        metrics={
            **DEFAULT_METRIC_REGISTRY.metrics,
            metric_id: MetricSpec(
                metric_id=metric_id,
                unit_id="value",
                description="Candidate-only model-input mean scenario delta",
                method_semantics=semantics,
            ),
        },
    )
    value_unit = GenericUnit(label="value")
    units_registry = DEFAULT_UNITS_REGISTRY.model_copy(
        update={"units": {**DEFAULT_UNITS_REGISTRY.units, "value": value_unit}},
    )
    slots = dict(DEFAULT_SLOT_REGISTRY.slots)
    slots["baseline"] = slots["agents.income"].model_copy(
        update={"slot_id": "baseline", "state_path": "agents.income"},
    )
    slots["scenario"] = SlotSpec(
        slot_id="scenario",
        scope=SlotScope.PER_AGENT,
        value_type=SlotValueType.DECIMAL,
        unit=DEFAULT_SLOT_REGISTRY.slots["agents.income"].unit,
        kind=SlotKind.STOCK,
        merge_rule=DEFAULT_SLOT_REGISTRY.slots["agents.income"].merge_rule,
        state_path="agents.savings",
        description="Scenario income values supplied for selected method input.",
        reset_rule="carry",
    )
    registry = build_registry_bundle(
        store,
        slot_registry=SlotRegistry(slots=slots),
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
        metric_registry=metric_registry,
        units_registry=units_registry,
        return_selected_profile=True,
    )

    baseline = np.asarray([10.0, 20.0], dtype=np.float64)
    scenario = np.asarray([12.0, 20.0], dtype=np.float64)
    source_payload_ref = _put_selected(
        store,
        {"baseline": baseline.tolist(), "scenario": scenario.tolist()},
        kind="test.method_metric_observational_input",
        schema_name="polisyos.tests.MethodMetricObservationalInput",
        schema_version="1.0",
    )
    from polisyos.fabric.data_plane.orchestrator import _build_snapshot_from_evidence_async
    from polisyos.fabric.evidence.evidence import build_evidence_bundle, persist_evidence_bundle

    evidence_ref = persist_evidence_bundle(
        store,
        build_evidence_bundle(
            sources=[source_payload_ref],
            notes=["Network-free selected inputs for compiled method integration."],
        ),
        return_selected_profile=True,
    )
    data_snapshot_ref = run_coro_sync(
        _build_snapshot_from_evidence_async(
            store=ensure_async_artifact_store(store),
            evidence_ref=evidence_ref,
            datasets_fetched=1,
            source="ad01_compiled_method_test",
        )
    )
    assert data_snapshot_ref is not None
    input_bindings = build_input_bindings(
        store,
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry.bundle_ref,
        return_selected_profile=True,
    )

    problem_frame = ProblemFrame(
        problem_id="ad01_method_metric_problem",
        domain=ProblemDomain.SOCIAL,
        objectives=[
            ObjectiveSpec(
                objective_id=objective_id,
                metric_id=metric_id,
                direction=OptimizationDirection.MAXIMIZE,
            )
        ],
    )
    trinity = TrinityBundle(
        problem_frame=problem_frame,
        policy_spec=PolicySpec(policy_id="ad01_method_metric_policy", interventions=[]),
        model_spec=ModelSpec(
            model_id="ad01_method_metric_model",
            data_snapshot_ref=str(data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    candidate_ref = persist_policy_candidate_schema(
        store,
        PolicyCandidateSchema(
            candidate_id="ad01_method_metric_candidate",
            trinity_bundle=trinity,
            target_population=TargetPopulationSpec(
                population_id="captured_model_input_rows",
                description="Rows provided to the Ex-Ante method fixture.",
            ),
        ),
        inputs=[
            input_ref_from_artifact_ref(data_snapshot_ref, role="world_model_data_snapshot"),
            input_ref_from_artifact_ref(registry.bundle_ref, role="world_model_registry"),
        ],
        return_selected_profile=True,
    )
    trinity_ref = _put_selected(
        store,
        trinity,
        kind=TrinityBundle.ARTIFACT_KIND,
        schema_name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
        schema_version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
        inputs=[input_ref_from_artifact_ref(candidate_ref, role="policy_candidate")],
    )

    run_id = "run-ad01-compiled-method"
    run = RunContext.start(
        store=store,
        registry_bundle=registry.bundle_ref,
        run_id=run_id,
        run_dir=tmp_path / "run",
    )

    class _FoundryPort:
        def compile(self, artifact_store, request):
            from polisyos.foundry.compile.api import compile

            return compile(artifact_store, request)

    context = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("tests.ad01_compiled_method"),
        foundry=_FoundryPort(),
    )
    method_node = MethodDagNode(
        node_id="ex_ante_node",
        method_fqn=signature.fqn,
        method_version=signature.version,
        backend=signature.execution_backend.value,
        params={"poverty_line": None},
        reads_slots=["baseline", "scenario"],
        writes_slots=["result"],
    )
    selected_plan = ExecutionPlan(
        plan_id="ad01-selected-plan",
        run_id=run_id,
        method_dag=[method_node],
    )
    initial_state = ExperimentState(
        run_id=run_id,
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry.bundle_ref,
        },
        params={"execution_plan": selected_plan.model_dump(mode="json")},
    )
    built = BuildExecutionPlanNode().execute(context, initial_state)
    assert built.status == "ok", built.error
    plan_ref = built.state.execution_plan_ref
    assert plan_ref is not None and plan_ref.manifest_profile_sha256 is not None
    candidate_edges = [
        edge for edge in store.get_manifest(plan_ref).inputs if edge.role == "policy_candidate"
    ]
    assert len(candidate_edges) == 1
    assert candidate_edges[0].artifact_id == trinity_ref.artifact_id
    assert candidate_edges[0].manifest_profile_sha256 == trinity_ref.manifest_profile_sha256

    class _CompileSpy:
        def __init__(self):
            self.calls = 0
            self.requests = []

        def compile(self, artifact_store, request):
            self.calls += 1
            self.requests.append(request)
            return _FoundryPort().compile(artifact_store, request)

    compile_spy = _CompileSpy()
    no_binding_context = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("tests.ad01_selected_plan_without_bindings"),
        foundry=compile_spy,
    )
    no_binding_outcome = CompileFoundryNode().execute(no_binding_context, built.state)
    assert compile_spy.calls == 0
    assert no_binding_outcome.status == "fail"
    assert no_binding_outcome.error is not None
    assert no_binding_outcome.error.code == "node.invalid_state"
    assert no_binding_outcome.artifacts == []
    assert ARTIFACT_PROGRAM_GRAPH_REF not in no_binding_outcome.state.artifacts_index
    assert ARTIFACT_METHOD_METRIC_BINDING_SET_REF not in no_binding_outcome.state.artifacts_index

    compile_node = CompileFoundryNode(
        method_metric_bindings=(
            MethodMetricBindingRequest(
                objective_id=objective_id,
                node_id="ex_ante_node",
                output_slot_id="result",
            ),
        )
    )
    compiled = compile_node.execute(context, built.state)
    assert compiled.status == "ok", compiled.error
    program_ref = compiled.state.artifacts_index[ARTIFACT_PROGRAM_GRAPH_REF]
    exec_plan_ref = compiled.state.artifacts_index[ARTIFACT_EXEC_PLAN_REF]
    binding_ref = compiled.state.artifacts_index[ARTIFACT_METHOD_METRIC_BINDING_SET_REF]
    graph = validate_core_model_json_artifact(ProgramGraph, store, program_ref)
    method = next(node for node in graph.nodes if node.node_id == "ex_ante_node")
    assert method.method_fqn == signature.fqn
    assert method.method_version == signature.version
    assert method.method_params == {"poverty_line": None}
    assert method.outputs == []
    source_plan_edges = [
        edge
        for edge in store.get_manifest(program_ref).inputs
        if edge.role == "execution_plan_source"
    ]
    assert len(source_plan_edges) == 1
    assert source_plan_edges[0].artifact_id == plan_ref.artifact_id
    assert source_plan_edges[0].manifest_profile_sha256 == plan_ref.manifest_profile_sha256

    execute_result = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=exec_plan_ref,
            input_bindings_ref=input_bindings.input_bindings_ref,
            registry_bundle_ref=registry.bundle_ref,
            exec_config=FoundryExecConfig(seed=41, mode="dev", capture_env=True),
            return_selected_profile=True,
        ),
    )
    assert execute_result.ok is True, execute_result.notes
    assert execute_result.simulation_result_ref is not None
    assert execute_result.method_execution_bundle_ref is not None
    bundle = validate_core_model_json_artifact(
        MethodExecutionBundle,
        store,
        execute_result.method_execution_bundle_ref,
    )
    occurrence = next(item for item in bundle.occurrences if item.node_id == "ex_ante_node")
    assert occurrence.dispatch is not None and occurrence.dispatch.outcome == "succeeded"
    output_slot = next(item for item in occurrence.output_slots if item.slot_id == "result")
    assert output_slot.output_ref is not None
    output = validate_core_model_json_artifact(MethodOutputPayload, store, output_slot.output_ref)
    assert output.value_path == ("mean_change",)
    assert output.value == pytest.approx(1.0)

    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        _MethodMetricSourceTuple,
        prepare_method_metric_projection_admission,
        read_completed_admitted_method_metric_projection,
    )

    job_id = "job-ad01-compiled-method"
    source_tuple = _MethodMetricSourceTuple(
        job_id=job_id,
        run_id=run_id,
        attempt=1,
        method_result_ref=None,
        simulation_result_ref=execute_result.simulation_result_ref,
        method_execution_bundle_ref=execute_result.method_execution_bundle_ref,
        method_metric_binding_set_ref=binding_ref,
    )
    admission = prepare_method_metric_projection_admission(store, source_tuple=source_tuple)
    assert admission.status == "verified", admission.limitations
    assert admission.admission is not None
    assert admission.admission.source_candidate_ref == candidate_ref
    experiment_state_ref = _put_selected(
        store,
        {"schema_version": "1.0"},
        kind="scientist.experiment_state",
        schema_name="polisyos.scientist.experiment.ExperimentState",
        schema_version="1.0",
    )
    selection = SimpleNamespace(
        selection_kind="graph_method",
        job_id=job_id,
        run_id=run_id,
        attempt=1,
        method_result_ref=None,
        simulation_result_ref=execute_result.simulation_result_ref,
        method_execution_bundle_ref=execute_result.method_execution_bundle_ref,
        method_metric_binding_set_ref=binding_ref,
        source_candidate_ref=candidate_ref,
        source_experiment_state_ref=experiment_state_ref,
        metric_verification_status="verified",
        method_metric_projection=SimpleNamespace(
            vector_ref=admission.admission.vector_ref,
            verifier_revision=admission.admission.verifier_revision,
            verifier_implementation_sha256=admission.admission.verifier_implementation_sha256,
        ),
    )
    completed_source = SimpleNamespace(
        source_run_id=run_id,
        source_candidate_ref=candidate_ref,
        source_experiment_state_ref=experiment_state_ref,
        selection=selection,
    )

    class _CompletedSourceOwner:
        def resolve_completed_method_metric_selection(
            self, *, source_run_id, candidate_ref, tenant_id, cell_id
        ):
            assert source_run_id == run_id
            assert candidate_ref == expected_candidate_ref
            assert (tenant_id, cell_id) == ("tenant-ad01", "cell-ad01")
            return completed_source

    expected_candidate_ref = candidate_ref
    completed = read_completed_admitted_method_metric_projection(
        store,
        owner=_CompletedSourceOwner(),
        source_run_id=run_id,
        candidate_ref=candidate_ref,
        tenant_id="tenant-ad01",
        cell_id="cell-ad01",
    )
    assert completed.status == "selected", completed.limitations
    assert completed.basis is not None
    assert len(completed.basis.observations) == 1
    observation = completed.basis.observations[0]
    assert observation.source_status == "observed"
    assert observation.value == pytest.approx(1.0)
    assert observation.metric_unit_id == "value"

    removed_plan = ExecutionPlan(plan_id="ad01-plan-without-method", run_id=run_id)
    removed_state = ExperimentState(
        run_id=run_id,
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry.bundle_ref,
        },
        params={"execution_plan": removed_plan.model_dump(mode="json")},
    )
    removed_build = BuildExecutionPlanNode().execute(context, removed_state)
    assert removed_build.status == "ok", removed_build.error
    empty_plan_spy = _CompileSpy()
    empty_plan_context = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("tests.ad01_empty_plan_without_bindings"),
        foundry=empty_plan_spy,
    )
    empty_plan_compile = CompileFoundryNode().execute(empty_plan_context, removed_build.state)
    assert empty_plan_spy.calls == 1
    assert empty_plan_spy.requests[0].schema_version == "1.0"
    assert empty_plan_compile.status == "ok", empty_plan_compile.error
    assert ARTIFACT_METHOD_METRIC_BINDING_SET_REF not in empty_plan_compile.state.artifacts_index

    removed_compile = compile_node.execute(context, removed_build.state)
    assert removed_compile.status == "fail"
    assert removed_compile.error is not None
    assert ARTIFACT_METHOD_METRIC_BINDING_SET_REF not in removed_compile.state.artifacts_index


def test_edge_only_selected_plan_without_bindings_is_refused_before_compile(tmp_path):
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagEdge
    from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
    from polisyos.scientist.nodes.builtins.state_keys import (
        ARTIFACT_EXEC_PLAN_REF,
        ARTIFACT_METHOD_METRIC_BINDING_SET_REF,
        ARTIFACT_PROGRAM_GRAPH_REF,
        INPUT_TRINITY_BUNDLE_REF,
        REPORT_COMPILE_REPORT_REF,
    )
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.llm.cycle import persist_candidate_execution_plan

    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = _put_selected(
        store,
        {"schema_version": "1.0"},
        kind="ir.trinity_bundle",
        schema_name="polisyos.ir.TrinityBundle",
        schema_version="1.0",
    )
    edge_only_plan = ExecutionPlan(
        plan_id="ad01-edge-only-selected-plan",
        method_dag=[],
        method_edges=[
            MethodDagEdge(
                src="missing-producer",
                dst="missing-consumer",
                relation="depends_on",
            )
        ],
    )
    selected_plan_ref, exact_candidate_ref = persist_candidate_execution_plan(
        store,
        edge_only_plan,
        candidate_ref,
    )
    assert selected_plan_ref.manifest_profile_sha256 is not None
    candidate_edges = [
        edge
        for edge in store.get_manifest(selected_plan_ref).inputs
        if edge.role == "policy_candidate"
    ]
    assert len(candidate_edges) == 1
    assert candidate_edges[0].artifact_id == exact_candidate_ref.artifact_id
    assert candidate_edges[0].manifest_profile_sha256 == exact_candidate_ref.manifest_profile_sha256

    class _CompileSpy:
        calls = 0

        def compile(self, _artifact_store, _request):
            self.calls += 1
            return SimpleNamespace(
                ok=True,
                compile_report_ref=exact_candidate_ref,
                exec_plan_ref=None,
                derived_refs=[],
            )

    compile_spy = _CompileSpy()
    context = ExecutionContext(
        store=store,
        run=SimpleNamespace(run_id="run-ad01-edge-only"),
        logger=logging.getLogger("tests.ad01_edge_only_selected_plan"),
        foundry=compile_spy,
    )
    state = ExperimentState(
        run_id="run-ad01-edge-only",
        inputs={INPUT_TRINITY_BUNDLE_REF: exact_candidate_ref},
        execution_plan_ref=selected_plan_ref,
    )

    outcome = CompileFoundryNode().execute(context, state)

    assert compile_spy.calls == 0
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.invalid_state"
    assert outcome.error.details["method_dag_node_count"] == 0
    assert outcome.error.details["method_edge_count"] == 1
    assert outcome.artifacts == []
    assert REPORT_COMPILE_REPORT_REF not in outcome.state.reports_index
    assert ARTIFACT_EXEC_PLAN_REF not in outcome.state.artifacts_index
    assert ARTIFACT_PROGRAM_GRAPH_REF not in outcome.state.artifacts_index
    assert ARTIFACT_METHOD_METRIC_BINDING_SET_REF not in outcome.state.artifacts_index
