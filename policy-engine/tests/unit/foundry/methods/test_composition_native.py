"""Native composition, selected diagnostics and fresh checkpoint consumers."""

from __future__ import annotations

import asyncio
import builtins
from dataclasses import replace
from itertools import pairwise
from threading import Barrier, Lock
from types import MappingProxyType
from typing import Any, ClassVar
from uuid import UUID

import pytest

from polisyos.foundry.methods.backends.chain_executor import (
    execute_heterogeneous_chain,
    execute_heterogeneous_chain_async,
)
from polisyos.foundry.methods.backends.checkpointing import (
    ChainCheckpoint,
    CheckpointDigestMismatchError,
    CheckpointingChainExecutor,
    CheckpointLoadError,
)
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.base import MethodMetadata, MethodSignature
from polisyos.foundry.methods.components.composer import (
    MethodComposer,
    SemanticValidationLevel,
)
from polisyos.foundry.methods.components.linker import LinkerConfig, SlotLinker
from polisyos.foundry.methods.components.semantic_validator import CrossMethodValidator
from polisyos.foundry.methods.components.slot_schema import SemanticCompatibilityError
from polisyos.foundry.methods.exceptions import MissingRequirementError
from polisyos.foundry.methods.registry import MethodRegistry
from tests._helpers.method_chain import (
    Dependent,
    Flexible,
    Independent,
    Left,
    Matched,
    Merge,
    Required,
    Right,
    Twice,
    register_methods,
    signature,
    slot,
)


class ValueConsumer:
    signature: ClassVar[MethodSignature] = signature(
        "value_consumer", inputs=(slot("value"),), outputs=(slot("answer"),)
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Read the limited selected value."
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {"answer": state}


@pytest.fixture(autouse=True)
def isolated_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def _replace_id(composer, node, number):
    restored = replace(node, id=UUID(int=number))
    composer.dag.nodes.pop(node.id)
    composer.dag.predecessors.pop(node.id)
    composer.dag.successors.pop(node.id)
    sig = composer._signatures.pop(node.id)
    composer.dag.add_node(restored)
    composer._signatures[restored.id] = sig
    return restored


def _observer(monkeypatch):
    dispatcher = MethodDispatcher(enable_runtime_selection=False)
    calls = []
    original = dispatcher.dispatch

    def observe(*args, **kwargs):
        calls.append(kwargs["signature"].fqn)
        return original(*args, **kwargs)

    monkeypatch.setattr(dispatcher, "dispatch", observe)
    return dispatcher, calls


def _required_chain(registry):
    composer = MethodComposer(registry=registry)
    composer.add(Dependent.signature.fqn)
    composer.add(Required.signature.fqn)
    composer.add(Independent.signature.fqn)
    return composer.build(validate_semantics=SemanticValidationLevel.STRICT)


def test_actual_async_requires_only_siblings_reach_shared_runtime_barrier(monkeypatch):
    registry = register_methods()
    chain = _required_chain(registry)
    barrier, lock = Barrier(2), Lock()
    completed = set()
    dispatcher = MethodDispatcher(enable_runtime_selection=False)
    original = dispatcher.dispatch

    def observe(*args, **kwargs):
        fqn = kwargs["signature"].fqn
        if fqn in {Required.signature.fqn, Independent.signature.fqn}:
            barrier.wait(timeout=5)
        else:
            assert completed == {Required.signature.fqn, Independent.signature.fqn}
        result = original(*args, **kwargs)
        with lock:
            completed.add(fqn)
        return result

    monkeypatch.setattr(dispatcher, "dispatch", observe)
    result = asyncio.run(
        execute_heterogeneous_chain_async(
            chain,
            state={"sentinel": 7},
            registry=registry,
            dispatcher=dispatcher,
        )
    )
    assert result.final_state["answer"] == 36
    assert not chain.bindings
    assert len(result.node_results) == 3


def test_missing_strict_requirement_refuses_before_native_dispatch(monkeypatch):
    registry = register_methods()
    dispatcher, calls = _observer(monkeypatch)
    composer = MethodComposer(registry=registry)
    composer.add(Dependent.signature.fqn)
    with pytest.raises(MissingRequirementError):
        composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    assert calls == []


def test_async_internal_import_failure_is_not_a_permanent_unavailable_latch(monkeypatch):
    registry = register_methods()
    chain = _required_chain(registry)
    original, failures = builtins.__import__, []

    def import_once(name, *args, **kwargs):
        if name.endswith("backends.async_chain_executor") and not failures:
            failures.append(name)
            raise ImportError("controlled native internal import fault")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_once)
    with pytest.raises(ImportError, match="controlled native internal import fault"):
        execute_heterogeneous_chain(
            chain, state={"sentinel": 7}, registry=registry, executor_mode="async"
        )
    result = execute_heterogeneous_chain(
        chain, state={"sentinel": 7}, registry=registry, executor_mode="async"
    )
    assert failures and result.final_state["answer"] == 36


def test_running_loop_sync_wrapper_names_working_await_route():
    registry = register_methods()
    chain = _required_chain(registry)

    async def run():
        with pytest.raises(RuntimeError, match="await execute_heterogeneous_chain_async"):
            execute_heterogeneous_chain(
                chain, state={"sentinel": 7}, registry=registry, executor_mode="async"
            )
        return await execute_heterogeneous_chain_async(
            chain, state={"sentinel": 7}, registry=registry
        )

    assert asyncio.run(run()).final_state["answer"] == 36


@pytest.mark.parametrize("swap", [False, True])
@pytest.mark.parametrize("mode", ["sequential", "async"])
def test_actual_explicit_merge_is_numeric_and_uuid_invariant(swap, mode):
    registry = register_methods()
    composer = MethodComposer(registry=registry)
    left = _replace_id(composer, composer.add(Left.signature.fqn), 2 if swap else 1)
    right = _replace_id(composer, composer.add(Right.signature.fqn), 1 if swap else 2)
    merge, twice = composer.add(Merge.signature.fqn), composer.add(Twice.signature.fqn)
    composer.connect(left, merge, {"left": "left"})
    composer.connect(right, merge, {"right": "right"})
    composer.connect(merge, twice, {"merged": "merged"})
    chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    result = execute_heterogeneous_chain(chain, state={}, registry=registry, executor_mode=mode)
    assert result.final_state["answer"] == 60
    assert dict(result.node_results)[merge.id].slot_outputs["merged"] == 30


def _warn_chain(registry, swap=False):
    registry.register(ValueConsumer, override=True)
    composer = MethodComposer(registry=registry)
    left = _replace_id(composer, composer.add(Left.signature.fqn), 2 if swap else 1)
    right = _replace_id(composer, composer.add(Right.signature.fqn), 1 if swap else 2)
    target = composer.add(ValueConsumer.signature.fqn)
    composer.connect(left, target, {"left": "value"})
    composer.connect(right, target, {"right": "value"})
    return composer.build(validate_semantics=SemanticValidationLevel.WARN)


@pytest.mark.parametrize("swap,expected", [(False, 20), (True, 10)])
def test_warn_values_and_diagnostics_survive_fresh_checkpoint(
    tmp_path, monkeypatch, swap, expected
):
    registry = register_methods()
    chain = _warn_chain(registry, swap)
    dispatcher, calls = _observer(monkeypatch)
    executor = CheckpointingChainExecutor(
        checkpoint_dir=tmp_path, registry=registry, dispatcher=dispatcher
    )
    result = executor.execute(chain, initial_state={})
    assert result.final_state["answer"] == expected
    assert any("connected multiple times" in warning for warning in result.warnings)
    assert len(calls) == 3
    checkpoint = ChainCheckpoint.load(sorted(tmp_path.glob("*.json"))[-1])
    calls.clear()
    resumed = CheckpointingChainExecutor(registry=registry, dispatcher=dispatcher).execute(
        chain,
        initial_state={},
        checkpoint=checkpoint,
    )
    assert resumed.final_state["answer"] == expected
    assert len(resumed.node_results) == 3 and calls == []
    assert resumed.warnings == chain.warnings
    assert resumed.validation_context == chain.validation_context


@pytest.mark.parametrize("mutation", ["warnings", "mode", "input", "seed", "prefix", "history"])
def test_limited_checkpoint_changes_refuse_before_new_dispatch(tmp_path, monkeypatch, mutation):
    registry = register_methods()
    chain = _warn_chain(registry)
    dispatcher, calls = _observer(monkeypatch)
    executor = CheckpointingChainExecutor(
        checkpoint_dir=tmp_path, registry=registry, dispatcher=dispatcher
    )
    executor.execute(chain, initial_state={})
    checkpoint = ChainCheckpoint.load(sorted(tmp_path.glob("*.json"))[-1])
    initial, seed = {}, 0
    if mutation == "warnings":
        chain = replace(chain, warnings=())
    elif mutation == "mode":
        chain = replace(
            chain,
            validation_context=replace(chain.validation_context, mode=SemanticValidationLevel.OFF),
        )
    elif mutation == "input":
        initial = {"changed": True}
    elif mutation == "seed":
        seed = 1
    elif mutation == "prefix":
        checkpoint.completed_node_ids.pop(0)
    else:
        checkpoint.node_results.pop()
    calls.clear()
    with pytest.raises((ValueError, CheckpointDigestMismatchError, CheckpointLoadError)):
        executor.execute(chain, initial_state=initial, checkpoint=checkpoint, seed=seed)
    assert calls == []


@pytest.mark.parametrize("mode", ["sequential", "async"])
def test_matched_diagnostics_reach_actual_execution_and_fresh_checkpoint(
    tmp_path, monkeypatch, mode
):
    registry = register_methods()
    composer = MethodComposer(registry=registry)
    source, target = composer.add(Flexible.signature.fqn), composer.add(Matched.signature.fqn)
    composer.connect(source, target)
    chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    result = execute_heterogeneous_chain(chain, state={}, registry=registry, executor_mode=mode)
    assert result.final_state["answer"] == 2010
    assert "Auto-linked: a_flexible -> d_second" in result.warnings
    assert not any("b_fixed -> d_second" in warning for warning in result.warnings)
    dispatcher, calls = _observer(monkeypatch)
    CheckpointingChainExecutor(
        checkpoint_dir=tmp_path, registry=registry, dispatcher=dispatcher
    ).execute(chain, initial_state={})
    checkpoint = ChainCheckpoint.load(sorted(tmp_path.glob("*.json"))[-1])
    calls.clear()
    resumed = CheckpointingChainExecutor(registry=registry, dispatcher=dispatcher).execute(
        chain, initial_state={}, checkpoint=checkpoint
    )
    assert resumed.final_state["answer"] == 2010
    assert resumed.warnings == chain.warnings and len(resumed.node_results) == 2
    assert calls == []


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize(
    "kinds,indices", [("ESE", ()), ("SES", (0,)), ("SSE", (0, 1)), ("B", (0,)), ("N", ())]
)
def test_ordering_issues_use_actual_registered_occurrences(strict, kinds, indices):
    registry = MethodRegistry.get_instance()
    signatures = {
        "E": replace(
            Required.signature,
            name="estimate",
            family="estimation",
            variant="estimate",
            requires=frozenset(),
        ),
        "S": replace(
            Independent.signature,
            name="sensitivity",
            family="sensitivity",
            variant="sensitivity",
            requires=frozenset(),
        ),
        "B": replace(
            Independent.signature,
            name="self",
            family="estimation",
            variant="sensitivity",
            requires=frozenset(),
        ),
        "N": replace(
            Independent.signature, name="neutral", family=None, variant=None, requires=frozenset()
        ),
    }
    for kind in set(kinds):
        cls = type(
            "Occurrence" + kind,
            (),
            {
                "signature": signatures[kind],
                "metadata": Required.metadata,
                "pure_step": staticmethod(Required.pure_step),
            },
        )
        registry.register(cls, override=True)
    composer = MethodComposer(registry=registry)
    nodes = [composer.add(signatures[kind].fqn) for kind in kinds]
    for first, second in pairwise(nodes):
        composer.connect(first, second, {})
    # OFF here supplies a real typed/frozen chain; the actual strict/warn
    # occurrence checker is invoked below, not replaced by a protocol stub.
    chain = composer.build(validate_semantics=SemanticValidationLevel.OFF)
    report = CrossMethodValidator(strict=strict).validate_chain(chain)
    issues = [issue for issue in report.issues if issue.category == "ordering"]
    assert tuple(issue.target_index for issue in issues) == indices
    assert tuple(issue.target_node_id for issue in issues) == tuple(
        nodes[index].id for index in indices
    )
    assert all(issue.severity == ("error" if strict else "warning") for issue in issues)


class PairWeighted:
    signature: ClassVar[MethodSignature] = signature(
        "pair_weighted", inputs=(slot("left"), slot("right")), outputs=(slot("answer"),)
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Distinguish both named selected inputs."
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {"answer": 100 * state["left"] + state["right"]}


@pytest.mark.parametrize("mode", ["sequential", "async"])
@pytest.mark.parametrize("reverse", [False, True])
def test_two_producer_auto_order_retains_exact_names_and_native_1020(reverse, mode):
    registry = register_methods()
    registry.register(PairWeighted, override=True)
    composer = MethodComposer(registry=registry)
    left, right = composer.add(Left.signature.fqn), composer.add(Right.signature.fqn)
    target = composer.add(PairWeighted.signature.fqn)
    for node in [right, left] if reverse else [left, right]:
        composer.connect(node, target)
    chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    assert {(b.source_slot, b.target_slot) for b in chain.bindings} == {
        ("left", "left"),
        ("right", "right"),
    }
    result = execute_heterogeneous_chain(chain, state={}, registry=registry, executor_mode=mode)
    assert result.final_state["answer"] == 1020


class OutcomeProducer:
    signature: ClassVar[MethodSignature] = signature("outcome_source", outputs=(slot("outcome"),))
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="Produce the named outcome.")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {"outcome": 30}


class ResidualConsumer:
    signature: ClassVar[MethodSignature] = signature(
        "residual_target", inputs=(slot("residual"),), outputs=(slot("answer"),)
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Consume the allowed semantic role."
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {"answer": state}


@pytest.mark.parametrize("mode", ["sequential", "async"])
@pytest.mark.parametrize("explicit", [False, True])
def test_actual_backend_replays_semantic_role_gate_before_dispatch(monkeypatch, mode, explicit):
    registry = register_methods()
    registry.register(OutcomeProducer, override=True)
    registry.register(ResidualConsumer, override=True)
    composer = MethodComposer(registry=registry, linker=SlotLinker(LinkerConfig.semantic_strict()))
    source, target = (
        composer.add(OutcomeProducer.signature.fqn),
        composer.add(ResidualConsumer.signature.fqn),
    )
    edge = composer.connect(source, target, {"outcome": "residual"} if explicit else None)
    chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    dispatcher, calls = _observer(monkeypatch)
    positive = execute_heterogeneous_chain(
        chain, state={}, registry=registry, dispatcher=dispatcher, executor_mode=mode
    )
    assert positive.final_state["answer"] == 30 and len(calls) == 2
    calls.clear()
    # Forge a complete type-compatible edge/target after compile, retaining the
    # actual semantic-strict context. The final consumer must replay its owner.
    forbidden = replace(chain.bindings[0], target_slot="treatment")
    corrupted = replace(
        chain,
        signatures=MappingProxyType(
            {
                **chain.signatures,
                target.id: replace(
                    chain.signatures[target.id], input_slots=frozenset({slot("treatment")})
                ),
            }
        ),
        bindings=(forbidden,),
        dag=replace(
            chain.dag,
            edges=MappingProxyType({(source.id, target.id): replace(edge, bindings=(forbidden,))}),
        ),
    )
    with pytest.raises(SemanticCompatibilityError):
        execute_heterogeneous_chain(
            corrupted, state={}, registry=registry, dispatcher=dispatcher, executor_mode=mode
        )
    assert calls == []
