"""Detach one provider call and bind reuse to its actual successful dispatch."""

from __future__ import annotations

import inspect
import json
import math
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from polisyos.common.serialization import decode_json_object

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def freeze_wire_object(value: dict[str, Any]) -> bytes:
    """Freeze already projected wire JSON without coercing unknown values.

    Typed DTO owners must apply their public JSON projection before this
    transport boundary. Raw datetime/model/unknown values and nonfinite numbers
    are rejected, rather than stringified or normalized to null.
    """

    def verify(item: object, depth: int) -> None:
        if depth > 128:
            raise ValueError("prepared_wire_depth_exceeded")
        if type(item) in (str, int, float, bool, type(None)):
            return
        if isinstance(item, (list, tuple)):
            for member in item:
                verify(member, depth + 1)
            return
        if type(item) is dict:
            for key, member in item.items():
                if type(key) is not str:
                    raise ValueError("prepared_wire_key_must_be_text")
                verify(member, depth + 1)
            return
        raise ValueError("prepared_wire_value_not_json")

    verify(value, 0)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def thaw_wire_object(value: bytes) -> dict[str, Any]:
    """Read a detached native object from an immutable prepared call."""
    return decode_json_object(
        value,
        source="polisyos.scientist.orchestration.llm.prepared_request",
        kind="prepared LLM request",
    )


@dataclass(frozen=True, slots=True)
class PreparedLLMResult:
    """One physical result and the actual successful request projection."""

    response: Any
    effective_identity: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class PreparedLLMRequest:
    """Immutable request identity with one owner-supplied physical executor."""

    identity: bytes = field(repr=False)
    execute: Callable[[], Awaitable[PreparedLLMResult]] = field(repr=False, compare=False)
    reusable: bool = True

    def admits(self, result: PreparedLLMResult) -> bool:
        """Admit only a result from the exact prepared successful request."""
        return self.reusable and result.effective_identity == self.identity


class _UnfreezableCallValue(Exception):
    """A value needs its Python owner rather than a native value snapshot."""


def _native_call_identity(args: tuple[Any, ...], kwargs: dict[str, Any]) -> bytes:
    # This is an exact Python value encoding, NOT cache/evidence normalization
    # and NOT a provider wire projection. Tags preserve type, bytes and order.
    seen: set[int] = set()

    def encode(value: Any, depth: int) -> Any:
        if depth > 128:
            raise _UnfreezableCallValue
        kind = type(value)
        if value is None:
            return ["none"]
        if kind is bool:
            return ["bool", value]
        if kind is int:
            try:
                return ["int", str(value)]
            except ValueError as exc:
                raise _UnfreezableCallValue from exc
        if kind is float:
            if not math.isfinite(value):
                raise _UnfreezableCallValue
            return ["float", value.hex()]
        if kind is str:
            return ["str", value]
        if kind is bytes:
            return ["bytes", value.hex()]
        if kind not in (tuple, list, dict, bytearray) or id(value) in seen:
            # Aliases/cycles, subclasses, views and custom objects retain their
            # original owner semantics on the physical-only path. Do not call
            # __iter__, __str__, __deepcopy__ or serialization hooks on them.
            raise _UnfreezableCallValue
        seen.add(id(value))
        if kind is bytearray:
            return ["bytearray", value.hex()]
        if kind is dict:
            return [
                "dict",
                [
                    [encode(key, depth + 1), encode(member, depth + 1)]
                    for key, member in value.items()
                ],
            ]
        return [kind.__name__, [encode(member, depth + 1) for member in value]]

    # Only owner-produced tag/value arrays enter this internal encoding. Its
    # native depth bound is independent of the Gateway's wire depth policy.
    return json.dumps(
        {
            "call_kind": "native_python_values_v1",
            "args": encode(args, 0),
            "kwargs": encode(kwargs, 0),
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _read_native_call(identity: bytes) -> tuple[tuple[Any, ...], dict[str, Any]]:
    def decode(value: Any) -> Any:
        tag = value[0]
        if tag == "none":
            return None
        if tag in {"str", "bool"}:
            return value[1]
        if tag == "int":
            return int(value[1])
        if tag == "float":
            return float.fromhex(value[1])
        if tag == "bytes":
            return bytes.fromhex(value[1])
        if tag == "bytearray":
            return bytearray.fromhex(value[1])
        if tag == "dict":
            return {decode(key): decode(member) for key, member in value[1]}
        if tag == "tuple":
            return tuple(decode(member) for member in value[1])
        if tag == "list":
            return [decode(member) for member in value[1]]
        raise ValueError("prepared_python_call_tag_invalid")

    snapshot = thaw_wire_object(identity)
    return decode(snapshot["args"]), decode(snapshot["kwargs"])


def _opaque_call_identity() -> bytes:
    return freeze_wire_object({"call_kind": "opaque_physical_only", "call_id": uuid.uuid4().hex})


@dataclass(frozen=True, slots=True)
class PreparedCallValues:
    """Native value snapshot or an explicitly nonreusable original Python call.

    Exact snapshots preserve native types, raw bytes and dictionary order.
    Unsupported graphs/objects stay with their Python owner and cannot bind
    an externally prepared cache plan. No equality claim follows from their
    unique physical-call token.
    """

    identity: bytes = field(repr=False)
    exact: bool
    _arguments: tuple[Any, ...] = field(repr=False, compare=False)
    _keywords: dict[str, Any] = field(repr=False, compare=False)

    def call_values(self) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Copy exact native values or forward opaque nested objects unchanged."""
        if self.exact:
            return _read_native_call(self.identity)
        return self._arguments, dict(self._keywords)


def prepare_call_values(args: tuple[Any, ...], kwargs: dict[str, Any]) -> PreparedCallValues:
    """Capture lossless supported values without interpreting cache evidence.

    Aliased/cyclic containers, views, subclasses, nonfinite values and opaque
    objects are not a native value contract. They remain supported physical
    Python inputs; their original identities are retained without reuse.
    """
    try:
        identity = _native_call_identity(args, kwargs)
    except _UnfreezableCallValue:
        return PreparedCallValues(_opaque_call_identity(), False, args, dict(kwargs))
    return PreparedCallValues(identity, True, (), {})


def prepare_immutable_call(
    generate: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    reusable: bool = False,
) -> PreparedLLMRequest:
    """Adapt the actual Python call entry, preserving its supported value types.

    Known non-negotiating providers may opt into reuse of exact native value
    snapshots. Opaque calls always remain physical-only and receive original
    Python objects, without JSON coercion or user-defined copying hooks.
    """
    call = prepare_call_values(args, kwargs)
    reusable = reusable and call.exact
    identity = call.identity if reusable else _opaque_call_identity()

    async def execute() -> PreparedLLMResult:
        actual_args, actual_kwargs = call.call_values() if reusable else (args, kwargs)
        response = generate(*actual_args, **actual_kwargs)
        if inspect.isawaitable(response):
            response = await response
        return PreparedLLMResult(response, identity)

    return PreparedLLMRequest(identity, execute, reusable)


def prepare_provider_call(
    client: object, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> tuple[PreparedLLMRequest, bytes]:
    """Delegate wire preparation to its real owner; preserve opaque Python calls.

    A prepared provider receives type-preserving copies of exact native inputs
    and owns its transport projection. Missing native identity disables reuse;
    an opaque provider without preparation receives its original call unchanged.
    """
    prepare = getattr(client, "prepare_cache_request", None)
    if callable(prepare):
        call = prepare_call_values(args, kwargs)
        actual_args, actual_kwargs = call.call_values()
        prepared = prepare(*actual_args, **actual_kwargs)
        if type(prepared) is not PreparedLLMRequest:
            raise TypeError("provider_prepared_request_untyped")
        if not call.exact:
            prepared = PreparedLLMRequest(prepared.identity, prepared.execute, False)
        return prepared, call.identity
    generate = getattr(client, "generate", None)
    if not callable(generate):
        raise TypeError("provider_generate_unavailable")
    prepared = prepare_immutable_call(generate, args, kwargs)
    return prepared, prepared.identity
