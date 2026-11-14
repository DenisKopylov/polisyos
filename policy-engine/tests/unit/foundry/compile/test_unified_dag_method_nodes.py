from __future__ import annotations

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import ProgramEdge, ProgramGraph, ProgramNode
from polisyos.foundry.compile._graph import _slot_dependency_edges, build_exec_order


def _dummy_ir_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="ir.trinity_bundle",
        media_type="application/json",
    )


def test_build_exec_order_accepts_method_nodes_in_unified_graph() -> None:
    graph = ProgramGraph(
        ir_ref=_dummy_ir_ref(),
        nodes=[
            ProgramNode(
                node_id="method.1",
                node_kind="method",
                method_fqn="causal.inference.synthetic_control@1.0.0",
                outputs=["slot.outcome"],
            ),
            ProgramNode(
                node_id="mechanism.1",
                node_kind="mechanism",
                mechanism_type="income_tax",
                inputs=["slot.outcome"],
                outputs=["slot.tax"],
            ),
        ],
        edges=[ProgramEdge(src="method.1", dst="mechanism.1", relation="depends_on")],
    )
    order = build_exec_order(graph)
    assert order.index("method.1") < order.index("mechanism.1")


def test_slot_dependency_edges_link_method_and_mechanism_nodes() -> None:
    nodes = [
        ProgramNode(
            node_id="method.1",
            node_kind="method",
            method_fqn="causal.inference.synthetic_control@1.0.0",
            outputs=["slot.x"],
        ),
        ProgramNode(
            node_id="mechanism.1",
            node_kind="mechanism",
            mechanism_type="income_tax",
            inputs=["slot.x"],
            outputs=["slot.y"],
        ),
    ]
    edges = _slot_dependency_edges(nodes)
    assert any(edge.src == "method.1" and edge.dst == "mechanism.1" for edge in edges)


def test_build_program_graph_adapts_the_selected_execution_plan_method_dag():
    from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagNode
    from polisyos.core.contracts.foundry import LoweredIRRef
    from polisyos.foundry.compile._graph import build_program_graph
    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry

    MethodRegistry.get_instance().register(ExAnteSimulationEstimator, override=True)
    signature = ExAnteSimulationEstimator.signature
    planned = MethodDagNode(
        node_id="ex_ante_node",
        method_fqn=signature.fqn,
        method_version=signature.version,
        backend=signature.execution_backend.value,
        params={"poverty_line": None},
        reads_slots=["baseline", "scenario"],
        writes_slots=["result"],
    )
    plan = ExecutionPlan(plan_id="selected-ex-ante", method_dag=[planned])
    lowered_ref = LoweredIRRef(
        artifact_id="sha256:" + "b" * 64,
        kind="foundry.lowered_ir",
        media_type="application/json",
    )

    graph, _ = build_program_graph(
        None,
        ir_ref=_dummy_ir_ref(),
        lowered_ir_ref=lowered_ref,
        mechanisms=[],
        constraint_ids=[],
        method_plan=plan,
    )

    method = next(node for node in graph.nodes if node.node_id == "ex_ante_node")
    assert method.node_kind == "method"
    assert method.method_fqn == signature.fqn
    assert method.method_version == signature.version
    assert method.method_params == {"poverty_line": None}
    assert method.inputs == ["baseline", "scenario"]
    assert method.outputs == []


def _plan_for(nodes, edges=(), *, schema_version="1.0"):
    from polisyos.core.contracts.execution_plan import ExecutionPlan

    return ExecutionPlan(
        plan_id="ad01-test-plan",
        schema_version=schema_version,
        method_dag=list(nodes),
        method_edges=list(edges),
    )


def _build_selected_plan(plan, mechanisms=(), *, store=None, lowered_ir_ref=None):
    from polisyos.core.contracts.foundry import LoweredIRRef
    from polisyos.foundry.compile._graph import build_program_graph

    return build_program_graph(
        store,
        ir_ref=_dummy_ir_ref(),
        lowered_ir_ref=lowered_ir_ref
        or LoweredIRRef(
            artifact_id="sha256:" + "b" * 64,
            kind="foundry.lowered_ir",
            media_type="application/json",
        ),
        mechanisms=list(mechanisms),
        constraint_ids=[],
        method_plan=plan,
    )[0]


def _selected_registry_store(tmp_path):
    from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.contracts.foundry import LoweredIRRef
    from polisyos.core.registry import build_default_registry_bundle

    store = FileSystemCAS(tmp_path / "cas")
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True)
    lowered_ref = store.put_json(
        {"schema_version": "1.0"},
        PutOptions(
            kind="foundry.lowered_ir",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.LoweredIR", version="1.0"),
            inputs=[
                input_ref_from_artifact_ref(registry_bundle.bundle_ref, role="registry_bundle")
            ],
        ),
        return_selected_profile=True,
    )
    return (
        store,
        registry_bundle.bundle_ref,
        LoweredIRRef.model_validate(lowered_ref.model_dump(mode="python")),
    )


def _registered_method_signature():
    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry

    registry = MethodRegistry.get_instance()
    registry.register(ExAnteSimulationEstimator, override=True)
    return ExAnteSimulationEstimator.signature


def _method_dag_node(
    signature,
    *,
    node_id,
    reads=None,
    writes=None,
    params=None,
    state_writes=None,
    input_ports=None,
    depends_on=None,
):
    from polisyos.core.contracts.execution_plan import MethodDagNode

    return MethodDagNode(
        node_id=node_id,
        method_fqn=signature.fqn,
        method_version=signature.version,
        backend=signature.execution_backend.value,
        params=params if params is not None else {"poverty_line": None},
        reads_slots=list(
            reads if reads is not None else sorted(s.name for s in signature.input_slots)
        ),
        writes_slots=list(
            writes if writes is not None else sorted(s.name for s in signature.output_slots)
        ),
        state_writes=state_writes,
        **({"input_ports": input_ports} if input_ports is not None else {}),
        depends_on=list(depends_on or []),
    )


def _register_patch_emitting_method_signature():
    from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
    from polisyos.foundry.methods.registry import MethodRegistry

    MethodRegistry.get_instance().register(PeriodFlowToStock, override=True)
    return PeriodFlowToStock.signature


def _register_consumer_signature(*, alias):
    from dataclasses import replace

    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry

    source = ExAnteSimulationEstimator.signature
    scenario = next(slot for slot in source.input_slots if slot.name == "scenario")
    input_name = "result_alias" if alias else "result"
    inputs = frozenset({replace(scenario, name="scenario"), replace(scenario, name=input_name)})
    output = next(iter(source.output_slots))
    signature = replace(
        source,
        namespace="test.ad01",
        name="consumer_alias" if alias else "consumer_result",
        input_slots=inputs,
        output_slots=frozenset({replace(output, name="consumer_out")}),
    )

    class ConsumerMethod:
        metadata = ExAnteSimulationEstimator.metadata
        pure_step = staticmethod(lambda state, params: {"consumer_out": state})

    ConsumerMethod.signature = signature
    MethodRegistry.get_instance().register(ConsumerMethod, override=True)
    return signature


def _register_two_scalar_money_input_method():
    from dataclasses import replace

    from polisyos.foundry.methods.base import SlotSpec, SlotType, Unit
    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry

    source = ExAnteSimulationEstimator.signature
    signature = replace(
        source,
        namespace="test.ad01",
        name="two_scalar_money_inputs",
        input_slots=frozenset(
            {
                SlotSpec("flow_a", SlotType.SCALAR, Unit("currency", "USD")),
                SlotSpec("flow_b", SlotType.SCALAR, Unit("currency", "USD")),
            }
        ),
    )

    class TwoScalarMoneyInputMethod:
        metadata = ExAnteSimulationEstimator.metadata
        pure_step = staticmethod(lambda state, params: {"result": 0.0})

    TwoScalarMoneyInputMethod.signature = signature
    MethodRegistry.get_instance().register(TwoScalarMoneyInputMethod, override=True)
    return signature


def _register_one_scalar_money_input_method(*, method_name, input_name):
    from dataclasses import replace

    from polisyos.foundry.methods.base import SlotSpec, SlotType, Unit
    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry

    source = ExAnteSimulationEstimator.signature
    signature = replace(
        source,
        namespace="test.ad01",
        name=method_name,
        input_slots=frozenset(
            {SlotSpec(input_name, SlotType.SCALAR, Unit("currency", "USD"))}
        ),
    )

    class OneScalarMoneyInputMethod:
        metadata = ExAnteSimulationEstimator.metadata
        pure_step = staticmethod(lambda state, params: {"result": 0.0})

    OneScalarMoneyInputMethod.signature = signature
    MethodRegistry.get_instance().register(OneScalarMoneyInputMethod, override=True)
    return signature


def test_selected_pure_method_return_is_not_a_program_state_patch() -> None:
    from polisyos.core.contracts.execution_plan import ExecutionPlan
    from polisyos.foundry.methods.base import MethodKind
    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry

    signature = ExAnteSimulationEstimator.signature
    MethodRegistry.get_instance().register(ExAnteSimulationEstimator, override=True)
    assert signature.kind is MethodKind.PURE
    plan = ExecutionPlan(
        plan_id="ad01-pure-return",
        method_dag=[_method_dag_node(signature, node_id="producer")],
    )
    graph = _build_selected_plan(plan)
    method = next(node for node in graph.nodes if node.node_id == "producer")
    assert method.outputs == []
    assert sorted(method.inputs) == ["baseline", "scenario"]


def test_selected_method_state_writes_are_separate_from_method_return_slots() -> None:
    from polisyos.core.contracts.execution_plan import ExecutionPlan

    signature = _register_patch_emitting_method_signature()
    plan = ExecutionPlan(
        plan_id="ad01-explicit-state-writes",
        schema_version="1.1",
        method_dag=[
            _method_dag_node(
                signature,
                node_id="writer",
                params={"target_slot": "government.balance"},
                state_writes=["government.balance"],
            )
        ],
    )

    graph = _build_selected_plan(plan)
    method = next(node for node in graph.nodes if node.node_id == "writer")

    assert method.inputs == ["period_flow"]
    assert method.outputs == ["government.balance"]
    assert {slot.name for slot in signature.output_slots} == {"result"}
    assert plan.method_dag[0].writes_slots == ["result"]


@pytest.mark.parametrize("state_writes", [None, [], ["government.other"]])
def test_selected_method_state_writes_match_signature_patch_targets(state_writes) -> None:
    from polisyos.core.contracts.execution_plan import ExecutionPlan

    signature = _register_patch_emitting_method_signature()
    plan = ExecutionPlan(
        plan_id="ad01-patch-target-mismatch",
        schema_version="1.1",
        method_dag=[
            _method_dag_node(
                signature,
                node_id="writer",
                params={"target_slot": "government.balance"},
                state_writes=state_writes,
            )
        ],
    )

    with pytest.raises(ValueError, match="execution_plan_method_patch_targets_mismatch"):
        _build_selected_plan(plan)


def test_selected_method_state_writes_require_patch_emission_profile() -> None:
    from polisyos.core.contracts.execution_plan import ExecutionPlan

    signature = _registered_method_signature()
    plan = ExecutionPlan(
        plan_id="ad01-undeclared-state-writes",
        schema_version="1.1",
        method_dag=[
            _method_dag_node(
                signature,
                node_id="writer",
                state_writes=["government.balance"],
            )
        ],
    )

    with pytest.raises(
        ValueError,
        match="execution_plan_method_state_writes_require_patch_emission",
    ):
        _build_selected_plan(plan)


def test_selected_method_preserves_explicit_empty_state_writes() -> None:
    from polisyos.core.contracts.execution_plan import ExecutionPlan

    signature = _registered_method_signature()
    plan = ExecutionPlan(
        plan_id="ad01-explicit-empty-state-writes",
        schema_version="1.1",
        method_dag=[_method_dag_node(signature, node_id="reader", state_writes=[])],
    )

    graph = _build_selected_plan(plan)
    method = next(node for node in graph.nodes if node.node_id == "reader")

    assert method.outputs == []
    assert plan.method_dag[0].model_dump(mode="json")["state_writes"] == []


def test_selected_method_input_ports_compile_to_global_registry_slots(tmp_path) -> None:
    from polisyos.core.contracts.execution_plan import ExecutionPlan

    signature = _register_patch_emitting_method_signature()
    store, _registry_bundle_ref, lowered_ir_ref = _selected_registry_store(tmp_path)
    plan = ExecutionPlan(
        plan_id="ad01-mapped-input-ports",
        schema_version="1.2",
        method_dag=[
            _method_dag_node(
                signature,
                node_id="writer",
                params={"target_slot": "government.balance"},
                state_writes=["government.balance"],
                input_ports={
                    "period_flow": {
                        "source_kind": "registry_slot",
                        "slot_id": "global.gdp",
                    }
                },
            )
        ],
    )

    graph = _build_selected_plan(plan, store=store, lowered_ir_ref=lowered_ir_ref)
    method = next(node for node in graph.nodes if node.node_id == "writer")

    assert graph.schema_version == "0.3"
    assert method.inputs == ["global.gdp"]
    assert method.input_ports is not None
    assert method.input_ports["period_flow"].source_kind == "registry_slot"
    assert method.input_ports["period_flow"].slot_id == "global.gdp"
    assert method.outputs == ["government.balance"]


def test_selected_method_input_aliases_and_repeated_fqn_are_node_scoped(tmp_path) -> None:
    from polisyos.core.canon import CanonSpec, to_canonical_bytes
    from polisyos.core.contracts.execution_plan import ExecutionPlan

    signature = _register_two_scalar_money_input_method()
    store, _registry_bundle_ref, lowered_ir_ref = _selected_registry_store(tmp_path)

    def _graph(*, reverse_ports):
        first_ports = [
            ("flow_a", {"source_kind": "registry_slot", "slot_id": "global.gdp"}),
            ("flow_b", {"source_kind": "registry_slot", "slot_id": "global.gdp"}),
        ]
        second_ports = [
            ("flow_a", {"source_kind": "registry_slot", "slot_id": "government.balance"}),
            ("flow_b", {"source_kind": "registry_slot", "slot_id": "global.gdp"}),
        ]
        if reverse_ports:
            first_ports.reverse()
            second_ports.reverse()
        plan = ExecutionPlan(
            plan_id="ad01-repeated-fqn-input-ports",
            schema_version="1.2",
            method_dag=[
                _method_dag_node(
                    signature,
                    node_id="reader.one",
                    input_ports=dict(first_ports),
                ),
                _method_dag_node(
                    signature,
                    node_id="reader.two",
                    input_ports=dict(second_ports),
                ),
            ],
        )
        return _build_selected_plan(plan, store=store, lowered_ir_ref=lowered_ir_ref)

    first = _graph(reverse_ports=False)
    permuted = _graph(reverse_ports=True)
    first_by_id = {node.node_id: node for node in first.nodes if node.node_kind == "method"}
    second_by_id = {node.node_id: node for node in permuted.nodes if node.node_kind == "method"}

    assert first.schema_version == permuted.schema_version == "0.3"
    assert first_by_id["reader.one"].method_fqn == first_by_id["reader.two"].method_fqn
    assert first_by_id["reader.one"].inputs == ["global.gdp"]
    assert first_by_id["reader.one"].input_ports is not None
    assert first_by_id["reader.one"].input_ports["flow_a"].slot_id == "global.gdp"
    assert first_by_id["reader.one"].input_ports["flow_b"].slot_id == "global.gdp"
    assert first_by_id["reader.two"].inputs == ["global.gdp", "government.balance"]
    assert first_by_id["reader.two"].input_ports is not None
    assert first_by_id["reader.two"].input_ports["flow_a"].slot_id == "government.balance"
    assert second_by_id["reader.one"].inputs == first_by_id["reader.one"].inputs
    assert second_by_id["reader.two"].input_ports == first_by_id["reader.two"].input_ports
    assert to_canonical_bytes(
        first.to_artifact_payload(), CanonSpec(forbid_floats=False)
    ) == to_canonical_bytes(permuted.to_artifact_payload(), CanonSpec(forbid_floats=False))


def test_program_graph_persistence_round_trips_each_payload_manifest_version(tmp_path) -> None:
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.contracts.execution_plan import ExecutionPlan
    from polisyos.core.contracts.foundry import ProgramGraph
    from polisyos.foundry.compile.trinity_compiler import _persist_program_graph

    store, _registry_bundle_ref, lowered_ir_ref = _selected_registry_store(tmp_path)
    legacy_signature = _registered_method_signature()
    legacy_graph = _build_selected_plan(
        ExecutionPlan(
            plan_id="ad01-persist-legacy-graph",
            schema_version="1.2",
            method_dag=[_method_dag_node(legacy_signature, node_id="legacy.reader")],
        )
    )
    mapped_signature = _register_patch_emitting_method_signature()
    mapped_graph = _build_selected_plan(
        ExecutionPlan(
            plan_id="ad01-persist-mapped-graph",
            schema_version="1.2",
            method_dag=[
                _method_dag_node(
                    mapped_signature,
                    node_id="mapped.writer",
                    params={"target_slot": "government.balance"},
                    state_writes=["government.balance"],
                    input_ports={
                        "period_flow": {
                            "source_kind": "registry_slot",
                            "slot_id": "global.gdp",
                        }
                    },
                )
            ],
        ),
        store=store,
        lowered_ir_ref=lowered_ir_ref,
    )

    assert legacy_graph.schema_version == "0.2"
    assert mapped_graph.schema_version == "0.3"
    for graph, expected_manifest_version in (
        (legacy_graph, "0.2.0"),
        (mapped_graph, "0.3.0"),
    ):
        graph_ref = _persist_program_graph(
            store,
            graph,
            inputs=[],
            return_selected_profile=True,
        )
        manifest = store.get_manifest(graph_ref)
        assert manifest.artifact_schema.version == expected_manifest_version
        reopened = validate_core_model_json_artifact(ProgramGraph, store, graph_ref)
        assert reopened == graph


def test_mixed_mapped_plan_normalizes_only_registry_validated_identity_inputs(tmp_path) -> None:
    from polisyos.core.contracts.execution_plan import ExecutionPlan

    signature = _register_one_scalar_money_input_method(
        method_name="selected_identity_reader",
        input_name="global.gdp",
    )
    store, _registry_bundle_ref, lowered_ir_ref = _selected_registry_store(tmp_path)
    plan = ExecutionPlan(
        plan_id="ad01-mixed-input-ports",
        schema_version="1.2",
        method_dag=[
            _method_dag_node(
                signature,
                node_id="reader.explicit",
                input_ports={
                    "global.gdp": {
                        "source_kind": "registry_slot",
                        "slot_id": "government.balance",
                    }
                },
            ),
            _method_dag_node(signature, node_id="reader.identity"),
        ],
    )

    graph = _build_selected_plan(plan, store=store, lowered_ir_ref=lowered_ir_ref)
    nodes = {node.node_id: node for node in graph.nodes if node.node_kind == "method"}

    assert graph.schema_version == "0.3"
    assert nodes["reader.explicit"].inputs == ["government.balance"]
    assert nodes["reader.identity"].inputs == ["global.gdp"]
    assert nodes["reader.identity"].input_ports is not None
    assert nodes["reader.identity"].input_ports["global.gdp"].slot_id == "global.gdp"


def test_mixed_mapped_plan_does_not_fallback_for_unregistered_identity_inputs(tmp_path) -> None:
    from polisyos.core.contracts.execution_plan import ExecutionPlan

    signature = _register_one_scalar_money_input_method(
        method_name="unregistered_identity_reader",
        input_name="not.registered",
    )
    store, _registry_bundle_ref, lowered_ir_ref = _selected_registry_store(tmp_path)
    plan = ExecutionPlan(
        plan_id="ad01-mixed-unregistered-identity",
        schema_version="1.2",
        method_dag=[
            _method_dag_node(
                signature,
                node_id="reader.explicit",
                input_ports={
                    "not.registered": {
                        "source_kind": "registry_slot",
                        "slot_id": "global.gdp",
                    }
                },
            ),
            _method_dag_node(signature, node_id="reader.identity"),
        ],
    )

    with pytest.raises(
        ValueError,
        match="execution_plan_method_input_slot_unregistered",
    ):
        _build_selected_plan(plan, store=store, lowered_ir_ref=lowered_ir_ref)


def test_mapped_plan_rejects_a_same_unit_slot_from_a_sibling_registry(tmp_path) -> None:
    from polisyos.core.contracts.execution_plan import ExecutionPlan
    from polisyos.core.registry import build_registry_bundle, load_registry_bundle_content
    from polisyos.ir.kernel import (
        DEFAULT_CONSTRAINT_REGISTRY,
        DEFAULT_MECHANISM_REGISTRY,
        DEFAULT_MERGE_RULE_REGISTRY,
        DEFAULT_SLOT_REGISTRY,
        DEFAULT_UNITS_REGISTRY,
    )
    from polisyos.ir.kernel.slots import SlotRegistry

    signature = _register_patch_emitting_method_signature()
    store, _selected_bundle_ref, lowered_ir_ref = _selected_registry_store(tmp_path)
    foreign_slots = dict(DEFAULT_SLOT_REGISTRY.slots)
    foreign_slots["foreign.same_unit_gdp"] = foreign_slots["global.gdp"].model_copy(
        update={"slot_id": "foreign.same_unit_gdp"}
    )
    foreign_bundle = build_registry_bundle(
        store,
        slot_registry=SlotRegistry(slots=foreign_slots),
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        units_registry=DEFAULT_UNITS_REGISTRY,
        return_selected_profile=True,
    )
    selected = load_registry_bundle_content(store, _selected_bundle_ref).slot_registry
    foreign = load_registry_bundle_content(store, foreign_bundle.bundle_ref).slot_registry
    assert foreign.slots["foreign.same_unit_gdp"].unit == selected.slots["global.gdp"].unit
    plan = ExecutionPlan(
        plan_id="ad01-foreign-registry-source",
        schema_version="1.2",
        method_dag=[
            _method_dag_node(
                signature,
                node_id="writer",
                params={"target_slot": "government.balance"},
                state_writes=["government.balance"],
                input_ports={
                    "period_flow": {
                        "source_kind": "registry_slot",
                        "slot_id": "foreign.same_unit_gdp",
                    }
                },
            )
        ],
    )

    with pytest.raises(
        ValueError,
        match="execution_plan_method_input_slot_unregistered",
    ):
        _build_selected_plan(plan, store=store, lowered_ir_ref=lowered_ir_ref)


def test_mapped_plan_refuses_method_output_sources_until_execution_bridge_exists(tmp_path) -> None:
    from polisyos.core.contracts.execution_plan import ExecutionPlan

    signature = _register_patch_emitting_method_signature()
    store, _registry_bundle_ref, lowered_ir_ref = _selected_registry_store(tmp_path)
    plan = ExecutionPlan(
        plan_id="ad01-method-output-source-not-yet-supported",
        schema_version="1.2",
        method_dag=[
            _method_dag_node(
                signature,
                node_id="writer",
                params={"target_slot": "government.balance"},
                state_writes=["government.balance"],
                input_ports={
                    "period_flow": {
                        "source_kind": "method_output",
                        "producer_node_id": "producer",
                        "output_slot_id": "result",
                    }
                },
            )
        ],
    )

    with pytest.raises(
        ValueError,
        match="execution_plan_method_output_input_not_supported",
    ):
        _build_selected_plan(plan, store=store, lowered_ir_ref=lowered_ir_ref)


def test_plan_v12_without_input_maps_keeps_legacy_graph_v02() -> None:
    from polisyos.core.contracts.execution_plan import ExecutionPlan

    signature = _registered_method_signature()
    plan = ExecutionPlan(
        plan_id="ad01-v12-without-input-maps",
        schema_version="1.2",
        method_dag=[_method_dag_node(signature, node_id="reader")],
    )

    graph = _build_selected_plan(plan)
    method = next(node for node in graph.nodes if node.node_id == "reader")

    assert graph.schema_version == "0.2"
    assert method.inputs == sorted(slot.name for slot in signature.input_slots)
    assert "input_ports" not in method.model_dump(mode="json")


def test_selected_method_plan_rejects_registered_return_slot_mismatch() -> None:
    signature = _registered_method_signature()
    plan = _plan_for(
        [
            _method_dag_node(signature, node_id="producer", writes=["not_the_registered_result"]),
        ]
    )
    with pytest.raises(ValueError, match="execution_plan_method_slots_mismatch"):
        _build_selected_plan(plan)


def test_selected_method_plan_rejects_return_slot_consumer_even_with_wrong_dependency() -> None:
    from polisyos.core.contracts.execution_plan import MethodDagEdge

    producer_sig = _registered_method_signature()
    consumer_sig = _register_consumer_signature(alias=False)
    producer = _method_dag_node(producer_sig, node_id="producer")
    consumer = _method_dag_node(consumer_sig, node_id="consumer", reads=["result", "scenario"])
    plan = _plan_for([producer, consumer], [MethodDagEdge(src="consumer", dst="producer")])
    with pytest.raises(ValueError, match="execution_plan_method_return_slot_consumer_unsupported"):
        _build_selected_plan(plan)


def test_selected_method_plan_rejects_return_slot_alias_through_declared_dependency() -> None:
    from polisyos.core.contracts.execution_plan import MethodDagEdge

    producer_sig = _registered_method_signature()
    consumer_sig = _register_consumer_signature(alias=True)
    producer = _method_dag_node(producer_sig, node_id="producer")
    consumer = _method_dag_node(
        consumer_sig,
        node_id="consumer",
        reads=["result_alias", "scenario"],
        depends_on=["producer"],
    )
    plan = _plan_for([producer, consumer], [MethodDagEdge(src="producer", dst="consumer")])
    with pytest.raises(ValueError, match="execution_plan_method_return_slot_consumer_unsupported"):
        _build_selected_plan(plan)


def test_selected_method_plan_rejects_non_pure_method_before_graph_creation() -> None:
    from dataclasses import replace

    from polisyos.core.contracts.execution_plan import ExecutionPlan
    from polisyos.foundry.methods.base import MethodKind
    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry

    source = ExAnteSimulationEstimator.signature
    signature = replace(
        source, namespace="test.ad01", name="non_pure_method", kind=MethodKind.MECHANISM
    )

    class NonPureMethod:
        metadata = ExAnteSimulationEstimator.metadata
        pure_step = staticmethod(lambda state, params: {"result": state})

    NonPureMethod.signature = signature
    MethodRegistry.get_instance().register(NonPureMethod, override=True)
    plan = ExecutionPlan(
        plan_id="ad01-non-pure",
        method_dag=[_method_dag_node(signature, node_id="mechanism")],
    )
    with pytest.raises(ValueError, match="execution_plan_method_kind_unsupported"):
        _build_selected_plan(plan)


def test_selected_method_plan_refuses_lowered_mechanism_consuming_return_slot() -> None:
    from polisyos.core.contracts.execution_plan import ExecutionPlan
    from polisyos.core.contracts.foundry import LoweredMechanism

    signature = _registered_method_signature()
    plan = ExecutionPlan(
        plan_id="ad01-cross-plane-consumer",
        method_dag=[_method_dag_node(signature, node_id="producer")],
    )
    mechanism = LoweredMechanism(
        binding_id="consume-result",
        mechanism_id="test_mechanism",
        inputs=["result"],
        outputs=["tax"],
    )
    with pytest.raises(ValueError, match="execution_plan_method_return_slot_consumer_unsupported"):
        _build_selected_plan(plan, mechanisms=[mechanism])


def test_slot_dependency_edges_reconcile_registered_state_path_aliases() -> None:
    from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY
    from polisyos.ir.kernel.slots import SlotRegistry

    slots = dict(DEFAULT_SLOT_REGISTRY.slots)
    slots["baseline"] = slots["agents.reported_income"].model_copy(
        update={"slot_id": "baseline", "state_path": "agents.reported_income"}
    )
    slots["scenario"] = slots["agents.income"].model_copy(
        update={"slot_id": "scenario", "state_path": "agents.income"}
    )
    registry = SlotRegistry(slots=slots)
    nodes = [
        ProgramNode(
            node_id="tax",
            node_kind="mechanism",
            mechanism_type="income_tax",
            outputs=["agents.income"],
        ),
        ProgramNode(
            node_id="ex_ante",
            node_kind="method",
            method_fqn="policy.evaluation.ex_ante_simulation@1.0.0",
            inputs=["baseline", "scenario"],
        ),
    ]

    edges = _slot_dependency_edges(nodes, slot_registry=registry)

    assert [(edge.src, edge.dst) for edge in edges] == [("tax", "ex_ante")]

    slots["scenario"] = slots["scenario"].model_copy(update={"state_path": "agents.savings"})
    wrong_registry = SlotRegistry(slots=slots)
    assert _slot_dependency_edges(nodes, slot_registry=wrong_registry) == []


@pytest.mark.parametrize(
    "producer_slot",
    ["scenario", "writer.slot"],
    ids=["exact-slot-id", "state-path-alias"],
)
def test_profileless_lowered_ir_refuses_intervention_method_transfer(producer_slot) -> None:
    from polisyos.core.contracts.foundry import LoweredIRRef, LoweredMechanism
    from polisyos.foundry.compile._graph import build_program_graph

    signature = _registered_method_signature()
    method_plan = _plan_for([_method_dag_node(signature, node_id="ex_ante")])

    class _DefaultManifestStore:
        def get_manifest(self, ref):
            pytest.fail(
                "profileless transfer must refuse before resolving the default LoweredIR view"
            )

    with pytest.raises(
        ValueError,
        match="execution_plan_method_lowered_ir_selected_profile_required_for_intervention_method_transfer",
    ):
        build_program_graph(
            _DefaultManifestStore(),
            ir_ref=_dummy_ir_ref(),
            lowered_ir_ref=LoweredIRRef(
                artifact_id="sha256:" + "b" * 64,
                kind="foundry.lowered_ir",
                media_type="application/json",
            ),
            mechanisms=[
                LoweredMechanism(
                    binding_id="tax-binding",
                    mechanism_id="income_tax",
                    intervention_ids=["tax"],
                    outputs=[producer_slot],
                )
            ],
            constraint_ids=[],
            method_plan=method_plan,
        )


def test_method_transfer_refuses_registry_lineage_without_selected_profile(monkeypatch) -> None:
    from types import SimpleNamespace

    from polisyos.core.artifacts.manifest import InputRef
    from polisyos.core.contracts.foundry import LoweredIRRef, LoweredMechanism
    from polisyos.foundry.compile import _graph as graph_module
    from polisyos.foundry.compile._graph import build_program_graph

    lowered_profile = "sha256:" + "b" * 64

    class _UnprofiledRegistryLineageStore:
        def get_manifest(self, ref):
            assert ref.manifest_profile_sha256 == lowered_profile
            return SimpleNamespace(
                kind="foundry.lowered_ir",
                inputs=[
                    InputRef(
                        artifact_id="sha256:" + "d" * 64,
                        role="registry_bundle",
                    )
                ],
            )

    def _must_not_load_registry(store, ref):
        pytest.fail("registry loader must not receive an unselected registry-bundle edge")

    monkeypatch.setattr(graph_module, "load_registry_bundle_content", _must_not_load_registry)
    signature = _registered_method_signature()
    with pytest.raises(
        ValueError,
        match="execution_plan_method_registry_bundle_selected_profile_required_for_intervention_method_transfer",
    ):
        build_program_graph(
            _UnprofiledRegistryLineageStore(),
            ir_ref=_dummy_ir_ref(),
            lowered_ir_ref=LoweredIRRef(
                artifact_id="sha256:" + "b" * 64,
                kind="foundry.lowered_ir",
                media_type="application/json",
                manifest_profile_sha256=lowered_profile,
            ),
            mechanisms=[
                LoweredMechanism(
                    binding_id="tax-binding",
                    mechanism_id="income_tax",
                    intervention_ids=["tax"],
                    outputs=["writer.slot"],
                )
            ],
            constraint_ids=[],
            method_plan=_plan_for([_method_dag_node(signature, node_id="ex_ante")]),
        )


def test_program_graph_uses_exact_registry_profiles_for_method_transfer(monkeypatch) -> None:
    from types import SimpleNamespace

    from polisyos.core.artifacts.manifest import InputRef
    from polisyos.core.contracts.foundry import LoweredIRRef, LoweredMechanism
    from polisyos.foundry.compile import _graph as graph_module
    from polisyos.foundry.compile._graph import build_program_graph
    from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY
    from polisyos.ir.kernel.slots import SlotRegistry

    lower_profile = "sha256:" + "b" * 64
    sibling_lower_profile = "sha256:" + "f" * 64
    registry_profile = "sha256:" + "c" * 64
    sibling_registry_profile = "sha256:" + "e" * 64
    lower_profiles = {
        lower_profile: registry_profile,
        sibling_lower_profile: sibling_registry_profile,
    }
    registry_artifact_id = "sha256:" + "d" * 64

    class _SelectedLoweredManifestStore:
        def get_manifest(self, ref):
            selected_registry_profile = lower_profiles.get(ref.manifest_profile_sha256)
            assert selected_registry_profile is not None
            return SimpleNamespace(
                kind="foundry.lowered_ir",
                inputs=[
                    InputRef(
                        artifact_id=registry_artifact_id,
                        role="registry_bundle",
                        manifest_profile_sha256=selected_registry_profile,
                    )
                ],
            )

    slots = dict(DEFAULT_SLOT_REGISTRY.slots)
    slots["writer.slot"] = slots["agents.income"].model_copy(
        update={"slot_id": "writer.slot", "state_path": "agents.income"}
    )
    slots["scenario"] = slots["agents.income"].model_copy(
        update={"slot_id": "scenario", "state_path": "agents.income"}
    )
    slots["baseline"] = slots["agents.reported_income"].model_copy(
        update={"slot_id": "baseline", "state_path": "agents.reported_income"}
    )
    same_registry_payload = SlotRegistry(slots=slots)
    seen_refs = []

    def _load_selected_bundle(store, ref):
        assert isinstance(store, _SelectedLoweredManifestStore)
        seen_refs.append(ref)
        return SimpleNamespace(slot_registry=same_registry_payload)

    monkeypatch.setattr(graph_module, "load_registry_bundle_content", _load_selected_bundle)
    signature = _registered_method_signature()
    method_plan = _plan_for([_method_dag_node(signature, node_id="ex_ante")])
    mechanisms = [
        LoweredMechanism(
            binding_id="tax-alias-binding",
            mechanism_id="income_tax",
            intervention_ids=["tax_alias"],
            outputs=["writer.slot"],
        ),
        LoweredMechanism(
            binding_id="tax-exact-binding",
            mechanism_id="income_tax",
            intervention_ids=["tax_exact"],
            outputs=["scenario"],
        ),
    ]

    def _build_graph(profile):
        return build_program_graph(
            _SelectedLoweredManifestStore(),
            ir_ref=_dummy_ir_ref(),
            lowered_ir_ref=LoweredIRRef(
                artifact_id="sha256:" + "b" * 64,
                kind="foundry.lowered_ir",
                media_type="application/json",
                manifest_profile_sha256=profile,
            ),
            mechanisms=mechanisms,
            constraint_ids=[],
            method_plan=method_plan,
        )[0]

    selected_graph = _build_graph(lower_profile)
    sibling_graph = _build_graph(sibling_lower_profile)

    assert [str(ref.artifact_id) for ref in seen_refs] == [
        registry_artifact_id,
        registry_artifact_id,
    ]
    assert [ref.manifest_profile_sha256 for ref in seen_refs] == [
        registry_profile,
        sibling_registry_profile,
    ]
    for graph in (selected_graph, sibling_graph):
        assert any(
            edge.src == "tax_alias" and edge.dst == "ex_ante" and edge.relation == "depends_on"
            for edge in graph.edges
        )
        assert any(
            edge.src == "tax_exact" and edge.dst == "ex_ante" and edge.relation == "depends_on"
            for edge in graph.edges
        )
