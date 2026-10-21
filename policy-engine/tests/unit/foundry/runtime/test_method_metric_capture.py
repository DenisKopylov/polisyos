from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import replace
from types import SimpleNamespace
from typing import ClassVar

import numpy as np
import pytest

import polisyos.core.artifacts as core_artifacts
from polisyos.core.artifacts import ArtifactReadBoundsError, validate_core_model_json_artifact
from polisyos.core.artifacts.environment import (
    CPUInfo,
    EnvironmentManifest,
    GPUInfo,
    JAXInfo,
    OSInfo,
    PythonInfo,
)
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecPlan,
    ExecPlanRef,
    LoweredIR,
    LoweredIRRef,
    MethodExecutionBundle,
    MethodMetricBinding,
    MethodMetricBindingRequest,
    MethodMetricBindingSet,
    MethodMetricBindingSetRef,
    MethodMetricInputCapturePayload,
    MethodOutputPayload,
    ProgramEdge,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
    StateSnapshotRef,
)
from polisyos.foundry.compile import trinity_compiler as trinity_compiler_module
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._internal import graph as graph_module
from polisyos.foundry.execute._internal import snapshots as snapshots_module
from polisyos.foundry.execute._internal.graph import (
    _bounded_method_input_arrays,
    _materialize_exact_method_input_state,
    _method_parameter_values,
    _runtime_slot_shape,
    execute_program_graph,
    new_method_execution_capture,
)
from polisyos.foundry.execute._internal.models import ExecutionStrictness
from polisyos.foundry.execute._internal.snapshots import (
    StateSnapshotInputReadRefusal,
    read_state_snapshot_inputs_bounded,
)
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
from polisyos.foundry.methods.exceptions import MethodExecutionAbortError
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
)
from polisyos.ir.kernel.method_metrics import (
    METHOD_METRIC_DIRECT_OUTPUT_LAW_ID,
    METHOD_METRIC_DIRECT_OUTPUT_LAW_VERSION,
    METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
    METHOD_METRIC_UNIT_ADAPTER_ID,
    METHOD_METRIC_UNIT_ADAPTER_VERSION,
    MethodMetricInputRole,
    MethodMetricSemanticContract,
    MethodMetricSourceUnit,
    registered_method_metric_law_metadata,
    registered_method_metric_law_metadata_for,
    registered_method_metric_semantics_match,
    registered_method_metric_unit_adapter_metadata,
    resolve_registered_method_metric_unit_adapter,
)
from polisyos.ir.kernel.metrics import MetricRegistry, MetricSpec
from polisyos.ir.kernel.units import GenericUnit, RateUnit, UnitsRegistry


def _put_owned(
    store: FileSystemCAS,
    payload: object,
    *,
    kind: str,
    inputs: list | None = None,
) -> ArtifactRef:
    payload_type = type(payload)
    schema_name = getattr(payload_type, "ARTIFACT_SCHEMA_NAME", None)
    schema_version = getattr(payload_type, "ARTIFACT_SCHEMA_VERSION", None)
    schema = (
        None
        if schema_name is None or schema_version is None
        else SchemaInfo(name=schema_name, version=schema_version)
    )
    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=schema,
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _metric_method_signature() -> MethodSignature:
    return MethodSignature(
        name="capture_scalar",
        namespace="tests.method_metric_capture",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="result",
                    slot_type=SlotType.SCALAR,
                    unit=Unit(dimension="ratio", symbol="ratio"),
                )
            }
        ),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )


class _ReturnsMetricScalar:
    signature: ClassVar[MethodSignature] = _metric_method_signature()
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="Returns a scalar metric slot")

    @staticmethod
    def pure_step(state, params):
        return {"result": 0.25}


def _make_graph_and_plan(store: FileSystemCAS) -> tuple[ProgramGraphRef, ExecPlanRef]:
    policy_ref = _put_owned(store, {"candidate": "metric-capture-test"}, kind="ir.trinity_bundle")
    registry_ref = _put_owned(store, {"candidate": "registry"}, kind="core.registry_bundle")
    metric_registry_ref = _put_owned(store, {"candidate": "metrics"}, kind="ir.metric_registry")
    units_registry_ref = _put_owned(store, {"candidate": "units"}, kind="ir.units_registry")
    lowered_ir = LoweredIR(ir_ref=policy_ref, mechanisms=[], constraints=[])
    lowered_ir_ref = _put_owned(store, lowered_ir, kind="foundry.lowered_ir")
    graph = ProgramGraph(
        ir_ref=policy_ref,
        lowered_ir_ref=LoweredIRRef.model_validate(lowered_ir_ref.model_dump(mode="python")),
        nodes=[
            ProgramNode(
                node_id="metric_node",
                node_kind="method",
                method_fqn=_ReturnsMetricScalar.signature.fqn,
                method_version=_ReturnsMetricScalar.signature.version,
            )
        ],
        edges=[],
        entrypoints=["metric_node"],
    )
    graph_ref = _put_owned(
        store,
        graph,
        kind="foundry.program_graph",
        inputs=[input_ref_from_artifact_ref(lowered_ir_ref, role="lowered_ir")],
    )
    typed_graph_ref = ProgramGraphRef.model_validate(graph_ref.model_dump(mode="python"))

    source_unit = MethodMetricSourceUnit(dimension="ratio", symbol="ratio", scale=1.0)
    target_unit = RateUnit(base="ratio")
    adapter = resolve_registered_method_metric_unit_adapter(source_unit, target_unit)
    law_id, law_version, law_digest = registered_method_metric_law_metadata()
    adapter_id, adapter_version, adapter_digest = registered_method_metric_unit_adapter_metadata()
    signature = _ReturnsMetricScalar.signature
    method_build_digest = (
        "sha256:"
        + hashlib.sha256(inspect.getsource(_ReturnsMetricScalar).encode("utf-8")).hexdigest()
    )
    binding = MethodMetricBinding(
        binding_id="metric.binding.capture_scalar",
        objective_id="objective.capture_scalar",
        metric_id="metric.capture_scalar",
        node_id="metric_node",
        method_fqn=signature.fqn,
        method_version=signature.version,
        method_abi_digest=signature.abi_digest(),
        method_abi_digest_algorithm="blake2b",
        method_build_digest=method_build_digest,
        method_build_digest_scope="class_source_only",
        output_slot_id="result",
        output_shape="scalar",
        semantics=MethodMetricSemanticContract(
            quantity_kind="economic.rate",
            quantity_role="outcome.level",
            population_id="population.eligible",
            axes=("time.simulation_step",),
            denominator_id="population.eligible",
            time_role="period.end",
            producer_contract_id="producer.policy_metric.v1",
        ),
        source_unit=source_unit,
        target_unit=target_unit,
        law_id=METHOD_METRIC_DIRECT_OUTPUT_LAW_ID,
        law_version=METHOD_METRIC_DIRECT_OUTPUT_LAW_VERSION,
        law_code_digest=law_digest,
        adapter_id=METHOD_METRIC_UNIT_ADAPTER_ID,
        adapter_version=METHOD_METRIC_UNIT_ADAPTER_VERSION,
        adapter_code_digest=adapter.code_digest or adapter_digest,
        conversion_operation=adapter.operation,
        conversion_factor_numerator=adapter.factor_numerator,
        conversion_factor_denominator=adapter.factor_denominator,
        availability="unavailable",
        limitation="test_only_unregistered_metric_semantics",
    )
    binding_set = MethodMetricBindingSet(
        program_graph_ref=typed_graph_ref,
        policy_ref=policy_ref,
        registry_bundle_ref=registry_ref,
        metric_registry_ref=metric_registry_ref,
        units_registry_ref=units_registry_ref,
        bindings=[binding],
    )
    binding_set_ref = _put_owned(
        store,
        binding_set,
        kind=MethodMetricBindingSet.ARTIFACT_KIND,
        inputs=[
            input_ref_from_artifact_ref(typed_graph_ref, role="program_graph"),
            input_ref_from_artifact_ref(policy_ref, role="policy"),
            input_ref_from_artifact_ref(registry_ref, role="registry_bundle"),
            input_ref_from_artifact_ref(metric_registry_ref, role="metric_registry"),
            input_ref_from_artifact_ref(units_registry_ref, role="units_registry"),
        ],
    )
    typed_binding_set_ref = MethodMetricBindingSetRef.model_validate(
        binding_set_ref.model_dump(mode="python")
    )
    plan = ExecPlan(program_ref=typed_graph_ref, order=["metric_node"])
    plan_ref = _put_owned(
        store,
        plan,
        kind=ExecPlan.ARTIFACT_KIND,
        inputs=[
            input_ref_from_artifact_ref(typed_graph_ref, role="program_graph"),
            input_ref_from_artifact_ref(typed_binding_set_ref, role="method_metric_bindings"),
        ],
    )
    return typed_graph_ref, ExecPlanRef.model_validate(plan_ref.model_dump(mode="python"))


def _ex_ante_semantics() -> MethodMetricSemanticContract:
    return MethodMetricSemanticContract(
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


def _make_ex_ante_graph_and_plan(
    store: FileSystemCAS,
    *,
    mutate_prestate: bool = False,
) -> tuple[ProgramGraphRef, ExecPlanRef, MethodMetricBindingSetRef]:
    policy_ref = _put_owned(
        store, {"candidate": "ex-ante-metric-capture"}, kind="ir.trinity_bundle"
    )
    registry_ref = _put_owned(store, {"candidate": "registry"}, kind="core.registry_bundle")
    metric_registry_ref = _put_owned(store, {"candidate": "metrics"}, kind="ir.metric_registry")
    units_registry_ref = _put_owned(store, {"candidate": "units"}, kind="ir.units_registry")
    lowered_ir_ref = _put_owned(
        store,
        LoweredIR(ir_ref=policy_ref, mechanisms=[], constraints=[]),
        kind="foundry.lowered_ir",
    )
    signature = ExAnteSimulationEstimator.signature
    nodes = []
    order = []
    edges = []
    if mutate_prestate:
        writer_payload_ref = _put_owned(
            store,
            {"schedule": {"start_step": 0, "duration_steps": 1}, "params": {}},
            kind="foundry.node_payload",
        )
        nodes.append(
            ProgramNode(
                node_id="prestate_writer",
                node_kind="mechanism",
                mechanism_type="test_prestate_writer",
                params_ref=writer_payload_ref,
                outputs=["agents.income", "agents.reported_income"],
            )
        )
        order.append("prestate_writer")
    nodes.append(
        ProgramNode(
            node_id="ex_ante_node",
            node_kind="method",
            method_fqn=signature.fqn,
            method_version=signature.version,
            inputs=["baseline", "scenario"],
        )
    )
    order.append("ex_ante_node")
    if mutate_prestate:
        edges.append(ProgramEdge(src="prestate_writer", dst="ex_ante_node", relation="depends_on"))
    graph = ProgramGraph(
        ir_ref=policy_ref,
        lowered_ir_ref=LoweredIRRef.model_validate(lowered_ir_ref.model_dump(mode="python")),
        nodes=nodes,
        edges=edges,
        entrypoints=[nodes[0].node_id],
    )
    graph_ref = _put_owned(
        store,
        graph,
        kind="foundry.program_graph",
        inputs=[input_ref_from_artifact_ref(lowered_ir_ref, role="lowered_ir")],
    )
    typed_graph_ref = ProgramGraphRef.model_validate(graph_ref.model_dump(mode="python"))
    semantics = _ex_ante_semantics()
    law_id, law_version, law_digest = registered_method_metric_law_metadata_for(
        signature.fqn, signature.version
    ) or (None, None, None)
    assert law_id is not None and law_version is not None and law_digest is not None
    assert registered_method_metric_semantics_match(law_id, semantics)
    baseline_slot = next(item for item in signature.input_slots if item.name == "baseline")
    source_unit = MethodMetricSourceUnit(
        dimension=baseline_slot.unit.dimension,
        symbol=baseline_slot.unit.symbol,
        scale=float(baseline_slot.unit.scale),
    )
    target_unit = GenericUnit(label="value")
    adapter = resolve_registered_method_metric_unit_adapter(
        source_unit,
        target_unit,
        law_id=law_id,
        semantics=semantics,
    )
    assert adapter.operation == "identity"
    adapter_id, adapter_version, adapter_digest = registered_method_metric_unit_adapter_metadata()
    method_build_digest = (
        "sha256:"
        + hashlib.sha256(inspect.getsource(ExAnteSimulationEstimator).encode("utf-8")).hexdigest()
    )
    output_slot = next(item for item in signature.output_slots if item.name == "result")
    binding = MethodMetricBinding(
        binding_id="method.metric.binding.ex_ante_mean_change",
        objective_id="objective.ex_ante_mean_change",
        metric_id="metric.ex_ante_mean_change",
        node_id="ex_ante_node",
        method_fqn=signature.fqn,
        method_version=signature.version,
        method_abi_digest=signature.abi_digest(),
        method_abi_digest_algorithm="blake2b",
        method_build_digest=method_build_digest,
        method_build_digest_scope="class_source_only",
        output_slot_id="result",
        output_value_path=("mean_change",),
        output_contract_id=output_slot.contract_id,
        output_shape="scalar",
        semantics=semantics,
        source_unit=source_unit,
        target_unit=target_unit,
        law_id=law_id,
        law_version=law_version,
        law_code_digest=law_digest,
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        adapter_code_digest=adapter.code_digest or adapter_digest,
        conversion_operation=adapter.operation,
        conversion_factor_numerator=adapter.factor_numerator,
        conversion_factor_denominator=adapter.factor_denominator,
        availability="available",
    )
    binding_set = MethodMetricBindingSet(
        program_graph_ref=typed_graph_ref,
        policy_ref=policy_ref,
        registry_bundle_ref=registry_ref,
        metric_registry_ref=metric_registry_ref,
        units_registry_ref=units_registry_ref,
        bindings=[binding],
    )
    binding_set_ref = _put_owned(
        store,
        binding_set,
        kind=MethodMetricBindingSet.ARTIFACT_KIND,
        inputs=[
            input_ref_from_artifact_ref(typed_graph_ref, role="program_graph"),
            input_ref_from_artifact_ref(policy_ref, role="policy"),
            input_ref_from_artifact_ref(registry_ref, role="registry_bundle"),
            input_ref_from_artifact_ref(metric_registry_ref, role="metric_registry"),
            input_ref_from_artifact_ref(units_registry_ref, role="units_registry"),
        ],
    )
    typed_binding_set_ref = MethodMetricBindingSetRef.model_validate(
        binding_set_ref.model_dump(mode="python")
    )
    plan = ExecPlan(program_ref=typed_graph_ref, order=order)
    plan_ref = _put_owned(
        store,
        plan,
        kind=ExecPlan.ARTIFACT_KIND,
        inputs=[
            input_ref_from_artifact_ref(typed_graph_ref, role="program_graph"),
            input_ref_from_artifact_ref(
                typed_binding_set_ref,
                role="method_metric_bindings",
            ),
        ],
    )
    return (
        typed_graph_ref,
        ExecPlanRef.model_validate(plan_ref.model_dump(mode="python")),
        typed_binding_set_ref,
    )


def _test_environment_manifest() -> EnvironmentManifest:
    return EnvironmentManifest(
        cpu=CPUInfo(architecture="test", model_name="test-cpu", core_count=1, thread_count=1),
        gpu=GPUInfo(),
        os=OSInfo(system="test", release="1", version="test-os"),
        python=PythonInfo(version="3.12.0", implementation="CPython", compiler="test"),
        jax=JAXInfo(),
    )


def test_signature_default_is_captured_as_effective_method_parameter() -> None:
    node = SimpleNamespace(method_params={})
    method_class = SimpleNamespace(
        signature=SimpleNamespace(parameters=(ParameterSpec(name="rate", default=0.25),))
    )

    values, limitation, observed_count, inventory_limit = _method_parameter_values(
        node, method_class
    )

    assert limitation is None
    assert observed_count == len(values) == 1
    assert inventory_limit == 32
    assert values[0].name == "rate"
    assert values[0].source == "signature_default"
    assert values[0].status == "captured"
    assert values[0].value == 0.25
    assert values[0].value_sha256 is not None


def test_non_method_occurrence_omits_method_inventory_even_with_selection() -> None:
    declared_slot = next(iter(_ReturnsMetricScalar.signature.output_slots))
    planned_method_slots = graph_module._planned_returned_slots(_ReturnsMetricScalar)
    assert planned_method_slots[0].declared_slot_type == declared_slot.slot_type.name

    occurrence = graph_module._planned_method_occurrence(
        occurrence_id="graph-invocation.000001:0:mechanism.one",
        invocation_id="graph-invocation.000001",
        plan_index=0,
        node=SimpleNamespace(node_kind="mechanism", method_params={}),
        node_id="mechanism.one",
        method_identity=None,
        method_class=_ReturnsMetricScalar,
        selected_slot_ids=("result",),
        metric_input_capture_required=True,
    )

    assert occurrence.node_kind == "mechanism"
    assert occurrence.output_slots == []
    assert occurrence.returned_slots == []
    assert occurrence.returned_slot_inventory_status == "not_started"
    assert occurrence.returned_slot_inventory_limit is None
    assert occurrence.dispatch is None


def test_method_input_state_requires_exact_graph_id_to_abi_slot_join() -> None:
    method_class = SimpleNamespace(
        signature=SimpleNamespace(
            input_slots=(
                SimpleNamespace(name="baseline"),
                SimpleNamespace(name="scenario"),
            )
        )
    )
    state = {"baseline": [1.0, 2.0], "scenario": [2.0, 1.0], "other": [99.0]}
    slot_registry = SimpleNamespace(slots={})

    materialized = _materialize_exact_method_input_state(
        state,
        node=SimpleNamespace(inputs=["scenario", "baseline"]),
        method_class=method_class,
        slot_registry=slot_registry,
    )
    ambiguous = _materialize_exact_method_input_state(
        state,
        node=SimpleNamespace(inputs=["baseline"]),
        method_class=method_class,
        slot_registry=slot_registry,
    )

    assert materialized == {
        "scenario": [2.0, 1.0],
        "baseline": [1.0, 2.0],
    }
    assert ambiguous is state


@pytest.mark.parametrize(
    ("scenario_unit", "expected_availability"),
    [
        (Unit("value", "amount"), "available"),
        (Unit("ratio", "ratio"), "unavailable"),
    ],
)
def test_method_metric_compiler_requires_complete_registered_input_unit_set(
    monkeypatch,
    scenario_unit: Unit,
    expected_availability: str,
) -> None:
    profile = "sha256:" + "a" * 64

    def ref(kind: str, index: int) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=f"sha256:{index:064x}",
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256=profile,
        )

    policy_ref = ref("ir.trinity_bundle", 1)
    registry_bundle_ref = ref("core.registry_bundle", 2)
    metric_registry_ref = ref("ir.metric_registry", 3)
    units_registry_ref = ref("ir.units_registry", 4)
    program_graph_ref = ProgramGraphRef.model_validate(ref("foundry.program_graph", 5).model_dump())
    objective_id = "objective.ex_ante_mean_change"
    metric_id = "metric.ex_ante_mean_change"
    request = CompileRequest(
        schema_version="1.1",
        policy_ref=policy_ref,
        method_metric_bindings=[
            MethodMetricBindingRequest(
                objective_id=objective_id,
                node_id="method.ex_ante",
                output_slot_id="result",
            )
        ],
    )
    bundle = SimpleNamespace(
        problem_frame=SimpleNamespace(
            objectives=[SimpleNamespace(objective_id=objective_id, metric_id=metric_id)]
        )
    )
    graph_node = SimpleNamespace(
        node_id="method.ex_ante",
        node_kind="method",
        method_fqn="policy.evaluation.ex_ante_simulation@1.0.0",
        method_version="1.0.0",
    )
    program_graph = SimpleNamespace(nodes=[graph_node])
    registry_content = SimpleNamespace(
        metric_registry=MetricRegistry(
            schema_version="1.1",
            metrics={
                metric_id: MetricSpec(
                    metric_id=metric_id,
                    unit_id="value",
                    method_semantics=_ex_ante_semantics(),
                )
            },
        ),
        units_registry=UnitsRegistry(
            units={"value": GenericUnit(label="value")},
        ),
    )

    class _BindingSetStore:
        payload: MethodMetricBindingSet | None = None

        def put_json(self, payload, _options, **_kwargs):
            self.payload = payload
            return MethodMetricBindingSetRef.model_validate(
                ref("foundry.method_metric_binding_set", 6).model_dump(mode="python")
            )

    store = _BindingSetStore()
    method_registry = MethodRegistry.get_instance()
    method_registry.register(ExAnteSimulationEstimator, override=True)
    signature = method_registry.get_signature(graph_node.method_fqn)
    assert signature is not None
    changed_inputs = frozenset(
        replace(slot, unit=scenario_unit) if slot.name == "scenario" else slot
        for slot in signature.input_slots
    )
    mismatched_signature = replace(signature, input_slots=changed_inputs)
    monkeypatch.setattr(method_registry, "get_signature", lambda _fqn: mismatched_signature)
    monkeypatch.setattr(
        trinity_compiler_module,
        "load_registry_bundle",
        lambda *_args, **_kwargs: SimpleNamespace(
            metric_registry=metric_registry_ref,
            units_registry=units_registry_ref,
        ),
    )
    monkeypatch.setattr(
        trinity_compiler_module,
        "_selected_profile_ref",
        lambda _store, selected: selected,
    )

    trinity_compiler_module._compile_method_metric_binding_set(
        store,
        request=request,
        bundle=bundle,
        program_graph=program_graph,
        program_graph_ref=program_graph_ref,
        registry_bundle_ref=registry_bundle_ref,
        registry_content=registry_content,
    )

    assert store.payload is not None
    assert store.payload.bindings[0].availability == expected_availability
    if expected_availability == "unavailable":
        assert "registered_method_input_unit_set_mismatch" in store.payload.bindings[0].limitation


def test_compiler_rejects_129_metric_bindings_before_collection_traversal() -> None:
    class _NoTraversalList(list):
        def __iter__(self):
            raise AssertionError("the compiler traversed an over-limit selection")

    request = CompileRequest.model_construct(method_metric_bindings=_NoTraversalList([None] * 129))
    with pytest.raises(ValueError, match="method_metric_binding_inventory_exceeds_capture_limit"):
        trinity_compiler_module.compile_trinity(object(), request)


def test_persisted_129_binding_rows_refuse_before_model_materialization(
    tmp_path, monkeypatch
) -> None:
    store = FileSystemCAS(tmp_path)
    MethodRegistry.get_instance().register(ExAnteSimulationEstimator, override=True)
    graph_ref, _original_plan_ref, original_binding_set_ref = _make_ex_ante_graph_and_plan(store)
    original = validate_core_model_json_artifact(
        MethodMetricBindingSet,
        store,
        original_binding_set_ref,
    )
    payload = original.model_dump(mode="json")
    template = payload["bindings"][0]
    payload["bindings"] = [dict(template) for _ in range(129)]
    binding_inputs = [
        input_ref_from_artifact_ref(original.program_graph_ref, role="program_graph"),
        input_ref_from_artifact_ref(original.policy_ref, role="policy"),
        input_ref_from_artifact_ref(original.registry_bundle_ref, role="registry_bundle"),
        input_ref_from_artifact_ref(original.metric_registry_ref, role="metric_registry"),
        input_ref_from_artifact_ref(original.units_registry_ref, role="units_registry"),
    ]
    oversized_binding_ref = store.put_json(
        payload,
        PutOptions(
            kind=MethodMetricBindingSet.ARTIFACT_KIND,
            media_type=MethodMetricBindingSet.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=MethodMetricBindingSet.ARTIFACT_SCHEMA_NAME,
                version=MethodMetricBindingSet.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=binding_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    oversized_binding_set_ref = MethodMetricBindingSetRef.model_validate(
        oversized_binding_ref.model_dump(mode="python")
    )
    plan = ExecPlan(program_ref=graph_ref, order=["ex_ante_node"])
    plan_ref = _put_owned(
        store,
        plan,
        kind=ExecPlan.ARTIFACT_KIND,
        inputs=[
            input_ref_from_artifact_ref(graph_ref, role="program_graph"),
            input_ref_from_artifact_ref(
                oversized_binding_set_ref,
                role="method_metric_bindings",
            ),
        ],
    )
    typed_plan_ref = ExecPlanRef.model_validate(plan_ref.model_dump(mode="python"))

    def _materialization_must_not_run(*_args, **_kwargs):
        raise AssertionError("129 binding rows reached typed model materialization")

    monkeypatch.setattr(
        core_artifacts,
        "validate_core_model_bounded_read",
        _materialization_must_not_run,
    )
    with pytest.raises(ValueError, match="method_metric_binding_inventory_exceeds_capture_limit"):
        new_method_execution_capture(
            store,
            program_ref=graph_ref,
            exec_plan_ref=typed_plan_ref,
        )


def test_ex_ante_graph_capture_persists_actual_inputs_and_bound_output(
    tmp_path, monkeypatch
) -> None:
    store = FileSystemCAS(tmp_path)
    MethodRegistry.get_instance().register(ExAnteSimulationEstimator, override=True)
    graph_ref, plan_ref, binding_set_ref = _make_ex_ante_graph_and_plan(
        store,
        mutate_prestate=True,
    )
    baseline = np.asarray([10.0, 20.0, 40.0], dtype=np.float64)
    scenario = np.asarray([11.0, 18.0, 44.0], dtype=np.float64)
    base_state = GlobalState.empty(n_agents=len(baseline), n_firms=1)
    base_state = base_state.replace(
        agents=base_state.agents.replace(
            income=np.asarray([1.0, 2.0, 3.0], dtype=np.float64),
            reported_income=np.asarray([4.0, 5.0, 6.0], dtype=np.float64),
        )
    )
    historical_origin = GlobalState.empty(n_agents=3, n_firms=1)
    historical_origin = historical_origin.replace(
        agents=historical_origin.agents.replace(
            income=np.asarray([1.0, 2.0, 3.0], dtype=np.float64),
            reported_income=np.asarray([4.0, 5.0, 6.0], dtype=np.float64),
        )
    )
    source_state_ref = StateSnapshotRef.model_validate(
        put_state_snapshot(
            store, state=historical_origin, step=0, return_selected_profile=True
        ).model_dump(mode="python")
    )
    capture = new_method_execution_capture(
        store,
        program_ref=graph_ref,
        exec_plan_ref=plan_ref,
    )
    assert capture is not None
    assert capture.method_metric_binding_set_ref == binding_set_ref
    monkeypatch.setattr(
        "polisyos.foundry.execute._internal.graph.capture_environment",
        lambda **_kwargs: _test_environment_manifest(),
    )
    state_paths = SimpleNamespace(
        slots={
            **DEFAULT_SLOT_REGISTRY.slots,
            "baseline": SimpleNamespace(state_path="agents.income"),
            "scenario": SimpleNamespace(state_path="agents.reported_income"),
        },
    )

    class _PrestateWriter:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            return {
                "agents.income": [{"delta": baseline - np.asarray(state.agents.income)}],
                "agents.reported_income": [{"value": scenario}],
            }, key

    monkeypatch.setattr(
        graph_module,
        "create_mechanism_from_spec",
        lambda _kind, _params, **_kwargs: _PrestateWriter(),
    )

    result = execute_program_graph(
        store,
        program_ref=graph_ref,
        exec_plan_ref=plan_ref,
        base_state=base_state,
        base_ref=None,
        method_input_state_source_ref=source_state_ref,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=state_paths,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        strictness=ExecutionStrictness.RESEARCH,
        method_execution_capture=capture,
    )

    assert result.method_execution_bundle_ref is not None
    bundle = validate_core_model_json_artifact(
        MethodExecutionBundle,
        store,
        result.method_execution_bundle_ref,
    )
    assert len(bundle.occurrences) == 2
    writer_occurrence, occurrence = bundle.occurrences
    assert writer_occurrence.node_id == "prestate_writer"
    assert writer_occurrence.status == "succeeded"
    assert writer_occurrence.output_slots == []
    assert writer_occurrence.returned_slots == []
    assert writer_occurrence.returned_slot_inventory_status == "not_started"
    assert writer_occurrence.returned_slot_inventory_limit is None
    assert writer_occurrence.dispatch is None
    assert writer_occurrence.artifacts == []
    assert occurrence.node_id == "ex_ante_node"
    assert occurrence.dispatch is not None
    dispatch = occurrence.dispatch
    signature = ExAnteSimulationEstimator.signature
    method_build_digest = (
        "sha256:"
        + hashlib.sha256(inspect.getsource(ExAnteSimulationEstimator).encode("utf-8")).hexdigest()
    )
    assert occurrence.method_fqn == signature.fqn
    assert occurrence.method_version == signature.version
    assert occurrence.method_abi_digest == signature.abi_digest()
    assert occurrence.method_build_digest == method_build_digest
    assert occurrence.method_build_digest_scope == "class_source_only"
    assert dispatch.outcome == "succeeded"
    assert dispatch.requested_backend == "numpy"
    assert dispatch.selected_backend == "numpy"
    assert dispatch.actual_backend == "numpy"
    assert dispatch.backend_trace_status == "captured"
    assert tuple((item.backend, item.outcome) for item in dispatch.backend_attempts) == (
        ("numpy", "success"),
    )
    assert dispatch.backend_identity_status == "reconciled"
    assert dispatch.fallback_status == "not_fell_back"
    assert dispatch.seed_status == "reconciled"
    assert dispatch.rng_state_status == "runner_rng_state_not_retained"
    assert dispatch.graph_input_ids == ("baseline", "scenario")
    assert dispatch.signature_input_slot_ids == ("baseline", "scenario")
    assert dispatch.signature_output_slot_ids == ("result",)
    assert dispatch.signature_parameter_names == ("poverty_line",)
    assert dispatch.method_metric_input_capture_status == "captured"
    assert occurrence.dispatch.input_role_values[0].value_sha256
    assert {row.slot_id for row in occurrence.returned_slots} == {"result"}
    assert all(row.declared_slot_type == SlotType.SCALAR.name for row in occurrence.returned_slots)
    output = validate_core_model_json_artifact(
        MethodOutputPayload,
        store,
        occurrence.output_slots[0].output_ref,
    )
    assert output.slot_id == "result"
    assert output.value_path == ("mean_change",)
    assert output.value == 1.0

    input_capture_ref = occurrence.dispatch.method_metric_input_capture_ref
    assert input_capture_ref is not None
    input_capture = validate_core_model_json_artifact(
        MethodMetricInputCapturePayload,
        store,
        input_capture_ref,
    )
    assert input_capture.pre_dispatch_state_ref.kind == "foundry.state_snapshot"
    assert input_capture.pre_dispatch_state_ref != source_state_ref
    assert occurrence.dispatch.input_state_status == "captured"
    assert occurrence.dispatch.input_state_ref == input_capture.pre_dispatch_state_ref
    assert occurrence.dispatch.input_state_source_ref == source_state_ref
    assert occurrence.dispatch.input_state_relation == "current_visible_state"
    assert input_capture.prestate_identity_sha256 == occurrence.dispatch.input_state_identity_sha256
    bounded_inputs = read_state_snapshot_inputs_bounded(
        store,
        snapshot_ref=input_capture.pre_dispatch_state_ref,
        slot_ids=("baseline", "scenario"),
        max_manifest_bytes=64 * 1024,
        max_snapshot_payload_bytes=256 * 1024,
        max_state_blob_bytes=1024 * 1024,
        max_entries=8,
        max_elements=32,
    )
    assert bounded_inputs.snapshot.schema_version == "2.3"
    assert bounded_inputs.snapshot.layout == "method_input_slots"
    assert bounded_inputs.snapshot_manifest.artifact_schema.version == "2.3.0"
    assert bounded_inputs.payload_integrity_verified is True
    assert bounded_inputs.usage.payload_integrity_verified is True
    assert bounded_inputs.observed_source_bytes == bounded_inputs.usage.observed_source_bytes
    assert bounded_inputs.observed_source_bytes == sum(
        (
            bounded_inputs.observed_snapshot_manifest_bytes,
            bounded_inputs.observed_snapshot_manifest_verification_bytes,
            bounded_inputs.observed_snapshot_payload_bytes,
            bounded_inputs.observed_blob_manifest_bytes,
            bounded_inputs.observed_blob_manifest_verification_bytes,
            bounded_inputs.observed_blob_bytes,
        )
    )
    capture_manifest = store.get_manifest(input_capture_ref)
    pre_dispatch_edges = [
        edge for edge in capture_manifest.inputs if edge.role == "pre_dispatch_state"
    ]
    assert len(pre_dispatch_edges) == 1
    assert pre_dispatch_edges[0].artifact_id == input_capture.pre_dispatch_state_ref.artifact_id
    assert (
        pre_dispatch_edges[0].manifest_profile_sha256
        == input_capture.pre_dispatch_state_ref.manifest_profile_sha256
    )
    assert (
        bounded_inputs.observed_snapshot_manifest_verification_bytes
        == bounded_inputs.observed_snapshot_manifest_bytes
    )
    assert (
        bounded_inputs.observed_blob_manifest_verification_bytes
        == bounded_inputs.observed_blob_manifest_bytes
    )
    origin_edges = [
        edge
        for edge in bounded_inputs.snapshot_manifest.inputs
        if edge.role == "dispatch_origin_state"
    ]
    assert len(origin_edges) == 1
    assert origin_edges[0].artifact_id == source_state_ref.artifact_id
    assert origin_edges[0].manifest_profile_sha256 == source_state_ref.manifest_profile_sha256
    actual_arrays = dict(bounded_inputs.arrays)
    assert np.array_equal(actual_arrays["baseline"], baseline)
    assert np.array_equal(actual_arrays["scenario"], scenario)
    capture_slots = {slot.slot_id: slot for slot in input_capture.slots}
    assert set(capture_slots) == {"baseline", "scenario"}
    for slot_id, expected in (("baseline", baseline), ("scenario", scenario)):
        array = actual_arrays[slot_id]
        slot = capture_slots[slot_id]
        assert array.dtype.str == slot.dtype
        assert array.shape == slot.shape
        digest = hashlib.sha256()
        digest.update(array.dtype.str.encode("ascii"))
        digest.update(json.dumps(array.shape, separators=(",", ":")).encode("ascii"))
        digest.update(memoryview(array).cast("B"))
        assert digest.hexdigest() == slot.value_sha256
        assert np.array_equal(array, expected)
    independent = hashlib.sha256(b"policyos.method_dispatch_input_map.sha256.v1\0")
    for slot_id in ("baseline", "scenario"):
        array = actual_arrays[slot_id]
        for part in (
            slot_id.encode("utf-8"),
            array.dtype.str.encode("ascii"),
            json.dumps(array.shape, separators=(",", ":")).encode("ascii"),
        ):
            independent.update(len(part).to_bytes(8, "big"))
            independent.update(part)
        raw = memoryview(array).cast("B")
        independent.update(len(raw).to_bytes(8, "big"))
        independent.update(raw)
    assert independent.hexdigest() == input_capture.prestate_identity_sha256
    bundle_manifest = store.get_manifest(result.method_execution_bundle_ref)
    capture_edges = [
        edge
        for edge in bundle_manifest.inputs
        if edge.role == f"method_metric_input_capture:{occurrence.occurrence_id}"
    ]
    assert len(capture_edges) == 1
    assert capture_edges[0].manifest_profile_sha256 == input_capture_ref.manifest_profile_sha256

    with pytest.raises(StateSnapshotInputReadRefusal) as bounded_refusal:
        read_state_snapshot_inputs_bounded(
            store,
            snapshot_ref=input_capture.pre_dispatch_state_ref,
            slot_ids=("baseline", "scenario"),
            max_manifest_bytes=64 * 1024,
            max_snapshot_payload_bytes=256 * 1024,
            max_state_blob_bytes=1,
            max_entries=8,
            max_elements=32,
        )
    assert bounded_refusal.value.observed_source_bytes is not None
    assert bounded_refusal.value.observed_source_bytes > 0
    assert bounded_refusal.value.payload_integrity_verified is False
    assert bounded_refusal.value.usage.observed_blob_bytes == 0

    # Keep the compiler binding and all marker refs but remove the producer's
    # returned slot data. A real graph dispatch must now produce no output ref.
    from dataclasses import replace

    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

    original_dispatch = MethodDispatcher.dispatch

    def dispatch_without_slot_outputs(self, **kwargs):
        method_result = original_dispatch(self, **kwargs)
        return replace(
            method_result,
            slot_outputs={},
            artifacts={f"bounded-artifact-{index:02d}": {"ok": True} for index in range(33)},
        )

    monkeypatch.setattr(MethodDispatcher, "dispatch", dispatch_without_slot_outputs)
    stripped_capture = new_method_execution_capture(
        store,
        program_ref=graph_ref,
        exec_plan_ref=plan_ref,
    )
    assert stripped_capture is not None
    stripped = execute_program_graph(
        store,
        program_ref=graph_ref,
        exec_plan_ref=plan_ref,
        base_state=base_state,
        method_input_state_source_ref=source_state_ref,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=state_paths,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        strictness=ExecutionStrictness.RESEARCH,
        method_execution_capture=stripped_capture,
    )
    assert stripped.method_execution_bundle_ref is not None
    stripped_bundle = validate_core_model_json_artifact(
        MethodExecutionBundle, store, stripped.method_execution_bundle_ref
    )
    stripped_occurrence = next(
        item for item in stripped_bundle.occurrences if item.node_id == "ex_ante_node"
    )
    assert stripped_occurrence.output_slots[0].status == "not_emitted"
    assert stripped_occurrence.output_slots[0].output_ref is None
    assert stripped_occurrence.returned_slot_inventory_status == "captured"
    assert all(
        row.declared_slot_type == SlotType.SCALAR.name for row in stripped_occurrence.returned_slots
    )
    assert stripped_occurrence.artifact_inventory_status == "not_established"
    assert stripped_occurrence.artifact_inventory_observed_count == 33
    assert stripped_occurrence.artifact_inventory_limit == 32
    assert stripped_occurrence.artifacts == []


def test_array_and_list_capture_caps_precede_materialization_or_unbounded_walk(
    monkeypatch,
) -> None:
    oversized = np.zeros(1_000_001, dtype=np.float64)
    calls = 0

    def unexpected_device_get(_value):
        nonlocal calls
        calls += 1
        raise AssertionError("oversized input must be rejected before device transfer")

    monkeypatch.setattr(graph_module.jax, "device_get", unexpected_device_get)
    assert (
        _bounded_method_input_arrays(
            {"baseline": oversized},
            slot_ids=("baseline",),
            require_vectors=True,
        )
        is None
    )
    assert calls == 0

    nested = [list(range(128)) for _ in range(64)]
    shape, status = _runtime_slot_shape(nested)
    assert shape is None
    assert status == "not_established"


def test_snapshot_refusal_usage_uses_transferred_bytes_not_member_size(
    tmp_path, monkeypatch
) -> None:
    store = FileSystemCAS(tmp_path)
    snapshot_ref = StateSnapshotRef.model_validate(
        put_state_snapshot(
            store,
            state={
                "baseline": np.asarray([1.0, 2.0]),
                "scenario": np.asarray([2.0, 4.0]),
            },
            step=0,
            return_selected_profile=True,
        ).model_dump(mode="python")
    )
    bounded = read_state_snapshot_inputs_bounded(
        store,
        snapshot_ref=snapshot_ref,
        slot_ids=("baseline", "scenario"),
        max_manifest_bytes=64 * 1024,
        max_snapshot_payload_bytes=256 * 1024,
        max_state_blob_bytes=1024 * 1024,
        max_entries=8,
        max_elements=32,
    )
    original = store.get_raw_manifest_bytes_bounded

    def refuse_blob_manifest(ref, *, max_manifest_bytes):
        if ref.artifact_id == bounded.state_blob_ref.artifact_id:
            raise ArtifactReadBoundsError(
                member="manifest",
                observed_bytes=4096,
                max_bytes=max_manifest_bytes,
                bytes_read=0,
            )
        return original(ref, max_manifest_bytes=max_manifest_bytes)

    monkeypatch.setattr(store, "get_raw_manifest_bytes_bounded", refuse_blob_manifest)
    with pytest.raises(StateSnapshotInputReadRefusal) as precise_refusal:
        read_state_snapshot_inputs_bounded(
            store,
            snapshot_ref=snapshot_ref,
            slot_ids=("baseline", "scenario"),
            max_manifest_bytes=64 * 1024,
            max_snapshot_payload_bytes=256 * 1024,
            max_state_blob_bytes=1024 * 1024,
            max_entries=8,
            max_elements=32,
        )
    precise_usage = precise_refusal.value.usage
    assert precise_usage.observed_blob_manifest_bytes == 0
    assert precise_usage.observed_source_bytes is not None
    assert precise_usage.observed_source_bytes == sum(
        (
            precise_usage.observed_snapshot_manifest_bytes,
            precise_usage.observed_snapshot_manifest_verification_bytes,
            precise_usage.observed_snapshot_payload_bytes,
            precise_usage.observed_blob_manifest_bytes,
            precise_usage.observed_blob_manifest_verification_bytes,
            precise_usage.observed_blob_bytes,
        )
    )

    def fail_without_usage(ref, *, max_manifest_bytes):
        if ref.artifact_id == bounded.state_blob_ref.artifact_id:
            raise RuntimeError("transfer_usage_not_reported")
        return original(ref, max_manifest_bytes=max_manifest_bytes)

    monkeypatch.setattr(store, "get_raw_manifest_bytes_bounded", fail_without_usage)
    with pytest.raises(StateSnapshotInputReadRefusal) as unknown_refusal:
        read_state_snapshot_inputs_bounded(
            store,
            snapshot_ref=snapshot_ref,
            slot_ids=("baseline", "scenario"),
            max_manifest_bytes=64 * 1024,
            max_snapshot_payload_bytes=256 * 1024,
            max_state_blob_bytes=1024 * 1024,
            max_entries=8,
            max_elements=32,
        )
    assert unknown_refusal.value.usage.observed_blob_manifest_bytes is None
    assert unknown_refusal.value.observed_source_bytes is None


def test_snapshot_json_refusal_does_not_treat_declared_size_as_transfer_usage(
    tmp_path, monkeypatch
) -> None:
    store = FileSystemCAS(tmp_path)
    snapshot_ref = StateSnapshotRef.model_validate(
        put_state_snapshot(
            store,
            state={
                "baseline": np.asarray([1.0]),
                "scenario": np.asarray([2.0]),
            },
            step=0,
            return_selected_profile=True,
        ).model_dump(mode="python")
    )

    class _DeclaredSizeOnlyError(RuntimeError):
        observed_bytes = 4096

    def fail_with_declared_size(*_args, **_kwargs):
        raise _DeclaredSizeOnlyError("transfer_count_unavailable")

    monkeypatch.setattr(
        snapshots_module, "read_core_json_artifact_bounded", fail_with_declared_size
    )
    with pytest.raises(StateSnapshotInputReadRefusal) as refusal:
        read_state_snapshot_inputs_bounded(
            store,
            snapshot_ref=snapshot_ref,
            slot_ids=("baseline", "scenario"),
            max_manifest_bytes=64 * 1024,
            max_snapshot_payload_bytes=256 * 1024,
            max_state_blob_bytes=1024 * 1024,
            max_entries=8,
            max_elements=32,
        )

    assert refusal.value.usage.observed_snapshot_payload_bytes is None
    assert refusal.value.observed_source_bytes is None


def test_over_limit_plan_is_refused_before_occurrence_scan(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path)
    graph_ref, plan_ref = _make_graph_and_plan(store)
    load_model = graph_module.load_model

    class _OverLimitUniterableOrder:
        def __len__(self) -> int:
            return 129

        def __iter__(self):
            raise AssertionError("over-limit plan order must not be scanned")

    def load_plan_with_over_limit_order(store_arg, ref, model):
        loaded = load_model(store_arg, ref, model)
        if model is ExecPlan:
            object.__setattr__(loaded, "order", _OverLimitUniterableOrder())
        return loaded

    monkeypatch.setattr(graph_module, "load_model", load_plan_with_over_limit_order)
    with pytest.raises(MethodExecutionAbortError, match="occurrence_inventory_exceeds") as raised:
        execute_program_graph(
            store,
            program_ref=graph_ref,
            exec_plan_ref=plan_ref,
            base_state=GlobalState.empty(n_agents=1, n_firms=1),
            mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            strictness=ExecutionStrictness.RESEARCH,
        )

    assert raised.value.method_execution_bundle_ref is not None
    bundle = validate_core_model_json_artifact(
        MethodExecutionBundle,
        store,
        raised.value.method_execution_bundle_ref,
    )
    assert "method_execution_occurrence_inventory_exceeds_capture_limit" in bundle.limitations
    assert bundle.occurrences == []


def test_shared_capture_keeps_feedback_occurrences_and_selected_profiles(
    tmp_path, monkeypatch
) -> None:
    store = FileSystemCAS(tmp_path)
    MethodRegistry.get_instance().register(_ReturnsMetricScalar)
    graph_ref, plan_ref = _make_graph_and_plan(store)
    capture = new_method_execution_capture(
        store,
        program_ref=graph_ref,
        exec_plan_ref=plan_ref,
    )
    assert capture is not None
    monkeypatch.setattr(
        "polisyos.foundry.execute._internal.graph.capture_environment",
        lambda **_kwargs: _test_environment_manifest(),
    )

    execute_kwargs = {
        "program_ref": graph_ref,
        "exec_plan_ref": plan_ref,
        "base_state": GlobalState.empty(n_agents=1, n_firms=1),
        "mechanism_registry": DEFAULT_MECHANISM_REGISTRY,
        "slot_registry": DEFAULT_SLOT_REGISTRY,
        "merge_registry": DEFAULT_MERGE_RULE_REGISTRY,
        "strictness": ExecutionStrictness.RESEARCH,
        "method_execution_capture": capture,
        "finalize_method_execution_capture": False,
    }
    first = execute_program_graph(store, **execute_kwargs)
    second = execute_program_graph(store, **execute_kwargs)
    assert first.method_execution_bundle_ref is None
    assert second.method_execution_bundle_ref is None
    assert capture.invocation_count == 2

    finalized = execute_program_graph(
        store,
        **{
            **execute_kwargs,
            "finalize_method_execution_capture": True,
        },
    )
    assert finalized.method_execution_bundle_ref is not None
    assert finalized.method_execution_bundle_ref.manifest_profile_sha256 is not None
    bundle = validate_core_model_json_artifact(
        MethodExecutionBundle,
        store,
        finalized.method_execution_bundle_ref,
    )

    assert [row.invocation_id for row in bundle.occurrences] == [
        "graph-invocation.000001",
        "graph-invocation.000002",
        "graph-invocation.000003",
    ]
    assert all(row.status == "succeeded" for row in bundle.occurrences)
    assert all(
        row.dispatch is not None and row.dispatch.outcome == "succeeded"
        for row in bundle.occurrences
    )
    assert all(
        row.dispatch is not None
        and row.dispatch.backend_trace_status == "captured"
        and row.dispatch.backend_attempts[-1].outcome == "success"
        and row.dispatch.actual_backend == row.dispatch.selected_backend
        for row in bundle.occurrences
    )
    assert all(
        row.dispatch is not None
        and row.dispatch.input_state_status == "not_established"
        and row.dispatch.input_state_ref is None
        and row.dispatch.input_state_limitation
        for row in bundle.occurrences
    )
    assert all(row.returned_slot_inventory_status == "captured" for row in bundle.occurrences)
    output_refs = [row.output_slots[0].output_ref for row in bundle.occurrences]
    assert all(ref is not None and ref.manifest_profile_sha256 is not None for ref in output_refs)
    output_payloads = [
        validate_core_model_json_artifact(MethodOutputPayload, store, ref)
        for ref in output_refs
        if ref is not None
    ]
    assert [payload.value for payload in output_payloads] == [0.25, 0.25, 0.25]

    assert bundle.environment_manifest_ref is not None
    assert bundle.environment_manifest_ref.manifest_profile_sha256 is not None
    bundle_manifest = store.get_manifest(finalized.method_execution_bundle_ref)
    environment_edges = [
        edge for edge in bundle_manifest.inputs if edge.role == "environment_manifest"
    ]
    assert len(environment_edges) == 1
    assert (
        environment_edges[0].manifest_profile_sha256
        == bundle.environment_manifest_ref.manifest_profile_sha256
    )
    output_edges = [
        edge for edge in bundle_manifest.inputs if edge.role.startswith("method_output:")
    ]
    assert len(output_edges) == 3
