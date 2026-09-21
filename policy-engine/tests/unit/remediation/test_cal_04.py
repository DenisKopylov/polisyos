"""Distinguishing witnesses for CAL-04 final evaluation and Hessian reuse."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.calibration.calibrator import (
    _HessianReuseKey,
    _hessian_reuse_key_matches,
    _select_lower_loss_state,
)

pytestmark = pytest.mark.unit


def test_last_produced_iterate_can_replace_previous_state_only_when_evaluated() -> None:
    """An evaluated 0.5 candidate wins, while an evaluated overshoot at 4 loses."""
    previous = _select_lower_loss_state(
        previous_loss=1.0,
        previous_state=0.0,
        candidate_loss=0.25,
        candidate_state=0.5,
    )
    overshoot = _select_lower_loss_state(
        previous_loss=1.0,
        previous_state=0.0,
        candidate_loss=9.0,
        candidate_state=4.0,
    )

    assert previous == (0.25, 0.5)
    assert overshoot == (1.0, 0.0)


def test_hessian_reuse_requires_point_coordinates_weights_seed_and_numeric_policy() -> None:
    """A cached Hessian is reusable only for the exact objective identity."""
    base = _HessianReuseKey(
        flat_theta=(0.25,),
        param_names=("rate",),
        weights=(1.0,),
        seed=7,
        seed_strategy="fixed",
        steps=2,
        dtype="float32",
        damping=1e-6,
        rank_tol=1e-6,
        max_params=None,
        fidelity_mode="relaxed",
        fidelity_temperature=1.0,
        fidelity_force_override=True,
    )

    assert _hessian_reuse_key_matches(base, base)
    assert not _hessian_reuse_key_matches(
        base,
        base.__class__(**{**base.__dict__, "flat_theta": (0.5,)}),
    )
    assert not _hessian_reuse_key_matches(
        base,
        base.__class__(**{**base.__dict__, "weights": (2.0,)}),
    )
    assert not _hessian_reuse_key_matches(
        base,
        base.__class__(**{**base.__dict__, "seed": 8}),
    )
    assert not _hessian_reuse_key_matches(
        base,
        base.__class__(**{**base.__dict__, "rank_tol": 1e-5}),
    )


def test_hessian_key_rejects_nonfinite_point_even_when_shape_matches() -> None:
    """A malformed point cannot inherit a diagnostic result by tuple shape."""
    finite = _HessianReuseKey(
        flat_theta=(0.25,),
        param_names=("rate",),
        weights=(1.0,),
        seed=7,
        seed_strategy="fixed",
        steps=2,
        dtype="float32",
        damping=1e-6,
        rank_tol=1e-6,
        max_params=None,
        fidelity_mode="relaxed",
        fidelity_temperature=1.0,
        fidelity_force_override=True,
    )
    malformed = finite.__class__(**{**finite.__dict__, "flat_theta": (np.nan,)})

    assert not _hessian_reuse_key_matches(finite, malformed)
