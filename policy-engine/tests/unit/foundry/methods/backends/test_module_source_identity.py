"""Imported module mutations must not reuse an incompatible actual checkpoint."""

from __future__ import annotations

import json
import math
import sys
from dataclasses import replace
from types import ModuleType
from typing import ClassVar, NamedTuple

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.backends.checkpointing import (
    ChainCheckpoint,
    CheckpointDigestMismatchError,
    CheckpointIdentityError,
    CheckpointingChainExecutor,
)
from polisyos.foundry.methods.base import ComputeBackend, ParameterSpec
from polisyos.foundry.methods.components.composer import MethodComposer

from .test_checkpoint_identity import (
    _CONSUMER_SIGNATURE,
    _METADATA,
    _PRODUCER_SIGNATURE,
    _chain,
    _Original,
    _RecordingDispatcher,
    _strict_context,
)

_DATA_GETTER = getattr
_DATA_FIELDS = ("product",)


class _DataFieldState(NamedTuple):
    operand: object
    product: object


class _DataFieldMethod:
    signature: ClassVar = replace(
        _PRODUCER_SIGNATURE,
        name="data_field",
        backend=ComputeBackend.JAX,
        input_slots=_CONSUMER_SIGNATURE.input_slots,
        parameters=(ParameterSpec("factor", default=2, is_static=False),),
        supports_jit=True,
    )
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return state._replace(product=state.operand * params["factor"])

    @staticmethod
    def dematerialize_output(output):
        return {field: _DATA_GETTER(output, field, output) for field in _DATA_FIELDS}


@pytest.mark.parametrize("jit", [False, True])
def test_finite_aliased_data_getter_keeps_real_numeric_warm_handles(jit):
    import jax.numpy as jnp

    from polisyos.foundry.methods.compiler import CompilationCache, MethodCompiler

    _, registry = _chain()
    registry.register(_DataFieldMethod)
    compiler = MethodCompiler(registry=registry, cache=CompilationCache())
    state = _DataFieldState(jnp.asarray(10.0), jnp.asarray(0.0))
    cold = compiler.compile(
        method_name=_DataFieldMethod.signature.fqn,
        params={"factor": 2},
        sample_inputs={"operand": state.operand},
        jit=jit,
    )
    warm = compiler.compile(
        method_name=_DataFieldMethod.signature.fqn,
        params={"factor": 3},
        sample_inputs={"operand": state.operand},
        jit=jit,
    )
    assert cold._kernel is warm._kernel
    assert float(_DataFieldMethod.dematerialize_output(cold.step_fn(state, {}))["product"]) == 20
    assert float(_DataFieldMethod.dematerialize_output(warm.step_fn(state, {}))["product"]) == 30


class _DynamicFieldSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": _DATA_GETTER(state, params["field"], state)}


class _ReboundFieldSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        try:
            raise ValueError("replacement input")
        except ValueError as state:
            return {"product": len(_DATA_GETTER(state, "args", state))}


class _GenericFieldSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step[T](state, params):
        return {"product": _DATA_GETTER(state, "product", state)}


@pytest.mark.parametrize("source", [_DynamicFieldSource, _ReboundFieldSource, _GenericFieldSource])
def test_runtime_selector_or_rebinding_does_not_gain_data_field_identity(tmp_path, source):
    chain, registry = _chain()
    registry.register(source, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    dispatcher = _RecordingDispatcher()
    with pytest.raises(CheckpointIdentityError):
        CheckpointingChainExecutor(
            registry=registry, dispatcher=dispatcher, artifact_store=store
        ).execute(chain, initial_state={"x": 3}, artifact_context=_strict_context(store, chain))
    assert dispatcher.calls == []


def _frame_original_increment(value, effect_path):
    with open(effect_path, "a", encoding="utf-8") as output:
        output.write("original\n")
    return value + 1


def _frame_replacement_increment(value, effect_path):
    with open(effect_path, "a", encoding="utf-8") as output:
        output.write("replacement\n")
    return value + 101


class _FrameConsumer:
    signature: ClassVar = replace(
        _CONSUMER_SIGNATURE, parameters=(ParameterSpec("effect_path", default=""),)
    )
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {
            "total": sys._getframe()
            .f_globals["math"]
            ._e02_b74_owner_frame_helper(state, params["effect_path"])
        }


def test_returned_frame_namespace_refuses_before_replacement_effect(tmp_path, monkeypatch):
    """Retain the genuine unresolved builtin-returned namespace counterexample."""
    monkeypatch.setattr(
        math, "_e02_b74_owner_frame_helper", _frame_original_increment, raising=False
    )
    _, registry = _chain()
    registry.register(_FrameConsumer, override=True)
    composer = MethodComposer(registry=registry)
    first = composer.add(_Original.signature.fqn)
    second = composer.add(_FrameConsumer.signature.fqn)
    composer.connect(first, second, {"product": "operand"})
    chain = composer.build(validate_semantics=False)
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    effects = tmp_path / "effects.txt"
    params = {second.id: {"effect_path": str(effects)}}
    executor = CheckpointingChainExecutor(
        registry=registry, artifact_store=store, checkpoint_dir=tmp_path / "checkpoints"
    )
    original = executor.execute(
        chain, initial_state={"x": 3}, params_per_node=params, seed=7, artifact_context=context
    )
    pointer = next((tmp_path / "checkpoints").glob("*_0000_*.json"))
    checkpoint = ChainCheckpoint.load(pointer)
    assert checkpoint.completed_node_ids == [str(first.id)]
    assert checkpoint.intermediate_state["product"] == 6
    assert checkpoint.node_results[0]["output"] == {"product": 6}
    original_pointer = pointer.read_bytes()
    fresh_store = FileSystemCAS(tmp_path / "cas")
    assert fresh_store.get_bytes(context.input_refs["x"]) == b'{"x":3}'
    reopened = CheckpointingChainExecutor(registry=registry, artifact_store=fresh_store)
    unchanged = reopened.execute(
        chain,
        initial_state={"x": 3},
        params_per_node=params,
        checkpoint=checkpoint,
        seed=7,
        artifact_context=context,
    )
    assert original.final_state["total"] == unchanged.final_state["total"] == 7
    assert unchanged.history_complete
    baseline_effects = effects.read_text().splitlines()
    assert baseline_effects == ["original", "original"]
    monkeypatch.setattr(math, "_e02_b74_owner_frame_helper", _frame_replacement_increment)
    observed = {"original": 7, "unchanged_resume": 7, "before_effects": baseline_effects}
    try:
        result = reopened.execute(
            chain,
            initial_state={"x": 3},
            params_per_node=params,
            checkpoint=checkpoint,
            seed=7,
            artifact_context=context,
        )
        observed.update(
            {
                "refusal": None,
                "changed_resume": result.final_state["total"],
                "history_complete": result.history_complete,
            }
        )
    except (CheckpointDigestMismatchError, CheckpointIdentityError) as error:
        observed.update({"refusal": type(error).__name__, "message": str(error)})
    observed.update(
        {
            "pointer_unchanged": pointer.read_bytes() == original_pointer,
            "actual_effects": effects.read_text().splitlines(),
        }
    )
    (tmp_path / "measurement.json").write_text(json.dumps(observed, indent=2) + "\n")
    print("FRAME_NAMESPACE_OBSERVATION", json.dumps(observed, sort_keys=True))  # noqa: T201
    assert observed["pointer_unchanged"]
    assert observed["refusal"] is not None, (
        "Builtin-returned frame namespace admitted a physically executed replacement helper"
    )
    assert observed["actual_effects"] == baseline_effects


def _original_multiplier(value):
    return value * 2


def _replacement_multiplier(value):
    return value * 3


class _ImportedSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": math._e02_b74_owner_multiplier(state["x"])}


def test_same_version_imported_member_change_refuses_actual_stale_prefix(tmp_path, monkeypatch):
    """The real cold result changes10 while stale resume would still produce7."""
    monkeypatch.setattr(math, "_e02_b74_owner_multiplier", _original_multiplier, raising=False)
    chain, registry = _chain()
    registry.register(_ImportedSource, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    dispatcher = _RecordingDispatcher()
    executor = CheckpointingChainExecutor(
        registry=registry,
        dispatcher=dispatcher,
        artifact_store=store,
        checkpoint_dir=tmp_path / "checkpoints",
    )
    original = executor.execute(chain, initial_state={"x": 3}, seed=7, artifact_context=context)
    pointer = next((tmp_path / "checkpoints").glob("*_0000_*.json"))
    checkpoint = ChainCheckpoint.load(pointer)
    original_pointer = pointer.read_bytes()
    unchanged = executor.execute(
        chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7, artifact_context=context
    )
    assert original.final_state["total"] == unchanged.final_state["total"] == 7
    assert unchanged.history_complete
    monkeypatch.setattr(math, "_e02_b74_owner_multiplier", _replacement_multiplier)
    cold = CheckpointingChainExecutor(registry=registry, artifact_store=store).execute(
        chain, initial_state={"x": 3}, seed=7, artifact_context=context
    )
    assert cold.final_state["total"] == 10
    dispatcher.calls.clear()
    with pytest.raises(CheckpointDigestMismatchError):
        executor.execute(
            chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7, artifact_context=context
        )
    assert dispatcher.calls == []
    assert pointer.read_bytes() == original_pointer


class _BuiltinSource:
    signature: ClassVar = replace(_PRODUCER_SIGNATURE, name="builtin")
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": math.fabs(state["x"]) * params["factor"]}


def test_unchanged_imported_builtin_retains_actual_arithmetic_resume(tmp_path):
    """A supported unchanged native member does not withdraw numerical reuse."""

    # Keep the same actual compiled FQN/required chain as the other profiles.
    class Source(_BuiltinSource):
        signature: ClassVar = _PRODUCER_SIGNATURE

    chain, registry = _chain()
    registry.register(Source, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    executor = CheckpointingChainExecutor(
        registry=registry, artifact_store=store, checkpoint_dir=tmp_path / "checkpoints"
    )
    original = executor.execute(chain, initial_state={"x": 3}, seed=7, artifact_context=context)
    checkpoint = ChainCheckpoint.load(next((tmp_path / "checkpoints").glob("*_0000_*.json")))
    resumed = executor.execute(
        chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7, artifact_context=context
    )
    assert original.final_state["total"] == resumed.final_state["total"] == 7
    assert resumed.history_complete


class _ImportedConstantSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": state["x"] * math._e02_b74_owner_constant}


class _NestedSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": math._e02_b74_owner_child.multiply(state["x"])}


class _NestedFunctionSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        def selected(value):
            return math._e02_b74_owner_multiplier(value)

        return {"product": selected(state["x"])}


@pytest.mark.parametrize("source", [_ImportedConstantSource, _NestedSource, _NestedFunctionSource])
def test_selected_constant_and_nested_module_are_bound_before_resume(tmp_path, monkeypatch, source):
    child = ModuleType("math.e02_child")
    child.multiply = _original_multiplier
    monkeypatch.setattr(math, "_e02_b74_owner_child", child, raising=False)
    monkeypatch.setattr(math, "_e02_b74_owner_constant", 2, raising=False)
    monkeypatch.setattr(math, "_e02_b74_owner_multiplier", _original_multiplier, raising=False)
    chain, registry = _chain()
    registry.register(source, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    executor = CheckpointingChainExecutor(
        registry=registry, artifact_store=store, checkpoint_dir=tmp_path / "checkpoints"
    )
    assert (
        executor.execute(chain, initial_state={"x": 3}, artifact_context=context).final_state[
            "total"
        ]
        == 7
    )
    checkpoint = ChainCheckpoint.load(next((tmp_path / "checkpoints").glob("*_0000_*.json")))
    monkeypatch.setattr(math, "_e02_b74_owner_constant", 3)
    monkeypatch.setattr(math, "_e02_b74_owner_multiplier", _replacement_multiplier)
    child.multiply = _replacement_multiplier
    assert (
        CheckpointingChainExecutor(registry=registry)
        .execute(chain, initial_state={"x": 3})
        .final_state["total"]
        == 10
    )
    with pytest.raises(CheckpointDigestMismatchError):
        executor.execute(
            chain, initial_state={"x": 3}, checkpoint=checkpoint, artifact_context=context
        )


def test_unselected_module_member_does_not_invalidate_real_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(math, "_e02_b74_owner_multiplier", _original_multiplier, raising=False)
    chain, registry = _chain()
    registry.register(_ImportedSource, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    executor = CheckpointingChainExecutor(
        registry=registry, artifact_store=store, checkpoint_dir=tmp_path / "checkpoints"
    )
    executor.execute(chain, initial_state={"x": 3}, artifact_context=context)
    checkpoint = ChainCheckpoint.load(next((tmp_path / "checkpoints").glob("*_0000_*.json")))
    monkeypatch.setattr(math, "_e02_b74_unselected", [1, 2], raising=False)
    resumed = executor.execute(
        chain, initial_state={"x": 3}, checkpoint=checkpoint, artifact_context=context
    )
    assert resumed.final_state["total"] == 7
    assert resumed.history_complete


class _ReflectiveSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        attribute_name = "_e02_b74_owner_multiplier"
        return {"product": getattr(math, attribute_name)(state["x"])}


def _transported(module, value):
    return module._e02_b74_owner_multiplier(value)


class _TransportSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": _transported(math, state["x"])}


class _MutableModuleSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": state["x"] * math._e02_b74_owner_mutable[0]}


class _DynamicImportSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": __import__("math")._e02_b74_owner_multiplier(state["x"])}


class _LocalImportSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        import math as selected

        return {"product": selected._e02_b74_owner_multiplier(state["x"])}


_module_namespace = globals


class _NamespaceSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": _module_namespace()["math"]._e02_b74_owner_multiplier(state["x"])}


@pytest.mark.parametrize(
    "source",
    [
        _ReflectiveSource,
        _TransportSource,
        _MutableModuleSource,
        _DynamicImportSource,
        _LocalImportSource,
        _NamespaceSource,
    ],
)
def test_unsupported_module_access_refuses_before_actual_dispatch(tmp_path, monkeypatch, source):
    monkeypatch.setattr(math, "_e02_b74_owner_multiplier", _original_multiplier, raising=False)
    monkeypatch.setattr(math, "_e02_b74_owner_mutable", [2], raising=False)
    chain, registry = _chain()
    registry.register(source, override=True)
    assert (
        CheckpointingChainExecutor(registry=registry)
        .execute(chain, initial_state={"x": 3})
        .final_state["total"]
        == 7
    )
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    dispatcher = _RecordingDispatcher()
    with pytest.raises(CheckpointIdentityError, match="source identity is unavailable"):
        CheckpointingChainExecutor(
            registry=registry,
            dispatcher=dispatcher,
            artifact_store=store,
            checkpoint_dir=tmp_path / "checkpoints",
        ).execute(chain, initial_state={"x": 3}, artifact_context=context)
    assert dispatcher.calls == []
    assert not (tmp_path / "checkpoints").exists()
