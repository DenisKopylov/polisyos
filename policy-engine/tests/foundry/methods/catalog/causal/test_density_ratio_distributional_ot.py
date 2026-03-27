from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal.density_ratio import (
    DEFAULT_DISTRIBUTIONAL_QUANTILES,
    DEFAULT_DISTRIBUTIONAL_TAIL_PROBS,
    compute_scalar_distributional_effect,
    compute_sinkhorn_coupling,
)


def test_distributional_ot_wasserstein_orders_larger_shift_higher() -> None:
    baseline = np.linspace(0.0, 10.0, 50)
    small_shift = baseline + 0.5
    large_shift = baseline + 2.0

    small = compute_scalar_distributional_effect(baseline, small_shift, n_bins=16)
    large = compute_scalar_distributional_effect(baseline, large_shift, n_bins=16)

    assert small.wasserstein_distance > 0.0
    assert large.wasserstein_distance > small.wasserstein_distance


def test_sinkhorn_coupling_preserves_mass_and_marginals() -> None:
    result = compute_scalar_distributional_effect(
        np.linspace(1.0, 5.0, 20),
        np.linspace(2.0, 6.0, 20),
        n_bins=10,
    )

    coupling = result.coupling_matrix
    assert coupling.shape == (10, 10)
    assert np.isclose(np.sum(coupling), 1.0)
    assert result.mass_conservation_error <= 1e-4
    assert np.isclose(
        np.sum(coupling, axis=1),
        result.baseline_measure.probabilities,
        atol=1e-4,
    ).all()
    assert np.isclose(
        np.sum(coupling, axis=0),
        result.counterfactual_measure.probabilities,
        atol=1e-4,
    ).all()


def test_raw_sample_ot_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="raw sample-to-sample OT is prohibited"):
        compute_sinkhorn_coupling([0.0, 1.0], None, [0.0, 1.0], None)


def test_quantile_and_tail_outputs_are_emitted_on_fixed_grid() -> None:
    baseline = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)
    counterfactual = baseline + 2.0

    result = compute_scalar_distributional_effect(baseline, counterfactual, n_bins=5)

    assert tuple(np.round(result.quantile_shift.quantiles, 2)) == DEFAULT_DISTRIBUTIONAL_QUANTILES
    assert tuple(np.round(result.tail_risk.tail_probs, 2)) == DEFAULT_DISTRIBUTIONAL_TAIL_PROBS
    assert np.all(result.quantile_shift.shifts >= 0.0)
    assert np.all(np.diff(result.tail_risk.thresholds) >= 0.0)
    assert np.all(result.tail_risk.exceedance_deltas >= 0.0)
