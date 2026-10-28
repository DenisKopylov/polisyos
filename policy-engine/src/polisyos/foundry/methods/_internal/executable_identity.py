"""Process-local identity of a selected implementation for executable caches."""

from __future__ import annotations

from collections.abc import Hashable
from types import CodeType, FunctionType, MethodType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from polisyos.foundry.methods.base import MethodSignature


class _ExecutableIdentity:
    """Keep strong object references and compare the selected implementation by identity.

    Python functions also bind their current code object. Non-Python callables
    receive an unshared nonce, so an opaque mutable callable is not cache-reused.
    This is not a persistent source fingerprint or a claim about closure state.
    """

    __slots__ = ("_code", "_method_class", "_nonce", "_operation", "_signature_binding")

    def __init__(
        self, method_class: type[Any], operation: Any, signature_binding: Hashable
    ) -> None:
        self._method_class = method_class
        self._operation = operation
        self._signature_binding = signature_binding
        function = operation.__func__ if isinstance(operation, MethodType) else operation
        code = function.__code__ if isinstance(function, FunctionType) else None
        self._code = code if isinstance(code, CodeType) else None
        self._nonce = object() if self._code is None else None

    def __hash__(self) -> int:
        return hash(
            (
                id(self._method_class),
                id(self._operation),
                id(self._code),
                id(self._nonce),
                self._signature_binding,
            )
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _ExecutableIdentity):
            return NotImplemented
        return (
            self._method_class is other._method_class
            and self._operation is other._operation
            and self._code is other._code
            and self._nonce is other._nonce
            and self._signature_binding == other._signature_binding
        )


_SlotBounds = tuple[float | int | None, float | int | None]
_SignatureBinding = tuple[
    str, tuple[tuple[str, _SlotBounds], ...], tuple[tuple[str, _SlotBounds], ...]
]


def _signature_binding(signature: MethodSignature) -> _SignatureBinding:
    """Bind ABI and numeric slot bounds without coercing distinct integers to floats."""
    inputs = tuple(sorted((slot.name, slot.bounds) for slot in signature.input_slots))
    outputs = tuple(sorted((slot.name, slot.bounds) for slot in signature.output_slots))
    return signature.stable_digest(), inputs, outputs


def _signature_matches(method_class: type[Any], expected: MethodSignature) -> bool:
    """Compare ABI and composition-relevant slot bounds with the admitted signature."""
    from polisyos.foundry.methods.base import MethodSignature

    actual = getattr(method_class, "signature", None)
    return isinstance(actual, MethodSignature) and _signature_binding(actual) == _signature_binding(
        expected
    )
