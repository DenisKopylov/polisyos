"""Held NumPy preparations exercise the same real dispatcher execution seam."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.numpy_runner import NumpyRunner
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
)
from polisyos.foundry.methods.types.units import Units


def _signature() -> MethodSignature:
    return MethodSignature(
        name="held_numpy",
        namespace="tests.preparation",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(ParameterSpec(name="offset", default=3),),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )


def test_preparation_holds_callable_default_postprocessor_and_rng(monkeypatch):
    calls = []

    class Method:
        signature: ClassVar[MethodSignature] = _signature()
        metadata: ClassVar[MethodMetadata] = MethodMetadata(description="held preparation")

        @staticmethod
        def pure_step(state, params):
            calls.append((state, params["offset"], params["__seed__"]))
            return float(params["__rng__"].normal()) + params["offset"]

        @staticmethod
        def postprocess_output(*, output, state, params):
            return output * 2

    dispatcher = MethodDispatcher(enable_runtime_selection=False)
    state = {"input": np.asarray(4.0)}
    signature = Method.signature
    prepared = dispatcher.prepare_call(
        method_class=Method, signature=signature, state=state, params={}, seed=17
    )
    assert calls == []
    numerical = prepared.numerical_call
    assert numerical.declared_params == {"offset": 3}
    assert numerical.rng_state == np.random.default_rng(17).bit_generator.state
    held_callable = Method.pure_step
    assert numerical.pure_step is held_callable
    monkeypatch.setattr(Method, "pure_step", staticmethod(lambda *_: -1000.0))
    monkeypatch.setattr(Method, "postprocess_output", staticmethod(lambda **_: -2000.0))
    monkeypatch.setattr(
        Method, "signature", replace(signature, parameters=(ParameterSpec("offset", 99),))
    )
    result = dispatcher.dispatch(
        method_class=Method,
        signature=signature,
        state=state,
        params={},
        seed=17,
        _prepared_call=prepared,
    )
    assert result.output == (float(np.random.default_rng(17).normal()) + 3) * 2
    assert calls == [(state, 3, 17)]


def test_preparation_refuses_alternate_runner_without_running_method():
    class Method:
        signature = _signature()

        @staticmethod
        def pure_step(*_):
            raise AssertionError("preparation executed numerical kernel")

    class AlternateRunner(NumpyRunner):
        pass

    dispatcher = MethodDispatcher(enable_runtime_selection=False)
    dispatcher.register_runner(AlternateRunner())
    with pytest.raises(ValueError, match="prepared_method_dispatch_runner_not_established"):
        dispatcher.prepare_call(
            method_class=Method, signature=Method.signature, state={}, params={}, seed=1
        )


def test_preparation_refuses_unclassified_signature_fields():
    @dataclass(frozen=True, slots=True)
    class ExtendedSignature(MethodSignature):
        future_model_axes: str = "unclassified"

    class Method:
        @staticmethod
        def pure_step(*_):
            raise AssertionError("preparation executed numerical kernel")

    signature = ExtendedSignature(
        **{field: getattr(_signature(), field) for field in _signature().__dataclass_fields__}
    )
    with pytest.raises(ValueError, match="prepared_method_signature_field_roles_not_established"):
        MethodDispatcher(enable_runtime_selection=False).prepare_call(
            method_class=Method, signature=signature, state={}, params={}, seed=1
        )


def test_preparation_cannot_be_used_for_a_different_actual_input():
    class Method:
        signature = _signature()

        @staticmethod
        def pure_step(*_):
            raise AssertionError("mismatched preparation executed numerical kernel")

    dispatcher = MethodDispatcher(enable_runtime_selection=False)
    prepared = dispatcher.prepare_call(
        method_class=Method, signature=Method.signature, state={}, params={}, seed=1
    )
    with pytest.raises(ValueError, match="prepared_method_dispatch_identity_mismatch"):
        dispatcher.dispatch(
            method_class=Method,
            signature=Method.signature,
            state={},
            params={},
            seed=1,
            _prepared_call=prepared,
        )


def test_observer_nested_parameter_projection_is_detached_from_actual_call():
    class Method:
        signature = replace(_signature(), parameters=(ParameterSpec("offset", {"values": [3]}),))

        @staticmethod
        def pure_step(_state, params):
            return params["offset"]["values"][0]

    dispatcher = MethodDispatcher(enable_runtime_selection=False)
    state = {}
    prepared = dispatcher.prepare_call(
        method_class=Method, signature=Method.signature, state=state, params={}, seed=1
    )
    prepared.numerical_call.declared_params["offset"]["values"][0] = 99
    result = dispatcher.dispatch(
        method_class=Method,
        signature=Method.signature,
        state=state,
        params={},
        seed=1,
        _prepared_call=prepared,
    )
    assert result.output == 3


def test_preparation_holds_actual_output_projection(monkeypatch):
    class Method:
        signature = replace(
            _signature(),
            output_slots=frozenset({SlotSpec("result", SlotType.SCALAR, Units.USD)}),
        )

        @staticmethod
        def pure_step(_state, params):
            return params["offset"]

        @staticmethod
        def dematerialize_output(output):
            return {"result": output * 2}

    dispatcher = MethodDispatcher(enable_runtime_selection=False)
    state = {}
    prepared = dispatcher.prepare_call(
        method_class=Method, signature=Method.signature, state=state, params={}, seed=1
    )
    monkeypatch.setattr(
        Method, "dematerialize_output", staticmethod(lambda output: {"result": -99})
    )
    monkeypatch.setattr(Method, "strict_output_contract", True, raising=False)
    result = dispatcher.dispatch(
        method_class=Method,
        signature=Method.signature,
        state=state,
        params={},
        seed=1,
        _prepared_call=prepared,
    )
    assert result.output == 3
    assert result.slot_outputs == {"result": 6}
