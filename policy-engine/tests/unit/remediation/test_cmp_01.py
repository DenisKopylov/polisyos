"""Regression tests for CMP-01 import, effective-DAG, and payload contracts."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import textwrap
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, ClassVar

import pytest

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
from polisyos.foundry.methods.composer import MethodComposer
from polisyos.foundry.methods.exceptions import CyclicDependencyError
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def reset_registry() -> None:
    """Keep synthetic CMP-01 methods isolated between tests."""
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def _make_method_class(
    name: str,
    *,
    requires: frozenset[str] = frozenset(),
    parameters: tuple[ParameterSpec, ...] = (),
    output_slots: frozenset[SlotSpec] = frozenset(),
    step: Callable[[Any, Mapping[str, Any]], Any] | None = None,
) -> type:
    """Build a small real registry method for an execution-contract test."""
    method_signature = MethodSignature(
        name=name,
        namespace="tests.cmp01",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=output_slots,
        parameters=parameters,
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
        requires=requires,
    )

    class TestMethod:
        signature: ClassVar[MethodSignature] = method_signature
        metadata: ClassVar[MethodMetadata] = MethodMetadata(
            description=f"CMP-01 test method: {name}",
            tags=frozenset({"cmp01", "test"}),
        )

        @staticmethod
        def pure_step(state: Any, params: dict[str, Any]) -> Any:
            if step is None:
                return None
            return step(state, params)

    TestMethod.__name__ = name.replace("_", " ").title().replace(" ", "")
    return TestMethod


def _register(*method_classes: type) -> MethodRegistry:
    registry = MethodRegistry.get_instance()
    for method_class in method_classes:
        registry.register(method_class, override=True)
    return registry


def test_async_wrapper_survives_both_fresh_import_orders() -> None:
    """The common async wrapper must work after either module import order."""
    repo_root = Path(__file__).parents[3]
    script = textwrap.dedent(
        """
        import asyncio
        import sys
        from typing import ClassVar

        order = sys.argv[1]
        if order == "chain-first":
            from polisyos.foundry.methods.backends import chain_executor as _chain_executor
            from polisyos.foundry.methods.backends import (
                async_chain_executor as _async_chain_executor,
            )
        else:
            from polisyos.foundry.methods.backends import (
                async_chain_executor as _async_chain_executor,
            )
            from polisyos.foundry.methods.backends import chain_executor as _chain_executor

        from polisyos.foundry.methods.backends.chain_executor import (
            execute_heterogeneous_chain_async,
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

        def make_method(name, requires=()):
            method_signature = MethodSignature(
                name=name,
                namespace="tests.cmp01",
                version="1.0.0",
                input_slots=frozenset(),
                output_slots=frozenset(),
                parameters=(),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_N,
                backend=ComputeBackend.NUMPY,
                supports_jit=False,
                supports_vmap=False,
                supports_grad=False,
                requires=frozenset(requires),
            )

            class TestMethod:
                signature: ClassVar[MethodSignature] = method_signature
                metadata: ClassVar[MethodMetadata] = MethodMetadata(
                    description=f"CMP-01 subprocess method: {name}",
                    tags=frozenset({"cmp01", "test"}),
                )

                @staticmethod
                def pure_step(state, params):
                    return None

            return TestMethod

        required = make_method("required")
        dependent = make_method(
            "dependent",
            requires=("tests.cmp01.required@1.0.0",),
        )
        registry = MethodRegistry.get_instance()
        registry.register(required, override=True)
        registry.register(dependent, override=True)

        composer = MethodComposer(registry=registry)
        dependent_node = composer.add("tests.cmp01.dependent@1.0.0")
        required_node = composer.add("tests.cmp01.required@1.0.0")
        chain = composer.build(validate_semantics=False)

        result = asyncio.run(
            execute_heterogeneous_chain_async(
                chain,
                state={"sentinel": 7},
                registry=registry,
            )
        )
        assert [node_id for node_id, _ in result.node_results] == [
            required_node.id,
            dependent_node.id,
        ]
        """
    )
    env = os.environ.copy()
    source_root = str(repo_root / "src")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (source_root, env.get("PYTHONPATH", "")) if part
    )

    for order in ("chain-first", "async-first"):
        completed = subprocess.run(
            [sys.executable, "-c", script, order],
            cwd=repo_root,
            env=env,
            capture_output=True,
            check=False,
            text=True,
        )
        assert completed.returncode == 0, (
            f"{order} import order failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )


def test_frozen_effective_graph_keeps_requires_and_parallel_sibling() -> None:
    """Freeze must retain ordering-only requirements without serializing siblings."""
    required = _make_method_class("required")
    dependent = _make_method_class(
        "dependent",
        requires=frozenset({"tests.cmp01.required@1.0.0"}),
    )
    sibling = _make_method_class("sibling")
    registry = _register(required, dependent, sibling)

    composer = MethodComposer(registry=registry)
    dependent_node = composer.add("tests.cmp01.dependent@1.0.0")
    required_node = composer.add("tests.cmp01.required@1.0.0")
    sibling_node = composer.add("tests.cmp01.sibling@1.0.0")
    chain = composer.build(validate_semantics=False)

    levels = chain.dag.compute_parallel_levels()
    assert required_node.id in levels[0]
    assert sibling_node.id in levels[0]
    assert dependent_node.id in levels[1]


def test_requirement_cycle_is_rejected_before_execution() -> None:
    """A requires-cycle must stop at build, before an executor can run it."""
    first = _make_method_class(
        "first",
        requires=frozenset({"tests.cmp01.second@1.0.0"}),
    )
    second = _make_method_class(
        "second",
        requires=frozenset({"tests.cmp01.first@1.0.0"}),
    )
    registry = _register(first, second)

    composer = MethodComposer(registry=registry)
    composer.add("tests.cmp01.first@1.0.0")
    composer.add("tests.cmp01.second@1.0.0")

    with pytest.raises(CyclicDependencyError, match=r"tests\.cmp01"):
        composer.build(validate_semantics=False)


def test_async_payload_matches_sequential_static_dynamic_override() -> None:
    """Async must preserve static, dynamic, and per-call parameter precedence."""
    result_slot = SlotSpec(
        name="result",
        slot_type=SlotType.SCALAR,
        unit=Unit(dimension="result", symbol="json"),
        shape=(),
    )

    def payload_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "result": {
                "window": params["window"],
                "scale": params["scale"],
            }
        }

    method = _make_method_class(
        "parameter_echo",
        parameters=(
            ParameterSpec(name="window", default=7, is_static=True),
            ParameterSpec(name="scale", default=2.0, is_static=False),
        ),
        output_slots=frozenset({result_slot}),
        step=payload_step,
    )
    registry = _register(method)

    composer = MethodComposer(registry=registry)
    node = composer.add(
        "tests.cmp01.parameter_echo@1.0.0",
        window=20,
        scale=2.0,
    )
    chain = composer.build(validate_semantics=False)
    params_map = {node.id: {"scale": 3.0}}

    from polisyos.foundry.methods.backends.async_chain_executor import AsyncChainExecutor
    from polisyos.foundry.methods.backends.chain_executor import execute_heterogeneous_chain

    sequential = execute_heterogeneous_chain(
        chain,
        state={},
        params_per_node=params_map,
        registry=registry,
        executor_mode="sequential",
    )
    asynchronous = asyncio.run(
        AsyncChainExecutor(registry=registry).execute(
            chain,
            initial_state={},
            params_map=params_map,
        )
    )

    expected = {"result": {"window": 20, "scale": 3.0}}
    assert sequential.final_state == expected
    assert asynchronous.final_state == expected
    assert asynchronous.final_state == sequential.final_state
