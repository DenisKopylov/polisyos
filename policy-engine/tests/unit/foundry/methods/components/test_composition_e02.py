"""Real registry DAG consumers for occurrence requirements and slot admission."""

from __future__ import annotations

from dataclasses import replace
from typing import ClassVar

import pytest

from polisyos.foundry.methods.backends.chain_executor import execute_heterogeneous_chain
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
from polisyos.foundry.methods.components.composer import MethodComposer, SemanticValidationLevel
from polisyos.foundry.methods.components.linker import LinkerConfig, SlotLinker
from polisyos.foundry.methods.exceptions import (
    MissingRequirementError,
    ShapeMismatchError,
    SlotConnectionError,
    UnitMismatchError,
)
from polisyos.foundry.methods.selection.registry import MethodRegistry

_UNIT = Unit("review", "unit")


def _slot(name, *, unit=_UNIT, shape=(), kind=SlotType.SCALAR):
    return SlotSpec(name, kind, unit, shape=shape)


_SIGNATURE = MethodSignature(
    name="source",
    namespace="tests.composition_e02",
    version="1.0.0",
    input_slots=frozenset(),
    output_slots=frozenset({_slot("value")}),
    parameters=(),
    fidelity=FidelityLevel.LOW,
    complexity=ComplexityClass.O_1,
    backend=ComputeBackend.NUMPY,
    supports_jit=False,
    supports_vmap=False,
    supports_grad=False,
)
_METADATA = MethodMetadata(description="Actual composition arithmetic")


class _Left:
    signature: ClassVar = _SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"value": 10}


class _Right:
    signature: ClassVar = replace(_SIGNATURE, name="right")
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"value": 20}


class _Merge:
    signature: ClassVar = replace(
        _SIGNATURE,
        name="merge",
        input_slots=frozenset({_slot("left"), _slot("right")}),
        output_slots=frozenset({_slot("result")}),
    )
    metadata: ClassVar = _METADATA

    @staticmethod
    def materialize_input(bound_inputs, fallback_state):
        return {**fallback_state, **bound_inputs}

    @staticmethod
    def pure_step(state, params):
        return {"result": state["left"] + state["right"]}


def _registry(*methods):
    registry = MethodRegistry._create_fresh()
    for method in methods:
        registry.register(method)
    return registry


@pytest.mark.parametrize("explicit", [False, True])
def test_strict_complete_incoming_dag_materializes_actual_two_source_values(explicit):
    registry = _registry(_Left, _Right, _Merge)
    composer = MethodComposer(registry=registry, linker=SlotLinker(LinkerConfig.semantic_strict()))
    left, right, merge = (composer.add(method.signature.fqn) for method in (_Left, _Right, _Merge))
    if explicit:
        composer.connect(left, merge, {"value": "left"})
        composer.connect(right, merge, {"value": "right"})
    else:
        # Each source has one candidate for each target: constrain the target
        # names by an explicit first edge, then auto-fill the residual input.
        composer.connect(left, merge, {"value": "left"})
        composer.connect(right, merge)
    chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    result = execute_heterogeneous_chain(
        chain, state={"left": 100, "right": 200}, registry=registry
    )
    assert result.final_state["result"] == 30
    assert not any("unconnected" in warning.lower() for warning in chain.warnings)


@pytest.mark.parametrize("level", list(SemanticValidationLevel))
def test_strict_linker_refuses_incomplete_incoming_dag_at_build(level):
    registry = _registry(_Left, _Merge)
    composer = MethodComposer(registry=registry, linker=SlotLinker(LinkerConfig.strict()))
    left = composer.add(_Left.signature.fqn)
    merge = composer.add(_Merge.signature.fqn)
    composer.connect(left, merge, {"value": "left"})
    with pytest.raises(SlotConnectionError, match="Unconnected required inputs"):
        composer.build(validate_semantics=level)
    # The standalone two-method interface still requires the whole input set.
    with pytest.raises(SlotConnectionError, match="Unconnected required inputs"):
        SlotLinker(LinkerConfig.strict()).link(_Left.signature, _Merge.signature, {"value": "left"})


class _Estimate:
    signature: ClassVar = replace(
        _SIGNATURE,
        name="estimate",
        input_slots=frozenset({_slot("value")}),
        family="estimation",
        variant="estimate",
    )
    metadata: ClassVar = _METADATA

    @staticmethod
    def materialize_input(bound_inputs, fallback_state):
        return {**fallback_state, **bound_inputs}

    @staticmethod
    def pure_step(state, params):
        return {"value": state["value"] + 1}


class _Sensitivity:
    signature: ClassVar = replace(
        _Estimate.signature,
        name="sensitivity",
        family="sensitivity",
        variant="sensitivity",
        requires=frozenset({_Estimate.signature.fqn}),
    )
    metadata: ClassVar = _METADATA

    @staticmethod
    def materialize_input(bound_inputs, fallback_state):
        return {**fallback_state, **bound_inputs}

    @staticmethod
    def pure_step(state, params):
        return {"value": state["value"] * 10}


def test_required_explicit_earlier_occurrence_excludes_future_same_fqn():
    registry = _registry(_Estimate, _Sensitivity)
    composer = MethodComposer(registry=registry)
    first = composer.add(_Estimate.signature.fqn)
    sensitivity = composer.add(_Sensitivity.signature.fqn)
    future = composer.add(_Estimate.signature.fqn)
    composer.connect(first, sensitivity, {"value": "value"})
    composer.connect(sensitivity, future, {"value": "value"})
    chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    assert chain.execution_order == (first.id, sensitivity.id, future.id)
    assert chain.dag.predecessors[sensitivity.id] == frozenset({first.id})
    assert execute_heterogeneous_chain(
        chain, state={"value": 2}, registry=registry
    ).final_state == {"value": 31}


def test_required_only_occurrence_selects_nearest_earlier_instance():
    registry = _registry(_Estimate, _Sensitivity)
    composer = MethodComposer(registry=registry)
    first = composer.add(_Estimate.signature.fqn)
    second = composer.add(_Estimate.signature.fqn)
    dependent = composer.add(_Sensitivity.signature.fqn)
    chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    assert chain.dag.predecessors[dependent.id] == frozenset({second.id})
    assert first.id in chain.execution_order
    assert execute_heterogeneous_chain(
        chain, state={"value": 2}, registry=registry
    ).final_state == {"value": 40}


@pytest.mark.parametrize("level", list(SemanticValidationLevel))
def test_required_only_ambiguous_future_instances_are_typed_refused(level):
    registry = _registry(_Estimate, _Sensitivity)
    composer = MethodComposer(registry=registry)
    composer.add(_Sensitivity.signature.fqn)
    composer.add(_Estimate.signature.fqn)
    composer.add(_Estimate.signature.fqn)
    with pytest.raises(MissingRequirementError, match="ambiguous"):
        composer.build(validate_semantics=level)


def test_strict_root_input_remains_actual_caller_context():
    registry = _registry(_Estimate)
    composer = MethodComposer(registry=registry, linker=SlotLinker(LinkerConfig.strict()))
    composer.add(_Estimate.signature.fqn)
    chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    assert not chain.bindings
    assert execute_heterogeneous_chain(
        chain, state={"value": 21}, registry=registry
    ).final_state == {"value": 22}


def test_two_explicit_required_occurrences_are_refused_with_exact_typed_context():
    registry = _registry(_Estimate, _Sensitivity)
    composer = MethodComposer(registry=registry)
    first = composer.add(_Estimate.signature.fqn)
    second = composer.add(_Estimate.signature.fqn)
    target = composer.add(_Sensitivity.signature.fqn)
    composer.connect(first, target, {"value": "value"})
    composer.connect(second, target, {"value": "value"})
    with pytest.raises(MissingRequirementError, match="ambiguous explicit") as error:
        composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    assert error.value.method_fqn == _Sensitivity.signature.fqn
    assert error.value.required_fqn == _Estimate.signature.fqn
    assert str(first.id) in error.value.reason
    assert str(second.id) in error.value.reason


@pytest.mark.parametrize("gate", ["unit", "shape"])
def test_manual_auto_single_edge_structural_refusal_has_identical_typed_reason(gate):
    if gate == "unit":
        source = _slot("source", unit=Unit("currency", "USD"))
        target = _slot("target", unit=Unit("time", "yr"))
        expected = UnitMismatchError
    else:
        source = _slot("source", shape=(2,), kind=SlotType.VECTOR)
        target = _slot("target", shape=(3,), kind=SlotType.VECTOR)
        expected = ShapeMismatchError
    source_sig = replace(_SIGNATURE, output_slots=frozenset({source}))
    target_sig = replace(_SIGNATURE, name="target", input_slots=frozenset({target}))
    errors = []
    for mapping in ({"source": "target"}, None):
        with pytest.raises(expected) as result:
            SlotLinker(LinkerConfig.strict()).link(source_sig, target_sig, mapping)
        errors.append(result.value)
    assert type(errors[0]) is type(errors[1])
    assert str(errors[0]) == str(errors[1])
