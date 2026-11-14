"""Exact selected tensor encoding, independent of JAX's default precision mode.

These physical operations do not admit a measurement or grant scientific
authority. The binding owner must independently resolve the selected source
and semantic correspondence before it supplies a value and encoding policy.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import MAX_EMAX, MIN_EMIN, ROUND_UP, Context, Decimal, InvalidOperation
from typing import Any

import numpy as np


def encode_selected_tensor(
    value: object,
    *,
    shape: tuple[int, ...],
    dtype: str,
    max_absolute_error: Decimal,
) -> np.ndarray:
    """Encode an already selected value without reshaping or narrowing its dtype.

    Scalar ``()`` and singleton ``(1,)`` are different physical contracts. Any
    deliberate projection must run before this function; this encoder performs
    no scalar packing, broadcast, missing-value substitution, or unit transform.
    """
    if (
        not isinstance(shape, tuple)
        or any(type(size) is not int or size < 0 for size in shape)
        or dtype not in {"float32", "float64"}
    ):
        raise ValueError("semantic_binding_target_encoding_mismatch")
    if (
        not isinstance(max_absolute_error, Decimal)
        or not max_absolute_error.is_finite()
        or max_absolute_error < 0
    ):
        raise ValueError("semantic_binding_precision_policy_invalid")
    try:
        source = np.asarray(value, dtype=object)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("semantic_binding_source_not_decimal") from exc
    if any(item is None for item in source.flat):
        raise ValueError("semantic_binding_source_null")
    if source.shape != shape:
        raise ValueError("semantic_binding_shape_mismatch")
    if any(
        not isinstance(item, int | float | Decimal | np.integer | np.floating)
        or isinstance(item, bool | np.bool_)
        for item in source.flat
    ):
        raise ValueError("semantic_binding_source_not_decimal")
    try:
        decimals = np.array(
            [item if isinstance(item, Decimal) else Decimal(str(item)) for item in source.flat],
            dtype=object,
        ).reshape(source.shape)
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError("semantic_binding_source_not_decimal") from exc
    if not all(item.is_finite() for item in decimals.flat):
        raise ValueError("semantic_binding_source_not_finite")
    with np.errstate(over="ignore", invalid="ignore"):
        encoded = np.array(decimals, dtype=np.dtype(dtype), copy=True, order="C")
    if encoded.shape != shape or encoded.dtype != np.dtype(dtype) or not np.isfinite(encoded).all():
        raise ValueError("semantic_binding_target_encoding_mismatch")
    # Outward rounding prevents ambient Decimal precision from hiding an error
    # just above the separately selected maximum absolute encoding error.
    error_context = Context(
        prec=len(max_absolute_error.as_tuple().digits),
        rounding=ROUND_UP,
        Emin=MIN_EMIN,
        Emax=MAX_EMAX,
    )
    if any(
        error_context.subtract(Decimal.from_float(float(stored)), exact).copy_abs()
        > max_absolute_error
        for stored, exact in zip(encoded.flat, decimals.flat, strict=True)
    ):
        raise ValueError("semantic_binding_precision_loss")
    return encoded


def selected_tensor_value_sha256(
    dtype: np.dtype[Any], shape: tuple[int, ...], raw: memoryview | bytes
) -> str:
    """Hash already bounded C-order numeric bytes using the dispatch identity.

    The graph retains its own metadata, aggregate-size, and device-read bounds.
    This shared final rule includes dtype byte order and the exact original
    dimensions, including a zero-dimensional scalar, rather than an NPY header.
    """
    resolved = np.dtype(dtype)
    if (
        resolved.hasobject
        or resolved.kind not in {"i", "u", "f", "b"}
        or not isinstance(shape, tuple)
        or any(type(size) is not int or size < 0 for size in shape)
        or memoryview(raw).nbytes != (math.prod(shape) if shape else 1) * resolved.itemsize
    ):
        raise ValueError("selected_tensor_value_identity_invalid")
    digest = hashlib.sha256()
    digest.update(resolved.str.encode("ascii"))
    digest.update(json.dumps(shape, separators=(",", ":")).encode("ascii"))
    digest.update(raw)
    return digest.hexdigest()
