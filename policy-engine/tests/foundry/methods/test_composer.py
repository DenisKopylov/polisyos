"""
Tests for MethodComposer and CompositionDAG.
"""

from __future__ import annotations

from typing import Any, ClassVar
from uuid import uuid4

import pytest

from polisyos.foundry.methods.base import (
    ComplexityClass,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.composer import (
    CompositionDAG,
    MethodComposer,
    MethodNode,
)
from polisyos.foundry.methods.exceptions import CyclicDependencyError, MethodNotFoundError
from polisyos.foundry.methods.linker import LinkResult
from polisyos.foundry.methods.registry import MethodRegistry

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


@pytest.fixture
def currency_unit() -> Unit:
    return Unit(dimension="currency", symbol="USD")


@pytest.fixture
def income_slot(currency_unit: Unit) -> SlotSpec:
    return SlotSpec(
        name="income",
        slot_type=SlotType.VECTOR,
        unit=currency_unit,
        shape=("n_agents",),
    )


@pytest.fixture
def tax_slot(currency_unit: Unit) -> SlotSpec:
    return SlotSpec(
        name="tax_due",
        slot_type=SlotType.VECTOR,
        unit=currency_unit,
        shape=("n_agents",),
    )


@pytest.fixture
def revenue_slot(currency_unit: Unit) -> SlotSpec:
    return SlotSpec(
        name="revenue",
        slot_type=SlotType.SCALAR,
        unit=currency_unit,
        shape=(),
    )


def make_method_class(
    name: str,
    namespace: str,
    version: str,
    input_slots: frozenset[SlotSpec],
    output_slots: frozenset[SlotSpec],
    parameters: tuple[ParameterSpec, ...] = (),
    requires: frozenset[str] = frozenset(),
    conflicts_with: frozenset[str] = frozenset(),
    commutes_with: frozenset[str] = frozenset(),
) -> type:
    sig = MethodSignature(
        name=name,
        namespace=namespace,
        version=version,
        input_slots=input_slots,
        output_slots=output_slots,
        parameters=parameters,
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        requires=requires,
        conflicts_with=conflicts_with,
        commutes_with=commutes_with,
    )

    class TestMethod:
        signature: ClassVar[MethodSignature] = sig
        metadata: ClassVar[MethodMetadata] = MethodMetadata(
            description=f"Test method: {name}",
            tags=frozenset({"test"}),
        )

        @staticmethod
        def pure_step(state: Any, params: dict[str, Any]) -> Any:
            return state

    TestMethod.__name__ = name.replace("_", " ").title().replace(" ", "")
    return TestMethod


@pytest.fixture
def tax_method(income_slot: SlotSpec, tax_slot: SlotSpec) -> type:
    return make_method_class(
        name="flat_tax",
        namespace="fiscal.taxation",
        version="1.0.0",
        input_slots=frozenset({income_slot}),
        output_slots=frozenset({tax_slot}),
        parameters=(ParameterSpec(name="rate", default=0.15, is_static=False),),
    )


@pytest.fixture
def tax_method_with_static(income_slot: SlotSpec, tax_slot: SlotSpec) -> type:
    return make_method_class(
        name="progressive_tax",
        namespace="fiscal.taxation",
        version="1.0.0",
        input_slots=frozenset({income_slot}),
        output_slots=frozenset({tax_slot}),
        parameters=(
            ParameterSpec(name="rate", default=0.15, is_static=False),
            ParameterSpec(name="threshold", default=10000.0, is_static=True),
        ),
    )


@pytest.fixture
def revenue_method(tax_slot: SlotSpec, revenue_slot: SlotSpec) -> type:
    return make_method_class(
        name="revenue_calc",
        namespace="fiscal.budget",
        version="1.0.0",
        input_slots=frozenset({tax_slot}),
        output_slots=frozenset({revenue_slot}),
    )


@pytest.fixture
def conflicting_tax(income_slot: SlotSpec, tax_slot: SlotSpec) -> type:
    return make_method_class(
        name="alt_tax",
        namespace="fiscal.taxation",
        version="1.0.0",
        input_slots=frozenset({income_slot}),
        output_slots=frozenset({tax_slot}),
        conflicts_with=frozenset({"fiscal.taxation.flat_tax@1.0.0"}),
    )


@pytest.fixture
def requiring_method(income_slot: SlotSpec, tax_slot: SlotSpec) -> type:
    return make_method_class(
        name="dependent_tax",
        namespace="fiscal.taxation",
        version="1.0.0",
        input_slots=frozenset({income_slot}),
        output_slots=frozenset({tax_slot}),
        requires=frozenset({"fiscal.core.validator@1.0.0"}),
    )


@pytest.fixture
def registry_with_methods(
    tax_method: type,
    tax_method_with_static: type,
    revenue_method: type,
    conflicting_tax: type,
    requiring_method: type,
) -> MethodRegistry:
    registry = MethodRegistry.get_instance()
    registry.register(tax_method)
    registry.register(tax_method_with_static)
    registry.register(revenue_method)
    registry.register(conflicting_tax)
    registry.register(requiring_method)
    return registry


# =============================================================================
# CompositionDAG Tests
# =============================================================================


class TestCompositionDAG:
    def test_add_node(self):
        dag = CompositionDAG()
        node = MethodNode(
            id=uuid4(),
            method_fqn="test.method@1.0.0",
            params={"x": 1.0},
            static_params={},
        )

        dag.add_node(node)
        assert node.id in dag.nodes
        assert len(dag) == 1

    def test_add_duplicate_node_raises(self):
        dag = CompositionDAG()
        node_id = uuid4()
        node1 = MethodNode(id=node_id, method_fqn="a@1.0.0", params={}, static_params={})
        node2 = MethodNode(id=node_id, method_fqn="b@1.0.0", params={}, static_params={})

        dag.add_node(node1)
        with pytest.raises(ValueError, match="already exists"):
            dag.add_node(node2)

    def test_add_edge(self):
        dag = CompositionDAG()
        node_a = MethodNode(id=uuid4(), method_fqn="a@1.0.0", params={}, static_params={})
        node_b = MethodNode(id=uuid4(), method_fqn="b@1.0.0", params={}, static_params={})

        dag.add_node(node_a)
        dag.add_node(node_b)

        link = LinkResult(
            source_fqn="a@1.0.0",
            target_fqn="b@1.0.0",
            bindings=(),
        )

        dag.add_edge(node_a.id, node_b.id, link)

        assert node_b.id in dag.successors[node_a.id]
        assert node_a.id in dag.predecessors[node_b.id]

    def test_cycle_detection(self):
        dag = CompositionDAG()

        node_a = MethodNode(id=uuid4(), method_fqn="A@1.0.0", params={}, static_params={})
        node_b = MethodNode(id=uuid4(), method_fqn="B@1.0.0", params={}, static_params={})

        dag.add_node(node_a)
        dag.add_node(node_b)

        dag.add_edge(node_a.id, node_b.id, LinkResult("A@1.0.0", "B@1.0.0", ()))
        dag.add_edge(node_b.id, node_a.id, LinkResult("B@1.0.0", "A@1.0.0", ()))

        with pytest.raises(CyclicDependencyError):
            dag.topological_order()


# =============================================================================
# MethodComposer Tests
# =============================================================================


class TestMethodComposerBasic:
    def test_add_method(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        node = composer.add("fiscal.taxation.flat_tax@1.0.0")
        assert node.method_fqn == "fiscal.taxation.flat_tax@1.0.0"
        assert len(composer) == 1

    def test_add_method_with_params(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        node = composer.add("fiscal.taxation.flat_tax@1.0.0", rate=0.25)
        assert node.params["rate"] == 0.25

    def test_add_unknown_method_raises(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        with pytest.raises(MethodNotFoundError):
            composer.add("nonexistent.method@1.0.0")

    def test_add_unknown_param_raises(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        with pytest.raises(ValueError, match="Unknown parameters"):
            composer.add("fiscal.taxation.flat_tax@1.0.0", unknown_param=42)


class TestParameterSplitting:
    def test_static_params_separated(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        node = composer.add(
            "fiscal.taxation.progressive_tax@1.0.0",
            rate=0.18,
            threshold=25000.0,
        )

        assert node.params["rate"] == 0.18
        assert node.static_params["threshold"] == 25000.0

    def test_default_static_params(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        node = composer.add("fiscal.taxation.progressive_tax@1.0.0")
        assert node.static_params["threshold"] == 10000.0


class TestMethodConnection:
    def test_connect_compatible_methods(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        tax = composer.add("fiscal.taxation.flat_tax@1.0.0")
        revenue = composer.add("fiscal.budget.revenue_calc@1.0.0")

        link = composer.connect(tax, revenue)

        assert link.source_id == tax.id
        assert link.target_id == revenue.id

    def test_connect_establishes_order(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)

        revenue = composer.add("fiscal.budget.revenue_calc@1.0.0")
        tax = composer.add("fiscal.taxation.flat_tax@1.0.0")

        composer.connect(tax, revenue)
        chain = composer.build()

        assert chain.execution_order.index(tax.id) < chain.execution_order.index(revenue.id)


class TestMultiInstanceBindings:
    def test_bindings_use_node_ids(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        tax1 = composer.add("fiscal.taxation.flat_tax@1.0.0", rate=0.1)
        tax2 = composer.add("fiscal.taxation.flat_tax@1.0.0", rate=0.2)
        rev1 = composer.add("fiscal.budget.revenue_calc@1.0.0")
        rev2 = composer.add("fiscal.budget.revenue_calc@1.0.0")

        composer.connect(tax1, rev1)
        composer.connect(tax2, rev2)

        chain = composer.build()

        bindings_rev1 = chain.get_bindings_for_target(rev1.id)
        bindings_rev2 = chain.get_bindings_for_target(rev2.id)

        assert bindings_rev1 and bindings_rev2
        assert all(b.target_node_id == rev1.id for b in bindings_rev1)
        assert all(b.target_node_id == rev2.id for b in bindings_rev2)
        assert {b.source_node_id for b in bindings_rev1} != {
            b.source_node_id for b in bindings_rev2
        }


class TestRequirementValidation:
    def test_missing_requirement_detected(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        composer.add("fiscal.taxation.dependent_tax@1.0.0")

        warnings = composer.validate()
        assert any("MISSING REQUIREMENT" in w for w in warnings)

    def test_requires_enforces_order(
        self, registry_with_methods: MethodRegistry, income_slot: SlotSpec, tax_slot: SlotSpec
    ):
        registry = MethodRegistry.get_instance()
        required = make_method_class(
            name="validator",
            namespace="fiscal.core",
            version="1.0.0",
            input_slots=frozenset({income_slot}),
            output_slots=frozenset({tax_slot}),
        )
        dependent = make_method_class(
            name="dependent",
            namespace="fiscal.core",
            version="1.0.0",
            input_slots=frozenset({income_slot}),
            output_slots=frozenset({tax_slot}),
            requires=frozenset({"fiscal.core.validator@1.0.0"}),
        )
        registry.register(required)
        registry.register(dependent)

        composer = MethodComposer(registry=registry)
        dependent_node = composer.add("fiscal.core.dependent@1.0.0")
        required_node = composer.add("fiscal.core.validator@1.0.0")

        chain = composer.build()

        assert chain.execution_order.index(required_node.id) < chain.execution_order.index(
            dependent_node.id
        )


class TestConflictDetection:
    def test_conflict_detected_in_validation(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        composer.add("fiscal.taxation.flat_tax@1.0.0")
        composer.add("fiscal.taxation.alt_tax@1.0.0")

        warnings = composer.validate()
        assert any("CONFLICT" in w for w in warnings)


class TestDeterministicOrdering:
    def test_commuting_nodes_canonical_order(self, income_slot: SlotSpec, tax_slot: SlotSpec):
        registry = MethodRegistry.get_instance()

        method_a = make_method_class(
            name="aaa",
            namespace="test",
            version="1.0.0",
            input_slots=frozenset({income_slot}),
            output_slots=frozenset({tax_slot}),
            commutes_with=frozenset({"test.bbb@1.0.0"}),
        )
        method_b = make_method_class(
            name="bbb",
            namespace="test",
            version="1.0.0",
            input_slots=frozenset({income_slot}),
            output_slots=frozenset({tax_slot}),
            commutes_with=frozenset({"test.aaa@1.0.0"}),
        )
        registry.register(method_a)
        registry.register(method_b)

        composer = MethodComposer(registry=registry)
        node_b = composer.add("test.bbb@1.0.0")
        node_a = composer.add("test.aaa@1.0.0")

        chain = composer.build()
        assert chain.execution_order.index(node_a.id) < chain.execution_order.index(node_b.id)

    def test_non_commuting_respects_insertion(self, income_slot: SlotSpec, tax_slot: SlotSpec):
        registry = MethodRegistry.get_instance()

        method_a = make_method_class(
            name="aaa",
            namespace="test",
            version="1.0.1",
            input_slots=frozenset({income_slot}),
            output_slots=frozenset({tax_slot}),
        )
        method_b = make_method_class(
            name="bbb",
            namespace="test",
            version="1.0.1",
            input_slots=frozenset({income_slot}),
            output_slots=frozenset({tax_slot}),
        )
        registry.register(method_a)
        registry.register(method_b)

        composer = MethodComposer(registry=registry)
        node_b = composer.add("test.bbb@1.0.1")
        node_a = composer.add("test.aaa@1.0.1")

        chain = composer.build()
        assert chain.execution_order.index(node_b.id) < chain.execution_order.index(node_a.id)


class TestImmutability:
    def test_node_params_are_frozen(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        node = composer.add("fiscal.taxation.flat_tax@1.0.0")

        with pytest.raises(TypeError):
            node.params["rate"] = 0.5  # type: ignore[index]

    def test_chain_dag_is_frozen(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        composer.add("fiscal.taxation.flat_tax@1.0.0")

        chain = composer.build()

        with pytest.raises(TypeError):
            chain.dag.nodes[uuid4()] = MethodNode(
                id=uuid4(),
                method_fqn="x@1.0.0",
                params={},
                static_params={},
            )

    def test_execution_order_is_tuple(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        composer.add("fiscal.taxation.flat_tax@1.0.0")

        chain = composer.build()

        assert isinstance(chain.execution_order, tuple)


class TestEdgeCases:
    def test_empty_composition(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)

        chain = composer.build()

        assert len(chain) == 0
        assert list(chain.methods_in_order()) == []

    def test_single_node_composition(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        tax = composer.add("fiscal.taxation.flat_tax@1.0.0")

        chain = composer.build()

        assert len(chain) == 1
        assert chain.execution_order[0] == tax.id

    def test_disconnected_components(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        tax1 = composer.add("fiscal.taxation.flat_tax@1.0.0")
        tax2 = composer.add("fiscal.taxation.progressive_tax@1.0.0")

        chain = composer.build()

        assert len(chain) == 2
        assert tax1.id in chain.execution_order
        assert tax2.id in chain.execution_order

    def test_multiple_instances_same_method(self, registry_with_methods: MethodRegistry):
        composer = MethodComposer(registry=registry_with_methods)
        tax1 = composer.add("fiscal.taxation.flat_tax@1.0.0", rate=0.1)
        tax2 = composer.add("fiscal.taxation.flat_tax@1.0.0", rate=0.2)

        assert tax1.id != tax2.id
        assert tax1.params["rate"] == 0.1
        assert tax2.params["rate"] == 0.2
