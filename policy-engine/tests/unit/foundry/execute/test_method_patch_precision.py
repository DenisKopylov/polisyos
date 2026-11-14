"""Discriminate exact declared SUM effects from silently rounded patches."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.execute._internal.precision import (
    METHOD_PATCH_PRECISION_REFUSAL,
    MethodPatchArithmeticPrecisionError,
    MethodPatchPrecisionTracker,
)


def _tracker(*, activate: bool = True) -> MethodPatchPrecisionTracker:
    tracker = MethodPatchPrecisionTracker({"model.stock"})
    if activate:
        tracker.activate({"model.stock": "add"}, method_fqn="example.flow@1")
    return tracker


def test_declared_add_refuses_a_lost_unit_at_a_large_float32_stock() -> None:
    tracker = _tracker()
    with pytest.raises(MethodPatchArithmeticPrecisionError, match=METHOD_PATCH_PRECISION_REFUSAL):
        tracker.before_flush(
            {"model.stock": [{"delta": np.float64(-1)}]},
            {"model.stock": np.float32(10_000_000_000)},
        )


def test_declared_add_accepts_exact_large_values_and_opposing_writers() -> None:
    tracker = _tracker()
    base = np.float32(10_000_000_000)
    expected = tracker.before_flush(
        {"model.stock": [{"delta": np.float64(-6_000_000_000)}]},
        {"model.stock": base},
    )
    tracker.after_flush(expected, {"model.stock": np.float32(4_000_000_000)})
    tracker.verify_serialized_delta(
        "model.stock",
        base=base,
        final=np.float32(4_000_000_000),
        delta=np.float32(-6_000_000_000),
        replayed=np.float32(4_000_000_000),
    )

    # Each individual dollar is smaller than one target ULP; their actual
    # aggregate is exactly zero, so no arbitrary per-record rejection applies.
    cancellation = _tracker()
    expected = cancellation.before_flush(
        {"model.stock": [{"delta": np.float64(1)}, {"delta": np.float64(-1)}]},
        {"model.stock": base},
    )
    cancellation.after_flush(expected, {"model.stock": base})
    cancellation.verify_serialized_delta(
        "model.stock", base=base, final=base, delta=np.float32(0), replayed=base
    )


def test_prior_uncontracted_rounding_is_not_laundered_by_a_later_contract() -> None:
    tracker = _tracker(activate=False)
    base = np.float32(10_000_000_000)
    expected = tracker.before_flush({"model.stock": [{"delta": -1.0}]}, {"model.stock": base})
    # Legacy-only work is still permitted, but cannot become exact evidence
    # merely because a later method writes the same target.
    tracker.after_flush(expected, {"model.stock": base})
    with pytest.raises(MethodPatchArithmeticPrecisionError, match=METHOD_PATCH_PRECISION_REFUSAL):
        tracker.activate({"model.stock": "add"}, method_fqn="example.flow@1")


def test_realized_merge_is_checked_even_when_target_is_representable() -> None:
    tracker = _tracker()
    expected = tracker.before_flush(
        {"model.stock": [{"delta": 2.0}, {"delta": -1.0}]},
        {"model.stock": np.float32(0)},
    )
    with pytest.raises(MethodPatchArithmeticPrecisionError, match=METHOD_PATCH_PRECISION_REFUSAL):
        tracker.after_flush(expected, {"model.stock": np.float32(0)})


def test_sum_accepts_canonical_new_value_and_delta_records_together() -> None:
    tracker = _tracker()
    expected = tracker.before_flush(
        {"model.stock": [{"new_value": np.float32(12)}, {"delta": np.float64(1)}]},
        {"model.stock": np.float32(10)},
    )
    tracker.after_flush(expected, {"model.stock": np.float32(13)})


def test_integer_opening_value_is_checked_after_the_owner_selects_a_dtype() -> None:
    tracker = _tracker()
    expected = tracker.before_flush({"model.stock": [{"delta": 1.5}]}, {"model.stock": 10})
    tracker.after_flush(expected, {"model.stock": np.float32(11.5)})
    tracker.verify_serialized_delta(
        "model.stock",
        base=10,
        final=np.float32(11.5),
        delta=np.float32(1.5),
        replayed=np.float32(11.5),
    )


def test_finite_float64_overflow_is_refused_before_a_float32_merge() -> None:
    tracker = _tracker()
    with pytest.raises(MethodPatchArithmeticPrecisionError, match=METHOD_PATCH_PRECISION_REFUSAL):
        tracker.before_flush(
            {"model.stock": [{"delta": np.float64(2**128)}]},
            {"model.stock": np.float32(0)},
        )


@pytest.mark.parametrize(
    ("delta", "replayed"),
    [
        (np.float32(-10_000_000_000), np.float32(0)),
        (np.float64(-9_999_999_999), np.float32(0)),
    ],
)
def test_net_delta_and_reapplication_are_checked_independently(delta, replayed) -> None:
    tracker = _tracker()
    with pytest.raises(MethodPatchArithmeticPrecisionError, match=METHOD_PATCH_PRECISION_REFUSAL):
        tracker.verify_serialized_delta(
            "model.stock",
            base=np.float32(10_000_000_000),
            final=np.float32(1),
            delta=delta,
            replayed=replayed,
        )


def test_replay_requires_the_actual_final_bits_including_signed_zero() -> None:
    tracker = _tracker()
    with pytest.raises(MethodPatchArithmeticPrecisionError, match=METHOD_PATCH_PRECISION_REFUSAL):
        tracker.verify_serialized_delta(
            "model.stock",
            base=np.float32(-0.0),
            final=np.float32(-0.0),
            delta=np.float32(0.0),
            replayed=np.float32(0.0),
        )


def test_unsupported_shape_is_not_coerced_into_a_scalar() -> None:
    tracker = _tracker()
    with pytest.raises(MethodPatchArithmeticPrecisionError, match=METHOD_PATCH_PRECISION_REFUSAL):
        tracker.before_flush(
            {"model.stock": [{"delta": np.array([1.0], dtype=np.float64)}]},
            {"model.stock": np.float32(0)},
        )


def test_refusal_retains_the_actual_method_identity() -> None:
    tracker = _tracker()
    with pytest.raises(MethodPatchArithmeticPrecisionError) as caught:
        tracker.refuse_active("model.stock")
    assert caught.value.method_fqn == "example.flow@1"
    assert caught.value.slot_id == "model.stock"
