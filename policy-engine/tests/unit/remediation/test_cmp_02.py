"""Test-first regression witnesses for CMP-02 (B45/B46).

These tests pin two composition invariants before the production repair:

* a concrete target input has one producer unless an explicit merge node owns
  the combination; and
* ordering prerequisites are evaluated per node occurrence, not by the last
  occurrence of a method FQN.

The synthetic methods are real registry entries for the B45 composition
cases.  The B46 tests use the validator's small compiled-chain protocol so
that repeated FQNs can be represented without coupling the witness to an
executor or backend.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar
from uuid import UUID, uuid4

import pytest

from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.components.composer import (
    MethodComposer,
    SemanticValidationLevel,
)
from polisyos.foundry.methods.components.semantic_validator import CrossMethodValidator
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def reset_registry() -> None:
    """Keep synthetic CMP-02 registry methods isolated between tests."""
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def _slot(name: str) -> SlotSpec:
    """Build a scalar slot with a neutral, matching contract for composition."""
    return SlotSpec(
        name=name,
        slot_type=SlotType.SCALAR,
        unit=Unit(dimension="cmp02", symbol="unit"),
    )


def _method_class(
    name: str,
    *,
    input_slots: frozenset[SlotSpec] = frozenset(),
    output_slots: frozenset[SlotSpec] = frozenset(),
) -> type:
    """Create a minimal concrete method class for the composer witness."""
    method_signature = MethodSignature(
        name=name,
        namespace="tests.cmp02",
        version="1.0.0",
        input_slots=input_slots,
        output_slots=output_slots,
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    class TestMethod:
        signature: ClassVar[MethodSignature] = method_signature
        metadata: ClassVar[MethodMetadata] = MethodMetadata(
            description=f"CMP-02 test method: {name}",
            tags=frozenset({"cmp02", "test"}),
        )

        @staticmethod
        def pure_step(state: Any, params: dict[str, Any]) -> Any:
            return state

    TestMethod.__name__ = name.replace("_", " ").title().replace(" ", "")
    return TestMethod


def _register(*method_classes: type) -> MethodRegistry:
    """Register synthetic methods in the isolated method registry."""
    registry = MethodRegistry.get_instance()
    for method_class in method_classes:
        registry.register(method_class, override=True)
    return registry


def test_duplicate_producers_are_visible_in_warn_mode() -> None:
    """B45: WARN mode must expose duplicate producers instead of last-wins."""
    value = _slot("value")
    producer_one = _method_class("producer_one", output_slots=frozenset({value}))
    producer_two = _method_class("producer_two", output_slots=frozenset({value}))
    consumer = _method_class("consumer", input_slots=frozenset({value}))
    registry = _register(producer_one, producer_two, consumer)

    composer = MethodComposer(registry=registry)
    first = composer.add("tests.cmp02.producer_one@1.0.0")
    second = composer.add("tests.cmp02.producer_two@1.0.0")
    target = composer.add("tests.cmp02.consumer@1.0.0")
    composer.connect(first, target, {"value": "value"})
    composer.connect(second, target, {"value": "value"})

    chain = composer.build(validate_semantics=SemanticValidationLevel.WARN)

    assert any("connected multiple times" in warning for warning in chain.warnings)


def test_duplicate_producers_fail_closed_in_strict_mode() -> None:
    """B45: STRICT mode must reject two producers for one concrete target slot."""
    value = _slot("value")
    producer_one = _method_class("producer_one", output_slots=frozenset({value}))
    producer_two = _method_class("producer_two", output_slots=frozenset({value}))
    consumer = _method_class("consumer", input_slots=frozenset({value}))
    registry = _register(producer_one, producer_two, consumer)

    composer = MethodComposer(registry=registry)
    first = composer.add("tests.cmp02.producer_one@1.0.0")
    second = composer.add("tests.cmp02.producer_two@1.0.0")
    target = composer.add("tests.cmp02.consumer@1.0.0")
    composer.connect(first, target, {"value": "value"})
    composer.connect(second, target, {"value": "value"})

    with pytest.raises(ValueError, match="connected multiple times"):
        composer.build(validate_semantics=SemanticValidationLevel.STRICT)


def test_distinct_target_slots_keep_multiple_producers_valid() -> None:
    """B45 control: separate target slots do not conflict."""
    left = _slot("left")
    right = _slot("right")
    producer_one = _method_class("producer_one", output_slots=frozenset({left}))
    producer_two = _method_class("producer_two", output_slots=frozenset({right}))
    consumer = _method_class(
        "consumer",
        input_slots=frozenset({left, right}),
    )
    registry = _register(producer_one, producer_two, consumer)

    composer = MethodComposer(registry=registry)
    first = composer.add("tests.cmp02.producer_one@1.0.0")
    second = composer.add("tests.cmp02.producer_two@1.0.0")
    target = composer.add("tests.cmp02.consumer@1.0.0")
    composer.connect(first, target, {"left": "left"})
    composer.connect(second, target, {"right": "right"})

    chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)

    assert not any("connected multiple times" in warning for warning in chain.warnings)


def test_explicit_merge_node_owns_multiple_source_values() -> None:
    """B45 control: an explicit merge node gives each source a distinct slot."""
    left = _slot("left")
    right = _slot("right")
    merged = _slot("merged")
    producer_one = _method_class("producer_one", output_slots=frozenset({left}))
    producer_two = _method_class("producer_two", output_slots=frozenset({right}))
    merge = _method_class(
        "merge",
        input_slots=frozenset({left, right}),
        output_slots=frozenset({merged}),
    )
    consumer = _method_class("consumer", input_slots=frozenset({merged}))
    registry = _register(producer_one, producer_two, merge, consumer)

    composer = MethodComposer(registry=registry)
    first = composer.add("tests.cmp02.producer_one@1.0.0")
    second = composer.add("tests.cmp02.producer_two@1.0.0")
    merge_node = composer.add("tests.cmp02.merge@1.0.0")
    target = composer.add("tests.cmp02.consumer@1.0.0")
    composer.connect(first, merge_node, {"left": "left"})
    composer.connect(second, merge_node, {"right": "right"})
    composer.connect(merge_node, target, {"merged": "merged"})

    chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)

    assert merge_node.id in chain.dag.nodes
    assert not any("connected multiple times" in warning for warning in chain.warnings)


def _ordering_chain(
    occurrences: tuple[tuple[str, str, str], ...],
) -> SimpleNamespace:
    """Build the validator's minimal chain protocol with repeated node FQNs."""
    node_ids: list[UUID] = [uuid4() for _ in occurrences]
    signatures = {
        node_id: SimpleNamespace(
            fqn=fqn,
            name=fqn.rsplit(".", 1)[-1].split("@", 1)[0],
            namespace="tests.cmp02",
            family=family,
            variant=variant,
            data_modalities=frozenset(),
            conflicts_with=frozenset(),
        )
        for node_id, (fqn, family, variant) in zip(node_ids, occurrences, strict=True)
    }
    return SimpleNamespace(
        execution_order=tuple(node_ids),
        signatures=signatures,
        bindings=[],
    )


_ESTIMATE = ("tests.cmp02.estimate@1.0.0", "estimation", "estimate")
_SENSITIVITY = ("tests.cmp02.sensitivity@1.0.0", "sensitivity", "sensitivity")


@pytest.mark.parametrize("strict", [False, True], ids=["warn", "strict"])
def test_ordering_uses_early_estimate_occurrence(strict: bool) -> None:
    """B46: estimate1 → sensitivity → estimate2 is valid in WARN and STRICT."""
    chain = _ordering_chain((_ESTIMATE, _SENSITIVITY, _ESTIMATE))

    report = CrossMethodValidator(strict=strict).validate_chain(chain)

    assert [issue for issue in report.issues if issue.category == "ordering"] == []


@pytest.mark.parametrize("strict", [False, True], ids=["warn", "strict"])
def test_ordering_does_not_hide_early_sensitivity_occurrence(strict: bool) -> None:
    """B46: sensitivity1 → estimate → sensitivity2 keeps the early violation."""
    chain = _ordering_chain((_SENSITIVITY, _ESTIMATE, _SENSITIVITY))

    report = CrossMethodValidator(strict=strict).validate_chain(chain)
    ordering_issues = [issue for issue in report.issues if issue.category == "ordering"]

    assert len(ordering_issues) == 1
    assert ordering_issues[0].severity == ("error" if strict else "warning")
    assert ordering_issues[0].target_fqn == _SENSITIVITY[0]
