"""Bounded exact arithmetic checks for declared additive method patches."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from fractions import Fraction
from typing import Any

import jax
import numpy as np

from polisyos.foundry.methods.exceptions import ContractViolationError

METHOD_PATCH_PRECISION_REFUSAL = "method_patch_arithmetic_precision_not_representable"
_MAX_INTEGER_BITS = 4096


class MethodPatchArithmeticPrecisionError(ContractViolationError):
    """A declared additive method effect cannot be carried exactly."""

    def __init__(self, method_fqn: str, slot_id: str) -> None:
        self.slot_id = slot_id
        super().__init__(method_fqn, "postcondition", METHOD_PATCH_PRECISION_REFUSAL)


def _scalar(value: Any) -> np.ndarray:
    """Materialize only a bounded, real numeric scalar, without coercing types."""
    if type(value) is int:
        if value.bit_length() > _MAX_INTEGER_BITS:
            raise ValueError("method_patch_integer_bound_exceeded")
        # Preserve arbitrarily sized bounded Python integers outside NumPy.
        raise TypeError("method_patch_python_integer_requires_fraction")
    if type(value) is float:
        value = np.float64(value)
    if not isinstance(value, (np.ndarray, np.generic, jax.Array)):
        raise TypeError("method_patch_scalar_type_unsupported")
    shape = getattr(value, "shape", None)
    dtype = getattr(value, "dtype", None)
    if shape != () or dtype is None:
        raise ValueError("method_patch_scalar_shape_unsupported")
    resolved = np.dtype(dtype)
    if resolved.kind not in {"i", "u", "f"} or resolved.hasobject or resolved.itemsize > 8:
        raise ValueError("method_patch_scalar_dtype_unsupported")
    array = np.asarray(value)
    if array.shape != () or array.dtype != resolved or not bool(np.isfinite(array).item()):
        raise ValueError("method_patch_scalar_not_finite")
    return array


def _fraction(value: Any) -> Fraction:
    """Return the exact represented value of one supported scalar."""
    if type(value) is int:
        if value.bit_length() > _MAX_INTEGER_BITS:
            raise ValueError("method_patch_integer_bound_exceeded")
        return Fraction(value)
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("method_patch_scalar_not_finite")
        return Fraction.from_float(value)
    array = _scalar(value)
    item = array.item()
    return Fraction(int(item)) if array.dtype.kind in {"i", "u"} else Fraction.from_float(item)


def _sum_records(base: Fraction, records: Sequence[Mapping[str, Any]]) -> Fraction:
    """Reproduce SUM's declared delta semantics using exact input values."""
    result = base
    for record in records:
        delta = record.get("delta")
        if delta is not None:
            result += _fraction(delta)
        elif "new_value" in record and "base_value" in record:
            result += _fraction(record["new_value"]) - _fraction(record["base_value"])
        else:
            value = record.get("value", record.get("new_value"))
            if value is None:
                raise ValueError("method_patch_additive_delta_not_established")
            result += _fraction(value) - base
    return result


def _representable_as_base(value: Fraction, base: Any) -> bool:
    """Check the target scalar's actual dtype without assuming a tolerance."""
    if type(base) is int:
        # Python integers have no fixed storage dtype. The actual merged and
        # serialized values are checked after the execution owner chooses one.
        return True
    base_array = _scalar(base)
    try:
        with np.errstate(over="ignore", invalid="ignore"):
            if base_array.dtype.kind in {"i", "u"}:
                if value.denominator != 1:
                    return False
                candidate = np.asarray(value.numerator, dtype=base_array.dtype)
            else:
                candidate = np.asarray(float(value), dtype=base_array.dtype)
        return _fraction(candidate) == value
    except (ArithmeticError, OverflowError, TypeError, ValueError):
        return False


class MethodPatchPrecisionTracker:
    """Verify exact SUM effects only for actually activated method contracts.

    Candidate targets are gathered from method-node outputs, permitting earlier
    flushes on the same slot to be checked if a later method activates its
    contract. Legacy graphs without an activated contract are never refused by
    this tracker.
    """

    def __init__(self, candidate_slots: set[str]) -> None:
        self._candidates = frozenset(candidate_slots)
        self._active: dict[str, str] = {}
        self._unestablished: set[str] = set()

    def activate(self, operations: Mapping[str, str], *, method_fqn: str) -> None:
        """Enable the validated add contract and check earlier target writes."""
        for slot_id, operation in operations.items():
            if operation != "add":
                continue
            self._active[slot_id] = method_fqn
            if slot_id not in self._candidates or slot_id in self._unestablished:
                raise MethodPatchArithmeticPrecisionError(method_fqn, slot_id)

    def _refuse(self, slot_id: str) -> None:
        self._unestablished.add(slot_id)
        if slot_id in self._active:
            raise MethodPatchArithmeticPrecisionError(self._active[slot_id], slot_id)

    def before_flush(
        self,
        records: Mapping[str, Sequence[Mapping[str, Any]]],
        base_values: Mapping[str, Any],
    ) -> dict[str, Fraction | None]:
        """Compute each candidate's exact mathematical result before merging."""
        expected: dict[str, Fraction | None] = {}
        for slot_id in self._candidates.intersection(records):
            try:
                base = base_values[slot_id]
                exact = _sum_records(_fraction(base), records[slot_id])
                if slot_id in self._active and not _representable_as_base(exact, base):
                    self._refuse(slot_id)
                expected[slot_id] = exact
            except MethodPatchArithmeticPrecisionError:
                raise
            except (ArithmeticError, KeyError, TypeError, ValueError):
                self._refuse(slot_id)
                expected[slot_id] = None
        return expected

    def after_flush(
        self, expected: Mapping[str, Fraction | None], values: Mapping[str, Any]
    ) -> None:
        """Check the real merged state, including operations from other writers."""
        for slot_id, target in expected.items():
            try:
                if target is None or _fraction(values[slot_id]) != target:
                    self._refuse(slot_id)
            except MethodPatchArithmeticPrecisionError:
                raise
            except (ArithmeticError, KeyError, TypeError, ValueError):
                self._refuse(slot_id)

    def verify_serialized_delta(
        self, slot_id: str, *, base: Any, final: Any, delta: Any, replayed: Any
    ) -> None:
        """Check stored net delta and actual reapplication to the opening state."""
        if slot_id not in self._active:
            return
        try:
            base_value = _fraction(base)
            final_value = _fraction(final)
            final_array = _scalar(final)
            replayed_array = _scalar(replayed)
            if (
                _fraction(delta) != final_value - base_value
                or replayed_array.dtype != final_array.dtype
                or replayed_array.tobytes() != final_array.tobytes()
            ):
                self._refuse(slot_id)
        except MethodPatchArithmeticPrecisionError:
            raise
        except (ArithmeticError, TypeError, ValueError):
            self._refuse(slot_id)

    def is_active(self, slot_id: str) -> bool:
        """Return whether a real invocation activated this target's contract."""
        return slot_id in self._active

    def refuse_active(self, slot_id: str) -> None:
        """Refuse using the method that actually selected this target."""
        if slot_id not in self._active:
            raise ValueError("method_patch_precision_target_not_active")
        self._refuse(slot_id)
