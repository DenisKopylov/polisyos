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


def _plan_for(nodes, edges=()):
    from polisyos.core.contracts.execution_plan import ExecutionPlan

    return ExecutionPlan(plan_id="ad01-test-plan", method_dag=list(nodes), method_edges=list(edges))


def _build_selected_plan(plan, mechanisms=()):
    from polisyos.core.contracts.foundry import LoweredIRRef
    from polisyos.foundry.compile._graph import build_program_graph

    return build_program_graph(
        None,
        ir_ref=_dummy_ir_ref(),
        lowered_ir_ref=LoweredIRRef(
            artifact_id="sha256:" + "b" * 64,
            kind="foundry.lowered_ir",
            media_type="application/json",
        ),
        mechanisms=list(mechanisms),
        constraint_ids=[],
        method_plan=plan,
    )[0]


def _registered_method_signature():
    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry

    registry = MethodRegistry.get_instance()
    registry.register(ExAnteSimulationEstimator, override=True)
    return ExAnteSimulationEstimator.signature


def _method_dag_node(signature, *, node_id, reads=None, writes=None, depends_on=None):
    from polisyos.core.contracts.execution_plan import MethodDagNode

    return MethodDagNode(
        node_id=node_id,
        method_fqn=signature.fqn,
        method_version=signature.version,
        backend=signature.execution_backend.value,
        params={"poverty_line": None},
        reads_slots=list(
            reads if reads is not None else sorted(s.name for s in signature.input_slots)
        ),
        writes_slots=list(
            writes if writes is not None else sorted(s.name for s in signature.output_slots)
        ),
        depends_on=list(depends_on or []),
    )


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
