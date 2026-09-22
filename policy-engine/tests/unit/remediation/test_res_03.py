"""Regression witnesses for RES-03 partial async-chain results."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from typing import Any, ClassVar

import pytest

from polisyos.foundry.methods.backends.async_chain_executor import (
    AsyncChainExecutionError,
    AsyncChainExecutor,
)
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
)
from polisyos.foundry.methods.composer import MethodComposer
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def reset_registry() -> None:
    """Keep synthetic RES-03 methods isolated between tests."""
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def _make_method(
    name: str,
    *,
    requires: frozenset[str] = frozenset(),
    step: Callable[[Any, Mapping[str, Any]], Any] | None = None,
) -> type:
    """Build a small real registry method for an async-chain witness."""
    signature = MethodSignature(
        name=name,
        namespace="tests.res03",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
        requires=requires,
    )

    class TestMethod:
        signature: ClassVar[MethodSignature] = signature
        metadata: ClassVar[MethodMetadata] = MethodMetadata(
            description=f"RES-03 test method: {name}",
            tags=frozenset({"res03", "test"}),
        )

        @staticmethod
        def pure_step(state: Any, params: dict[str, Any]) -> Any:
            if step is None:
                return None
            return step(state, params)

    TestMethod.__name__ = name.replace("_", " ").title().replace(" ", "")
    return TestMethod


def _register(*method_classes: type) -> MethodRegistry:
    """Register synthetic methods in the isolated process registry."""
    registry = MethodRegistry.get_instance()
    for method_class in method_classes:
        registry.register(method_class, override=True)
    return registry


def _partial_chain(*, fail_b: bool = True) -> tuple[MethodComposer, MethodRegistry, dict[str, Any]]:
    """Build a previous level, an independent A/B level, and dependent C."""
    observations: dict[str, Any] = {"c_calls": 0}

    previous = _make_method(
        "previous",
        step=lambda _state, _params: {
            "previous": "previous-value",
            "scope": "world:previous",
            "artifact_ref": "sha256:previous",
        },
    )
    left = _make_method(
        "left",
        requires=frozenset({"tests.res03.previous@1.0.0"}),
        step=lambda _state, _params: {
            "left": 7,
            "scope": "world:left",
            "artifact_ref": "sha256:left",
        },
    )

    def right_step(_state: Any, _params: Mapping[str, Any]) -> Any:
        if fail_b:
            raise ValueError("right node failed exactly")
        return {
            "right": 11,
            "scope": "world:right",
            "artifact_ref": "sha256:right",
        }

    right = _make_method(
        "right",
        requires=frozenset({"tests.res03.previous@1.0.0"}),
        step=right_step,
    )

    def dependent_step(_state: Any, _params: Mapping[str, Any]) -> Any:
        observations["c_calls"] += 1
        return {"dependent": True}

    dependent = _make_method(
        "dependent",
        requires=frozenset({"tests.res03.right@1.0.0"}),
        step=dependent_step,
    )

    registry = _register(previous, left, right, dependent)
    composer = MethodComposer(registry=registry)
    composer.add("tests.res03.previous@1.0.0")
    composer.add("tests.res03.left@1.0.0")
    composer.add("tests.res03.right@1.0.0")
    composer.add("tests.res03.dependent@1.0.0")
    return composer, registry, observations


def test_independent_success_survives_sibling_failure_with_exact_error_and_scope() -> None:
    """A's result remains readable with its scope while B's exact error stays terminal."""
    composer, registry, _observations = _partial_chain()
    chain = composer.build(validate_semantics=False)

    with pytest.raises(AsyncChainExecutionError) as raised:
        asyncio.run(AsyncChainExecutor(registry=registry).execute(chain, initial_state={}))

    error = raised.value
    assert len(error.node_errors) == 1
    assert error.node_errors[0].method_fqn == "tests.res03.right@1.0.0"
    assert type(error.node_errors[0].error) is ValueError
    assert str(error.node_errors[0].error) == "right node failed exactly"

    partial = error.partial_result
    assert partial.final_state["left"] == 7
    assert partial.final_state["scope"] == "world:left"
    assert partial.final_state["artifact_ref"] == "sha256:left"
    assert [node_id for node_id, _result in partial.node_results] == [
        node_id
        for node_id, _node in chain.dag.nodes.items()
        if _node.method_fqn in {"tests.res03.previous@1.0.0", "tests.res03.left@1.0.0"}
    ]
    assert error.failed_level_index == 1


def test_dependent_node_is_not_reported_as_successful_partial_result() -> None:
    """A dependent node is withheld when its common basis failed."""
    composer, registry, observations = _partial_chain()
    chain = composer.build(validate_semantics=False)

    with pytest.raises(AsyncChainExecutionError) as raised:
        asyncio.run(AsyncChainExecutor(registry=registry).execute(chain, initial_state={}))

    error = raised.value
    partial_ids = {node_id for node_id, _result in error.partial_result.node_results}
    dependent_id = next(
        node_id
        for node_id, node in chain.dag.nodes.items()
        if node.method_fqn == "tests.res03.dependent@1.0.0"
    )
    assert dependent_id not in partial_ids
    assert dependent_id in error.blocked_node_ids
    assert observations["c_calls"] == 0


def test_previous_completed_level_survives_later_level_failure() -> None:
    """Completed levels remain available after a later parallel level fails."""
    composer, registry, _observations = _partial_chain()
    chain = composer.build(validate_semantics=False)

    with pytest.raises(AsyncChainExecutionError) as raised:
        asyncio.run(AsyncChainExecutor(registry=registry).execute(chain, initial_state={}))

    partial = raised.value.partial_result
    assert partial.final_state["previous"] == "previous-value"
    assert partial.final_state["scope"] == "world:left"
    assert [result.output["previous"] for _node_id, result in partial.node_results[:1]] == [
        "previous-value"
    ]


def test_all_success_control_returns_all_levels_without_partial_metadata() -> None:
    """The all-success path remains a normal complete ChainExecutionResult."""
    composer, registry, observations = _partial_chain(fail_b=False)
    chain = composer.build(validate_semantics=False)

    result = asyncio.run(AsyncChainExecutor(registry=registry).execute(chain, initial_state={}))

    assert result.final_state["previous"] == "previous-value"
    assert result.final_state["left"] == 7
    assert result.final_state["right"] == 11
    assert result.final_state["dependent"] is True
    assert len(result.node_results) == 4
    assert observations["c_calls"] == 1
