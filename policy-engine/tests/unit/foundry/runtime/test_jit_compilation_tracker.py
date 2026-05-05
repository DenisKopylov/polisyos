from __future__ import annotations

import jax.numpy as jnp
from polisyos.foundry.runtime import get_jit_tracker


def test_jit_tracker_marks_first_call():
    tracker = get_jit_tracker()
    tracker.reset()

    arr = jnp.zeros((2, 3))
    signature = tracker.signature_key("fn", arr)

    assert tracker.check_and_mark(signature) is True
    assert tracker.check_and_mark(signature) is False


def test_jit_tracker_distinguishes_shapes():
    tracker = get_jit_tracker()
    tracker.reset()

    sig_a = tracker.signature_key("fn", jnp.zeros((2, 3)))
    sig_b = tracker.signature_key("fn", jnp.zeros((2, 4)))

    assert sig_a != sig_b
