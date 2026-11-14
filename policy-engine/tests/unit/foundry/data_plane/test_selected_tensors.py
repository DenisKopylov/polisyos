"""Physical selected tensors retain precision and exact scalar/vector identity."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, localcontext

import jax
import numpy as np
import pytest

from polisyos.foundry.data_plane.selected_tensors import (
    encode_selected_tensor,
    selected_tensor_value_sha256,
)


def test_float64_scalar_remains_numpy_with_jax_x64_disabled() -> None:
    assert not jax.config.x64_enabled, "This test uses the supported JAX-x64-disabled profile."
    encoded = encode_selected_tensor(
        Decimal("16777217"), shape=(), dtype="float64", max_absolute_error=Decimal(0)
    )
    assert type(encoded) is np.ndarray
    assert encoded.shape == ()
    assert encoded.dtype == np.dtype("float64")
    assert encoded.item() == 16777217
    independent = hashlib.sha256(
        encoded.dtype.str.encode("ascii")
        + json.dumps((), separators=(",", ":")).encode("ascii")
        + encoded.tobytes(order="C")
    ).hexdigest()
    assert (
        selected_tensor_value_sha256(encoded.dtype, encoded.shape, memoryview(encoded).cast("B"))
        == independent
    )


@pytest.mark.parametrize("limit", [Decimal(0), Decimal("0.9999999999999999999999999999")])
def test_float32_rounding_error_above_the_selected_limit_refuses(limit: Decimal) -> None:
    with pytest.raises(ValueError, match="^semantic_binding_precision_loss$"):
        encode_selected_tensor(
            Decimal("16777217"), shape=(), dtype="float32", max_absolute_error=limit
        )


def test_exact_precision_threshold_and_ambient_context_are_distinct() -> None:
    with localcontext() as context:
        context.prec = 1
        encoded = encode_selected_tensor(
            Decimal("16777217"), shape=(), dtype="float32", max_absolute_error=Decimal(1)
        )
    assert encoded.item() == 16777216


@pytest.mark.parametrize(
    ("value", "shape", "reason"),
    [
        (None, (), "semantic_binding_source_null"),
        ([None], (1,), "semantic_binding_source_null"),
        (True, (), "semantic_binding_source_not_decimal"),
        (np.bool_(False), (), "semantic_binding_source_not_decimal"),
        ("1", (), "semantic_binding_source_not_decimal"),
        (object(), (), "semantic_binding_source_not_decimal"),
        (Decimal("NaN"), (), "semantic_binding_source_not_finite"),
        (Decimal("Infinity"), (), "semantic_binding_source_not_finite"),
        (float("-inf"), (), "semantic_binding_source_not_finite"),
        (Decimal(1), (1,), "semantic_binding_shape_mismatch"),
        ([Decimal(1)], (), "semantic_binding_shape_mismatch"),
        ([Decimal(1)], (2,), "semantic_binding_shape_mismatch"),
    ],
)
def test_selected_encoder_refuses_missing_nonfinite_nonnumeric_and_implicit_shape(
    value: object, shape: tuple[int, ...], reason: str
) -> None:
    with pytest.raises(ValueError, match=f"^{reason}$"):
        encode_selected_tensor(value, shape=shape, dtype="float64", max_absolute_error=Decimal(0))


def test_an_explicit_singleton_value_is_not_a_scalar_or_a_broadcast() -> None:
    scalar = encode_selected_tensor(
        Decimal(7), shape=(), dtype="float64", max_absolute_error=Decimal(0)
    )
    singleton = encode_selected_tensor(
        [Decimal(7)], shape=(1,), dtype="float64", max_absolute_error=Decimal(0)
    )
    assert scalar.shape == () and singleton.shape == (1,)
    assert selected_tensor_value_sha256(
        scalar.dtype, scalar.shape, memoryview(scalar).cast("B")
    ) != selected_tensor_value_sha256(
        singleton.dtype, singleton.shape, memoryview(singleton).cast("B")
    )


@pytest.mark.parametrize("dtype", ["float16", "int64", "object", ">f8"])
def test_unsupported_target_dtype_cannot_replace_selected_float_encoding(dtype: str) -> None:
    with pytest.raises(ValueError, match="^semantic_binding_target_encoding_mismatch$"):
        encode_selected_tensor(Decimal(1), shape=(), dtype=dtype, max_absolute_error=Decimal(0))
