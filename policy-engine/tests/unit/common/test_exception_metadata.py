"""Real exception metadata storage remains available behind subclass hooks."""

from __future__ import annotations

from typing import Any

import pytest

from polisyos.common import exception_metadata as common_exception_metadata
from polisyos.common.exception_metadata import (
    _EXCEPTION_CAUSE_MAX_DEPTH,
    _bounded_exception_cause_nodes,
    _exception_instance_dict,
)


def test_exception_metadata_lazy_facade_preserves_canonical_module_identity() -> None:
    """The package facade resolves to the canonical exception metadata module."""
    import importlib

    import polisyos.common as common_package

    canonical_module = importlib.import_module("polisyos.common.exception_metadata")

    assert "exception_metadata" in common_package.__all__
    assert common_exception_metadata is canonical_module
    assert common_exception_metadata._exception_instance_dict is _exception_instance_dict


def test_exception_instance_dict_uses_base_descriptor_without_subclass_hooks() -> None:
    """The shared primitive reads the actual backing dict without attribute dispatch."""

    class HostileError(RuntimeError):
        @property
        def __dict__(self) -> dict[str, Any]:
            raise RuntimeError("subclass dictionary descriptor refuses access")

        def __getattribute__(self, name: str) -> Any:
            if name in {"__dict__", "_diagnostic_marker"}:
                raise RuntimeError("subclass get refuses access")
            return super().__getattribute__(name)

        def __setattr__(self, name: str, value: Any) -> None:
            if name in {"__dict__", "_diagnostic_marker"}:
                raise RuntimeError("subclass set refuses access")
            super().__setattr__(name, value)

        def __delattr__(self, name: str) -> None:
            if name in {"__dict__", "_diagnostic_marker"}:
                raise RuntimeError("subclass delete refuses access")
            super().__delattr__(name)

    error = HostileError("original text")
    cause = LookupError("original cause")
    error.__cause__ = cause
    original = (type(error), error.args, str(error), error.__cause__, error.__traceback__)
    with pytest.raises(RuntimeError, match="subclass get refuses access"):
        _ = error.__dict__
    with pytest.raises(RuntimeError, match="subclass set refuses access"):
        error._diagnostic_marker = "unissued diagnostic"
    with pytest.raises(RuntimeError, match="subclass delete refuses access"):
        del error._diagnostic_marker

    metadata = _exception_instance_dict(error)
    assert type(metadata) is dict
    assert metadata is BaseException.__dict__["__dict__"].__get__(error)
    marker = object()
    metadata["_diagnostic_marker"] = marker
    assert _exception_instance_dict(error) is metadata
    assert metadata["_diagnostic_marker"] is marker
    assert metadata.pop("_diagnostic_marker") is marker
    assert "_diagnostic_marker" not in metadata
    assert (type(error), error.args, str(error), error.__cause__, error.__traceback__) == original
    assert error.__cause__ is cause


def test_bounded_exception_cause_nodes_preserves_typed_storage_without_messages() -> None:
    """The shared node walk keeps actual objects but serializes no error text."""
    original = RuntimeError("outer-message-secret")
    cause = LookupError("inner-message-secret")
    metadata = _exception_instance_dict(cause)
    assert metadata is not None
    metadata["code"] = "content_addressed_storage_timeout"
    original.__cause__ = cause
    original_state = (original.args, str(original), original.__cause__, original.__traceback__)

    nodes, termination = _bounded_exception_cause_nodes(original)

    assert termination == "no_linked_cause"
    assert len(nodes) == 2
    assert nodes[0].error is original
    assert nodes[0].code == "not_established"
    assert nodes[0].exception_type.endswith(".RuntimeError")
    assert nodes[1].error is cause
    assert nodes[1].code == "content_addressed_storage_timeout"
    assert nodes[1].exception_type.endswith(".LookupError")
    assert "message-secret" not in repr(nodes)
    assert (
        original.args,
        str(original),
        original.__cause__,
        original.__traceback__,
    ) == original_state

    metadata["code"] = "payload=secret"
    invalid_code_nodes, invalid_code_termination = _bounded_exception_cause_nodes(cause)
    assert invalid_code_termination == "no_linked_cause"
    assert invalid_code_nodes[0].code == "not_established"
    assert "payload=secret" not in repr(invalid_code_nodes)


def test_bounded_exception_cause_nodes_uses_builtin_descriptors_without_hooks() -> None:
    """Subclass properties and metaclass hooks cannot redirect cause/type reads."""
    reflection_calls: list[str] = []

    class HookedMeta(type):
        @property
        def __module__(cls) -> str:
            reflection_calls.append("type.__module__")
            return "payload=secret"

    class HookedError(RuntimeError, metaclass=HookedMeta):
        @property
        def __cause__(self) -> BaseException | None:
            reflection_calls.append("exception.__cause__")
            return None

        @property
        def __context__(self) -> BaseException | None:
            reflection_calls.append("exception.__context__")
            return None

        @property
        def __suppress_context__(self) -> bool:
            reflection_calls.append("exception.__suppress_context__")
            return False

    error = HookedError("outer-message-secret")
    context = LookupError("context-message-secret")
    reflection_calls.clear()
    BaseException.__dict__["__cause__"].__set__(error, None)
    BaseException.__dict__["__context__"].__set__(error, context)
    BaseException.__dict__["__suppress_context__"].__set__(error, False)

    nodes, termination = _bounded_exception_cause_nodes(error)

    assert termination == "no_linked_cause"
    assert len(nodes) == 2
    assert nodes[0].error is error
    assert nodes[0].exception_type.endswith(".HookedError")
    assert nodes[1].error is context
    assert reflection_calls == []
    assert "message-secret" not in repr(nodes)
    assert "payload=secret" not in repr(nodes)


def test_bounded_exception_cause_nodes_reports_suppression_cycles_and_depth() -> None:
    """The finite walk distinguishes suppressed links, cycles, and a depth cap."""
    cause_descriptor = BaseException.__dict__["__cause__"]
    context_descriptor = BaseException.__dict__["__context__"]
    suppress_descriptor = BaseException.__dict__["__suppress_context__"]

    suppressed = RuntimeError("suppressed-message-secret")
    context = LookupError("suppressed-context-secret")
    cause_descriptor.__set__(suppressed, None)
    context_descriptor.__set__(suppressed, context)
    suppress_descriptor.__set__(suppressed, True)
    suppressed_nodes, suppressed_termination = _bounded_exception_cause_nodes(suppressed)
    assert len(suppressed_nodes) == 1
    assert suppressed_termination == "context_suppressed"
    assert "secret" not in repr(suppressed_nodes)

    cyclic = RuntimeError("cycle-message-secret")
    cause_descriptor.__set__(cyclic, cyclic)
    cyclic_nodes, cyclic_termination = _bounded_exception_cause_nodes(cyclic)
    assert len(cyclic_nodes) == 1
    assert cyclic_termination == "cycle_detected"

    chain = [
        RuntimeError(f"depth-message-{index}") for index in range(_EXCEPTION_CAUSE_MAX_DEPTH + 2)
    ]
    for index in range(len(chain) - 1):
        cause_descriptor.__set__(chain[index], chain[index + 1])
    depth_nodes, depth_termination = _bounded_exception_cause_nodes(chain[0])
    assert len(depth_nodes) == _EXCEPTION_CAUSE_MAX_DEPTH
    assert depth_termination == "depth_limited"
    assert "depth-message" not in repr(depth_nodes)
